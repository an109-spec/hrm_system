from flask import request, jsonify, g
from . import contract_bp
from app.modules.contract.manager_service import Manager_Contract_Service
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def swal_success(title: str, message: str, data=None, status_code: int = 200):
    """Response thành công theo chuẩn SweetAlert2."""
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
    """Response lỗi theo chuẩn SweetAlert2."""
    payload = {
        "swal": {
            "icon": "error",
            "title": title,
            "text": message,
        },
        "success": False,
    }
    return jsonify(payload), status_code


def _manager_id() -> int:
    """Lấy employee_id của manager đang đăng nhập từ g.employee."""
    return g.employee.id


# ─────────────────────────────────────────────
# Route 1 – GET /api/manager/contracts
# Danh sách hợp đồng có lọc & phân trang
# ─────────────────────────────────────────────

@contract_bp.route("/api/manager/contracts", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_get_contracts():
    """
    Lấy danh sách hợp đồng nhân viên thuộc quyền quản lý (có lọc & phân trang).

    Query params:
        search          (str, tuỳ chọn) – tìm theo tên, mã hợp đồng, ID nhân viên
        contract_type   (str, tuỳ chọn) – vd: "probation", "official", "all"
        contract_status (str, tuỳ chọn) – vd: "active", "expired", "expiring", "all"
        page            (int, mặc định 1)
        per_page        (int, mặc định 20)
    """
    search = request.args.get("search")
    contract_type = request.args.get("contract_type")
    contract_status = request.args.get("contract_status")
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    try:
        result = Manager_Contract_Service.get_filtered_contracts_with_pagination(
            manager_id=_manager_id(),
            search=search,
            contract_type=contract_type,
            contract_status=contract_status,
            page=page,
            per_page=per_page,
        )
        total = result.get("meta", {}).get("total", 0)
        return swal_success(
            "Thành công",
            f"Tìm thấy {total} hợp đồng.",
            data=result,
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – GET /api/manager/contracts/expiring
# Danh sách hợp đồng sắp hết hạn (trong 30 ngày)
# ─────────────────────────────────────────────

@contract_bp.route("/api/manager/contracts/expiring", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_get_expiring_contracts():
    """
    Trả về danh sách hợp đồng sắp hết hạn trong 30 ngày tới
    của các nhân viên thuộc quyền quản lý.
    """
    try:
        items = Manager_Contract_Service.get_contract_expiring(
            manager_id=_manager_id()
        )
        return swal_success(
            "Thành công",
            f"Có {len(items)} hợp đồng sắp hết hạn trong 30 ngày tới.",
            data={"items": items, "total": len(items)},
        )

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 3 – GET /api/manager/contracts/<id>
# Chi tiết một hợp đồng cụ thể
# ─────────────────────────────────────────────

@contract_bp.route("/api/manager/contracts/<int:id>", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_get_contract_detail(id: int):
    """
    Xem chi tiết hợp đồng theo ID.
    Manager chỉ được xem hợp đồng của nhân viên thuộc phòng ban mình quản lý.
    """
    try:
        detail = Manager_Contract_Service.get_contract_detail(
            manager_id=_manager_id(),
            contract_id=id,
        )
        return swal_success(
            "Thành công",
            "Lấy thông tin hợp đồng thành công.",
            data=detail,
        )

    except PermissionError as e:
        return swal_error("Không có quyền", str(e), 403)

    except ValueError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 4 – GET /api/manager/employees/<emp_id>/latest-contract
# Lấy hợp đồng gần nhất của nhân viên (chuẩn bị gia hạn)
# ─────────────────────────────────────────────

@contract_bp.route("/api/manager/employees/<int:emp_id>/latest-contract", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_get_latest_contract(emp_id: int):
    """
    Lấy hợp đồng active/expired gần nhất của một nhân viên cụ thể,
    phục vụ cho luồng gửi yêu cầu gia hạn.
    Manager chỉ được truy cập nhân viên thuộc quyền quản lý của mình.
    """
    try:
        detail = Manager_Contract_Service.get_contract_for_renewal_or_adjustment(
            manager_id=_manager_id(),
            employee_id=emp_id,
        )
        return swal_success(
            "Thành công",
            "Lấy hợp đồng gần nhất thành công.",
            data=detail,
        )

    except PermissionError as e:
        return swal_error("Không có quyền", str(e), 403)

    except ValueError as e:
        return swal_error("Không tìm thấy", str(e), 404)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 5 – POST /api/manager/contracts/<id>/request-renewal
# Gửi yêu cầu gia hạn hợp đồng lên HR
# ─────────────────────────────────────────────

@contract_bp.route("/api/manager/contracts/<int:id>/request-renewal", methods=["POST"])
@auth_required
@role_required(RoleName.MANAGER)
def manager_request_renewal(id: int):
    """
    Manager gửi yêu cầu gia hạn hợp đồng lên HR.

    Body JSON:
        reason                   (str, bắt buộc)  – lý do gia hạn
        proposed_duration_months (int, bắt buộc)  – số tháng đề xuất gia hạn
        professional_note        (str, tuỳ chọn)  – ghi chú chuyên môn bổ sung
    """
    data = request.get_json(silent=True) or {}

    # Validate bắt buộc
    reason = data.get("reason", "").strip()
    proposed_duration_months = data.get("proposed_duration_months")

    if not reason:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp lý do gia hạn ('reason').",
            400,
        )

    if proposed_duration_months is None:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp số tháng đề xuất gia hạn ('proposed_duration_months').",
            400,
        )

    try:
        proposed_duration_months = int(proposed_duration_months)
        if proposed_duration_months <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return swal_error(
            "Dữ liệu không hợp lệ",
            "'proposed_duration_months' phải là số nguyên dương.",
            400,
        )

    professional_note = data.get("professional_note")

    try:
        result = Manager_Contract_Service.request_contract_renewal(
            manager_id=_manager_id(),
            contract_id=id,
            reason=reason,
            proposed_duration_months=proposed_duration_months,
            professional_note=professional_note,
        )
        return swal_success(
            "Gửi yêu cầu thành công",
            result.get("message", "Yêu cầu gia hạn đã được gửi đến HR."),
            data=result,
            status_code=201,
        )

    except PermissionError as e:
        return swal_error("Không có quyền", str(e), 403)

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)