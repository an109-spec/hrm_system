
from flask import render_template, g
from app.constants.common import RoleName
from . import contract_bp

# Helper function to render templates with a base path
def render_contract_template(template_name, **context):
    return render_template(f"modules/contract/{template_name}", **context)

@contract_bp.route('/')
def list_contracts():
    """Render the list of contracts page."""
    return render_contract_template('list.html')

@contract_bp.route('/<int:contract_id>')
def contract_detail(contract_id):
    """Render the contract detail page."""
    # Logic to check permission will be in the template or a service
    return render_contract_template('detail.html', contract_id=contract_id)

@contract_bp.route('/create')
def create_contract():
    """Render the create contract page."""
    return render_contract_template('create.html')

@contract_bp.route('/reminders')
def expiration_reminders():
    """Render the expiration reminders page."""
    return render_contract_template('expiration_reminders.html')

@contract_bp.route('/renewal-request')
def renewal_request():
    """Render the renewal request page for employees."""
    return render_contract_template('renewal_request.html')

