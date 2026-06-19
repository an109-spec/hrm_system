app/
│
├─ 📁 templates/                        [Jinja2 Templates]
│  ├─ base.html                         [Base layout - ALL pages extend]
│  │
│  ├─ 📁 layouts/
│  │  ├─ main_layout.html               [Main layout (header, sidebar, footer)]
│  │  ├─ auth_layout.html               [Auth layout (minimal, no sidebar)]
│  │
│  ├─ 📁 modules/                       [Feature modules by role]
│  │  │
│  │  ├─ 📁 auth/
│  │  │  ├─ login.html                  [Login page]
│  │  │  ├─ forgot_password.html        [Forgot password page]
│  │  │  ├─ verify_otp.html             [OTP verification]
│  │  │  └─ password_reset.html         [Password reset page]
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
│  │  │  ├─ attendance             [Main attendance page]
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
│  │  ├─ 📁 admin/
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
│
├─ 📁 static/
│  │
│  ├─ 📁 css
│  │  ├─ main.css                       [Main stylesheet]
│  │  ├─ layouts.css                    [Layout styles]
│  │  ├─ forms.css                      [Form styles]
│  │  ├─ tables.css                     [Table styles]
│  │  ├─ responsive.css                 [Responsive/Mobile styles]
│  │
│  ├─ 📁 js/
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
│  └─ 📁 uploads/