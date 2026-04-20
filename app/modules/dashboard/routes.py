from flask import Blueprint, render_template, request, jsonify
from app.models.employee import Employee
from app.modules.dashboard.service import DashboardService
from app.common.exceptions import ValidationError, UnauthorizedError

from . import dashboard_bp


# ==============================
# 📊 DASHBOARD TỔNG QUAN (ADMIN / HR)
# ==============================
@dashboard_bp.route("/overview", methods=["GET"])
def get_overview():
    """
    Tổng quan hệ thống:
    - Tổng nhân viên
    - Đang làm / nghỉ / nghỉ việc
    - Tổng phòng ban
    - Tổng hợp cơ bản
    """
    try:
        data = DashboardService.get_overview()
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 📅 CHẤM CÔNG HÔM NAY
# ==============================
@dashboard_bp.route("/attendance/today", methods=["GET"])
def attendance_today():
    """
    Thống kê chấm công hôm nay:
    - Có mặt
    - Đi muộn
    - Vắng
    """
    try:
        data = DashboardService.get_today_attendance()
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 💰 LƯƠNG THÁNG HIỆN TẠI
# ==============================
@dashboard_bp.route("/salary/summary", methods=["GET"])
def salary_summary():
    """
    Tổng hợp lương tháng:
    - Tổng quỹ lương
    - Đã trả / chưa trả
    """
    try:
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)

        if not month or not year:
            raise ValidationError("month và year là bắt buộc")

        data = DashboardService.get_salary_summary(month, year)

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🏢 THEO PHÒNG BAN
# ==============================
@dashboard_bp.route("/department", methods=["GET"])
def department_stats():
    """
    Thống kê theo phòng ban:
    - Số nhân viên
    - Trạng thái
    """
    try:
        data = DashboardService.get_department_stats()
        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# ⚠️ KHIẾU NẠI GẦN ĐÂY
# ==============================
@dashboard_bp.route("/complaints/recent", methods=["GET"])
def recent_complaints():
    """
    Lấy danh sách khiếu nại gần đây
    """
    try:
        limit = request.args.get("limit", 5, type=int)

        data = DashboardService.get_recent_complaints(limit)

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🔔 THÔNG BÁO
# ==============================
@dashboard_bp.route("/notifications", methods=["GET"])
def notifications():
    """
    Lấy thông báo của user hiện tại
    (Giả định có user_id từ session)
    """
    try:
        user_id = request.args.get("user_id", type=int)

        if not user_id:
            raise UnauthorizedError("Thiếu user_id")

        data = DashboardService.get_notifications(user_id)

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except UnauthorizedError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 📈 BIỂU ĐỒ CHẤM CÔNG (7 NGÀY)
# ==============================
@dashboard_bp.route("/attendance/chart", methods=["GET"])
def attendance_chart():
    """
    Data cho chart 7 ngày gần nhất
    """
    try:
        data = DashboardService.get_attendance_chart()
        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@dashboard_bp.route("/employee", methods=["GET"])
def employee_dashboard():
    # Giả sử bạn dùng Flask-Login hoặc JWT để lấy current_user
    # Ở đây tôi lấy tạm từ args theo cấu trúc file cũ của bạn
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return "Unauthorized", 401
    
    # Tìm employee tương ứng với user_id
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return render_template('employee/dashboard.html', employee=None)

    data = DashboardService.get_employee_dashboard_data(employee.id)
    return render_template('employee/dashboard.html', **data)