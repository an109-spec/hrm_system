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

    today = AttendanceService.get_today(employee.id, request.args.get("simulated_now"))
    history = AttendanceService.get_history(employee.id)

    for a in history:
        if a.check_in and a.check_out:
            a.working_hours = AttendanceService.recalculate_hours(a.check_in, a.check_out)

    simulated_now = request.args.get("simulated_now")

    if simulated_now:
        now = datetime.fromisoformat(simulated_now.replace("Z", "+00:00"))
    else:
        now = datetime.now()

    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now
    )


@attendance_bp.route("/check", methods=["POST"])
def check_in_out():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Bạn chưa đăng nhập"}), 401
    data = request.get_json() or {}
    qr_text = str(data.get("qr_text", "")).strip()
    simulated_now = data.get("simulated_now")

    if not qr_text:
        return jsonify({"error": "Không đọc được dữ liệu QR hợp lệ."}), 400

    if not simulated_now:
        return jsonify({"error": "Thiếu simulated time"}), 400

    from app.models import Employee
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return jsonify({"error": "Không tìm thấy nhân viên"}), 404

    today_record = AttendanceService.get_today(employee.id, simulated_now)
    expected_action = "check_in" if not today_record else ("done" if today_record.check_out else "check_out")
    try:
        result = AttendanceService.check_in_out(employee.id, simulated_now)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    response = {
        "status": expected_action,

        "message": result.get("message", "Chấm công thành công")
    }
    if expected_action == "check_in" and "muộn" in response["message"]:
        response["warning"] = "Bạn đã muộn hơn 10 phút. Thời gian tính công sẽ bắt đầu từ 09:00"
    return jsonify(response)