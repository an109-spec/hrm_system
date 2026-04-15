from flask import jsonify, request, session
from . import history_bp
from .service import HistoryService


def get_user():
    return session.get("user_id")


# =========================
# GET EMPLOYEE TIMELINE
# =========================
@history_bp.route("/employee/<int:employee_id>", methods=["GET"])
def get_employee_history(employee_id):
    data = HistoryService.get_employee_timeline(employee_id)
    return jsonify(data)


# =========================
# GET MY HISTORY
# =========================
@history_bp.route("/me", methods=["GET"])
def get_my_history():
    user_id = get_user()

    # giả sử employee_id = user_id mapping (tuỳ hệ thống mày)
    data = HistoryService.get_employee_timeline(user_id)
    return jsonify(data)


# =========================
# CREATE MANUAL LOG (ADMIN/DEBUG)
# =========================
@history_bp.route("/log", methods=["POST"])
def create_log():
    body = request.json

    log = HistoryService.log_event(
        action=body.get("action"),
        employee_id=body.get("employee_id"),
        entity_type=body.get("entity_type"),
        entity_id=body.get("entity_id"),
        description=body.get("description"),
        performed_by=get_user()
    )

    return jsonify({
        "message": "log created",
        "id": log.id
    })