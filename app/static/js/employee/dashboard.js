import { SummaryCard } from "./dashboard/summary-card.js";
import { NotificationWidget } from "./dashboard/notification-widget.js";
import { AttendanceWidget } from "./dashboard/attendance-widget.js";
import { DashboardAPI } from "../api/dashboard.api.js";

export class EmployeeDashboard {
  constructor() {
    this.notificationWidget = new NotificationWidget();
    this.attendanceWidget = new AttendanceWidget();
  }

  async init() {
    await this.loadData();
    this.attendanceWidget.init();
  }

  async loadData() {
    const data = await DashboardAPI.getDashboard();

    SummaryCard.render(data.summary);
    this.attendanceWidget.updateUI(data.attendance);
    await this.notificationWidget.load();
  }
}