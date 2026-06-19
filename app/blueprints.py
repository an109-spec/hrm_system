"""
app/blueprints.py
Đăng ký tất cả Blueprint vào Flask app.
Thêm blueprint mới vào tuple BLUEPRINTS là đủ — không cần chỉnh __init__.py.
"""


def register_blueprints(app):
    from app.modules.admin        import admin_bp
    from app.modules.attendance   import attendance_bp
    from app.modules.auth         import auth_bp
    from app.modules.contract     import contract_bp
    from app.modules.history      import history_bp
    from app.modules.hr           import hr_bp
    from app.modules.leave        import leave_bp
    from app.modules.manager      import manager_bp
    from app.modules.notification import notification_bp
    from app.modules.payroll      import payroll_bp
    from app.modules.personnel    import personnel_bp
    from app.modules.resignation  import resignation_bp
    from app.modules.home         import home_bp
    BLUEPRINTS = (
            (auth_bp, "/auth"),
            (personnel_bp, "/personnel"),
            (notification_bp, "/notification"),
            (leave_bp, "/leave"),
            (attendance_bp, "/attendance"),
            (history_bp, "/history"),
            (manager_bp, "/manager"),
            (admin_bp, "/admin"),
            (hr_bp, "/hr"),
            (payroll_bp, "/payroll"),
            (contract_bp, "/contract"),
            (resignation_bp, "/resignation"),
            (home_bp, "/")
        )

    for bp, prefix in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix=prefix)