from app import create_app
from app.extensions.db import db
from app.models.user import User
from app.models.role import Role
from app.models.employee import Employee
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
            "full_name": "Employee User",
            "phone": "0999999999",
        },
    ]

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
        else:
            user.email = u["email"]
            user.role_id = role_map[u["role"]].id

    db.session.commit()

    print("------ ACCOUNTS ------")
    print("ADMIN    : duyannguyen100@gmail.com / 123456")
    print("HR       : an12ept@gmail.com / 123456")
    print("MANAGER  : manager@test.com / 123456")
    print("EMPLOYEE : employee@test.com / 123456")