import { Toast } from "../components/toast.js";
import { formatDateTime } from "../core/utils.js";
import { AttendanceAPI } from "../api/attendance.api.js";
import { attendanceStore } from "../store/attendance.store.js";

function normalizeApiResponse(res = {}) {
  return {
    type: res.type || "success",
    action: res.action || null,
    message: res.message || null,
    ...res,
  };
}

function toLocalISO(dateObj = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${dateObj.getFullYear()}-${pad(dateObj.getMonth() + 1)}-${pad(dateObj.getDate())}T${pad(dateObj.getHours())}:${pad(dateObj.getMinutes())}:${pad(dateObj.getSeconds())}.${String(dateObj.getMilliseconds()).padStart(3, "0")}`;
}
export class Attendance {
  static async submitEmployeeAttendance(payload = {}) {
    attendanceStore.setSubmitting(true);
    attendanceStore.setError(null);
    try {
      const response = normalizeApiResponse(await AttendanceAPI.submitEmployeeAttendance(payload));
      attendanceStore.applyActionResult(response);
      return response;
    } catch (err) {
      attendanceStore.setError(err.message || "Không thể chấm công");
      throw err;
    } finally {
      attendanceStore.setSubmitting(false);
    }
  }

  static async checkIn(simulatedNow = toLocalISO(new Date()), qrText = "QR") {
    try {
      const res = await this.submitEmployeeAttendance({
        qr_text: qrText,
        simulated_now: simulatedNow,
      });

      if (res.type === "warning") {
        Toast.warning?.(res.message || "Yêu cầu xác nhận thêm") || Toast.error(res.message || "Yêu cầu xác nhận thêm");
      } else {
        Toast.success(res.message || "Check-in thành công");
      }
      return res;
    } catch (err) {
      Toast.error(err.message || "Check-in thất bại");
      return null;
    }
  }

  static async checkOut(simulatedNow = toLocalISO(new Date()), qrText = "QR", options = {}) {
    try {
      const res = await this.submitEmployeeAttendance({
        qr_text: qrText,
        simulated_now: simulatedNow,
        early_checkout_confirmed: Boolean(options.earlyCheckoutConfirmed),
      });

      if (res.action === "early_checkout_prompt") {
        return res;
      }

      Toast.success(res.message || "Check-out thành công");
      return res;
    } catch (err) {
      Toast.error(err.message || "Check-out thất bại");
      return null;
    }
  }

  static async submitOffdayConfirmation(qrText, simulatedNow) {
    return this.submitEmployeeAttendance({
      qr_text: qrText,
      simulated_now: simulatedNow,
      confirm_work_on_offday: true,
    });
  }

  static async submitOffdayDecline(qrText, simulatedNow) {
    return this.submitEmployeeAttendance({
      qr_text: qrText,
      simulated_now: simulatedNow,
      decline_offday_work: true,
    });
  }

  static async submitOvertimeDecision(qrText, simulatedNow, decision) {
    return this.submitEmployeeAttendance({
      qr_text: qrText,
      simulated_now: simulatedNow,
      overtime_decision: decision,
    });
  }

  static async createOvertimeRequest(payload = {}) {
    try {
      const response = normalizeApiResponse(await AttendanceAPI.createOvertimeRequest(payload));
      attendanceStore.applyActionResult(response);
      Toast.success(response.message || "Đã gửi yêu cầu OT");
      return response;
    } catch (err) {
      Toast.error(err.message || "Không thể gửi yêu cầu OT");
      return null;
    }
  }

  static async deleteRecord(dateIso) {
    try {
      const response = await AttendanceAPI.deleteEmployeeAttendance(dateIso);
      Toast.success(response.message || "Đã xóa bản ghi chấm công");
      return response;
    } catch (err) {
      Toast.error(err.message || "Không thể xóa bản ghi chấm công");
      return null;
    }
  }

  static renderStatus(data) {
    const el = document.getElementById("attendance-status");
    if (!el) return;

    el.innerHTML = `
      <div><strong>Trạng thái:</strong> ${data.shift_status_label || data.status_name || "N/A"}</div>
      <div>Check-in: ${formatDateTime(data.check_in)}</div>
      <div>Check-out: ${formatDateTime(data.check_out)}</div>
      <div>Công chuẩn: ${Number(data.regular_hours || 0).toFixed(2)}h</div>
      <div>OT: ${Number(data.overtime_hours || 0).toFixed(2)}h</div>
      <div>Tổng công: ${Number(data.working_hours || 0).toFixed(2)}h</div>
    `;
  }
}