from flask import request, jsonify, g
from . import contract_bp
from app.modules.contract.hr_service import HR_Contract_Service
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName


# ─────────────────────────────────────────────
# Helpers (dùng chung với admin_routes nếu tách file)
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


def contract_to_dict(contract) -> dict:
    """Serialize Contract object sang dict."""
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
# Route 1 – POST /api/hr/contracts/<id>/extend
# Gia hạn hợp đồng trực tiếp (không qua yêu cầu)
# ─────────────────────────────────────────────

@contract_bp.route("/api/hr/contracts/<int:id>/extend", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def extend_contract(id: int):
    """
    HR gia hạn hợp đồng trực tiếp theo ID hợp đồng.

    Body JSON (một trong hai):
        duration  (str) – vd: "6m", "1y"  ← ưu tiên nếu truyền cả hai
        end_date  (str ISO) – vd: "2026-12-31"
        note      (str, tuỳ chọn)
    """
    data = request.get_json(silent=True) or {}

    # Validate: phải có ít nhất duration hoặc end_date
    if not data.get("duration") and not data.get("end_date"):
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp 'duration' (vd: '6m', '1y') hoặc 'end_date' (ISO date).",
            400,
        )

    try:
        contract = HR_Contract_Service.extend_contract(
            contract_id=id,
            data=data,
            current_user_id=g.user.id,
        )
        return swal_success(
            "Gia hạn thành công",
            f"Hợp đồng {contract.contract_code} đã được gia hạn đến ngày "
            f"{contract.end_date.isoformat() if contract.end_date else 'vô thời hạn'}.",
            data=contract_to_dict(contract),
        )

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)


# ─────────────────────────────────────────────
# Route 2 – POST /api/hr/contract-proposals/<id>/process
# HR duyệt hoặc từ chối yêu cầu gia hạn từ Manager
# ─────────────────────────────────────────────

@contract_bp.route("/api/hr/contract-proposals/<int:id>/process", methods=["POST"])
@auth_required
@role_required(RoleName.HR)
def process_renewal_request(id: int):
    """
    HR duyệt hoặc từ chối yêu cầu gia hạn hợp đồng do Manager gửi.

    Body JSON:
        is_approved  (bool, bắt buộc) – true = duyệt, false = từ chối
        feedback     (str, tuỳ chọn) – phản hồi/ghi chú của HR
    """
    data = request.get_json(silent=True) or {}

    # Validate: is_approved là bắt buộc và phải là bool
    if "is_approved" not in data:
        return swal_error(
            "Thiếu thông tin",
            "Vui lòng cung cấp trường 'is_approved' (true/false).",
            400,
        )

    is_approved = data.get("is_approved")
    if not isinstance(is_approved, bool):
        return swal_error(
            "Dữ liệu không hợp lệ",
            "Trường 'is_approved' phải là giá trị boolean (true hoặc false).",
            400,
        )

    feedback = data.get("feedback") or data.get("hr_feedback")

    try:
        result = HR_Contract_Service.process_renewal_request(
            proposal_id=id,
            is_approved=is_approved,
            hr_id=g.user.id,
            feedback=feedback,
        )

        action_label = "duyệt" if is_approved else "từ chối"
        return swal_success(
            f"Đã {action_label} yêu cầu",
            result.get("message", f"Yêu cầu gia hạn đã được {action_label} thành công."),
            data=result,
        )

    except ValueError as e:
        return swal_error("Không hợp lệ", str(e), 400)

    except Exception as e:
        return swal_error("Lỗi hệ thống", f"Đã xảy ra lỗi: {str(e)}", 500)