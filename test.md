@attendance_bp.route("/")
def attendance_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    from app.models import Employee
    employee = Employee.query.filter_by(user_id=user_id).first()
    simulated_now = request.args.get("simulated_now") \
        or session.get("simulated_now")
    if simulated_now:
        now = datetime.fromisoformat(
            simulated_now.replace("Z", "+00:00")
        )
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        session["simulated_now"] = simulated_now
    else:
        now = datetime.now()
    selected_month = (
        request.args.get("month", type=int)
        or now.month
    )
    selected_year = (
        request.args.get("year", type=int)
        or now.year
    )
    today = AttendanceService.get_today(
        employee.id,
        simulated_now
    )
    history = AttendanceService.get_history(
        employee.id,
        simulated_now,
        month=selected_month,
        year=selected_year,
    )
    for a in history:
        if a.check_in and a.check_out:
            a.calculated_hours = (
                AttendanceService.recalculate_hours(a)
            )
        else:
            a.calculated_hours = Decimal("0.00")

    return render_template(
        "employee/attendance.html",
        employee=employee,
        today=today,
        history=history,
        now=now,
        selected_month=selected_month,
        selected_year=selected_year,
    )

