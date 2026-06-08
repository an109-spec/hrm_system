from flask import Blueprint, g, request, jsonify

from app.common.security.decorators import auth_required
from app.models.notification import Notification
from app.modules.notification.notification_service import NotificationService
from app.common.exceptions import NotFoundError
from . import notification_bp
from app.common.responses import flat_swal_success as swal_success, flat_swal_error as swal_error, flat_swal_info as swal_info



# ─────────────────────────────────────────────
# 1. GET /notifications
#    Lấy danh sách thông báo (phân trang / limit)
# ─────────────────────────────────────────────
@notification_bp.route("", methods=["GET"])
@auth_required
def get_notifications():
    """
    Query params:
        limit (int, default=50): Số lượng thông báo tối đa trả về
    """
    try:
        limit = int(request.args.get("limit", 50))
        if limit <= 0 or limit > 200:
            return swal_error(
                title="Tham số không hợp lệ",
                message="limit phải nằm trong khoảng 1 – 200",
                status_code=400
            )
    except (ValueError, TypeError):
        return swal_error(
            title="Tham số không hợp lệ",
            message="limit phải là số nguyên dương",
            status_code=400
        )

    notifications = NotificationService.get_notifications(
        user_id=g.user.id,
        limit=limit
    )

    return swal_success(
        title="Danh sách thông báo",
        data={
            "notifications": notifications,
            "total": len(notifications),
        }
    )


# ─────────────────────────────────────────────
# 2. GET /notifications/<id>
#    Xem chi tiết & tự động đánh dấu "đã đọc"
# ─────────────────────────────────────────────
@notification_bp.route("/<int:notification_id>", methods=["GET"])
@auth_required
def get_notification_detail(notification_id: int):
    try:
        detail = NotificationService.notification_detail(
            user_id=g.user.id,
            noti_id=notification_id
        )
        return swal_success(
            title="Chi tiết thông báo",
            data=detail
        )
    except NotFoundError as e:
        return swal_error(
            title="Không tìm thấy",
            message=str(e),
            status_code=404
        )
    except Exception as e:
        return swal_error(
            title="Lỗi hệ thống",
            message=str(e),
            status_code=500
        )


# ─────────────────────────────────────────────
# 3. POST /notifications/mark-all-read
#    Đánh dấu tất cả thông báo là đã đọc
# ─────────────────────────────────────────────
@notification_bp.route("/mark-all-read", methods=["POST"])
@auth_required
def mark_all_as_read():
    try:
        updated_count = NotificationService.mark_all_as_read(user_id=g.user.id)

        if updated_count == 0:
            return swal_info(
                title="Không có gì thay đổi",
                message="Tất cả thông báo đã được đọc trước đó.",
                data={"updated_count": 0}
            )

        return swal_success(
            title="Đã đánh dấu tất cả là đã đọc",
            message=f"Đã cập nhật {updated_count} thông báo.",
            data={"updated_count": updated_count}
        )
    except Exception as e:
        return swal_error(
            title="Lỗi hệ thống",
            message=str(e),
            status_code=500
        )


# ─────────────────────────────────────────────
# 4. GET /notifications/unread-count
#    Lấy số lượng thông báo chưa đọc (Badge)
# ─────────────────────────────────────────────
@notification_bp.route("/unread-count", methods=["GET"])
@auth_required
def get_unread_count():
    try:
        count = Notification.get_unread_count(user_id=g.user.id)
        return swal_success(
            title="Số thông báo chưa đọc",
            data={"unread_count": count}
        )
    except Exception as e:
        return swal_error(
            title="Lỗi hệ thống",
            message=str(e),
            status_code=500
        )


# ─────────────────────────────────────────────
# 5. DELETE /notifications/<id>
#    Xoá thông báo (Soft delete)
# ─────────────────────────────────────────────
@notification_bp.route("/<int:notification_id>", methods=["DELETE"])
@auth_required
def delete_notification(notification_id: int):
    try:
        Notification.remove(
            notification_id=notification_id,
            user_id=g.user.id
        )
        return swal_success(
            title="Đã xoá thông báo",
            message="Thông báo đã được xoá thành công.",
            data={"deleted_id": notification_id}
        )
    except ValueError as e:
        return swal_error(
            title="Không tìm thấy",
            message=str(e),
            status_code=404
        )
    except Exception as e:
        return swal_error(
            title="Lỗi hệ thống",
            message=str(e),
            status_code=500
        )