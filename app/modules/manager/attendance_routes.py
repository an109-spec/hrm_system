from flask import jsonify, request, g
from app.modules.manager import manager_bp
from app.modules.manager.attendance_service import AttendanceManagerService
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName


# ─────────────────────────────────────────────
# Helper: lấy manager_id từ g.employee
# ─────────────────────────────────────────────
def _get_manager_id():
    return g.employee.id


# ─────────────────────────────────────────────
# GET /api/manager/attendance
# Lấy danh sách điểm danh phòng ban (có phân trang/lọc)
# ─────────────────────────────────────────────
@manager_bp.route("/attendance", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_department_attendance():
    """
    Query params:
        month, year, status, page, per_page
    """
    try:
        filters = {
            "month":    request.args.get("month"),
            "year":     request.args.get("year"),
            "status":   request.args.get("status", ""),
            "page":     request.args.get("page", 1),
            "per_page": request.args.get("per_page", 10),
        }
        # Loại bỏ giá trị None để service dùng default
        filters = {k: v for k, v in filters.items() if v is not None}

        result = AttendanceManagerService.get_department_attendance_rows(
            manager_id=_get_manager_id(),
            filters=filters
        )
        return jsonify({
            "success": True,
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# GET /api/manager/attendance/dashboard
# Thống kê biểu đồ chấm công theo tháng
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/dashboard", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_attendance_dashboard():
    """
    Query params:
        month (int), year (int)
    """
    try:
        from app.utils.time import get_current_time
        now = get_current_time()

        month = int(request.args.get("month", now.month))
        year  = int(request.args.get("year",  now.year))

        result = AttendanceManagerService.get_manager_attendance_dashboard(
            manager_id=_get_manager_id(),
            month=month,
            year=year
        )
        return jsonify({
            "success": True,
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# GET /api/manager/attendance/summary
# Đếm nhanh: check-in, vắng, OT, nghỉ phép...
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/summary", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_attendance_summary():
    """
    Query params:
        month, year
    """
    try:
        filters = {
            "month": request.args.get("month"),
            "year":  request.args.get("year"),
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        result = AttendanceManagerService.get_department_attendance_summary(
            manager_id=_get_manager_id(),
            filters=filters
        )
        return jsonify({
            "success": True,
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# GET /api/manager/attendance/employee/<int:employee_id>
# Chi tiết điểm danh + đơn từ của 1 nhân viên hôm nay
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/employee/<int:employee_id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def get_attendance_detail(employee_id: int):
    """
    Query params:
        month, year (tùy chọn – service hiện dùng ngày hôm nay)
    """
    try:
        filters = {
            "month": request.args.get("month"),
            "year":  request.args.get("year"),
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        result = AttendanceManagerService.get_department_attendance_detail(
            manager_id=_get_manager_id(),
            employee_id=employee_id,
            filters=filters
        )
        return jsonify({
            "success": True,
            "data": result
        }), 200

    except ValueError as e:
        # Lỗi quyền hoặc không tìm thấy nhân viên
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Không có quyền",
                "text": str(e)
            }
        }), 403

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# PUT /api/manager/attendance/<int:attendance_id>
# Chỉnh sửa check-in / check-out (correction)
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/<int:attendance_id>", methods=["PUT"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def update_attendance_correction(attendance_id: int):
    """
    Body JSON:
        new_check_in  (str, "HH:MM" hoặc ISO, tùy chọn)
        new_check_out (str, "HH:MM" hoặc ISO, tùy chọn)
        reason        (str)
    """
    try:
        from datetime import datetime
        body = request.get_json(silent=True) or {}

        def _parse_dt(val):
            """Chấp nhận 'HH:MM' hoặc 'YYYY-MM-DDTHH:MM:SS'."""
            if not val:
                return None
            for fmt in ("%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Không thể parse thời gian: {val}")

        new_check_in  = _parse_dt(body.get("new_check_in"))
        new_check_out = _parse_dt(body.get("new_check_out"))
        reason        = body.get("reason", "").strip()

        result = AttendanceManagerService.update_attendance_correction(
            manager_id=_get_manager_id(),
            attendance_id=attendance_id,
            new_check_in=new_check_in,
            new_check_out=new_check_out,
            reason=reason
        )

        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Cập nhật thành công",
                "text": result.get("message", "Dữ liệu chấm công đã được cập nhật.")
            },
            "data": result
        }), 200

    except ValueError as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "warning",
                "title": "Dữ liệu không hợp lệ",
                "text": str(e)
            }
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# GET /api/manager/attendance/export
# Xuất báo cáo chấm công ra file Excel
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/export", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def export_attendance_report():
    """
    Query params:
        month, year, status
    """
    try:
        filters = {
            "month":  request.args.get("month"),
            "year":   request.args.get("year"),
            "status": request.args.get("status", ""),
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        result = AttendanceManagerService.export_attendance_report(
            manager_id=_get_manager_id(),
            filters=filters
        )

        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Xuất báo cáo thành công",
                "text": "File Excel đã được tạo. Nhấn OK để tải về.",
                "confirmButtonText": "Tải về"
            },
            "data": {
                "file_url": result["file_url"]
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Xuất báo cáo thất bại",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# POST /api/manager/attendance/sync-abnormal
# Quét & đánh dấu các bản ghi chấm công bất thường
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/sync-abnormal", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def sync_abnormal_records():
    try:
        AttendanceManagerService.auto_detect_abnormal_records(
            manager_id=_get_manager_id()
        )
        return jsonify({
            "success": True,
            "swal": {
                "icon": "success",
                "title": "Đồng bộ hoàn tất",
                "text": "Hệ thống đã quét và cập nhật các bản ghi bất thường."
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Đồng bộ thất bại",
                "text": str(e)
            }
        }), 500


# ─────────────────────────────────────────────
# POST /api/manager/attendance/reminders
# Gửi thông báo nhắc nhở chấm công
# ─────────────────────────────────────────────
@manager_bp.route("/attendance/reminders", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.ADMIN, RoleName.HR)
def send_attendance_reminder():
    """
    Body JSON:
        employee_ids (list[int])  – danh sách ID nhân viên cần nhắc
        message      (str|null)   – nội dung tùy chỉnh (để trống = dùng mặc định)
    """
    try:
        body = request.get_json(silent=True) or {}
        employee_ids = body.get("employee_ids", [])
        message      = body.get("message", None)

        if not employee_ids or not isinstance(employee_ids, list):
            return jsonify({
                "success": False,
                "swal": {
                    "icon": "warning",
                    "title": "Thiếu dữ liệu",
                    "text": "Vui lòng cung cấp danh sách employee_ids hợp lệ."
                }
            }), 400

        success = AttendanceManagerService.send_reminder(
            manager_id=_get_manager_id(),
            employee_ids=employee_ids,
            message=message
        )

        if success:
            return jsonify({
                "success": True,
                "swal": {
                    "icon": "success",
                    "title": "Gửi thành công",
                    "text": f"Đã gửi nhắc nhở tới {len(employee_ids)} nhân viên."
                }
            }), 200
        else:
            return jsonify({
                "success": False,
                "swal": {
                    "icon": "warning",
                    "title": "Không gửi được",
                    "text": "Không tìm thấy nhân viên hợp lệ thuộc quyền quản lý của bạn."
                }
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "swal": {
                "icon": "error",
                "title": "Lỗi hệ thống",
                "text": str(e)
            }
        }), 500