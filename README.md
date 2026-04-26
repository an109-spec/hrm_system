
```
HRM_TOTNGHIEP
├─ .dockerignore
├─ app
│  ├─ cli.py
│  ├─ common
│  │  ├─ constants.py
│  │  ├─ exceptions.py
│  │  ├─ security
│  │  │  ├─ decorators.py
│  │  │  ├─ otp.py
│  │  │  ├─ password.py
│  │  │  ├─ permissions.py
│  │  │  └─ __init__.py
│  │  └─ __init__.py
│  ├─ config
│  │  ├─ config.py
│  │  └─ __init__.py
│  ├─ extensions
│  │  ├─ db.py
│  │  ├─ jwt.py
│  │  ├─ mail.py
│  │  ├─ socketio.py
│  │  └─ __init__.py
│  ├─ models
│  │  ├─ allowance.py
│  │  ├─ attendance.py
│  │  ├─ base.py
│  │  ├─ complaint.py
│  │  ├─ contract.py
│  │  ├─ department.py
│  │  ├─ dependent.py
│  │  ├─ employee.py
│  │  ├─ file_upload.py
│  │  ├─ history.py
│  │  ├─ leave.py
│  │  ├─ leave_usage.py
│  │  ├─ notification.py
│  │  ├─ otp.py
│  │  ├─ overtime_request.py
│  │  ├─ position.py
│  │  ├─ role.py
│  │  ├─ salary.py
│  │  ├─ system.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ modules
│  │  ├─ admin
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ attendance
│  │  │  ├─ dto.py
│  │  │  ├─ overtime_service.py
│  │  │  ├─ qr_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ auth
│  │  │  ├─ dto.py
│  │  │  ├─ mail_service.py
│  │  │  ├─ otp_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  ├─ sms_service.py
│  │  │  ├─ validators.py
│  │  │  └─ __init__.py
│  │  ├─ complaint
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ dashboard
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ employee
│  │  │  ├─ dto.py
│  │  │  ├─ ess_service.py
│  │  │  ├─ profile_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  ├─ validators.py
│  │  │  └─ __init__.py
│  │  ├─ history
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ home
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ hr
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ jobs
│  │  │  ├─ attendance_job.py
│  │  │  ├─ notification_job.py
│  │  │  └─ __init__.py
│  │  ├─ leave
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  ├─ validators.py
│  │  │  └─ __init__.py
│  │  ├─ leave_type
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ manager
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ notification
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ salary
│  │  │  ├─ complaint_service.py
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  └─ upload
│  │     ├─ routes.py
│  │     ├─ service.py
│  │     └─ __init__.py
│  ├─ static
│  │  ├─ css
│  │  │  ├─ admin
│  │  │  │  └─ admin.css
│  │  │  ├─ auth.css
│  │  │  ├─ base.css
│  │  │  ├─ components
│  │  │  │  ├─ card.css
│  │  │  │  ├─ form.css
│  │  │  │  ├─ modal.css
│  │  │  │  ├─ table.css
│  │  │  │  └─ tabs.css
│  │  │  ├─ employee
│  │  │  │  ├─ attendance.css
│  │  │  │  ├─ dashboard.css
│  │  │  │  ├─ employee.css
│  │  │  │  ├─ leave.css
│  │  │  │  ├─ profile.css
│  │  │  │  ├─ salary.css
│  │  │  │  └─ staff_profile.css
│  │  │  ├─ hr
│  │  │  │  ├─ attendance.css
│  │  │  │  ├─ contracts.css
│  │  │  │  ├─ employees.css
│  │  │  │  ├─ payroll.css
│  │  │  │  └─ profile.css
│  │  │  ├─ manager
│  │  │  │  ├─ attendance.css
│  │  │  │  ├─ contract.css
│  │  │  │  ├─ dashboard.css
│  │  │  │  ├─ department_employees.css
│  │  │  │  ├─ leave.css
│  │  │  │  └─ payroll.css
│  │  │  └─ sidebar.css
│  │  ├─ js
│  │  │  ├─ admin
│  │  │  │  └─ admin.js
│  │  │  ├─ api
│  │  │  │  ├─ attendance.api.js
│  │  │  │  ├─ auth.api.js
│  │  │  │  ├─ dashboard.api.js
│  │  │  │  ├─ employee.api.js
│  │  │  │  ├─ http.client.js
│  │  │  │  ├─ leave.api.js
│  │  │  │  ├─ manager.api.js
│  │  │  │  ├─ notification.api.js
│  │  │  │  └─ salary.api.js
│  │  │  ├─ auth.js
│  │  │  ├─ base.js
│  │  │  ├─ components
│  │  │  │  ├─ dropdown.js
│  │  │  │  ├─ modal.js
│  │  │  │  ├─ table.js
│  │  │  │  ├─ tabs.js
│  │  │  │  └─ toast.js
│  │  │  ├─ core
│  │  │  │  ├─ router.js
│  │  │  │  ├─ socket.js
│  │  │  │  ├─ store.js
│  │  │  │  └─ utils.js
│  │  │  ├─ employee
│  │  │  │  ├─ attendance.js
│  │  │  │  ├─ complaint.js
│  │  │  │  ├─ dashboard
│  │  │  │  │  ├─ attendance-widget.js
│  │  │  │  │  ├─ notification-widget.js
│  │  │  │  │  └─ summary-card.js
│  │  │  │  ├─ dashboard.js
│  │  │  │  ├─ leave.js
│  │  │  │  ├─ notification.js
│  │  │  │  ├─ profile.js
│  │  │  │  ├─ qr-attendance.shared.js
│  │  │  │  ├─ salary.js
│  │  │  │  └─ staff_profile.js
│  │  │  ├─ hr
│  │  │  │  ├─ attendance.js
│  │  │  │  ├─ contracts.js
│  │  │  │  ├─ employees.js
│  │  │  │  ├─ payroll.js
│  │  │  │  └─ profile.js
│  │  │  ├─ manager
│  │  │  │  ├─ attendance.js
│  │  │  │  ├─ contract.js
│  │  │  │  ├─ dashboard.js
│  │  │  │  ├─ department_employees.js
│  │  │  │  ├─ leave.js
│  │  │  │  └─ payroll.js
│  │  │  ├─ socket
│  │  │  │  └─ notification.socket.js
│  │  │  ├─ store
│  │  │  │  ├─ attendance.store.js
│  │  │  │  ├─ auth.store.js
│  │  │  │  ├─ employee.store.js
│  │  │  │  └─ notification.store.js
│  │  │  └─ utils
│  │  │     ├─ format.js
│  │  │     ├─ time.js
│  │  │     └─ validator.js
│  │  └─ uploads
│  │     ├─ 3ac0031867ef212e4c2329fe9028fca1.jpg
│  │     ├─ 7a8211a2161799550aa868aaab6d5c84.jpg
│  │     ├─ 8108d6c72ad345dbb9fdb11d6c7ac1ef.jpg
│  │     ├─ bf88d3f5c61052a917a29560582d3b081.jpg
│  │     └─ leave
│  │        └─ sick
│  │           └─ 1667c583850345b798fe946ae6a292f6_textbook_kana_all.pdf
│  ├─ templates
│  │  ├─ admin
│  │  │  ├─ attendance.html
│  │  │  ├─ base_admin.html
│  │  │  ├─ dashboard.html
│  │  │  ├─ departments.html
│  │  │  ├─ employees.html
│  │  │  ├─ positions.html
│  │  │  ├─ profile.html
│  │  │  ├─ salary.html
│  │  │  └─ staff_profile.html
│  │  ├─ auth
│  │  │  ├─ forgot_password.html
│  │  │  ├─ login.html
│  │  │  ├─ register.html
│  │  │  ├─ reset_password.html
│  │  │  └─ verify_otp.html
│  │  ├─ employee
│  │  │  ├─ attendance.html
│  │  │  ├─ complaint_modal.html
│  │  │  ├─ dashboard.html
│  │  │  ├─ leave.html
│  │  │  ├─ notifications.html
│  │  │  ├─ payslip.html
│  │  │  ├─ profile.html
│  │  │  ├─ search.html
│  │  │  └─ staff_profile.html
│  │  ├─ home
│  │  │  └─ support.html
│  │  ├─ hr
│  │  │  ├─ attendance.html
│  │  │  ├─ contracts.html
│  │  │  ├─ employees.html
│  │  │  ├─ payroll.html
│  │  │  └─ profile.html
│  │  ├─ layouts
│  │  │  ├─ base.html
│  │  │  ├─ header.html
│  │  │  └─ sidebar.html
│  │  └─ manager
│  │     ├─ attendance.html
│  │     ├─ contract.html
│  │     ├─ dashboard.html
│  │     ├─ department_employees.html
│  │     ├─ leave.html
│  │     └─ payroll.html
│  ├─ utils
│  │  └─ time.py
│  └─ __init__.py
├─ create_db.py
├─ docker-compose.yml
├─ Dockerfile
├─ migrations
│  ├─ alembic.ini
│  ├─ env.py
│  ├─ README
│  ├─ script.py.mako
│  └─ versions
│     ├─ 0e8242241019_add_address_fields_to_employee.py
│     ├─ 4f2b6f9f8a1a_add_overtime_columns_to_attendance.py
│     ├─ 9b2d7f7b4c10_add_leave_extended_fields_and_holidays.py
│     ├─ c3d9f7a1b2e4_add_attendance_required_flag_to_employee.py
│     └─ f1a2b3c4d5e6_add_ess_overtime_and_complaint_columns.py
├─ README.md
├─ requirements.txt
├─ run.py
└─ seed_dev.py

```