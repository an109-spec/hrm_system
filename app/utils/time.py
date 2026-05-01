from datetime import datetime
from flask import has_request_context, request, session
SIM_TIME_HEADER = "X-Simulated-Time"
def get_demo_system_time() -> datetime:
    """Nguồn thời gian chuẩn cho toàn hệ thống (server-side)."""
    return datetime.now()
def get_current_time(payload: dict | None = None) -> datetime:
    """Single source of truth for business time.

    REAL mode: datetime.now()
    SIMULATED mode: simulated datetime from header/body/session
    """
    return parse_simulated_time(payload)

def _normalize_datetime(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        dt = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None)


def parse_simulated_time(payload: dict | None = None) -> datetime:
    payload = payload or {}

    # Ưu tiên dữ liệu gửi trực tiếp từ API/body JSON
    dt = _normalize_datetime(payload.get("simulated_now"))

    # Hỗ trợ các page GET truyền simulated_now qua query string
    if not dt and has_request_context():
        dt = _normalize_datetime(request.args.get("simulated_now"))
    if not dt and has_request_context():
        dt = _normalize_datetime(request.headers.get(SIM_TIME_HEADER))

    # Hỗ trợ form POST (nếu có)
    if not dt and has_request_context():
        dt = _normalize_datetime(request.form.get("simulated_now"))

    if dt:


        session["simulated_now"] = dt.isoformat()
        return dt

    session_time = session.get("simulated_now") if has_request_context() else None
    dt = _normalize_datetime(session_time)
    if dt:
        return dt

    return get_demo_system_time()