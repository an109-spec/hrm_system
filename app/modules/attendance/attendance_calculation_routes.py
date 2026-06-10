from flask import request, g
from http import HTTPStatus
from datetime import datetime, date

from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.department import Department
from app.constants.common import RoleName
from app.common.security.decorators import auth_required
from app.common.exceptions import ForbiddenError, NotFoundError
from app.modules.attendance import attendance_bp
from app.modules.attendance.attendance_calculation_service import attendance_calculation_service


# ============================================================
# 🔧 HELPER: Lọc danh sách employee_id theo Role
# ============================================================

def _resolve_target_employee_ids(requested_employee_id=None):
    """
    Trả về danh sách employee_id được phép truy cập dựa trên role hiện tại.

    Logic phân quyền:
        - EMPLOYEE : chỉ được xem chính mình
        - MANAGER  : được xem nhân viên trong phòng ban mình quản lý (bao gồm chính mình)
        - HR/ADMIN : xem tất cả (có thể lọc thêm theo requested_employee_id)
    """
    user = g.user
    current_employee = g.employee
    role = user.role.name

    # ── ADMIN / HR: Không giới hạn ──────────────────────────────────────
    if role in [RoleName.ADMIN, RoleName.HR]:
        if requested_employee_id:
            target = Employee.query.filter_by(
                id=requested_employee_id, is_deleted=False
            ).first()
            if not target:
                raise NotFoundError("Không tìm thấy nhân viên")
            return [int(requested_employee_id)]
        # Trả về None → caller hiểu là "không lọc theo employee"
        return None

    # ── MANAGER: Xem nhân viên trong phòng ban mình quản lý ─────────────
    if role == RoleName.MANAGER:
        managed_dept = Department.query.filter_by(
            manager_id=current_employee.id, is_deleted=False
        ).first()

        if managed_dept:
            allowed_ids = [
                e.id for e in managed_dept.employees
                if not e.is_deleted
            ]
        else:
            # Manager chưa được gán phòng ban → chỉ xem chính mình
            allowed_ids = [current_employee.id]

        if requested_employee_id:
            requested_employee_id = int(requested_employee_id)
            if requested_employee_id not in allowed_ids:
                raise ForbiddenError("Bạn không có quyền xem thông tin nhân viên này")
            return [requested_employee_id]

        return allowed_ids

    # ── EMPLOYEE: Chỉ xem chính mình ────────────────────────────────────
    if requested_employee_id and int(requested_employee_id) != current_employee.id:
        raise ForbiddenError("Bạn chỉ được xem thông tin của chính mình")

    return [current_employee.id]


# ============================================================
# 📅 GET /attendance/daily-summary
# ============================================================

@attendance_bp.route("/daily-summary", methods=["GET"])
@auth_required
def get_daily_summary():
    """
    Lấy dữ liệu công trong ngày (Dashboard / Lịch cá nhân).

    Query params:
        date          (str, optional) : Ngày cần xem, định dạng YYYY-MM-DD. Mặc định: hôm nay.
        employee_id   (int, optional) : ID nhân viên cần xem. HR/Admin có thể truyền tự do;
                                        Manager chỉ được truyền ID thuộc phòng ban;
                                        Employee chỉ được xem chính mình.
    """
    # ── 1. Parse ngày ────────────────────────────────────────────────────
    date_str = request.args.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {
                "swal": {
                    "icon": "error",
                    "title": "Định dạng ngày không hợp lệ",
                    "text": "Vui lòng nhập ngày theo định dạng YYYY-MM-DD",
                }
            }, HTTPStatus.BAD_REQUEST
    else:
        target_date = date.today()

    # ── 2. Xác định danh sách employee_id được xem ───────────────────────
    requested_employee_id = request.args.get("employee_id", type=int)

    try:
        allowed_ids = _resolve_target_employee_ids(requested_employee_id)
    except ForbiddenError as e:
        return {
            "swal": {
                "icon": "error",
                "title": "Không có quyền truy cập",
                "text": str(e),
            }
        }, HTTPStatus.FORBIDDEN
    except NotFoundError as e:
        return {
            "swal": {
                "icon": "warning",
                "title": "Không tìm thấy",
                "text": str(e),
            }
        }, HTTPStatus.NOT_FOUND

    # ── 3. Truy vấn dữ liệu chấm công ───────────────────────────────────
    query = Attendance.query.filter(
        Attendance.date == target_date,
        Attendance.is_deleted == False,
    )

    if allowed_ids is not None:
        query = query.filter(Attendance.employee_id.in_(allowed_ids))

    attendance_records = query.all()

    if not attendance_records:
        return {
            "swal": {
                "icon": "info",
                "title": "Không có dữ liệu",
                "text": f"Không tìm thấy bản ghi chấm công nào cho ngày {target_date.strftime('%d/%m/%Y')}",
            },
            "data": [],
        }, HTTPStatus.OK

    # ── 4. Tính toán công cho từng bản ghi ───────────────────────────────
    results = []
    for record in attendance_records:
        work_unit = attendance_calculation_service.calculate_regular_work_units(record)

        employee = record.employee
        results.append({
            "employee_id":       employee.id,
            "full_name":         employee.full_name,
            "date":              target_date.strftime("%Y-%m-%d"),
            "check_in":          record.check_in.strftime("%H:%M:%S") if record.check_in else None,
            "check_out":         record.check_out.strftime("%H:%M:%S") if record.check_out else None,
            "attendance_type":   record.attendance_type,
            "work_units":        float(work_unit.units),
            "worked_hours":      float(work_unit.worked_hours),
            "is_half_day":       work_unit.is_half_day,
            "late_minutes":      work_unit.late_minutes,
            "early_leave_minutes": work_unit.early_leave_minutes,
        })

    return {
        "swal": {
            "icon": "success",
            "title": "Lấy dữ liệu thành công",
            "text": f"Tổng {len(results)} bản ghi chấm công ngày {target_date.strftime('%d/%m/%Y')}",
            "timer": 1500,
            "showConfirmButton": False,
        },
        "date":  target_date.strftime("%Y-%m-%d"),
        "total": len(results),
        "data":  results,
    }, HTTPStatus.OK


# ============================================================
# ⏱️  POST /attendance/overtime/calc
# ============================================================

@attendance_bp.route("/overtime/calc", methods=["POST"])
@auth_required
def calc_overtime():
    """
    Tính toán / Kiểm tra giờ OT trước khi đăng ký hoặc lưu.

    Body JSON:
        overtime_check_in   (str)           : Thời điểm bắt đầu OT, định dạng ISO hoặc "HH:MM" / "YYYY-MM-DD HH:MM:SS"
        overtime_check_out  (str)           : Thời điểm kết thúc OT
        employee_id         (int, optional) : ID nhân viên (HR/Admin có thể tính hộ người khác)
    """
    body = request.get_json(silent=True) or {}

    # ── 1. Validate payload ──────────────────────────────────────────────
    raw_in  = body.get("overtime_check_in")
    raw_out = body.get("overtime_check_out")

    if not raw_in or not raw_out:
        return {
            "swal": {
                "icon": "warning",
                "title": "Thiếu thông tin",
                "text": "Vui lòng cung cấp đầy đủ overtime_check_in và overtime_check_out",
            }
        }, HTTPStatus.BAD_REQUEST

    # ── 2. Parse datetime ─────────────────────────────────────────────────
    DATETIME_FORMATS = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
    ]

    def _parse_dt(value: str) -> datetime | None:
        for fmt in DATETIME_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    dt_in  = _parse_dt(raw_in)
    dt_out = _parse_dt(raw_out)

    if not dt_in or not dt_out:
        return {
            "swal": {
                "icon": "error",
                "title": "Định dạng thời gian không hợp lệ",
                "text": (
                    "Vui lòng nhập thời gian theo định dạng: "
                    "YYYY-MM-DD HH:MM:SS hoặc YYYY-MM-DDTHH:MM:SS"
                ),
            }
        }, HTTPStatus.BAD_REQUEST

    if dt_out <= dt_in:
        return {
            "swal": {
                "icon": "warning",
                "title": "Thời gian không hợp lệ",
                "text": "Thời gian check-out OT phải sau thời gian check-in OT",
            }
        }, HTTPStatus.BAD_REQUEST

    # ── 3. Kiểm tra quyền xem employee_id ────────────────────────────────
    requested_employee_id = body.get("employee_id")

    if requested_employee_id:
        try:
            _resolve_target_employee_ids(requested_employee_id)
        except ForbiddenError as e:
            return {
                "swal": {
                    "icon": "error",
                    "title": "Không có quyền truy cập",
                    "text": str(e),
                }
            }, HTTPStatus.FORBIDDEN
        except NotFoundError as e:
            return {
                "swal": {
                    "icon": "warning",
                    "title": "Không tìm thấy",
                    "text": str(e),
                }
            }, HTTPStatus.NOT_FOUND

    # ── 4. Tính giờ OT ───────────────────────────────────────────────────
    ot_hours = attendance_calculation_service.calculate_overtime_hours_raw(dt_in, dt_out)

    if ot_hours <= 0:
        return {
            "swal": {
                "icon": "info",
                "title": "Không có giờ OT hợp lệ",
                "text": (
                    "Khoảng thời gian bạn nhập không nằm trong khung giờ tăng ca "
                    "được quy định của hệ thống"
                ),
            },
            "data": {
                "overtime_hours":    0.0,
                "overtime_check_in":  raw_in,
                "overtime_check_out": raw_out,
            },
        }, HTTPStatus.OK

    return {
        "swal": {
            "icon": "success",
            "title": "Tính toán thành công",
            "text": f"Tổng giờ OT hợp lệ: {float(ot_hours):.2f} giờ",
            "timer": 2000,
            "showConfirmButton": False,
        },
        "data": {
            "overtime_hours":     float(ot_hours),
            "overtime_check_in":  dt_in.strftime("%Y-%m-%d %H:%M:%S"),
            "overtime_check_out": dt_out.strftime("%Y-%m-%d %H:%M:%S"),
            "employee_id":        requested_employee_id or g.employee.id,
        },
    }, HTTPStatus.OK