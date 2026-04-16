
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
│  │  ├─ employee.py
│  │  ├─ file_upload.py
│  │  ├─ history.py
│  │  ├─ leave.py
│  │  ├─ leave_usage.py
│  │  ├─ notification.py
│  │  ├─ otp.py
│  │  ├─ position.py
│  │  ├─ role.py
│  │  ├─ salary.py
│  │  ├─ system.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ modules
│  │  ├─ attendance
│  │  │  ├─ dto.py
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
│  │  │  ├─ auth.css
│  │  │  ├─ base.css
│  │  │  ├─ components
│  │  │  │  ├─ card.css
│  │  │  │  ├─ form.css
│  │  │  │  ├─ modal.css
│  │  │  │  ├─ table.css
│  │  │  │  └─ tabs.css
│  │  │  └─ employee
│  │  │     ├─ attendance.css
│  │  │     ├─ dashboard.css
│  │  │     ├─ employee.css
│  │  │     ├─ leave.css
│  │  │     ├─ profile.css
│  │  │     └─ salary.css
│  │  └─ js
│  │     ├─ api
│  │     │  ├─ attendance.api.js
│  │     │  ├─ auth.api.js
│  │     │  ├─ dashboard.api.js
│  │     │  ├─ employee.api.js
│  │     │  ├─ http.client.js
│  │     │  ├─ leave.api.js
│  │     │  ├─ notification.api.js
│  │     │  └─ salary.api.js
│  │     ├─ auth.js
│  │     ├─ base.js
│  │     ├─ components
│  │     │  ├─ dropdown.js
│  │     │  ├─ modal.js
│  │     │  ├─ table.js
│  │     │  ├─ tabs.js
│  │     │  └─ toast.js
│  │     ├─ core
│  │     │  ├─ router.js
│  │     │  ├─ socket.js
│  │     │  ├─ store.js
│  │     │  └─ utils.js
│  │     ├─ employee
│  │     │  ├─ attendance.js
│  │     │  ├─ complaint.js
│  │     │  ├─ dashboard
│  │     │  │  ├─ attendance-widget.js
│  │     │  │  ├─ notification-widget.js
│  │     │  │  └─ summary-card.js
│  │     │  ├─ dashboard.js
│  │     │  ├─ leave.js
│  │     │  ├─ notification.js
│  │     │  ├─ profile.js
│  │     │  └─ salary.js
│  │     ├─ socket
│  │     │  └─ notification.socket.js
│  │     ├─ store
│  │     │  ├─ attendance.store.js
│  │     │  ├─ auth.store.js
│  │     │  ├─ employee.store.js
│  │     │  └─ notification.store.js
│  │     └─ utils
│  │        ├─ format.js
│  │        ├─ time.js
│  │        └─ validator.js
│  ├─ templates
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
│  │  │  └─ search.html
│  │  ├─ home
│  │  │  └─ support.html
│  │  └─ layouts
│  │     ├─ base.html
│  │     ├─ header.html
│  │     └─ sidebar.html
│  ├─ utils
│  │  └─ time.py
│  └─ __init__.py
├─ create_db.py
├─ docker-compose.yml
├─ Dockerfile
├─ README.md
├─ requirements.txt
└─ run.py

```