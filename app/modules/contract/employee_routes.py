from flask import jsonify, g
from . import contract_bp  
from app.common.security.decorators import auth_required, role_required
from app.modules.contract.employee_service import ContractService
from app.constants.common import RoleName
@contract_bp.route("/<int:contract_id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_my_contract_detail(contract_id):
    """
    API lấy chi tiết hợp đồng của nhân viên đang đăng nhập.
    """
    try:
        # Service đã xử lý logic kiểm tra quyền (user_id)
        # g.user.id được lấy từ decorator @auth_required
        data = ContractService.get_my_contract_details(contract_id, g.user.id)
        
        # Trả về định dạng JSON chuẩn cho Frontend xử lý Swal
        return jsonify({
            "status": "success",
            "message": "Lấy thông tin hợp đồng thành công",
            "data": data
        }), 200

    except ValueError as e:
        # Trường hợp không tìm thấy hợp đồng
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404
        
    except PermissionError as e:
        # Trường hợp cố tình truy cập hợp đồng người khác
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 403
        
    except Exception as e:
        # Lỗi hệ thống
        return jsonify({
            "status": "error",
            "message": "Đã có lỗi xảy ra, vui lòng thử lại sau."
        }), 500