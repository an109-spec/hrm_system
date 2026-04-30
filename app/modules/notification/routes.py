from flask import request, jsonify
from flask_login import login_required, current_user

from . import notification_bp
from .service import NotificationService
from .dto import NotificationDTO
from app.models.user import User
from app.models.notification import Notification
from app.models.overtime_request import OvertimeRequest
from app.models.attendance import Attendance
from app.models.history import HistoryLog


# =========================
# GET MY NOTIFICATIONS
# =========================
@notification_bp.route("/", methods=["GET"])
@login_required
def get_my_notifications():
    limit = int(request.args.get("limit", 20))
    only_unread = request.args.get("unread", "false").lower() == "true"

    notifications = NotificationService.get_by_user(
        user_id=current_user.id,
        limit=limit,
        only_unread=only_unread
    )

    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "type": n.type,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat()
        }
        for n in notifications
    ])


# =========================
# COUNT UNREAD (badge UI)
# =========================
@notification_bp.route("/unread-count", methods=["GET"])
@login_required
def unread_count():
    count = NotificationService.count_unread(current_user.id)

    return jsonify({
        "unread_count": count
    })


# =========================
# MARK AS READ
# =========================
@notification_bp.route("/<int:noti_id>/read", methods=["POST"])
@login_required
def mark_read(noti_id):
    try:
        noti = NotificationService.mark_as_read(
            notification_id=noti_id,
            user_id=current_user.id
        )

        return jsonify({
            "id": noti.id,
            "is_read": noti.is_read
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# MARK ALL AS READ
# =========================
@notification_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    NotificationService.mark_all_as_read(current_user.id)

    return jsonify({
        "message": "All notifications marked as read"
    })


# =========================
# DELETE NOTIFICATION
# =========================
@notification_bp.route("/<int:noti_id>", methods=["DELETE"])
@login_required
def delete(noti_id):
    try:
        before_noti = Notification.query.filter_by(id=noti_id, user_id=current_user.id).first()
        overtime_request_id = getattr(before_noti, "overtime_request_id", None) if before_noti else None
        attendance_id = getattr(before_noti, "attendance_id", None) if before_noti else None
        before_ot_deleted = None
        before_attendance_ot = None
        before_logs = None
        if overtime_request_id:
            ot_row = OvertimeRequest.query.filter_by(id=overtime_request_id).first()
            before_ot_deleted = bool(ot_row.is_deleted) if ot_row else None
        if attendance_id:
            att_row = Attendance.query.filter_by(id=attendance_id).first()
            before_attendance_ot = float(att_row.overtime_hours or 0) if att_row else None
        if before_noti:
            before_logs = HistoryLog.query.filter_by(entity_type="notification", entity_id=before_noti.id).count()

        NotificationService.delete(
            notification_id=noti_id,
            user_id=current_user.id
        )
        after_noti = Notification.query.filter_by(id=noti_id, user_id=current_user.id).first()
        deleted_notification = bool(after_noti and after_noti.is_deleted)

        deleted_overtime_request = False
        if overtime_request_id:
            ot_after = OvertimeRequest.query.filter_by(id=overtime_request_id).first()
            deleted_overtime_request = bool(ot_after and ot_after.is_deleted)

        updated_attendance = False
        if attendance_id:
            att_after = Attendance.query.filter_by(id=attendance_id).first()
            if att_after:
                current_ot = float(att_after.overtime_hours or 0)
                if before_attendance_ot is None:
                    updated_attendance = current_ot == 0
                else:
                    updated_attendance = current_ot != before_attendance_ot

        deleted_logs = False
        if before_noti:
            after_logs = HistoryLog.query.filter_by(entity_type="notification", entity_id=before_noti.id).count()
            deleted_logs = bool(after_logs > (before_logs or 0))

        related_checks = []
        if overtime_request_id is not None:
            related_checks.append(deleted_overtime_request)
        if attendance_id is not None:
            related_checks.append(updated_attendance)
        related_checks.append(deleted_logs)

        if deleted_notification and all(related_checks):
            status = "success"
        elif deleted_notification:
            status = "partial"
        else:
            status = "failed"
        return jsonify({
            "deleted_notification": deleted_notification,
            "deleted_overtime_request": deleted_overtime_request,
            "updated_attendance": updated_attendance,
            "deleted_logs": deleted_logs,
            "notification_id": noti_id,
            "overtime_request_id": overtime_request_id,
            "attendance_id": attendance_id,
            "status": status,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# CREATE (ADMIN/TEST ONLY)
# =========================
@notification_bp.route("/", methods=["POST"])
@login_required
def create():
    data = request.json

    dto = NotificationDTO(
        user_id=data["user_id"],
        title=data["title"],
        content=data.get("content"),
        type=data.get("type"),
        link=data.get("link")
    )

    noti = NotificationService.create(dto)

    return jsonify({
        "id": noti.id,
        "message": "Created"
    })