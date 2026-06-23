"""
rendering_routes.py for attendance module
"""
from flask import Blueprint, render_template
from app.common.security.decorators import login_required, roles_required

# Create a new Blueprint for attendance rendering
attendance_bp = Blueprint('attendance', __name__,
                    template_folder='../../templates/modules/attendance',
                    url_prefix='/attendance')

@attendance_bp.route('/')
@login_required
def render_attendance_page():
    """Render the main attendance page, accessible by all logged-in users."""
    return render_template("attendance.html")

@attendance_bp.route('/check-in-out')
@login_required
@roles_required('Employee')
def render_checkin_interface():
    """Render the check-in/out interface for employees."""
    return render_template("checkin_interface.html")
    
@attendance_bp.route('/qr-scanner')
@login_required
@roles_required('Employee')
def render_qr_scanner():
    """Render the QR code scanner page for employees."""
    return render_template("qr_scanner.html")

@attendance_bp.route('/history')
@login_required
@roles_required('Employee')
def render_attendance_history():
    """Render the personal attendance history page for employees."""
    return render_template("history.html")

@attendance_bp.route('/summary')
@login_required
@roles_required('Employee')
def render_attendance_summary():
    """Render the personal attendance summary page for employees."""
    return render_template("summary.html")

@attendance_bp.route('/overtime-request')
@login_required
@roles_required('Employee')
def render_overtime_request():
    """Render the overtime request form for employees."""
    return render_template("overtime_request.html")

# --- Manager-specific routes ---
@attendance_bp.route('/manager/team-attendance')
@login_required
@roles_required('Manager')
def render_team_attendance():
    """Render the team attendance view for managers."""
    return render_template("team_attendance.html")

@attendance_bp.route('/manager/ot-approval')
@login_required
@roles_required('Manager')
def render_manager_ot_approval():
    """Render the overtime approval page for managers."""
    return render_template("manager_ot_approval.html")
