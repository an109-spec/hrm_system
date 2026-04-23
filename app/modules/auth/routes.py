from flask import request, render_template, redirect, url_for, session, current_app
from flask_jwt_extended import create_access_token, set_access_cookies
from app.common.exceptions import UnauthorizedError, ValidationError, ConflictError

from . import auth_bp
from .validators import validate_login, validate_register
# CHỈ import các Class cần thiết, KHÔNG import module 'dto' trùng tên
from .dto import (
    LoginDTO,
    RegisterDTO,
    RequestPasswordResetDTO,
    ResetPasswordDTO,
)
from .service import AuthService

def _mask_identifier(identifier: str) -> str:
    identifier = (identifier or "").strip()
    if "@" in identifier:
        local, domain = identifier.split("@", 1)
        masked_local = local[:2] + "*" * (len(local) - 2) if len(local) > 2 else local + "*"
        return f"{masked_local}@{domain}"
    return f"{identifier[:2]}{'*' * (len(identifier) - 4)}{identifier[-2:]}" if len(identifier) > 4 else "*" * len(identifier)
def _redirect_after_login(user, next_url: str | None):
    if next_url:
        return redirect(next_url)

    role_name = (user.role.name if getattr(user, "role", None) else "Employee").strip().lower()
    if role_name == "admin":
        return redirect(url_for("admin.admin_dashboard_page"))
    if role_name == "manager":
        return redirect(url_for("manager.dashboard_page"))
    return redirect(url_for("employee.dashboard"))
# ======================================================
# LOGIN
# ======================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html", next_url=request.args.get("next"))

    data = request.form.to_dict()
    next_url = data.get("next") or request.args.get("next")
    
    try:
        # 1. Validate dữ liệu đầu vào
        validate_login(data)
        
        # 2. Khởi tạo đối tượng DTO từ dữ liệu form (Đặt tên là auth_dto để tránh trùng)
        auth_dto = LoginDTO(
            identifier=data.get("identifier"),
            password=data.get("password")
        )
        
        # 3. Gọi service xử lý logic login
        user = AuthService.login(auth_dto)
        
        # 4. Tạo JWT Token
        access_token = create_access_token(identity=str(user.id))

        response = _redirect_after_login(user, next_url)

        # 6. Đính Token vào Cookie (Quan trọng để @jwt_required đọc được)
        set_access_cookies(response, access_token)
        
        # Lưu session song song nếu cần dùng cho inject_globals
        session["user_id"] = user.id
        
        return response

    except (ValidationError, UnauthorizedError) as e:
        return render_template(
            "auth/login.html",
            error=str(e),
            next_url=next_url
        )

# ======================================================
# REGISTER
# ======================================================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    data = request.form.to_dict()
    
    # Tạo DTO để truyền vào Service
    reg_dto = RegisterDTO(
        email=data.get("email"),
        phone=data.get("phone"),
        password=data.get("password"),
        full_name=data.get("full_name"),
        position=data.get("position"),
        department_id=data.get("department_id")
    )

    try:
        user = AuthService.register(reg_dto)
        
        # Sau khi đăng ký, tạo luôn token để user vào thẳng dashboard
        access_token = create_access_token(identity=str(user.id))
        response = redirect(url_for("employee.dashboard"))
        set_access_cookies(response, access_token)
        
        session["user_id"] = user.id
        return response

    except ConflictError as e:
        return render_template("auth/register.html", error=str(e), data=data)

# ... Các hàm Logout, Forgot Password giữ nguyên ...

# ======================================================
# LOGOUT
# ======================================================

@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auth.login"))
# ======================================================
# FORGOT PASSWORD
# ======================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html", otp_sent=False)

    identifier = (request.form.get("identifier") or "").strip()

    try:
        dto = RequestPasswordResetDTO(identifier=identifier)
        result = AuthService.request_password_reset(dto)
        channel_text = "email" if result.delivery_channel == "email" else "SMS"

        return render_template(
            "auth/forgot_password.html",
            otp_sent=True,
            masked_identifier=_mask_identifier(identifier),
            identifier=identifier,
            otp_type=result.delivery_channel,
            otp_expires_at=result.otp_expires_at_iso,
            otp_preview=result.otp_preview if current_app.debug else None,
        )

    except ValidationError as e:
        return render_template(
            "auth/forgot_password.html",
            otp_sent=False,
            error=str(e),
            identifier=identifier,
        )
# ======================================================
# RESET PASSWORD
# ======================================================

@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        return render_template(
            "auth/reset_password.html",
            identifier=(request.args.get("identifier") or "").strip(),
        )

    data = request.form.to_dict()
    identifier = (data.get("identifier") or "").strip()
    otp_code = (data.get("otp_code") or "").strip()
    new_password = data.get("new_password") or ""
    confirm_password = data.get("confirm_password") or ""
    otp_type = "email"

    if new_password != confirm_password:
        return render_template(
            "auth/reset_password.html",
            identifier=identifier,
            error="Mật khẩu xác nhận không khớp",
        )

    try:
        dto = ResetPasswordDTO(
            identifier=identifier,
            otp_code=otp_code,
            new_password=new_password,
            otp_type=otp_type,
        )

        AuthService.reset_password(dto)

        return redirect(url_for("auth.login"))
    except (ValidationError, UnauthorizedError, ConflictError) as e:
        return render_template(
            "auth/reset_password.html",
            identifier=identifier,
            error=str(e),
        )
@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "GET":
        identifier = request.args.get("identifier")
        return render_template("auth/verify_otp.html", identifier=identifier)

    data = request.form.to_dict()

    try:
        dto = ResetPasswordDTO(
            identifier=data["identifier"],
            otp_code=data["otp_code"],
            otp_type=data["otp_type"],
            new_password=data["new_password"],
        )

        AuthService.reset_password(dto)

        return redirect(url_for("auth.login"))

    except (ValidationError, UnauthorizedError, ConflictError) as e:
        return render_template(
            "auth/verify_otp.html",
            error=str(e),
            identifier=data.get("identifier"),
        )