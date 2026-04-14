from flask import request, render_template, redirect, url_for, session, current_app

from app.common.exceptions import (
    UnauthorizedError,
    ValidationError,
    ConflictError,
)

from . import auth_bp
from .validators import validate_login, validate_register
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
        if len(local) <= 2:
            masked_local = local[0] + "*" if local else "*"
        else:
            masked_local = local[:2] + "*" * (len(local) - 2)
        return f"{masked_local}@{domain}"

    if len(identifier) <= 4:
        return "*" * len(identifier)

    return f"{identifier[:2]}{'*' * (len(identifier) - 4)}{identifier[-2:]}"

# ======================================================
# REGISTER
# ======================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        # Duy An có thể truyền danh sách phòng ban sang để user chọn
        # departments = Department.query.all()
        return render_template("auth/register.html")

    data = request.form.to_dict()
    # Check mật khẩu khớp... (giữ nguyên)
    
    dto = RegisterDTO(
        email=data.get("email") or None,
        phone=data.get("phone") or None,
        password=data["password"],
        full_name=data["full_name"],
        position=data.get("position"), # Lấy từ form
        department_id=data.get("department_id") # Lấy từ form
    )

    try:
        user = AuthService.register(dto)
        session["user_id"] = user.id
        return redirect(url_for("employee.dashboard"))

    except ConflictError as e:
        return render_template("auth/register.html", errors=[str(e)], data=data)


# ======================================================
# LOGIN
# ======================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template(
            "auth/login.html",
            next_url=request.args.get("next")
        )

    data = request.form.to_dict()
    next_url = data.get("next") or request.args.get("next")
    
    try:
        validate_login(data)
        dto = LoginDTO(identifier=data["identifier"], password=data["password"])
        user = AuthService.login(dto)
        
        session["user_id"] = user.id

        return redirect(next_url or url_for("employee.dashboard"))

    except (ValidationError, UnauthorizedError) as e:
        return render_template(
            "auth/login.html",
            error=str(e),
            locked_until=getattr(e, "locked_until", None),
            next_url=next_url
        )

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