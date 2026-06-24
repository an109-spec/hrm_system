
from flask import render_template, g, jsonify
from app.constants.common import RoleName
from . import contract_bp
from app.common.security.decorators import auth_required
import datetime

# Helper function to render templates with a base path
def render_contract_template(template_name, **context):
    return render_template(f"modules/contract/{template_name}", **context)

# --------------------------------------------------------------------------
# PAGE RENDERING ROUTES
# --------------------------------------------------------------------------

@contract_bp.route('/')
@auth_required
def list_contracts():
    """Render the list of contracts page."""
    return render_contract_template('list.html')

@contract_bp.route('/<int:contract_id>')
@auth_required
def contract_detail(contract_id):
    """Render the contract detail page."""
    return render_contract_template('detail.html', contract_id=contract_id)

@contract_bp.route('/create')
@auth_required
def create_contract():
    """Render the create contract page."""
    return render_contract_template('create.html')

@contract_bp.route('/reminders')
@auth_required
def expiration_reminders():
    """Render the expiration reminders page."""
    return render_contract_template('expiration_reminders.html')

@contract_bp.route('/renewal-request')
@auth_required
def renewal_request():
    """Render the renewal request page for employees."""
    return render_contract_template('renewal_request.html')

# --------------------------------------------------------------------------
# API ENDPOINTS (NEW)
# --------------------------------------------------------------------------

def get_mock_contract(contract_id):
    """Generates mock data for a contract."""
    # In a real application, you would query the database here.
    if contract_id != 4:
        return None
    return {
        "id": contract_id,
        "contract_code": f"HD-00{contract_id}",
        "contract_status": "expiring",  # 'active', 'expiring', 'expired', 'terminated'
        "days_left": 25,
        "employee_name": "Nguyen Van A",
        "employee_code": "NV-0123",
        "department": "Phòng Công nghệ",
        "position": "Lập trình viên",
        "employment_type": "Toàn thời gian",
        "start_date": datetime.datetime(2023, 8, 1).isoformat(),
        "end_date": datetime.datetime(2024, 8, 1).isoformat(),
        "basic_salary": 25000000,
        "note": "Hợp đồng lao động có thời hạn 1 năm. Xem xét gia hạn trước 30 ngày."
    }

@contract_bp.route('/api/contracts/<int:contract_id>')
@auth_required
def api_get_contract_detail(contract_id):
    """API endpoint for Admin, HR, and Employee to get contract details."""
    # Here you would add permission checks, e.g.:
    # if not (current_user.is_admin() or current_user.is_hr() or current_user.owns_contract(contract_id)):
    #     return jsonify({"success": False, "message": "Permission denied"}), 403
    
    contract = get_mock_contract(contract_id)
    if not contract:
        return jsonify({"success": False, "message": "Contract not found"}), 404
        
    return jsonify(contract)

@contract_bp.route('/api/manager/contracts/<int:contract_id>')
@auth_required
def api_manager_get_contract_detail(contract_id):
    """API endpoint for Managers to get contract details of their team members."""
    # Here you would add permission checks, e.g.:
    # if not current_user.is_manager_of_contract(contract_id):
    #     return jsonify({"success": False, "message": "Permission denied"}), 403
        
    contract = get_mock_contract(contract_id) # Using same mock for simplicity
    if not contract:
        return jsonify({"success": False, "message": "Contract not found"}), 404
        
    return jsonify(contract)
