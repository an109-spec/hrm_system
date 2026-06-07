from flask import jsonify, request

from app.modules.contract import contract_bp
from app.modules.contract.base_service import Base_Service
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName


# ---------------------------------------------------------------------------
# GET /contract/meta
# Phải đặt TRƯỚC route /contract/<int:contract_id> để tránh Flask hiểu
# "meta" là một contract_id kiểu string.
# ---------------------------------------------------------------------------
@contract_bp.route("/meta", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_filter_meta():
    """
    Trả về danh sách danh mục (Phòng ban, Vị trí, Quản lý, Loại HĐ, Trạng thái HĐ)
    dùng để đổ vào các Dropdown bộ lọc phía client.
    """
    try:
        data = Base_Service.get_filter_meta()
        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Lỗi hệ thống",
            "text": str(e)
        }), 500


# ---------------------------------------------------------------------------
# GET /contract/reminders
# Đặt TRƯỚC route /<int:contract_id> vì lý do tương tự.
# ---------------------------------------------------------------------------
@contract_bp.route("/reminders", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_contract_reminders():
    """
    Trả về danh sách cảnh báo hợp đồng:
      - Hợp đồng đã quá hạn  (level: critical)
      - Nhân viên chưa có HĐ (level: critical)
      - Sắp hết hạn ≤ 7 ngày (level: warning)
      - Sắp hết hạn ≤ 30 ngày(level: warning)
      - Đang hiệu lực bình thường (level: info)
    """
    try:
        data = Base_Service.get_contract_reminders()
        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Lỗi hệ thống",
            "text": str(e)
        }), 500


# ---------------------------------------------------------------------------
# GET /contract/
# Danh sách hợp đồng, hỗ trợ tìm kiếm + filter qua query params.
# ---------------------------------------------------------------------------
@contract_bp.route("/", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_contracts():
    """
    Query params (tùy chọn):
      - search          : tìm theo mã HĐ / tên NV / mã NV
      - contract_type   : loại hợp đồng (all | full_time | part_time | ...)
      - contract_status : trạng thái   (all | active | expiring | expired | terminated)
    """
    try:
        search          = request.args.get("search", "").strip() or None
        contract_type   = request.args.get("contract_type", "all").strip()
        contract_status = request.args.get("contract_status", "all").strip()

        data = Base_Service.get_contracts(
            search=search,
            contract_type=contract_type,
            contract_status=contract_status
        )

        return jsonify({
            "success": True,
            "data": data          # { items: [...], summary: {...} }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Lỗi hệ thống",
            "text": str(e)
        }), 500


# ---------------------------------------------------------------------------
# GET /contract/<int:contract_id>
# Chi tiết 1 hợp đồng.
# ---------------------------------------------------------------------------
@contract_bp.route("/<int:contract_id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_contract_detail(contract_id: int):
    """
    Trả về toàn bộ thông tin chi tiết của hợp đồng có id = contract_id.
    Trả về 404 nếu không tìm thấy hoặc đã bị xóa mềm.
    """
    try:
        data = Base_Service.get_contract_detail(contract_id)
        return jsonify({
            "success": True,
            "data": data
        }), 200

    except ValueError as e:
        # get_contract_detail raise ValueError khi không tìm thấy HĐ
        return jsonify({
            "success": False,
            "icon": "warning",
            "title": "Không tìm thấy",
            "text": str(e)
        }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "icon": "error",
            "title": "Lỗi hệ thống",
            "text": str(e)
        }), 500