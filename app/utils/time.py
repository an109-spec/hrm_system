from datetime import datetime
from flask import session
def parse_simulated_time(payload: dict) -> datetime:
    sim_time = payload.get("simulated_now")

    if sim_time:
        dt = datetime.fromisoformat(sim_time.replace("Z", "+00:00"))

        # 🔥 CHUẨN HOÁ: luôn bỏ timezone
        dt = dt.replace(tzinfo=None)

        session["simulated_now"] = dt.isoformat()
        return dt

    session_time = session.get("simulated_now")
    if session_time:
        dt = datetime.fromisoformat(session_time)
        dt = dt.replace(tzinfo=None)
        return dt

    return datetime.now()