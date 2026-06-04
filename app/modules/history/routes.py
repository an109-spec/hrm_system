from flask import jsonify, request, g
from . import history_bp
from app.modules.history.service import HistoryService
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName
from app.common.exceptions import NotFoundError, PermissionError

# 1. Route cho cá nhân
@history_bp.route("/my-timeline", methods=["GET"])
@auth_required
def get_my_timeline():
    try:
        # Lấy dữ liệu của chính người đang đăng nhập từ g.user.id
        data = HistoryService.get_personal_timeline(g.user.id)
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        # Frontend sẽ nhận được message này và hiển thị Swal.fire({icon: 'error', text: e})
        return jsonify({"status": "error", "message": str(e)}), 400

# 2. Route cho Manager
@history_bp.route("/manager/team", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER, RoleName.HR, RoleName.ADMIN)
def get_team_timeline():
    try:
        page = request.args.get('page', 1, type=int)
        data = HistoryService.get_manager_subordinates_timeline(g.employee, page=page)
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# 3. Route cho Admin/HR
@history_bp.route("/admin/logs", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_audit_logs():
    try:
        page = request.args.get('page', 1, type=int)
        emp_name = request.args.get('employee_name')
        action = request.args.get('action')
        
        data = HistoryService.get_system_logs(
            current_user=g.user, 
            page=page, 
            employee_name=emp_name, 
            action_type=action
        )
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400