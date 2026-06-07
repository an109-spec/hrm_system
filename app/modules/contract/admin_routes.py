from flask import request, jsonify, g
from . import contract_bp
from app.modules.contract.admin_service import Admin_Contract_Service
from app.common.security.decorators import auth_required, role_required
from app.common.security.permissions import permission_required
from app.constants.common import RoleName
from app.common.exceptions import NotFoundError
from app.models.contract import Contract


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def swal_success(title: str, message: str, data=None, status_code: int = 200):
    """Trả về response theo định dạng SweetAlert2."""
    payload = {
        "swal": {
            "icon": "success",
            "title": title,
            "text": message,
        },
        "success": True,
    }
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def swal_error(title: str, message: str, status_code: int = 400):
    """Trả về response lỗi theo định dạng SweetAlert2."""
    payload = {
        "swal": {
            "icon": "error",
            "title": title,
            "text": message,
        },
        "success": False,
    }
    return jsonify(payload), status_code


def contract_to_dict(contract: Contract) -> dict:
    """Serialize một Contract object sang dict."""
    return {
        "id": contract.id,
        "contract_code": contract.contract_code,
        "employee_id": contract.employee_id,
        "employee_name": contract.employee.full_name if contract.employee else None,
        "basic_salary": str(contract.basic_salary),
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "status": contract.status,
        "contract_type": contract.contract_type,
        "note": contract.note,
    }


# ─────────────────────────────────────────────
# Route 1 – POST /api/admin/contracts
# Tạo mới hợp đồng
# ─────────────────────────────────────────────

@contract_bp.route("/api/admin/contracts", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def create_contract():
    """
    Tạo hợp đồng mới cho nhân viên.
    Body JSON:
        employee_id  (int, bắt buộc)
        basic_salary (Decimal, tuỳ chọn)
        duration     (str, vd: "2m", "1y", "permanent")
        contract_type (str, tuỳ chọn)
        note         (str, tuỳ chọn)
    """
    data = request.get_json(silent=True) or {}

    if not data.get("employee_id"):
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp employee_id.",
            400,
        )

    try:
        contract = Admin_Contract_Service.create_contract(
            data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Tạo hợp đồng thành công",
            f"Hợp đồng {contract.contract_code} đã được tạo.",
            data=contract_to_dict(contract),
            status_code=201,
        )

    except NotFoundError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – PATCH /api/admin/contracts/<id>/terminate
# Chấm dứt hợp đồng
# ─────────────────────────────────────────────

@contract_bp.route("/api/admin/contracts/<int:id>/terminate", methods=["PATCH"])
@auth_required
@role_required(RoleName.ADMIN)
def terminate_contract(id: int):
    """
    Chấm dứt hợp đồng theo ID.
    Body JSON:
        end_date (str ISO hoặc date, tuỳ chọn – mặc định hôm nay)
        note     (str, tuỳ chọn)
    """
    data = request.get_json(silent=True) or {}

    try:
        contract = Admin_Contract_Service.terminate_contract(
            contract_id=id,
            data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Chấm dứt hợp đồng thành công",
            f"Hợp đồng {contract.contract_code} đã được chấm dứt. Tài khoản người dùng liên quan đã bị khóa.",
            data=contract_to_dict(contract),
        )

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – GET /api/admin/contracts
# Lấy danh sách hợp đồng (có bộ lọc tuỳ chọn)
# ─────────────────────────────────────────────

@contract_bp.route("/api/admin/contracts", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN)
def get_all_contracts():
    """
    Lấy danh sách tất cả hợp đồng.
    Query params:
        status      (str, tuỳ chọn) – vd: ?status=active
        employee_id (int, tuỳ chọn) – lọc theo nhân viên
        page        (int, mặc định 1)
        per_page    (int, mặc định 20)
    """
    status_filter = request.args.get("status")
    employee_id_filter = request.args.get("employee_id", type=int)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    try:
        query = Contract.query.filter_by(is_deleted=False)

        if status_filter:
            query = query.filter(Contract.status == status_filter)

        if employee_id_filter:
            query = query.filter(Contract.employee_id == employee_id_filter)

        pagination = query.order_by(Contract.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        result = {
            "contracts": [contract_to_dict(c) for c in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }

        return swal_success(
            "Thành công",
            f"Tìm thấy {pagination.total} hợp đồng.",
            data=result,
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 4 – GET /api/admin/contracts/<id>
# Xem chi tiết một hợp đồng
# ─────────────────────────────────────────────

@contract_bp.route("/api/admin/contracts/<int:id>", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN)
def get_contract_by_id(id: int):
    """
    Lấy chi tiết hợp đồng theo ID.
    """
    try:
        contract = Contract.query.filter_by(id=id, is_deleted=False).first()

        if not contract:
            return swal_error(
                "Không tìm thấy",
                f"Không tìm thấy hợp đồng với ID {id}.",
                404,
            )

        return swal_success(
            "Thành công",
            "Lấy thông tin hợp đồng thành công.",
            data=contract_to_dict(contract),
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)