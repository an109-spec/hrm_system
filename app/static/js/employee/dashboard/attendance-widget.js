import { Attendance } from "../attendance.js";

export class AttendanceWidget {
  constructor() {
    this.btnCheckIn = document.getElementById("btn-checkin");
    this.btnCheckOut = document.getElementById("btn-checkout");
  }

  init() {
    if (this.btnCheckIn) {
      this.btnCheckIn.onclick = () => Attendance.checkIn();
    }

    if (this.btnCheckOut) {
      this.btnCheckOut.onclick = () => Attendance.checkOut();
    }
  }

  updateUI(data) {
    const statusEl = document.getElementById("attendance-widget-status");
    if (!statusEl) return;

    statusEl.innerText = data.status_name || "N/A";
  }
}