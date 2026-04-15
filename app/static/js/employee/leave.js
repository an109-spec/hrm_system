import { LeaveAPI } from "../api/leave.api.js";
import { Toast } from "../components/toast.js";

export class Leave {
  static async submit(data) {
    try {
      await LeaveAPI.create(data);
      Toast.success("Gửi đơn nghỉ phép thành công");
    } catch {
      Toast.error("Gửi đơn thất bại");
    }
  }

  static async cancel(id) {
    try {
      await LeaveAPI.cancel(id);
      Toast.success("Đã hủy đơn");
    } catch {
      Toast.error("Không thể hủy đơn");
    }
  }
}