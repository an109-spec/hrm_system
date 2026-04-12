import secrets
import string
from datetime import datetime, timezone, timedelta

OTP_EXPIRE_MINUTES = 5
def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))

def get_otp_expired_at() -> datetime:
    """Return the expiration time of an OTP (UTC)."""
    now = datetime.now(timezone.utc)
    return now + timedelta(minutes=OTP_EXPIRE_MINUTES)



def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_otp_expired(expired_at: datetime) -> bool:
    """
    Compare expiry robustly for both naive and aware datetimes.
    Some DB backends return naive datetime even if source was timezone-aware.
    """
    return datetime.now(timezone.utc) > _as_utc_aware(expired_at)
