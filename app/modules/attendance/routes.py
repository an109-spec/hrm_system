from flask import render_template, request, session, redirect, url_for, jsonify
from datetime import datetime

from . import attendance_bp
from .service import AttendanceService
from app.common.exceptions import ValidationError

# =============================
# PAGE
# =============================
@attendance_bp.route("/")
def attendance_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    from app.models import Employee

    employee = Employee.query.filter_by(user_id=user_id).first()

    today = AttendanceService.get_today(employee.id)
    history = AttendanceService.get_history(employee.id)

    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=datetime.now()
    )


@attendance_bp.route("/check", methods=["POST"])
def check_in_out():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Bạn chưa đăng nhập"}), 401
    data = request.get_json() or {}
    qr_text = str(data.get("qr_text", "")).strip()
    sim_time = data.get("sim_time")
    simulated_now = data.get("simulated_now")

    if not qr_text:
        return jsonify({"error": "Không đọc được dữ liệu QR hợp lệ."}), 400

    if not sim_time and simulated_now:
        try:
            sim_dt = datetime.fromisoformat(simulated_now)
            sim_time = sim_dt.strftime("%H:%M:%S")
        except ValueError:
            return jsonify({"error": "Thời gian mô phỏng không hợp lệ."}), 400

    from app.models import Employee
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return jsonify({"error": "Không tìm thấy nhân viên"}), 404

    today_record = AttendanceService.get_today(employee.id)
    expected_action = "check_in" if not today_record else ("done" if today_record.check_out else "check_out")
    try:
        # Truyền sim_time vào service
        result = AttendanceService.check_in_out(employee.id, sim_time)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    response = {
        "status": expected_action,
        "message": result.get("message", "Chấm công thành công")
    }
    if expected_action == "check_in" and "muộn" in response["message"]:
        response["warning"] = "Bạn đã muộn hơn 10 phút. Thời gian tính công sẽ bắt đầu từ 09:00"
    return jsonify(response)