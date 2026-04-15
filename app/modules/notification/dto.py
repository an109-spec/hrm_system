from dataclasses import dataclass
from datetime import datetime


@dataclass
class NotificationDTO:
    user_id: int
    title: str
    content: str | None = None
    type: str | None = None
    link: str | None = None
    is_read: bool = False