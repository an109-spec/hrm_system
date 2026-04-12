from app.extensions.db import db
from .base import BaseModel
from datetime import datetime, timezone

class OTPCode(BaseModel):
    __tablename__ = "otp_codes"

    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Hash OTP -> cần đủ dài
    otp_code = db.Column(db.String(255), nullable=False)

    # Dùng string để dễ mở rộng
    type = db.Column(db.String(20), nullable=False)

    expired_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)

    failed_attempts = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.Index("idx_otp_user_type_used", "user_id", "type", "is_used"),
        db.Index("idx_otp_expired", "expired_at"),
    )


