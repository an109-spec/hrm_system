import logging
from flask import current_app
from flask_mail import Message
from app.extensions import mail
from app.common.exceptions import ValidationError

logger = logging.getLogger(__name__)

class MailService:
    """Service tập trung quản lý toàn bộ việc gửi Email cho hệ thống HRM."""

    @staticmethod
    def send_otp(to_email: str, otp_code: str) -> None:
        """Gửi mã OTP xác thực cho nhân viên."""
        if not to_email or "@" not in to_email:
            raise ValidationError("Email người nhận không hợp lệ")

        try:
            # 1. Chế độ Test/Development: Không gửi mail thật để tiết kiệm quota/tránh spam
            if current_app.config.get("DEBUG") or current_app.config.get("ENV") == "development":
                logger.info(f"--- [DEV MODE EMAIL] ---")
                logger.info(f"To: {to_email}")
                logger.info(f"Subject: Mã OTP đặt lại mật khẩu HRM")
                logger.info(f"OTP: {otp_code}")
                logger.info(f"------------------------")
                return

            # 2. Chế độ Production: Gửi mail thật qua SMTP
            subject = "Mã OTP đặt lại mật khẩu - Hệ thống HRM"
            
            # Nội dung đã được chỉnh sửa phù hợp với môi trường công ty
            body = (
                "Xin chào,\n\n"
                "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản nhân sự của bạn.\n"
                f"Mã OTP xác thực của bạn là: {otp_code}\n"
                "Mã có hiệu lực trong 05 phút. Vì lý do bảo mật, vui lòng không chia sẻ mã này cho bất kỳ ai.\n\n"
                "Nếu bạn không thực hiện yêu cầu này, vui lòng liên hệ với bộ phận IT để được hỗ trợ.\n"
                "Trân trọng,\n"
                "Ban quản trị hệ thống HRM."
            )

            sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "annduyy85@gmail.com"
            
            msg = Message(
                subject=subject,
                recipients=[to_email.strip()],
                body=body,
                sender=sender
            )

            mail.send(msg)
            logger.info(f"Successfully sent OTP email to {to_email}")

        except Exception as e:
            logger.error(f"Email sending failed to {to_email}: {str(e)}")
            # Không raise lỗi hệ thống ở đây để tránh làm crash luồng đăng ký của User,
            # nhưng vẫn báo cho phía Service biết
            raise RuntimeError("Dịch vụ gửi email hiện không khả dụng")