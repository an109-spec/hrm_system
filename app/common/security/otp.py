import secrets
import string
from datetime import datetime, timezone, timedelta
from app.utils.time import get_current_time

OTP_EXPIRE_MINUTES = 5

def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))

def get_otp_expired_at() -> datetime:
    """
    Return the expiration time of an OTP (UTC).
    Sử dụng get_current_time() để hỗ trợ Simulation Mode.
    """
    now_vn = get_current_time()
    now_utc = now_vn.astimezone(timezone.utc)
    return now_utc + timedelta(minutes=OTP_EXPIRE_MINUTES)

def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def is_otp_expired(expired_at: datetime) -> bool:
    """
    So sánh thời gian hết hạn dựa trên thời gian hệ thống hiện tại.
    Hỗ trợ Simulation Mode thông qua get_current_time().
    """
    now_utc = get_current_time().astimezone(timezone.utc)
    return now_utc > _as_utc_aware(expired_at)