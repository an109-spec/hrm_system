from flask import jsonify

from app.common.security.decorators import auth_required
from . import common_bp
from app.models.department import Department


@common_bp.route("/departments", methods=['GET'])
@auth_required
def get_departments():
    """
    API endpoint to get a list of all departments.
    Used by various modules to populate department filter dropdowns.
    """
    try:
        departments = Department.query.all()
        # Chuyển đổi list object sang list dictionary để jsonify
        dept_list = [{"id": d.id, "name": d.name} for d in departments]
        return jsonify({"data": dept_list, "success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500
