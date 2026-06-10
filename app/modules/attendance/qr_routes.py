from flask import request, g
from http import HTTPStatus
from app.common.security.decorators import auth_required
from app.modules.attendance import attendance_bp
from app.modules.attendance.service import AttendanceService
from app.utils.time import get_current_time
def _ok(icon: str, title: str, text: str,
        data: dict | None = None,
        timer: int | None = None) -> tuple:
    """Response 200 kèm swal. Tự thêm timer + ẩn nút khi icon=success và có timer."""
    swal = {"icon": icon, "title": title, "text": text}
    if timer:
        swal["timer"] = timer
        swal["showConfirmButton"] = False
    response = {"swal": swal}
    if data is not None:
        response["data"] = data
    return response, HTTPStatus.OK


def _err(icon: str, title: str, text: str, status: int) -> tuple:
    return {"swal": {"icon": icon, "title": title, "text": text}}, status

def _bad_request(msg: str):
    return _err("warning", "Dữ liệu không hợp lệ", msg, HTTPStatus.BAD_REQUEST)

@attendance_bp.route("/qr/process", methods=["POST"])
@auth_required
def process_qr_scan():
    """
    Nhận nội dung thô từ bất kỳ mã QR nào và xử lý ngay lập tức.
    """
    data = request.get_json(silent=True) or {}
    # QR_content ở đây là chuỗi văn bản bất kỳ (ví dụ: "CHECKIN", "CHECKOUT", hoặc 1 chuỗi ngẫu nhiên)
    qr_content = data.get("qr_content") 

    if not qr_content:
        return _bad_request("Dữ liệu QR trống")

    # Giả lập payload dựa trên dữ liệu quét được
    # Bạn có thể dùng logic if-else hoặc mapping dictionary để hiểu nội dung QR
    action_payload = {
        "action": qr_content.strip().upper(), # Ví dụ: biến thành "CHECKIN"
        "scanned_at": get_current_time().isoformat()
    }

    # Đẩy thẳng vào Service xử lý chấm công
    try:
        result = AttendanceService.process_employee_action(
            employee_id=g.employee.id,
            payload=action_payload,
            current_time=get_current_time()
        )
        return _ok("success", "Xử lý QR", "Đã ghi nhận quét mã thành công", data=result)
    except Exception as e:
        return _err("error", "Lỗi xử lý", str(e), HTTPStatus.INTERNAL_SERVER_ERROR)