app/
│
├─ 📁 templates/                        [Jinja2 Templates]
│  ├─ base.html                         [Base layout - ALL pages extend]
│  ├─ macros.html                       [Reusable macro components]
│  │
│  ├─ 📁 layouts/
│  │  ├─ main_layout.html               [Main layout (header, sidebar, footer)]
│  │  ├─ auth_layout.html               [Auth layout (minimal, no sidebar)]
│  │  └─ blank_layout.html              [Blank layout (error pages)]
│  │
│  ├─ 📁 modules/                       [Feature modules by role]
│  │  │
│  │  ├─ 📁 auth/
│  │  │  ├─ login.html                  [Login page]
│  │  │  ├─ forgot_password.html        [Forgot password page]
│  │  │  ├─ verify_otp.html             [OTP verification]
│  │  │  └─ password_reset.html         [Password reset page]
│  │  │
│  │  ├─ 📁 dashboard/
│  │  │  ├─ employee_dashboard.html     [Employee dashboard]
│  │  │  ├─ manager_dashboard.html      [Manager dashboard]
│  │  │  ├─ hr_dashboard.html           [HR dashboard]
│  │  │  ├─ admin_dashboard.html        [Admin dashboard]
│  │  │  └─ 📁 widgets/                 [Dashboard widgets]
│  │  │     ├─ stats_widget.html
│  │  │     ├─ attendance_widget.html
│  │  │     ├─ leave_widget.html
│  │  │     └─ quick_actions.html
│  │  │
│  │  ├─ 📁 personnel/
│  │  │  ├─ profile.html                [View profile]
│  │  │  ├─ edit_profile.html           [Edit profile]
│  │  │  ├─ change_password.html        [Change password]
│  │  │  ├─ avatar_upload.html          [Avatar upload]
│  │  │  ├─ dependents_list.html        [Dependents list]
│  │  │  ├─ dependent_form.html         [Add/Edit dependent]
│  │  │  ├─ activity_history.html       [Activity history]
│  │  │  └─ employee_list.html          [Employee list (HR/Admin)]
│  │  │
│  │  ├─ 📁 leave/
│  │  │  ├─ my_requests.html            [My leave requests]
│  │  │  ├─ request_form.html           [Create leave request]
│  │  │  ├─ request_detail.html         [View request details]
│  │  │  ├─ manager_pending.html        [Manager: pending list]
│  │  │  ├─ manager_approval.html       [Manager: approval view]
│  │  │  ├─ leave_calendar.html         [Leave calendar]
│  │  │  └─ department_report.html      [Dept leave report]
│  │  │
│  │  ├─ 📁 attendance/
│  │  │  ├─ attendance.html             [Main attendance page]
│  │  │  ├─ checkin_interface.html      [Check-in/out interface]
│  │  │  ├─ history.html                [Attendance history]
│  │  │  ├─ summary.html                [Daily/Monthly summary]
│  │  │  ├─ overtime_request.html       [Overtime request form]
│  │  │  ├─ manager_ot_approval.html    [Manager OT approval]
│  │  │  ├─ team_attendance.html        [Manager: team attendance]
│  │  │  └─ qr_scanner.html             [QR scanner page]
│  │  │
│  │  ├─ 📁 contract/
│  │  │  ├─ list.html                   [Contract list]
│  │  │  ├─ detail.html                 [Contract details]
│  │  │  ├─ create.html                 [Create contract (Admin)]
│  │  │  ├─ renewal_request.html        [Renewal request (Manager)]
│  │  │  └─ expiration_reminders.html   [Expiring contracts]
│  │  │
│  │  ├─ 📁 payroll/
│  │  │  ├─ history.html                [Salary history]
│  │  │  ├─ salary_slip.html            [View salary slip]
│  │  │  ├─ complaint_form.html         [File complaint]
│  │  │  ├─ manager_approval.html       [Manager approval]
│  │  │  ├─ generate.html               [HR: Generate payroll]
│  │  │  ├─ finalize.html               [HR: Finalize payroll]
│  │  │  ├─ analytics.html              [Analytics/Reports]
│  │  │  └─ reports.html                [Detailed reports]
│  │  │
│  │  ├─ 📁 admin/
│  │  │  ├─ employee_management.html    [Employee list]
│  │  │  ├─ create_employee.html        [Create employee]
│  │  │  ├─ user_account.html           [User account management]
│  │  │  ├─ reset_password.html         [Reset password]
│  │  │  ├─ lock_unlock.html            [Lock/Unlock account]
│  │  │  ├─ metadata.html               [Dept, position, roles]
│  │  │  └─ system_settings.html        [System settings]
│  │  │
│  │  ├─ 📁 manager/
│  │  │  ├─ team.html                   [Team member list]
│  │  │  ├─ team_analytics.html         [Team analytics]
│  │  │  └─ team_reports.html           [Team reports]
│  │  │
│  │  ├─ 📁 hr/
│  │  │  ├─ company_analytics.html      [Company analytics]
│  │  │  ├─ reports.html                [HR reports]
│  │  │  └─ settings.html               [HR settings]
│  │  │
│  │  ├─ 📁 notifications/
│  │  │  ├─ center.html                 [Notification center]
│  │  │  └─ detail.html                 [Notification detail]
│  │  │
│  │  └─ 📁 error/
│  │     ├─ 404.html                    [404 page]
│  │     ├─ 403.html                    [403 Forbidden]
│  │     └─ 500.html                    [500 Server error]
│  │
│  └─ 📁 components/                    [UI Reusable Components]
│     ├─ navbar.html                    [Top navigation bar]
│     ├─ sidebar.html                   
│     │
│     ├─ 📁 sidebars/                   
│     │  ├─ _sidebar_common.html        [Các menu chung mà quyền nào cũng thấy]
│     │  ├─ _sidebar_admin.html         [Menu dành riêng cho Admin]
│     │  ├─ _sidebar_hr.html            [Menu dành riêng cho HR]
│     │  ├─ _sidebar_manager.html       [Menu dành riêng cho Manager]
│     │  └─ _sidebar_employee.html      [Menu dành riêng cho Employee]
│     │
│     ├─ footer.html                    [Footer]
│     ├─ pagination.html                [Pagination component]
│     ├─ modal.html                     [Modal template]
│     ├─ alert.html                     [Alert/notification]
│     ├─ form_errors.html               [Form error display]
│     ├─ table.html                     [Table component]
│     ├─ card.html                      [Card component]
│     ├─ badge.html                     [Badge component]
│     ├─ spinner.html                   [Loading spinner]
│     ├─ breadcrumb.html                [Breadcrumb nav]
│     └─ form_inputs.html               [Reusable form inputs]
│
├─ 📁 static/
│  │
│  ├─ 📁 css/
│  │  ├─ main.css                       [Main stylesheet]
│  │  ├─ variables.css                  [CSS variables (colors, etc)]
│  │  ├─ layouts.css                    [Layout styles]
│  │  ├─ components.css                 [Component styles]
│  │  ├─ forms.css                      [Form styles]
│  │  ├─ tables.css                     [Table styles]
│  │  ├─ responsive.css                 [Responsive/Mobile styles]
│  │  ├─ utilities.css                  [Utility classes]
│  │  └─ dark.css                       [Dark theme (optional)]
│  │
│  ├─ 📁 js/
│  │  ├─ utils/
│  │  │  ├─ api-client.js               [Fetch/Axios wrapper]
│  │  │  ├─ helpers.js                  [Helper functions]
│  │  │  ├─ validators.js               [Form validators]
│  │  │  ├─ formatters.js               [Date, number formatters]
│  │  │  ├─ storage.js                  [LocalStorage helper]
│  │  │  ├─ auth.js                     [Auth token management]
│  │  │  └─ logger.js                   [Console logging utility]
│  │  │
│  │  ├─ shared/
│  │  │  ├─ ui.js                       [UI interactions (modals, dropdowns)]
│  │  │  ├─ form-handler.js             [Form submission handler]
│  │  │  ├─ table-handler.js            [Table interactions (sort, filter)]
│  │  │  ├─ notification.js             [Toast notifications]
│  │  │  └─ theme-switcher.js           [Dark/light theme toggle]
│  │  │
│  │  ├─ modules/                       [Feature-specific JS]
│  │  │  ├─ auth.js                     [Auth form handlers]
│  │  │  ├─ personnel.js                [Profile, dependent handlers]
│  │  │  ├─ leave.js                    [Leave request handlers]
│  │  │  ├─ attendance.js               [Check-in/out handlers]
│  │  │  ├─ contract.js                 [Contract handlers]
│  │  │  ├─ payroll.js                  [Payroll handlers]
│  │  │  ├─ admin.js                    [Admin panel handlers]
│  │  │  ├─ manager.js                  [Manager dashboard handlers]
│  │  │  └─ notifications.js            [Notification handlers]
│  │  │
│  │  └─ main.js                        [Entry point - initialize on page load]
│  │
│  ├─ 📁 libs/
│  │  └─ [External libraries - Bootstrap, jQuery, Chart.js, etc.]
│  │
│  ├─ 📁 images/
│  │  ├─ logo.png
│  │  ├─ icons/
│  │  ├─ avatars/
│  │  └─ backgrounds/
│  │
│  ├─ 📁 fonts/
│  │  └─ [Custom fonts]
│  │
│  └─ 📁 uploads/
│     └─ [User-generated files: avatars, docs, etc.]
│
└─ 📁 static-docs/                      [Optional: Generated docs for FE devs]
   ├─ api-endpoints.md
   └─ frontend-guide.md bạn có thể sửa cho tôi mà
