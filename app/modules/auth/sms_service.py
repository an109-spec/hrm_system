import logging
import re
from flask import current_app
from app.common.exceptions import ValidationError

logger = logging.getLogger(__name__)

class SMSService:
    # Regex hỗ trợ từ 9-15 chữ số, có thể có dấu +
    PHONE_REGEX = r"^\+?\d{9,15}$"

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Chuẩn hóa số điện thoại về định dạng +84 cho Việt Nam."""
        phone = phone.strip().replace(" ", "").replace("-", "")

        # Chuyển đổi số 0 đầu thành +84
        if phone.startswith("0"):
            phone = "+84" + phone[1:]
        
        # Nếu chưa có dấu + thì thêm vào (giả định mặc định là VN nếu không có mã vùng)
        if not phone.startswith("+"):
            phone = "+" + phone

        return phone

    @staticmethod
    def send(phone: str, message: str) -> None:
        """Gửi tin nhắn SMS (OTP, thông báo khẩn cấp HRM)."""
        if not phone:
            raise ValidationError("Số điện thoại không được để trống")

        if not message:
            raise ValidationError("Nội dung tin nhắn không được để trống")

        phone = SMSService._normalize_phone(phone)

        if not re.match(SMSService.PHONE_REGEX, phone):
            raise ValidationError("Định dạng số điện thoại không hợp lệ")

        try:
            # 1. Chế độ Development/Debug
            if current_app.config.get("DEBUG") or current_app.config.get("ENV") == "development":
                logger.info("--- [DEV MODE SMS] ---")
                logger.info(f"To: {phone}")
                logger.info(f"Content: {message}")
                logger.info("-----------------------")
                return

            # 2. Chế độ Production
            # Duy An có thể lấy API Key từ config để chuẩn bị tích hợp
            # api_key = current_app.config.get("SMS_API_KEY")
            
            logger.info(f"[PROD SMS] Đang gửi tới {phone} thông qua Provider...")
            
            # TODO: Duy An có thể dùng thư viện `requests` để call API của 
            # các bên như Esms.vn hoặc Twilio tại đây.
            
        except Exception as e:
            logger.error(f"Lỗi khi gửi SMS tới {phone}: {str(e)}")
            # Trong HRM, nếu SMS lỗi thường ta sẽ fallback sang Email 
            # nên không nhất thiết phải làm crash hệ thống.
            raise RuntimeError("Dịch vụ gửi SMS hiện không khả dụng")