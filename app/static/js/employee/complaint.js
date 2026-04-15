import { Toast } from "../components/toast.js";
import { ComplaintAPI } from "../api/employee.api.js";

export class Complaint {
  static async submit(data) {
    try {
      await ComplaintAPI.create(data);
      Toast.success("Gửi khiếu nại thành công");
    } catch (err) {
      Toast.error("Không thể gửi khiếu nại");
    }
  }

  static async reply(id, message) {
    try {
      await ComplaintAPI.reply(id, { message });
      Toast.success("Đã gửi phản hồi");
    } catch {
      Toast.error("Lỗi gửi phản hồi");
    }
  }
}