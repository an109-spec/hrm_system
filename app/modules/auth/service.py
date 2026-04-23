from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from app.common.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.extensions import db
from app.models import User, Employee # Đổi UserProfile thành Employee cho HRM
from app.models.otp import OTPCode

from app.common.security.otp import get_otp_expired_at
from .dto import (
    LoginDTO, RegisterDTO, RequestPasswordResetDTO, 
    ResetPasswordDTO, RequestPasswordResetResultDTO,
)

from .otp_service import OTPService
from .mail_service import MailService
from .sms_service import SMSService

logger = logging.getLogger(__name__)

class AuthService:

    # ======================================================
    # UTIL
    # ======================================================
    @staticmethod
    def _normalize_identifier(identifier: str) -> str:
        if not identifier or not identifier.strip():
            raise ValidationError("Thiếu email hoặc số điện thoại")
        identifier = identifier.strip()
        return identifier.lower() if "@" in identifier else AuthService._normalize_phone(identifier)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return phone.strip().replace(" ", "").replace("-", "").replace(".", "")

    @staticmethod
    def _get_user_by_identifier(identifier: str) -> User | None:
            return User.query.filter(
                or_(
                    User.email == identifier,       # Tìm theo email
                    User.username == identifier,    # Tìm theo username (VD: "admin", "hr")
                    User.employee_profile.has(Employee.phone == identifier) # Tìm theo SĐT
                )
            ).first()

    @staticmethod
    def _generate_username(email: str | None, phone: str | None) -> str:
        base_username = email.split("@", 1)[0].strip().lower() if email else phone.strip()
        candidate = base_username
        suffix = 1
        while User.query.filter_by(username=candidate).first() is not None:
            candidate = f"{base_username}{suffix}"
            suffix += 1
        return candidate

    # ======================================================
    # REGISTER (Tối ưu cho HRM)
    # ======================================================
    @staticmethod
    def register(dto: RegisterDTO) -> User:
        # 1. Kiểm tra input
        if not dto.email and not dto.phone:
            raise ValidationError("Phải cung cấp email hoặc số điện thoại")

        email = dto.email.lower().strip() if dto.email else None
        phone = AuthService._normalize_phone(dto.phone) if dto.phone else None

        # Hack nhỏ để tránh lỗi null email nếu dùng Database cũ
        if not email and phone:
            email = f"{phone}@hrm.local"

        # 2. Tạo User tài khoản
        user = User(
            username=AuthService._generate_username(email, phone),
            email=email,
            password_hash=generate_password_hash(dto.password),
            role_id=3
        )

        try:
            db.session.add(user)
            db.session.flush() # Để lấy user.id

            # 3. QUAN TRỌNG: Tạo bản ghi Nhân viên (Employee) trong HRM
            # Thay vì UserProfile đơn giản, HRM cần Employee để quản lý lương/nghỉ phép
            employee = Employee(
                user_id=user.id,
                full_name=dto.full_name.strip(),
                phone=phone,
                working_status='working',
                hire_date=datetime.now(timezone.utc).date()
            )
            
            db.session.add(employee)
            db.session.commit()
            return user

        except IntegrityError:
            db.session.rollback()
            raise ConflictError("Tài khoản hoặc nhân viên đã tồn tại trong hệ thống")

    # ======================================================
    # LOGIN
    # ======================================================
    @staticmethod
    def login(dto: LoginDTO) -> User:
        identifier = AuthService._normalize_identifier(dto.identifier)
        user = AuthService._get_user_by_identifier(identifier)

        if not user or not check_password_hash(user.password_hash, dto.password):
            # Tăng số lần sai để lock tài khoản
            if user:
                user.failed_login_attempts += 1
                db.session.commit()
            raise UnauthorizedError("Sai thông tin đăng nhập")

        now = datetime.now(timezone.utc)
        if user.locked_at and user.locked_at > now:
            raise UnauthorizedError(f"Tài khoản bị khóa đến {user.locked_until}")

        # Login thành công: Reset số lần sai
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        # XÓA: CartService (HRM không có giỏ hàng)
        return user

    # ... Các hàm Reset Password Duy An giữ nguyên logic xử lý OTP là ổn ...

    # ======================================================
    # REQUEST PASSWORD RESET
    # ======================================================
    def request_password_reset(dto: RequestPasswordResetDTO) -> RequestPasswordResetResultDTO:
        identifier = AuthService._normalize_identifier(dto.identifier)
        user = AuthService._get_user_by_identifier(identifier)

        expires_at = get_otp_expired_at()

        # Không tiết lộ user tồn tại
        if not user:
            logger.info("Password reset requested for non-existing identifier")
            return RequestPasswordResetResultDTO(
                otp_expires_at_iso=expires_at.isoformat(),
                delivery_channel="email",
                otp_preview=None,
            )

        is_internal_phone_email = bool(user.email and user.email.endswith("@hrm.local"))
        # Chỉ gửi OTP qua email thật
        if user.email and not is_internal_phone_email:
            email_code = OTPService.create_otp(user, otp_type="email")
            try:
                MailService.send_otp(user.email, email_code)
                logger.info("Password reset OTP sent via email for user_id=%s", user.id)
            except Exception as exc:
                logger.exception("Failed to send OTP email for user_id=%s: %s", user.id, exc)
                raise ValidationError("Không thể gửi OTP qua email. Vui lòng kiểm tra cấu hình mail và thử lại.")
            return RequestPasswordResetResultDTO(
                otp_expires_at_iso=expires_at.isoformat(),
                delivery_channel="email",
                otp_preview=None,
            )
        logger.warning("User has no valid email for OTP delivery. user_id=%s", user.id)
        return RequestPasswordResetResultDTO(
            otp_expires_at_iso=expires_at.isoformat(),
            delivery_channel="email",
            otp_preview=None,
        )

    # ======================================================
    # RESET PASSWORD
    # ======================================================

    @staticmethod
    def reset_password(dto: ResetPasswordDTO) -> None:
        identifier = AuthService._normalize_identifier(dto.identifier)
        user = AuthService._get_user_by_identifier(identifier)

        if not user:
            raise UnauthorizedError("OTP không hợp lệ")

        if dto.otp_type not in ("email", "sms"):
            raise ValidationError("Loại OTP không hợp lệ")

        is_valid = OTPService.verify_otp(
            user_id=user.id,
            code=dto.otp_code,
            otp_type=dto.otp_type,
        )

        if not is_valid:
            raise UnauthorizedError("OTP không hợp lệ hoặc đã hết hạn")

        if len(dto.new_password) < 8:
            raise ConflictError("Mật khẩu phải tối thiểu 8 ký tự")

        if check_password_hash(user.password_hash, dto.new_password):
            raise ConflictError("Mật khẩu mới không được trùng mật khẩu cũ")

        try:
            user.password_hash = generate_password_hash(dto.new_password)
            user.failed_login_attempts = 0
            user.locked_until = None

            OTPCode.query.filter(
                OTPCode.user_id == user.id,
                OTPCode.type.in_(("email", "sms"))
            ).delete()

            db.session.commit()   # ← BẮT BUỘC

        except Exception as e:
            db.session.rollback()
            raise RuntimeError("Không thể cập nhật mật khẩu") from e