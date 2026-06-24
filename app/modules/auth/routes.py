import logging
from flask import request, jsonify, redirect, url_for, render_template, make_response, session
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies, jwt_required, get_jwt_identity
)

from app.common.exceptions import (
    UnauthorizedError, ValidationError, ConflictError, TooManyRequestsError
)
from app.constants.common import RoleName
from app.extensions.db import db
from app.modules.auth import auth_bp
from app.modules.auth.service import AuthService
from app.modules.auth.dto import (
    LoginDTO, RequestPasswordResetDTO, ResetPasswordDTO
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _swal_error(title: str, text: str, status: int = 400):
    """JSON dùng cho SweetAlert2 – phía client hiển thị Swal.fire(...)."""
    return jsonify({
        "swal": {
            "icon": "error",
            "title": title,
            "text": text,
        }
    }), status


def _swal_success(title: str, text: str, redirect_url: str | None = None, status: int = 200):
    payload: dict = {
        "swal": {
            "icon": "success",
            "title": title,
            "text": text,
        }
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url
    return jsonify(payload), status


def _swal_warning(title: str, text: str, status: int = 429):
    return jsonify({
        "swal": {
            "icon": "warning",
            "title": title,
            "text": text,
        }
    }), status


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET"])
def login_page():
    """Hiển thị giao diện đăng nhập."""
    return render_template("modules/auth/login.html")


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    """Xác thực thông tin, cấp JWT và chuyển hướng về dashboard phù hợp."""
    # 1. Lấy dữ liệu an toàn
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")
    
    dto = LoginDTO(identifier=identifier, password=password)
    
    try:
        # 2. Thực hiện đăng nhập
        user = AuthService.login(dto)
        session["user_id"] = user.id
        # 3. MỌI XỬ LÝ LIÊN QUAN ĐẾN 'user' PHẢI NẰM TRONG KHỐI TRY NÀY
        user_id_str = str(user.id)
        access_token = create_access_token(identity=user_id_str)
        refresh_token = create_refresh_token(identity=user_id_str)
        
        redirect_url = url_for("auth.dashboard_redirect")
        
        result = _swal_success(
            "Đăng nhập thành công",
            f"Chào mừng trở lại, {user.username}!",
            redirect_url=redirect_url,
        )
        
        # Chuyển đổi tuple (Response, status) thành response object
        resp_obj = make_response(result[0])
        resp_obj.status_code = result[1]
            
        set_access_cookies(resp_obj, access_token)
        set_refresh_cookies(resp_obj, refresh_token)
        return resp_obj

    except ValidationError as exc:
        return _swal_error("Thông tin không hợp lệ", str(exc), 422)
    except UnauthorizedError as exc:
        return _swal_error("Đăng nhập thất bại", str(exc), 401)
    except Exception as exc:
        # Ghi log lỗi thực tế để debug
        logger.exception("Unexpected login error")
        return _swal_error("Lỗi hệ thống", "Vui lòng thử lại sau.", 500)
# ---------------------------------------------------------------------------
# GET /auth/dashboard
# ---------------------------------------------------------------------------

@auth_bp.route("/dashboard", methods=["GET"])
@jwt_required(locations=["headers", "cookies"])
def dashboard_redirect():
    return redirect(url_for("home.home"))


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    response = make_response(redirect(url_for("auth.login_page")))
    unset_jwt_cookies(response)
    return response


# ---------------------------------------------------------------------------
# GET /auth/forgot-password
# ---------------------------------------------------------------------------

@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    """Hiển thị form nhập Email / SĐT để yêu cầu khôi phục mật khẩu."""
    return render_template("modules/auth/forgot_password.html")


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------

@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Tiếp nhận yêu cầu, gọi AuthService.request_password_reset và gửi OTP."""
    data = request.get_json(silent=True) or request.form

    dto = RequestPasswordResetDTO(identifier=data.get("identifier", ""))

    try:
        result = AuthService.request_password_reset(dto)
    except ValidationError as exc:
        return _swal_error("Không thể gửi OTP", str(exc), 422)
    except TooManyRequestsError as exc:
        return _swal_warning("Quá nhiều yêu cầu", str(exc))
    except Exception as exc:
        logger.exception("Unexpected forgot_password error: %s", exc)
        return _swal_error("Lỗi hệ thống", "Vui lòng thử lại sau.", 500)

    return jsonify({
        "swal": {
            "icon": "success",
            "title": "Đã gửi mã OTP",
            "text": (
                f"Mã OTP đã được gửi qua {result.delivery_channel}. "
                f"Mã có hiệu lực đến {result.otp_expires_at_iso}."
            ),
        },
        "redirect_url": url_for("auth.verify_otp_page"),
        "otp_expires_at": result.otp_expires_at_iso,
        "delivery_channel": result.delivery_channel,
    }), 200


# ---------------------------------------------------------------------------
# GET /auth/verify-otp
# ---------------------------------------------------------------------------

@auth_bp.route("/verify-otp", methods=["GET"])
def verify_otp_page():
    """Hiển thị form nhập mã OTP và mật khẩu mới."""
    return render_template("modules/auth/verify_otp.html")


# ---------------------------------------------------------------------------
# POST /auth/verify-otp  (Cách 1 – verify OTP + đặt mật khẩu mới trong 1 bước)
# ---------------------------------------------------------------------------

@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """Xác thực OTP và cập nhật mật khẩu mới."""
    data = request.get_json(silent=True) or request.form

    dto = ResetPasswordDTO(
        identifier=data.get("identifier", ""),
        otp_code=data.get("otp_code", ""),
        new_password=data.get("new_password", ""),
        otp_type=data.get("otp_type", "email"),
    )

    try:
        AuthService.reset_password(dto)
    except ValidationError as exc:
        return _swal_error("Thông tin không hợp lệ", str(exc), 422)
    except UnauthorizedError as exc:
        return _swal_error("OTP không hợp lệ", str(exc), 401)
    except ConflictError as exc:
        return _swal_error("Không thể đặt mật khẩu", str(exc), 409)
    except Exception as exc:
        logger.exception("Unexpected verify_otp error: %s", exc)
        return _swal_error("Lỗi hệ thống", "Vui lòng thử lại sau.", 500)

    return _swal_success(
        "Đặt lại mật khẩu thành công",
        "Mật khẩu của bạn đã được cập nhật. Vui lòng đăng nhập lại.",
        redirect_url=url_for("auth.login_page"),
    )


# ---------------------------------------------------------------------------
# POST /auth/reset-password  (Cách 2 – có xác nhận mật khẩu confirm)
# ---------------------------------------------------------------------------

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Kiểm tra khớp mật khẩu (confirm) rồi gọi AuthService.reset_password."""
    data = request.get_json(silent=True) or request.form

    new_password     = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if new_password != confirm_password:
        return _swal_error(
            "Mật khẩu không khớp",
            "Mật khẩu xác nhận không trùng với mật khẩu mới.",
            422,
        )

    dto = ResetPasswordDTO(
        identifier=data.get("identifier", ""),
        otp_code=data.get("otp_code", ""),
        new_password=new_password,
        otp_type=data.get("otp_type", "email"),
    )

    try:
        AuthService.reset_password(dto)
    except ValidationError as exc:
        return _swal_error("Thông tin không hợp lệ", str(exc), 422)
    except UnauthorizedError as exc:
        return _swal_error("OTP không hợp lệ", str(exc), 401)
    except ConflictError as exc:
        return _swal_error("Không thể đặt mật khẩu", str(exc), 409)
    except Exception as exc:
        logger.exception("Unexpected reset_password error: %s", exc)
        return _swal_error("Lỗi hệ thống", "Vui lòng thử lại sau.", 500)

    return _swal_success(
        "Đặt lại mật khẩu thành công",
        "Mật khẩu của bạn đã được cập nhật. Vui lòng đăng nhập lại.",
        redirect_url=url_for("auth.login_page"),
    )