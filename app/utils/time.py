from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import has_request_context, request, session

VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

SESSION_KEY = "sim_clock"
SPEED_KEY = "sim_speed"

ANCHOR_REAL_KEY = "_sim_anchor_real"
ANCHOR_SIM_KEY = "_sim_anchor_sim"
def get_system_time() -> datetime:
    return datetime.now(VN_TIMEZONE)
def get_current_time() -> datetime:
    """
    Priority:
    1. Simulation (if enabled)
    2. Real system time
    """
    sim = _get_simulated_time()
    return sim if sim is not None else get_system_time()

def _get_simulated_time() -> datetime | None:
    if not has_request_context():
        return None
    sim_anchor = session.get(SESSION_KEY)
    if not sim_anchor:
        return None
    speed = float(session.get(SPEED_KEY, 1))
    sim_anchor_dt = _normalize(sim_anchor)
    if not sim_anchor_dt:
        return None
    if ANCHOR_REAL_KEY not in session or ANCHOR_SIM_KEY not in session:
        session[ANCHOR_REAL_KEY] = get_system_time().isoformat()
        session[ANCHOR_SIM_KEY] = sim_anchor_dt.isoformat()

        return sim_anchor_dt

    real_anchor = _normalize(session.get(ANCHOR_REAL_KEY))
    sim_anchor_stored = _normalize(session.get(ANCHOR_SIM_KEY))

    if not real_anchor or not sim_anchor_stored:
        return sim_anchor_dt

    now_real = get_system_time()
    elapsed_real = now_real - real_anchor
    elapsed_sim = elapsed_real * speed

    simulated_now = sim_anchor_stored + elapsed_sim

    return simulated_now

def set_simulated_time(dt: datetime, speed: float = 1):
    if not has_request_context():
        return

    session[SESSION_KEY] = dt.isoformat()
    session[SPEED_KEY] = float(speed)

    session[ANCHOR_REAL_KEY] = get_system_time().isoformat()
    session[ANCHOR_SIM_KEY] = dt.isoformat()

def reset_simulated_time():
    if not has_request_context():
        return

    session.pop(SESSION_KEY, None)
    session.pop(SPEED_KEY, None)
    session.pop(ANCHOR_REAL_KEY, None)
    session.pop(ANCHOR_SIM_KEY, None)

def is_simulation_mode() -> bool:
    return has_request_context() and SESSION_KEY in session


def _normalize(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        if len(value) == 10:
            dt = datetime.combine(
                dt.date(),
                datetime.min.time()
            )
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=VN_TIMEZONE)
        return dt.astimezone(VN_TIMEZONE)
    except ValueError:
        return None
    