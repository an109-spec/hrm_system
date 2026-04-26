from datetime import datetime
from flask import has_request_context, request, session

def get_demo_system_time() -> datetime:
    """Nguồn thời gian chuẩn cho toàn hệ thống (server-side)."""
    return datetime.now()

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