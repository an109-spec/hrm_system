from flask import request, jsonify, g, render_template
from http import HTTPStatus

from app.modules.payroll import payroll_bp
from app.common.security.decorators import auth_required, role_required
from app.constants.common import RoleName
from app.modules.payroll.admin_service import PayrollPolicyService
from app.common.responses import payroll_success_payload as swal_success, payroll_error_payload as swal_error, payroll_warning_payload as swal_warning, payroll_info_payload as swal_info

# ════════════════════════════════════════════════════════════════
# NHÓM 1: CẤU HÌNH CHÍNH SÁCH LƯƠNG (Global Policy)
# ════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# GET /payroll/admin/policy
# Xem cấu hình chính sách lương hiện tại
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/policy", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_policy():
    """
    Trả về toàn bộ cấu hình lương hiện tại:
    bảo hiểm, thuế TNCN, mức phạt đi muộn, giảm trừ, phụ cấp miễn thuế.
    """
    try:
        policy = PayrollPolicyService.get_policy()

        # Cảnh báo nếu cấu hình đang bị khóa
        if policy.get("config_edit_locked"):
            return jsonify(swal_warning(
                "Cấu hình lương đang bị khóa chỉnh sửa. "
                "Vui lòng mở khóa trước khi cập nhật.",
                data=policy
            )), HTTPStatus.OK

        return jsonify(swal_success(
            "Lấy cấu hình chính sách lương thành công.",
            data=policy
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/admin/policy
# Cập nhật cấu hình chính sách lương
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/policy", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def update_policy():
    """
    Body JSON (tuỳ chọn – gửi phần nào cập nhật phần đó):
        late_penalty        (dict) – under_15, from_15_to_30, over_60_half_day
        insurance           (dict) – social_percent, health_percent, unemployment_percent
        deduction           (dict) – personal, dependent_per_person
        tax                 (dict) – brackets: [{from, to, rate_percent, quick_deduction}]
        tax_free_allowances (dict) – fuel_allowance, meal_allowance, ...
    """
    try:
        payload = request.get_json(silent=True) or {}

        if not payload:
            return jsonify(swal_error(
                "Không có dữ liệu để cập nhật.",
                title="Thiếu dữ liệu"
            )), HTTPStatus.BAD_REQUEST

        updated_policy = PayrollPolicyService.update_policy(
            payload=payload,
            actor_user_id=g.user.id,
        )

        return jsonify(swal_success(
            "Cập nhật cấu hình chính sách lương thành công.",
            data=updated_policy
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể cập nhật")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/admin/policy/lock
# Khóa hoặc mở khóa cấu hình lương
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/policy/lock", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def set_edit_lock():
    """
    Body JSON (bắt buộc):
        locked  (bool) – true: khóa | false: mở khóa
    """
    try:
        body = request.get_json(silent=True) or {}

        if "locked" not in body:
            return jsonify(swal_error(
                "Vui lòng cung cấp trường 'locked' (true/false).",
                title="Thiếu tham số"
            )), HTTPStatus.BAD_REQUEST

        locked = bool(body["locked"])

        PayrollPolicyService.set_edit_lock(
            locked=locked,
            actor_user_id=g.user.id,
        )

        if locked:
            return jsonify(swal_success(
                "Đã khóa cấu hình lương. Hệ thống sẽ không cho phép chỉnh sửa cho đến khi mở khóa."
            )), HTTPStatus.OK
        else:
            return jsonify(swal_warning(
                "Đã mở khóa cấu hình lương. Vui lòng cẩn thận khi thực hiện thay đổi."
            )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ════════════════════════════════════════════════════════════════
# NHÓM 2: DUYỆT QUY TRÌNH LƯƠNG (Payroll Workflow)
# ════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# POST /payroll/admin/<id>/process
# Duyệt / Chốt / Từ chối bảng lương
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/<int:salary_id>/process", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def approve_payroll_flow(salary_id: int):
    """
    Body JSON (bắt buộc):
        action  (str) – "approve" | "finalize" | "reject" | "notify_review" | "paid"
        note    (str, tuỳ chọn) – Ghi chú / lý do
    """
    try:
        body = request.get_json(silent=True) or {}
        action = body.get("action", "").strip().lower()
        note   = body.get("note", "").strip()

        # 1. Cập nhật danh sách hành động hợp lệ
        allowed_actions = ("approve", "finalize", "reject", "notify_review", "paid")
        
        if action not in allowed_actions:
            return jsonify(swal_error(
                f"Hành động không hợp lệ. Các hành động hỗ trợ: {', '.join(allowed_actions)}.",
                title="Tham số không hợp lệ"
            )), HTTPStatus.BAD_REQUEST

        # 2. Yêu cầu note khi từ chối
        if action == "reject" and not note:
            return jsonify(swal_error(
                "Vui lòng nhập lý do từ chối để HR và nhân viên nắm được thông tin.",
                title="Thiếu thông tin"
            )), HTTPStatus.BAD_REQUEST

        # 3. Gọi Service (Service đã xử lý logic trạng thái và DB transaction)
        result = PayrollPolicyService.approve_payroll_flow(
            salary_id=salary_id,
            action=action,
            note=note,
            actor_user_id=g.user.id,
        )

        # 4. Định nghĩa thông báo tương ứng
        action_messages = {
            "approve":       "Bảng lương đã được phê duyệt thành công.",
            "finalize":      "Bảng lương đã được chốt sổ (Locked) thành công.",
            "reject":        "Bảng lương đã bị từ chối. Thông báo đã được gửi đến HR.",
            "notify_review": "Thông báo kiểm tra bảng lương đã được gửi đến toàn bộ nhân viên.",
            "paid":          "Thanh toán lương thành công. Thông báo đã được gửi đến nhân viên."
        }

        # 5. Phản hồi UI
        # Giữ nguyên việc "reject" là warning, các hành động khác là success
        if action == "reject":
            return jsonify(swal_warning(
                action_messages.get(action, "Đã thực hiện xong."),
                data=result
            )), HTTPStatus.OK

        return jsonify(swal_success(
            action_messages.get(action, "Đã thực hiện xong."),
            data=result
        )), HTTPStatus.OK

    except ValueError as e:
        # Xử lý các lỗi logic (Ví dụ: Trạng thái không hợp lệ)
        return jsonify(swal_error(str(e), title="Không thể xử lý")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        # Xử lý các lỗi hệ thống
        return jsonify(swal_error("Có lỗi xảy ra trong hệ thống, vui lòng thử lại sau.")), HTTPStatus.INTERNAL_SERVER_ERROR
# ════════════════════════════════════════════════════════════════
# NHÓM 3: CẤU HÌNH LƯƠNG THEO CHỨC DANH (Position Specific)
# ════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# GET /payroll/admin/positions/<id>/salary-config
# Xem cấu hình lương của một chức danh
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/positions/<int:position_id>/salary-config", methods=["GET"])
@auth_required
@role_required(RoleName.ADMIN, RoleName.HR)
def get_salary_config_for_position(position_id: int):
    try:
        config = PayrollPolicyService.get_salary_config_for_position(position_id)

        if not config:
            return jsonify(swal_info(
                f"Chưa có cấu hình lương riêng cho chức danh ID {position_id}. "
                "Hệ thống đang dùng cấu hình mặc định.",
                data={}
            )), HTTPStatus.OK

        return jsonify(swal_success(
            f"Lấy cấu hình lương cho chức danh ID {position_id} thành công.",
            data=config
        )), HTTPStatus.OK

    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR


# ─────────────────────────────────────────────
# POST /payroll/admin/positions/<id>/salary-config
# Tạo / cập nhật cấu hình lương của một chức danh
# ─────────────────────────────────────────────
@payroll_bp.route("/admin/positions/<int:position_id>/salary-config", methods=["POST"])
@auth_required
@role_required(RoleName.ADMIN)
def set_salary_config_for_position(position_id: int):
    """
    Body JSON (bắt buộc – ít nhất 1 trường):
        base_salary         (int/float)
        lunch_allowance     (int/float)
        responsibility_allowance (int/float)
        ... (các key tùy ý theo cấu trúc hệ thống)

    Ví dụ:
        {
            "base_salary": 20000000,
            "lunch_allowance": 730000,
            "responsibility_allowance": 1000000
        }
    """
    try:
        salary_data = request.get_json(silent=True) or {}

        if not salary_data:
            return jsonify(swal_error(
                "Vui lòng cung cấp ít nhất một trường cấu hình lương.",
                title="Thiếu dữ liệu"
            )), HTTPStatus.BAD_REQUEST

        PayrollPolicyService.set_salary_config_for_position(
            position_id=position_id,
            salary_data=salary_data,
            actor_user_id=g.user.id,
        )

        # Trả về config sau khi cập nhật
        updated_config = PayrollPolicyService.get_salary_config_for_position(position_id)

        return jsonify(swal_success(
            f"Cập nhật cấu hình lương cho chức danh ID {position_id} thành công.",
            data=updated_config
        )), HTTPStatus.OK

    except ValueError as e:
        return jsonify(swal_error(str(e), title="Không thể cập nhật")), HTTPStatus.BAD_REQUEST
    except Exception as e:
        return jsonify(swal_error(str(e))), HTTPStatus.INTERNAL_SERVER_ERROR
    
@payroll_bp.route("" \
"", methods=["GET"])
@auth_required
def finalize_page():
    """
    Hiển thị trang giao diện Chốt sổ & Duyệt bảng lương cho HR/Admin.
    """
    return render_template("modules/payroll/finalize.html")