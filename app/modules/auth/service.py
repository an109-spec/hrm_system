import logging
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import re
from app.common.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.extensions import db
from app.models import User, Employee 
from app.models.otp import OTPCode

from app.common.security.otp import get_otp_expired_at
from .dto import ( RequestPasswordResetDTO, 
    LoginDTO, ResetPasswordDTO, RequestPasswordResetResultDTO,
)
from app.utils.time import get_current_time
from .otp_service import OTPService
from .mail_service import MailService

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")
class AuthService:
    @staticmethod
    def validate_password(password: str) -> None:
        if not password or not password.strip():
            raise ValidationError("Mật khẩu không được để trống")
        if len(password) < 8:
            raise ValidationError("Mật khẩu phải có ít nhất 8 ký tự")

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return re.sub(r'\D', '', phone)

    @staticmethod
    def validate_identifier_data(raw_identifier: str) -> str:
        """
        Nhận vào chuỗi thô, trả về chuỗi đã chuẩn hóa.
        """
        if not raw_identifier or not raw_identifier.strip():
            raise ValidationError("Vui lòng nhập Email hoặc Số điện thoại")
        clean_identifier = raw_identifier.strip()
        if "@" in clean_identifier:
            if not EMAIL_PATTERN.fullmatch(clean_identifier):
                raise ValidationError("Định dạng Email không hợp lệ")
            clean_identifier = clean_identifier.lower()
        else:
            clean_identifier = AuthService._normalize_phone(clean_identifier)
            if not PHONE_PATTERN.fullmatch(clean_identifier):
                raise ValidationError("Số điện thoại không hợp lệ")
                
        return clean_identifier
    
    '''
    CHO PHÉP ĐĂNG NHẬP BẰNG SDT HOẶC EMAIL 
    '''
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
    def login(dto: LoginDTO) -> User:
        """
        Xử lý đăng nhập với LoginDTO.
        """
        clean_identifier = AuthService.validate_identifier_data(dto.identifier)
        AuthService.validate_password(dto.password)
        user = AuthService._get_user_by_identifier(clean_identifier)
        if not user or not user.check_password(dto.password):
            if user:
                user.failed_login_attempts += 1
                db.session.commit()
            raise UnauthorizedError("Sai thông tin đăng nhập")
        now = get_current_time()
        if user.locked_at and user.locked_at > now:
            raise UnauthorizedError(f"Tài khoản bị khóa đến {user.locked_at}")
        user.failed_login_attempts = 0
        user.locked_at = None
        user.lock_reason = None 
        db.session.commit()
        return user

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