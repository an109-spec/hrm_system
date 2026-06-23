from flask import render_template
from . import admin_bp

@admin_bp.route("/admin/create-employee")
def render_create_employee():
    """Renders the create employee page."""
    return render_template("modules/admin/create_employee.html")

@admin_bp.route("/admin/employee-management")
def render_employee_management():
    """Renders the employee management page."""
    return render_template("modules/admin/employee_management.html")

@admin_bp.route("/admin/lock-unlock")
def render_lock_unlock():
    """Renders the lock/unlock user page."""
    return render_template("modules/admin/lock_unlock.html")

@admin_bp.route("/admin/metadata")
def render_metadata():
    """Renders the metadata management page."""
    return render_template("modules/admin/metadata.html")

@admin_bp.route("/admin/reset-password")
def render_reset_password():
    """Renders the reset password page."""
    return render_template("modules/admin/reset_password.html")

@admin_bp.route("/admin/system-settings")
def render_system_settings():
    """Renders the system settings page."""
    return render_template("modules/admin/system_settings.html")

@admin_bp.route("/admin/user-account")
def render_user_account():
    """Renders the user account page."""
    return render_template("modules/admin/user_account.html")
