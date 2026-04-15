from flask import request, jsonify
from flask_login import login_required, current_user

from . import notification_bp
from .service import NotificationService
from .dto import NotificationDTO
from app.models.user import User


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
        NotificationService.delete(
            notification_id=noti_id,
            user_id=current_user.id
        )

        return jsonify({
            "message": "Deleted"
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