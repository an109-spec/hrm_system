from __future__ import annotations
from flask import Response, jsonify, render_template, request, session, redirect, url_for
from datetime import date
import os
import uuid
from werkzeug.utils import secure_filename
from app.models.employee import Employee
from app.models.salary import Salary
from app.models.complaint import Complaint
from app.models.file_upload import FileUpload
from app.extensions.db import db
from . import manager_bp
from .service import ManagerService
from app.modules.employee.routes import _get_holiday_for_date
from app.utils.time import parse_simulated_time
from app.modules.employee.ess_service import EmployeeESSService

def _current_manager() -> Employee | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()

def _guard_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.url))
    return None

@manager_bp.route("/")
def dashboard_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/dashboard.html", employee=manager)


@manager_bp.route("/attendance")
def self_attendance_page():
    guard = _guard_login()
    if guard:
        return guard
    return redirect(url_for("employee.attendance"))


@manager_bp.route("/department-attendance")
def attendance_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    now = parse_simulated_time({})
    today_holiday = _get_holiday_for_date(now.date())
    return render_template(
        "manager/department_attendance.html",
        employee=manager,
        today_holiday=today_holiday,
    )

@manager_bp.route("/department-employees")
def department_employees_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/department_employees.html", employee=manager)

@manager_bp.route("/department-employees/summary", methods=["GET"])
def department_employee_summary_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_department_employee_summary(manager.id))


@manager_bp.route("/department-employees/list", methods=["GET"])
def department_employee_list_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_department_employee_list(manager.id, request.args))


@manager_bp.route("/department-employees/<int:employee_id>/detail", methods=["GET"])
def department_employee_detail_api(employee_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    try:
        return jsonify(ManagerService.get_department_employee_detail(manager.id, employee_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/department-employees/<int:employee_id>/proposal", methods=["POST"])
def department_employee_proposal_api(employee_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    proposal_type = (data.get("proposal_type") or "").strip().lower()
    reason = (data.get("reason") or "").strip()
    if proposal_type not in {"promotion", "transfer", "probation_conversion", "termination"}:
        return jsonify({"error": "proposal_type không hợp lệ"}), 400
    if not reason:
        return jsonify({"error": "Lý do đề xuất là bắt buộc"}), 400
    try:
        payload = ManagerService.get_department_employee_detail(manager.id, employee_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    from app.models.history import HistoryLog
    from app.models.notification import Notification
    from app.models.user import User
    from app.models.role import Role

    db.session.add(
        HistoryLog(
            employee_id=employee_id,
            action=f"MANAGER_{proposal_type.upper()}_PROPOSAL",
            entity_type="employee",
            entity_id=employee_id,
            description=reason,
            performed_by=manager.id,
        )
    )
    hr_users = User.query.join(Role, User.role_id == Role.id).filter(Role.role_name.in_(["hr", "admin"]), User.is_active.is_(True)).all()
    for user in hr_users:
        db.session.add(
            Notification(
                user_id=user.id,
                title="Đề xuất nhân sự mới từ Manager",
                content=f"{payload.get('full_name')} - {proposal_type}: {reason}",
                type="manager_proposal",
                link="/hr/employees",
            )
        )
    db.session.commit()
    return jsonify({"message": "Đã gửi đề xuất tới HR/Admin"})

@manager_bp.route("/leave-management")
def leave_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/leave.html", employee=manager)


@manager_bp.route("/contracts")
def contracts_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/contract.html", employee=manager)


@manager_bp.route("/payroll")
def payroll_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/payroll.html", employee=manager)


@manager_bp.route("/profile")
def profile_page():
    return redirect(url_for("employee.profile"))

@manager_bp.route("/profile/payslip")
def personal_payroll_page():
    guard = _guard_login()
    if guard:
        return guard
    manager = _current_manager()
    return render_template("manager/self_payroll.html", employee=manager, current_year=date.today().year)


@manager_bp.route("/notifications")
def notifications_page():
    return redirect(url_for("employee.notifications"))


@manager_bp.route("/dashboard", methods=["GET"])
def dashboard_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_dashboard(manager.id))


@manager_bp.route("/department-attendance/summary", methods=["GET"])
def department_attendance_summary_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_department_attendance_summary(manager.id, request.args))


@manager_bp.route("/department-attendance/list", methods=["GET"])
def attendance_today_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_department_attendance_rows(manager.id, request.args))


@manager_bp.route("/department-attendance/<int:employee_id>/detail", methods=["GET"])
def department_attendance_detail_api(employee_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    try:
        return jsonify(ManagerService.get_department_attendance_detail(manager.id, employee_id, request.args))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/department-attendance/<int:attendance_id>/abnormal-review", methods=["POST"])
def department_attendance_abnormal_review_api(attendance_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        result = ManagerService.review_abnormal_attendance(
            manager.id,
            attendance_id=attendance_id,
            action=data.get("action", ""),
            note=data.get("note"),
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/attendance/month", methods=["GET"])
def attendance_month_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year:
        return jsonify({"error": "month và year là bắt buộc"}), 400

    return jsonify(ManagerService.get_month_attendance_summary(manager.id, month, year))

@manager_bp.route("/overtime", methods=["GET"])
def overtime_list_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_overtime_requests(manager.id))


@manager_bp.route("/overtime/<int:overtime_id>/review", methods=["POST"])
def overtime_review_api(overtime_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        row = ManagerService.review_overtime(manager.id, overtime_id, data.get("action", ""), data.get("note"))
        return jsonify({"message": "processed", "id": row.id, "status": row.status})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400



@manager_bp.route("/leave", methods=["GET"])
def leave_list_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    return jsonify(ManagerService.get_leave_requests(manager.id, request.args))


@manager_bp.route("/leave/summary", methods=["GET"])
def leave_summary_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(ManagerService.get_leave_summary(manager.id, request.args))


@manager_bp.route("/leave/<int:leave_id>/detail", methods=["GET"])
def leave_detail_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    try:
        return jsonify(ManagerService.get_leave_detail(manager.id, leave_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@manager_bp.route("/leave/<int:leave_id>/approve", methods=["POST"])
def approve_leave_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        leave = ManagerService.approve_leave(manager.id, leave_id, data.get("note"))
        return jsonify({"message": "Đã chuyển đơn sang HR duyệt", "id": leave.id, "status": leave.status})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/leave/<int:leave_id>/reject", methods=["POST"])
def reject_leave_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        leave = ManagerService.reject_leave(manager.id, leave_id, data.get("note"))
        return jsonify({"message": "Đã từ chối đơn nghỉ phép", "id": leave.id, "status": leave.status})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/leave/<int:leave_id>/supplement", methods=["POST"])
def supplement_leave_api(leave_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        leave = ManagerService.request_leave_supplement(manager.id, leave_id, data.get("note", ""))
        return jsonify({"message": "Đã yêu cầu nhân viên bổ sung hồ sơ", "id": leave.id, "status": leave.status})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@manager_bp.route("/reminder", methods=["POST"])
def reminder_api():
    data = request.get_json(silent=True) or {}
    employee_ids = data.get("employee_ids") or []
    ManagerService.send_reminder(employee_ids, data.get("message"))
    return jsonify({"message": "Sent"})


@manager_bp.route("/contracts/expiring", methods=["GET"])
def contract_expiring_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    return jsonify(ManagerService.get_contract_expiring(manager.id))


@manager_bp.route("/contracts/overview", methods=["GET"])
def contracts_overview_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    return jsonify(
        ManagerService.get_department_contract_overview(
            manager.id,
            employee_name=request.args.get("employee_name"),
            employee_code=request.args.get("employee_code"),
            contract_type=request.args.get("contract_type"),
            contract_status=request.args.get("contract_status"),
            end_date_from=request.args.get("end_date_from"),
            end_date_to=request.args.get("end_date_to"),
            department=request.args.get("department"),
            position=request.args.get("position"),
        )
    )


@manager_bp.route("/contracts/<int:contract_id>", methods=["GET"])
def contract_detail_manager_api(contract_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    try:
        return jsonify(ManagerService.get_contract_detail_for_manager(manager.id, contract_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/contracts/<int:contract_id>/proposals", methods=["POST"])
def contract_proposal_manager_api(contract_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(
            ManagerService.create_contract_proposal(
                manager.id,
                contract_id=contract_id,
                proposal_type=data.get("proposal_type", ""),
                reason=data.get("reason", ""),
                proposed_date=data.get("proposed_date"),
                proposed_duration_months=data.get("proposed_duration_months"),
                professional_note=data.get("professional_note"),
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/contracts/<int:contract_id>/review-confirm", methods=["POST"])
def contract_review_confirm_manager_api(contract_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(ManagerService.confirm_contract_review(manager.id, contract_id, data.get("note")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/salary", methods=["GET"])
def salary_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year:
        return jsonify({"error": "month và year là bắt buộc"}), 400


    return jsonify(ManagerService.get_department_salary(manager.id, month, year))

@manager_bp.route("/payroll/department", methods=["GET"])
def department_payroll_review_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year:
        return jsonify({"error": "month và year là bắt buộc"}), 400
    payload = ManagerService.get_department_payroll_review(
        manager.id,
        month,
        year,
        employee_name=request.args.get("employee_name"),
        employee_code=request.args.get("employee_code"),
        status=request.args.get("status"),
        employment_type=request.args.get("employment_type"),
        position=request.args.get("position"),
    )
    return jsonify(payload)


@manager_bp.route("/payroll/department/<int:salary_id>", methods=["GET"])
def department_payroll_detail_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    try:
        return jsonify(ManagerService.get_department_payroll_detail(manager.id, salary_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/payroll/department/<int:salary_id>/confirm", methods=["POST"])
def department_payroll_confirm_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(ManagerService.confirm_department_payroll(manager.id, salary_id, data.get("note")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/payroll/department/<int:salary_id>/feedback", methods=["POST"])
def department_payroll_feedback_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(
            ManagerService.send_payroll_feedback(
                manager.id,
                salary_id,
                data.get("issue_type", "salary_data_error"),
                data.get("description", ""),
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@manager_bp.route("/payroll/complaints", methods=["GET"])
def department_payroll_complaints_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    subordinate_ids = [x.id for x in ManagerService._get_subordinates(manager.id)]
    rows = Complaint.query.filter(Complaint.employee_id.in_(subordinate_ids), Complaint.salary_id.isnot(None), Complaint.is_deleted.is_(False)).order_by(Complaint.created_at.desc()).all() if subordinate_ids else []
    data = []
    for row in rows:
        files = FileUpload.query.filter_by(complaint_id=row.id, is_deleted=False).all()
        data.append({
            "id": row.id,
            "salary_id": row.salary_id,
            "employee_name": row.employee.full_name if row.employee else "--",
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "attachments": [{"name": f.file_name, "url": f.file_url} for f in files],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return jsonify(data)


@manager_bp.route("/payroll/complaints/<int:complaint_id>/approve", methods=["POST"])
def manager_approve_complaint_api(complaint_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    row = Complaint.query.get(complaint_id)
    if not row:
        return jsonify({"error": "Không tìm thấy complaint"}), 404
    row.status = "in_progress"
    row.handled_by = manager.id
    db.session.commit()
    return jsonify({"message": "Đã chuyển complaint sang HR xử lý", "status": row.status})


@manager_bp.route("/payroll/complaints/<int:complaint_id>/reject", methods=["POST"])
def manager_reject_complaint_api(complaint_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    row = Complaint.query.get(complaint_id)
    if not row:
        return jsonify({"error": "Không tìm thấy complaint"}), 404
    row.status = "rejected"
    row.handled_by = manager.id
    db.session.commit()
    return jsonify({"message": "Đã từ chối complaint không hợp lệ", "status": row.status})


@manager_bp.route("/self-payroll/history", methods=["GET"])
def self_payroll_history_api():
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    year = request.args.get("year", date.today().year, type=int)
    rows = Salary.query.filter_by(employee_id=manager.id, year=year, is_deleted=False).order_by(Salary.month.desc()).all()
    return jsonify([
        {
            "id": r.id,
            "month": r.month,
            "year": r.year,
            "basic_salary": float(r.basic_salary or 0),
            "allowance": float(r.total_allowance or 0),
            "overtime": 0,
            "deduction": float(r.penalty or 0),
            "insurance": ManagerService._tax_and_insurance(r)[0],
            "tax": ManagerService._tax_and_insurance(r)[1],
            "net_salary": float(r.net_salary or 0),
            "status": r.status,
            "status_label": ManagerService._payroll_status_label(r.status),
            "payment_date": r.updated_at.strftime("%d/%m/%Y") if r.updated_at else None,
        } for r in rows
    ])


@manager_bp.route("/self-payroll/<int:salary_id>", methods=["GET"])
def self_payroll_detail_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    row = Salary.query.filter_by(id=salary_id, employee_id=manager.id, is_deleted=False).first()
    if not row:
        return jsonify({"error": "Not found"}), 404
    insurance, tax = ManagerService._tax_and_insurance(row)
    dependents = EmployeeESSService.list_dependents(session.get("user_id"))
    return jsonify({
        "id": row.id,
        "month": row.month,
        "year": row.year,
        "basic_salary": float(row.basic_salary or 0),
        "lunch_allowance": float(row.total_allowance or 0) * 0.5,
        "responsibility_allowance": float(row.total_allowance or 0) * 0.5,
        "bonus": float(row.bonus or 0),
        "overtime": 0,
        "deduction": float(row.penalty or 0),
        "insurance": insurance,
        "tax": tax,
        "number_of_dependents": dependents.get("number_of_dependents", 0),
        "family_deduction": 11_000_000 + (dependents.get("number_of_dependents", 0) * 4_400_000),
        "net_salary": float(row.net_salary or 0),
        "status_label": ManagerService._payroll_status_label(row.status),
    })


@manager_bp.route("/self-payroll/<int:salary_id>/pdf", methods=["GET"])
def self_payroll_pdf_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    row = Salary.query.filter_by(id=salary_id, employee_id=manager.id, is_deleted=False).first()
    if not row:
        return jsonify({"error": "Not found"}), 404
    content = f"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 180 >>
stream
BT
/F1 16 Tf
50 780 Td (PAYSLIP {row.month:02d}/{row.year}) Tj
0 -30 Td /F1 12 Tf (Employee: {manager.full_name}) Tj
0 -20 Td (Basic: {float(row.basic_salary or 0):,.0f} VND) Tj
0 -20 Td (Allowance: {float(row.total_allowance or 0):,.0f} VND) Tj
0 -20 Td (Net: {float(row.net_salary or 0):,.0f} VND) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000243 00000 n 
0000000473 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
543
%%EOF"""
    return Response(content.encode("latin-1", "ignore"), mimetype="application/pdf", headers={"Content-Disposition": f"attachment; filename=payslip_{row.month}_{row.year}.pdf"})


@manager_bp.route("/self-payroll/<int:salary_id>/complaint", methods=["POST"])
def self_payroll_complaint_api(salary_id: int):
    manager = _current_manager()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    row = Salary.query.filter_by(id=salary_id, employee_id=manager.id, is_deleted=False).first()
    if not row:
        return jsonify({"error": "Not found"}), 404
    issue_type = request.form.get("issue_type", "other")
    description = (request.form.get("description") or "").strip()
    if not description:
        return jsonify({"error": "Nội dung khiếu nại là bắt buộc"}), 400
    complaint = Complaint(employee_id=manager.id, salary_id=row.id, type=issue_type, title=f"Khiếu nại phiếu lương #{row.id}", description=description, status="pending")
    db.session.add(complaint)
    db.session.flush()
    attachment = request.files.get("attachment")
    if attachment and attachment.filename:
        save_dir = os.path.join("app", "static", "uploads", "complaint")
        os.makedirs(save_dir, exist_ok=True)
        filename = secure_filename(attachment.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        attachment.save(os.path.join(save_dir, unique_name))
        db.session.add(FileUpload(file_name=filename, file_url=f"/static/uploads/complaint/{unique_name}", file_type="attachment", uploaded_by=session.get("user_id"), complaint_id=complaint.id))
    db.session.commit()
    return jsonify({"message": "Đã gửi khiếu nại", "complaint_id": complaint.id})


@manager_bp.route("/self/dependents", methods=["GET"])
def manager_dependents_list_api():
    return jsonify(EmployeeESSService.list_dependents(session.get("user_id")))


@manager_bp.route("/self/dependents", methods=["POST"])
def manager_dependents_create_api():
    return jsonify(EmployeeESSService.create_dependent(session.get("user_id"), request.get_json(silent=True) or {}, actor_user_id=session.get("user_id")))


@manager_bp.route("/self/dependents/<int:dependent_id>", methods=["PUT"])
def manager_dependents_update_api(dependent_id: int):
    return jsonify(EmployeeESSService.update_dependent(session.get("user_id"), dependent_id, request.get_json(silent=True) or {}, actor_user_id=session.get("user_id")))


@manager_bp.route("/self/dependents/<int:dependent_id>", methods=["DELETE"])
def manager_dependents_delete_api(dependent_id: int):
    return jsonify(EmployeeESSService.delete_dependent(session.get("user_id"), dependent_id, actor_user_id=session.get("user_id")))