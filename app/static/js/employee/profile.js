import { EmployeeAPI } from "../api/employee.api.js";
import { Toast } from "../components/toast.js";

export class Profile {
  static async update(data) {
    try {
      await EmployeeAPI.updateProfile(data);
      Toast.success("Cập nhật hồ sơ thành công");
    } catch {
      Toast.error("Cập nhật thất bại");
    }
  }

  static async changePassword(data) {
    try {
      await EmployeeAPI.changePassword(data);
      Toast.success("Đổi mật khẩu thành công");
    } catch {
      Toast.error("Sai mật khẩu hoặc lỗi hệ thống");
    }
  }
}