from app import create_app
from app.extensions.db import db
from app.models.user import User
from app.models.role import Role
from app.models.employee import Employee
from app.models.department import Department
from app.models.leave_usage import EmployeeLeaveUsage
from datetime import date
app = create_app()

with app.app_context():
    print("🚀 Seeding data...")

    roles = ["ADMIN", "HR", "MANAGER", "EMPLOYEE"]
    role_map = {}

    for r in roles:
        role = Role.query.filter_by(name=r).first()
        if not role:
            role = Role(name=r)
            db.session.add(role)
            db.session.flush()
        role_map[r] = role

    users_seed = [
        {
            "username": "admin",
            "email": "duyannguyen100@gmail.com",
            "role": "ADMIN",
            "full_name": "Admin System",
            "phone": "0123456789",
        },
        {
            "username": "hr",
            "email": "an12ept@gmail.com",
            "role": "HR",
            "full_name": "HR User",
            "phone": "0123000000",
        },
        {
            "username": "manager",
            "email": "manager@test.com",
            "role": "MANAGER",
            "full_name": "Manager User",
            "phone": "0987654321",
        },
        {
            "username": "employee",
            "email": "employee@test.com",
            "role": "EMPLOYEE",
            "full_name": "Employee Test",
            "phone": "0999999999",
        },
        {
            "username": "employee_gmail",
            "email": "employee@gmail.com",
            "role": "EMPLOYEE",
            "full_name": "Employee Gmail",
            "phone": "0999999998",
        },
    ]
    employee_profiles = {}
    for u in users_seed:
        user = User.query.filter_by(username=u["username"]).first()

        if not user:
            user = User(
                username=u["username"],
                email=u["email"],
                role_id=role_map[u["role"]].id,
                is_active=True
            )
            user.set_password("123456")

            db.session.add(user)
            db.session.flush()

            employee = Employee(
                user_id=user.id,
                full_name=u["full_name"],
                phone=u["phone"],
                dob=date(2000, 1, 1), 
                gender="male",              
                hire_date=date(2024, 1, 1), 
                working_status="working"
            )

            db.session.add(employee)
            db.session.flush()
            employee_profiles[u["username"]] = employee
        else:
            user.email = u["email"]
            user.role_id = role_map[u["role"]].id
            employee = Employee.query.filter_by(user_id=user.id).first()
            if employee:
                employee_profiles[u["username"]] = employee

    manager_emp = employee_profiles.get("manager")
    employee_test = employee_profiles.get("employee")
    employee_gmail = employee_profiles.get("employee_gmail")
    if manager_emp:
        for subordinate in (employee_test, employee_gmail):
            if subordinate:
                subordinate.manager_id = manager_emp.id

    department = Department.query.filter_by(name="Phòng Kỹ thuật").first()
    if not department:
        department = Department(name="Phòng Kỹ thuật", description="Phòng kỹ thuật mặc định")
        db.session.add(department)
        db.session.flush()

    if manager_emp:
        department.manager_id = manager_emp.id
        manager_emp.department_id = department.id
    if employee_test:
        employee_test.department_id = department.id
    if employee_gmail:
        employee_gmail.department_id = department.id

    current_year = date.today().year
    for username in ("manager", "employee", "employee_gmail"):
        profile = employee_profiles.get(username)
        if not profile:
            continue
        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=profile.id,
            year=current_year,
        ).first()
        if not usage:
            db.session.add(
                EmployeeLeaveUsage(
                    employee_id=profile.id,
                    year=current_year,
                    total_days=12,
                    used_days=0,
                    remaining_days=12,
                )
            )
    db.session.commit()

    print("------ ACCOUNTS ------")
    print("ADMIN    : duyannguyen100@gmail.com / 123456")
    print("HR       : an12ept@gmail.com / 123456")
    print("MANAGER  : manager@test.com / 123456")
    print("EMPLOYEE : employee@test.com / 123456")