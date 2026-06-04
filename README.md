
```
HRM_TOTNGHIEP
├─ .dockerignore
├─ .postman
│  └─ resources.yaml
├─ app
│  ├─ cli.py
│  ├─ common
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
│  ├─ constants
│  │  ├─ attendance.py
│  │  ├─ common.py
│  │  ├─ contract.py
│  │  ├─ dependent.py
│  │  ├─ employee.py
│  │  ├─ holidays.py
│  │  ├─ leave.py
│  │  ├─ overtime.py
│  │  ├─ payroll.py
│  │  ├─ resignation.py
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
│  │  ├─ contract_proposal.py
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
│  │  ├─ resignation.py
│  │  ├─ role.py
│  │  ├─ salary.py
│  │  ├─ system.py
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ modules
│  │  ├─ admin
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ attendance
│  │  │  ├─ attendance_calculation_service.py
│  │  │  ├─ attendance_query_service.py
│  │  │  ├─ attendance_state_service.py
│  │  │  ├─ attendance_workflow_service.py
│  │  │  ├─ constants.py
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
│  │  ├─ dashboard
│  │  │  ├─ dto.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ history
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ home
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ hr
│  │  │  ├─ contract_service.py
│  │  │  ├─ dto.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ jobs
│  │  │  ├─ attendance_job.py
│  │  │  ├─ notification_job.py
│  │  │  └─ __init__.py
│  │  ├─ leave
│  │  │  ├─ dto.py
│  │  │  ├─ holiday_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  ├─ validators.py
│  │  │  └─ __init__.py
│  │  ├─ manager
│  │  │  ├─ attendance_service.py
│  │  │  ├─ dto.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ notification
│  │  │  ├─ dto.py
│  │  │  ├─ notification_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ payroll
│  │  │  ├─ admin_routes.py
│  │  │  ├─ admin_service.py
│  │  │  ├─ base_service.py
│  │  │  ├─ employee_routes.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ hr_routes.py
│  │  │  ├─ hr_service.py
│  │  │  ├─ manager_routes.py
│  │  │  ├─ manager_service.py
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ personnel
│  │  │  ├─ dependent_service.py
│  │  │  ├─ dto.py
│  │  │  ├─ profile_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ validators.py
│  │  │  └─ __init__.py
│  │  └─ resignation
│  │     ├─ resignation_service.py
│  │     ├─ routes.py
│  │     └─ __init__.py
│  ├─ static
│  │  ├─ css
│  │  │  ├─ admin
│  │  │  │  ├─ admin.css
│  │  │  │  └─ profile.css
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
│  │  │  │  ├─ admin.js
│  │  │  │  ├─ profile.js
│  │  │  │  └─ salary_policy.js
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
│  │  │  │  ├─ payslip.js
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
│  │  │  │  ├─ payroll.js
│  │  │  │  └─ self_payroll.js
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
│  │  │  ├─ salary_config.html
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
│  │     ├─ department_attendance.html
│  │     ├─ department_employees.html
│  │     ├─ leave.html
│  │     ├─ payroll.html
│  │     └─ self_payroll.html
│  ├─ utils
│  │  ├─ date_utils.py
│  │  ├─ holiday.py
│  │  ├─ time.py
│  │  ├─ ui_helpers.py
│  │  └─ upload_service.py
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
│     ├─ 0d62fdb8db22_remove_manager_fields_and_update_status_.py
│     ├─ 0e8242241019_add_address_fields_to_employee.py
│     ├─ 1f2e3d4c5b6a_expand_shift_status_length.py
│     ├─ 37f52a6ac6b8_your_message.py
│     ├─ 4f2b6f9f8a1a_add_overtime_columns_to_attendance.py
│     ├─ 779ee223a0da_merge_multiple_heads.py
│     ├─ 7c3b2a1f9d10_add_holiday_ot_fields_to_overtime_request.py
│     ├─ 847dd96147c7_sync_employee_relationships.py
│     ├─ 8ef0316da466_update_file_upload_model_and_enum.py
│     ├─ 9b2d7f7b4c10_add_leave_extended_fields_and_holidays.py
│     ├─ a1b2c3d4e5f6_expand_leave_status_workflow.py
│     ├─ aa11bb22cc33_extend_overtime_request_audit_fields.py
│     ├─ b7c8d9e0f1a2_add_resignation_offboarding_flow.py
│     ├─ bbccddeeff00_merge_overtime_and_leave_heads.py
│     ├─ c3d9f7a1b2e4_add_attendance_required_flag_to_employee.py
│     ├─ c6cb2272e6bb_sync_complaint_relationships.py
│     ├─ d4e5f6a7b8c9_fix_legacy_working_status_value.py
│     ├─ d4ed9284e08b_sync_payroll_complaint_relationships.py
│     ├─ def57f8ad206_add_employee_relationships.py
│     ├─ e6f7a8b9c0d1_fix_postgres_leave_status_enum_values.py
│     ├─ eb82bff93566_sync_employee_relationships.py
│     ├─ ed4b229451af_upgrade_salary_model_to_store_static_.py
│     ├─ f1a2b3c4d5e6_add_ess_overtime_and_complaint_columns.py
│     └─ xxxx_add_enterprise_attendance_flow.py
├─ postman
│  ├─ collections
│  ├─ environments
│  ├─ flows
│  ├─ globals
│  │  └─ workspace.globals.yaml
│  ├─ mocks
│  └─ specs
├─ README.md
├─ requirements.txt
├─ run.py
├─ seed_dev.py
└─ test.md

```