from calendar import calendar
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from app.constants.attendance import WorkConfig
from flask import request, jsonify, g
from app.constants.common import RoleName
from app.constants.payroll import SalaryStatus
from app.extensions.db import db
from app.common.security.decorators import auth_required, role_required, self_or_hr_required
from app.common.exceptions import ValidationError, ForbiddenError, UnauthorizedError
from app.models.contract import Contract
from app.models.salary import Salary
from app.modules.attendance.attendance_query_service import AttendanceCommandService
from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
from app.modules.attendance.attendance_state_service import AttendanceStateService
from app.modules.attendance.attendance_calculation_service import attendance_calculation_service
from app.modules.attendance.overtime_service import OvertimeService
from . import attendance_bp
from app.modules.attendance.service import AttendanceService
from app.models.attendance import Attendance, AttendanceShiftStatus, AttendanceType
from app.models.overtime_request import OvertimeRequest
from app.models.employee import Employee
from app.utils.time import VN_TIMEZONE, get_current_time, _normalize, set_simulated_time

@attendance_bp.route("/overtime/pending", methods=["GET"])
@auth_required
@role_required(RoleName.MANAGER)
def get_pending_overtime():
    """
    API lấy danh sách các đơn tăng ca chờ duyệt của cấp dưới.
    """
    try:
        manager_id = g.employee.id
        data = OvertimeService.get_overtime_requests(manager_id)
        return jsonify({
            "status": "success",
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "icon": "error",
            "title": "Thất bại",
            "text": f"Có lỗi xảy ra khi tải dữ liệu: {str(e)}"
        }), 400