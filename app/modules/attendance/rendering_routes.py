"""
rendering_routes.py for attendance module
"""
from flask import render_template
from . import attendance_bp
from app.common.security.decorators import auth_required

@attendance_bp.route('/')
@auth_required
def render_attendance_page():
    """Render the main attendance page, accessible by all logged-in users."""
    return render_template("modules/attendance/attendance.html")

@attendance_bp.route('/check-in-out')
@auth_required
def render_checkin_interface():
    """Render the check-in/out interface for employees."""
    return render_template("modules/attendance/checkin_interface.html")
    
@attendance_bp.route('/qr-scanner')
@auth_required
def render_qr_scanner():
    """Render the QR code scanner page for employees."""
    return render_template("modules/attendance/qr_scanner.html")

@attendance_bp.route('/history')
@auth_required
def render_attendance_history():
    """Render the personal attendance history page for employees."""
    return render_template("modules/attendance/history.html")

@attendance_bp.route('/summary')
@auth_required
def render_attendance_summary():
    """Render the personal attendance summary page for employees."""
    return render_template("modules/attendance/summary.html")

@attendance_bp.route('/overtime-request')
@auth_required
def render_overtime_request():
    """Render the overtime request form for employees."""
    return render_template("modules/attendance/overtime_request.html")

# --- Manager-specific routes ---
@attendance_bp.route('/manager/team-attendance')
@auth_required
def render_team_attendance():
    """Render the team attendance view for managers."""
    return render_template("modules/attendance/team_attendance.html")

@attendance_bp.route('/manager/ot-approval')
@auth_required
def render_manager_ot_approval():
    """Render the overtime approval page for managers."""
    return render_template("modules/attendance/manager_ot_approval.html")
