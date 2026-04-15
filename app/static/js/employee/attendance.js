import { Toast } from "../components/toast.js";
import { formatDateTime } from "../core/utils.js";
import { AttendanceAPI } from "../api/attendance.api.js";

export class Attendance {
  static async checkIn() {
    try {
      const res = await AttendanceAPI.checkIn();

      Toast.success("Check-in thành công");
      return res;
    } catch (err) {
      Toast.error(err.message || "Check-in thất bại");
    }
  }

  static async checkOut() {
    try {
      const res = await AttendanceAPI.checkOut();

      Toast.success("Check-out thành công");
      return res;
    } catch (err) {
      Toast.error(err.message || "Check-out thất bại");
    }
  }

  static renderStatus(data) {
    const el = document.getElementById("attendance-status");
    if (!el) return;

    el.innerHTML = `
      <div>
        <strong>Trạng thái:</strong> ${data.status_name || "N/A"}
      </div>
      <div>
        Check-in: ${formatDateTime(data.check_in)}
      </div>
      <div>
        Check-out: ${formatDateTime(data.check_out)}
      </div>
    `;
  }
}