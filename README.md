
```
HRM_TOTNGHIEP
├─ .dockerignore
├─ .postman
│  └─ resources.yaml
├─ app
│  ├─ blueprints.py
│  ├─ cli.py
│  ├─ common
│  │  ├─ errors.py
│  │  ├─ exceptions.py
│  │  ├─ responses.py
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
│  ├─ context_processors.py
│  ├─ errors.py
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
│  │  │  ├─ contract_routes.py
│  │  │  ├─ contract_service.py
│  │  │  ├─ dept_pos_routes.py
│  │  │  ├─ dept_pos_service.py
│  │  │  ├─ employee_routes.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ routes.py
│  │  │  ├─ user_routes.py
│  │  │  ├─ user_service.py
│  │  │  └─ __init__.py
│  │  ├─ attendance
│  │  │  ├─ attendance_calculation_routes.py
│  │  │  ├─ attendance_calculation_service.py
│  │  │  ├─ attendance_query_routes.py
│  │  │  ├─ attendance_query_service.py
│  │  │  ├─ attendance_routes.py
│  │  │  ├─ attendance_state_routes.py
│  │  │  ├─ attendance_state_service.py
│  │  │  ├─ attendance_workflow_routes.py
│  │  │  ├─ attendance_workflow_service.py
│  │  │  ├─ constants.py
│  │  │  ├─ dto.py
│  │  │  ├─ overtime_routes.py
│  │  │  ├─ overtime_service.py
│  │  │  ├─ qr_routes.py
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
│  │  │  └─ __init__.py
│  │  ├─ contract
│  │  │  ├─ admin_routes.py
│  │  │  ├─ admin_service.py
│  │  │  ├─ base_routes.py
│  │  │  ├─ base_service.py
│  │  │  ├─ employee_routes.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ hr_routes.py
│  │  │  ├─ hr_service.py
│  │  │  ├─ manager_routes.py
│  │  │  ├─ manager_service.py
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ history
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
│  │  │  └─ __init__.py
│  │  ├─ home
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ hr
│  │  │  ├─ routes.py
│  │  │  ├─ service.py
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
│  │  │  ├─ attendance_routes.py
│  │  │  ├─ attendance_service.py
│  │  │  ├─ employee_service.py
│  │  │  ├─ routes.py
│  │  │  └─ __init__.py
│  │  ├─ notification
│  │  │  ├─ dto.py
│  │  │  ├─ notification_service.py
│  │  │  ├─ routes.py
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
│  │  │  ├─ tax_rules.py
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
│  ├─ scheduler.py
│  ├─ static
│  │  ├─ css
│  │  │  ├─ admin.css
│  │  │  ├─ admin_1.css
│  │  │  ├─ attendance.css
│  │  │  ├─ contract.css
│  │  │  ├─ hr.css
│  │  │  ├─ leave.css
│  │  │  ├─ manager.css
│  │  │  ├─ notification.css
│  │  │  ├─ payroll.css
│  │  │  ├─ resignation.css
│  │  │  ├─ layouts.css
│  │  │  ├─ main.css
│  │  │  ├─ forms.css
│  │  │  ├─ responsive.css
│  │  │  └─ tables.css
│  │  ├─ favicon.ico
│  │  └─ js
│  │     ├─ main.js
│  │     ├─ modules
│  │     │  ├─ admin
│  │     │  │  ├─ admin.js
│  │     │  │  ├─ create_employee.js
│  │     │  │  ├─ employee_management.js
│  │     │  │  ├─ lock_unlock.js
│  │     │  │  ├─ metadata.js
│  │     │  │  ├─ reset_password.js
│  │     │  │  ├─ system_setting.js
│  │     │  │  └─ user_account.js
│  │     │  ├─ attendance.js
│  │     │  ├─ auth.js
│  │     │  ├─ contract
│  │     │  │  ├─ Contract_api.js
│  │     │  │  ├─ Contract_create.js
│  │     │  │  ├─ Contract_detail.js
│  │     │  │  ├─ Contract_list.js
│  │     │  │  ├─ Expiration_reminders.js
│  │     │  │  └─ Renewal_request.js
│  │     │  ├─ contract.js
│  │     │  ├─ hr
│  │     │  │  ├─ company_analytics.js
│  │     │  │  ├─ reports.js
│  │     │  │  └─ settings.js
│  │     │  ├─ leave.js
│  │     │  ├─ manager
│  │     │  │  ├─ team.js
│  │     │  │  ├─ team_analytics.js
│  │     │  │  └─ team_reports.js
│  │     │  ├─ notification
│  │     │  │  ├─ notification.js
│  │     │  │  └─ notification_detail.js
│  │     │  ├─ personnel.js
│  │     │  └─ resignation
│  │     │     ├─ resignation.js
│  │     │     └─ resignation_api.js
│  │     └─ payroll
│  │        ├─ analytics.js
│  │        ├─ complaint_form.js
│  │        ├─ finalize.js
│  │        ├─ generate.js
│  │        ├─ manager_approval.js
│  │        ├─ payroll_api.js
│  │        ├─ payroll_history.js
│  │        ├─ reports.js
│  │        └─ salary_slip.js
│  ├─ templates
│  │  ├─ base.html
│  │  ├─ components
│  │  │  ├─ footer.html
│  │  │  ├─ sidebar.html
│  │  │  ├─ sidebars
│  │  │  │  ├─ _sidebar_admin.html
│  │  │  │  ├─ _sidebar_common.html
│  │  │  │  ├─ _sidebar_employee.html
│  │  │  │  ├─ _sidebar_hr.html
│  │  │  │  └─ _sidebar_manager.html
│  │  │  └─ _navbar.html
│  │  ├─ layouts
│  │  │  ├─ auth_layout.html
│  │  │  └─ main_layout.html
│  │  └─ modules
│  │     ├─ admin
│  │     │  ├─ create_employee.html
│  │     │  ├─ employee_management.html
│  │     │  ├─ lock_unlock.html
│  │     │  ├─ metadata.html
│  │     │  ├─ reset_password.html
│  │     │  ├─ system_settings.html
│  │     │  └─ user_account.html
│  │     ├─ attendance
│  │     │  ├─ attendance.html
│  │     │  ├─ checkin_interface.html
│  │     │  ├─ history.html
│  │     │  ├─ manager_ot_approval.html
│  │     │  ├─ overtime_request.html
│  │     │  ├─ qr_scanner.html
│  │     │  ├─ summary.html
│  │     │  └─ team_attendance.html
│  │     ├─ auth
│  │     │  ├─ forgot_password.html
│  │     │  ├─ login.html
│  │     │  ├─ password_reset.html
│  │     │  └─ verify_otp.html
│  │     ├─ contract
│  │     │  ├─ create.html
│  │     │  ├─ detail.html
│  │     │  ├─ expiration_reminders.html
│  │     │  ├─ list.html
│  │     │  └─ renewal_request.html
│  │     ├─ home
│  │     │  └─ home.html
│  │     ├─ hr
│  │     │  ├─ company_analytics.html
│  │     │  ├─ reports.html
│  │     │  └─ settings.html
│  │     ├─ leave
│  │     │  ├─ department_report.html
│  │     │  ├─ leave_calendar.html
│  │     │  ├─ manager_approval.html
│  │     │  ├─ manager_pending.html
│  │     │  ├─ my_requests.html
│  │     │  ├─ request_detail.html
│  │     │  └─ request_form.html
│  │     ├─ manager
│  │     │  ├─ team.html
│  │     │  ├─ team_analytics.html
│  │     │  └─ team_reports.html
│  │     ├─ notifications
│  │     │  ├─ center.html
│  │     │  └─ detail.html
│  │     ├─ payroll
│  │     │  ├─ analytics.html
│  │     │  ├─ complaint_form.html
│  │     │  ├─ finalize.html
│  │     │  ├─ generate.html
│  │     │  ├─ history.html
│  │     │  ├─ manager_approval.html
│  │     │  ├─ reports.html
│  │     │  └─ salary_slip.html
│  │     ├─ personnel
│  │     │  ├─ activity_history.html
│  │     │  ├─ avatar_upload.html
│  │     │  ├─ change_password.html
│  │     │  ├─ dependents_list.html
│  │     │  ├─ dependent_form.html
│  │     │  ├─ edit_profile.html
│  │     │  ├─ employee_list.html
│  │     │  └─ profile.html
│  │     └─ resignation
│  │        ├─ detail.html
│  │        ├─ list_all.html
│  │        ├─ my_list.html
│  │        ├─ propose_form.html
│  │        └─ submit_form.html
│  ├─ utils
│  │  ├─ date_utils.py
│  │  ├─ holiday.py
│  │  ├─ time.py
│  │  ├─ ui_helpers.py
│  │  └─ upload_service.py
│  └─ __init__.py
├─ create_db.py
├─ CTTM.md
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
│  └─ globals
│     └─ workspace.globals.yaml
├─ README.md
├─ requirements.txt
├─ run.py
├─ seed_dev.py
├─ test.md
└─ tests
   └─ test_app_factory.py

```