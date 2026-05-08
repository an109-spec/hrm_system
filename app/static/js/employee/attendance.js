import { Toast } from "../components/toast.js";
import { AttendanceAPI } from "../api/attendance.api.js";
import { attendanceStore } from "../store/attendance.store.js";

// ─────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────

function toLocalISO(dateObj = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${dateObj.getFullYear()}-${pad(dateObj.getMonth() + 1)}-${pad(dateObj.getDate())}` +
    `T${pad(dateObj.getHours())}:${pad(dateObj.getMinutes())}:${pad(dateObj.getSeconds())}` +
    `.${String(dateObj.getMilliseconds()).padStart(3, "0")}`
  );
}

function normalizeResponse(res = {}) {
  return {
    type:   res.type   || "success",
    action: res.action || null,
    message: res.message || null,
    ...res,
  };
}

// ─────────────────────────────────────────────────────────────
// UI MAPPING  (attendance_state → nút + badge)
// Đồng bộ với compute_attendance_state() trong service.py
// ─────────────────────────────────────────────────────────────

const STATE_UI = {
  not_started: {
    btnText:  "🔳 XÁC THỰC CHẤM CÔNG",
    btnClass: "btn-primary",
    disabled: false,
    badge:    null,
  },
  working_regular: {
    btnText:  "🔳 XÁC NHẬN HẾT CA HÀNH CHÍNH",
    btnClass: "btn-primary",
    disabled: false,
    badge:    { cls: "status-warning", text: "🟢 Đang làm ca chính" },
  },
  regular_done: {
    btnText:  "✅ Đã hoàn thành ca chính",
    btnClass: "btn-success",
    disabled: true,
    badge:    { cls: "status-success", text: "✅ Hoàn thành ca chính" },
  },
  regular_done_pending_ot_decision: {
    btnText:  "⏳ ĐANG CHỜ DUYỆT OT",
    btnClass: "btn-warning",
    disabled: true,
    badge:    { cls: "status-warning", text: "⏳ Chờ duyệt tăng ca" },
  },
  lunch_break: {
    btnText:  "⏸️ ĐANG NGHỈ TRƯA",
    btnClass: "btn-warning",
    disabled: true,
    badge:    { cls: "status-warning", text: "⏸️ Nghỉ trưa" },
  },
  // pre_ot_rest có 2 sub-state — button_enabled từ server quyết định
  pre_ot_rest: {
    btnText:  "🔳 XÁC THỰC TĂNG CA",   // enabled khi approved, chưa check-in OT
    btnClass: "btn-primary",
    disabled: true,                     // server sẽ override nếu cần disable
    badge:    { cls: "status-warning", text: "🟡 Nghỉ trước tăng ca" },
  },
  working_overtime: {
    btnText:  "🔳 XÁC NHẬN KẾT THÚC TĂNG CA",
    btnClass: "btn-primary",
    disabled: false,
    badge:    { cls: "status-warning", text: "🟣 Đang tăng ca" },
  },
  completed: {
    btnText:  "✅ ĐÃ HOÀN THÀNH CÔNG VIỆC",
    btnClass: "btn-success",
    disabled: true,
    badge:    { cls: "status-success", text: "🏁 Hoàn tất ngày công" },
  },
  holiday_off: {
    btnText:  "🛌 Đã ghi nhận nghỉ lễ",
    btnClass: "btn-success",
    disabled: true,
    badge:    { cls: "status-success", text: "🎉 Nghỉ lễ" },
  },
  weekend_off: {
    btnText:  "🛌 Đã ghi nhận nghỉ cuối tuần",
    btnClass: "btn-success",
    disabled: true,
    badge:    { cls: "status-success", text: "🛌 Nghỉ cuối tuần" },
  },
  absent: {
    btnText:  "❌ Vắng mặt",
    btnClass: "btn-danger",
    disabled: true,
    badge:    { cls: "status-danger", text: "❌ Vắng mặt" },
  },
  leave: {
    btnText:  "📋 Đang nghỉ phép",
    btnClass: "btn-warning",
    disabled: true,
    badge:    { cls: "status-warning", text: "📋 Nghỉ phép" },
  },
};

// ─────────────────────────────────────────────────────────────
// MAIN CLASS
// ─────────────────────────────────────────────────────────────

export class Attendance {

  // ── Lấy state hiện tại từ API ─────────────────────────────
  static async fetchCurrentState() {
    try {
      const remote  = await AttendanceAPI.getEmployeeAttendanceState();
      const payload = remote?.data || remote || {};
      attendanceStore.setToday(payload.today || payload);
      return payload;
    } catch (_) {
      return null;
    }
  }

  // ── Gọi API chấm công ─────────────────────────────────────
  static async submit(payload = {}) {
    attendanceStore.setSubmitting(true);
    attendanceStore.setError(null);
    try {
      const res = normalizeResponse(
        await AttendanceAPI.submitEmployeeAttendance(payload)
      );
      if (res.attendance) attendanceStore.setToday(res.attendance);
      return res;
    } catch (err) {
      attendanceStore.setError(err.message || "Không thể chấm công");
      throw err;
    } finally {
      attendanceStore.setSubmitting(false);
    }
  }

  // ── Xử lý toàn bộ luồng sau khi scan QR ──────────────────
  static _lockScanButtonTemporarily() {
    const btn = document.getElementById("attendanceBtn");
    if (!btn) return;
    btn.disabled = true;
    btn.classList.add("btn-disabled");
  }

static async handleQrScan(qrText, serverNow) {
  const simulatedNow = serverNow || toLocalISO(new Date());
  this._lockScanButtonTemporarily();

  let res;
  try { 
    res = await this.submit({ qr_text: qrText, simulated_now: simulatedNow });
  } catch (err) {
    console.error("QR Scan Error:", err);
    res = {
      type: "error",
      action: null,
      message: err.message || "Lỗi hệ thống",
    };
  }
  await this._handleResponse(res, qrText, simulatedNow);
}

  // ── Dispatcher theo action ────────────────────────────────
  static async _handleResponse(res, qrText, simulatedNow) {
    const action = res?.action;

    switch (action) {

      case "check_in": {
        const toastFn = res.type === "warning" ? Toast.warning : Toast.success;
        (toastFn || Toast.success)(res.message || "Check-in thành công");
        await this._reloadUI();
        break;
      }

      case "check_out": {
        Toast.success(res.message || "Check-out thành công");
        if (res.requires_overtime_decision) {
          await this._askOvertimeDecision(qrText, simulatedNow);
        } else {
          await this._reloadUI();
        }
        break;
      }

      case "check_in_overtime": {
        Toast.success(res.message || "Check-in OT thành công");
        await this._reloadUI();
        break;
      }

      case "check_out_overtime": {
        Toast.success(
          res.message || `Check-out OT thành công. Tăng ca: ${res.overtime_hours}h`
        );
        await this._reloadUI();
        break;
      }

      case "early_checkout_prompt": {
        const earlyMins = res.flags?.early_minutes || res.early_minutes || 0;
        const confirm   = await Swal.fire({
          icon:              "question",
          title:             "Tan ca nghỉ sớm?",
          text:              res.message || `Bạn sẽ về sớm ${earlyMins} phút.`,
          showCancelButton:  true,
          confirmButtonText: "Có, về sớm",
          cancelButtonText:  "Không, tiếp tục làm",
        });

        if (confirm.isConfirmed) {
          const earlyRes = await this.submit({
            qr_text:                  qrText,
            simulated_now:            simulatedNow,
            early_checkout_confirmed: true,
          });
          Toast.warning(earlyRes.message || "Check-out sớm thành công");
          await this._reloadUI();
        }
        break;
      }

      case "holiday_work_prompt":
      case "weekend_work_prompt": {
        const isHoliday = action === "holiday_work_prompt";
        const confirm   = await Swal.fire({
          icon:              "question",
          title:             isHoliday ? "Ngày nghỉ lễ" : "Ngày nghỉ cuối tuần",
          text:              res.message || "Bạn có muốn đi làm hôm nay không?",
          showCancelButton:  true,
          confirmButtonText: "Có, đi làm",
          cancelButtonText:  "Không, nghỉ",
        });

        if (confirm.isConfirmed) {
          const workRes = await this.submit({
            qr_text:               qrText,
            simulated_now:         simulatedNow,
            confirm_work_on_offday: true,
          });
          Toast.success(workRes.message || "Check-in thành công");
        } else {
          const offRes = await this.submit({
            qr_text:           qrText,
            simulated_now:     simulatedNow,
            decline_offday_work: true,
          });
          const infoFn = Toast.info || Toast.success;
          infoFn(offRes.message || "Đã ghi nhận nghỉ");
        }
        await this._reloadUI();
        break;
      }

      case "holiday_off":
      case "weekend_off": {
        Toast.success(res.message || "Đã ghi nhận nghỉ");
        await this._reloadUI();
        break;
      }

      case "offer_overtime": {
        await this._askOvertimeDecision(qrText, simulatedNow);
        break;
      }

      case "overtime_request_created": {
        Toast.success(res.message || "Đã gửi yêu cầu tăng ca. Chờ phê duyệt.");
        await this._reloadUI();
        break;
      }

      case "complete_without_overtime": {
        Toast.success(res.message || "Đã hoàn tất ngày công.");
        await this._reloadUI();
        break;
      }

      case "ot_pending_approval": {
        const infoFn = Toast.info || Toast.success;
        infoFn(res.message || "Đang chờ duyệt tăng ca");
        this._updateOtStatusBox(res.message, "pending");
        break;
      }

      case "ot_approved_wait": {
        Toast.success(res.message || "OT đã được duyệt. Có thể xác thực tăng ca.");
        this._updateOtStatusBox(res.message, "approved");
        // Reload để button chuyển sang enabled
        await this._reloadUI();
        break;
      }

      case "pre_ot_rest": {
        Toast.success(res.message || "Đã xác thực tăng ca. Chờ đến 19:00 bắt đầu tính công.");
        await this._reloadUI();
        break;
      }

      case "already_completed":
      case "already_recorded": {
        const infoFn = Toast.info || Toast.success;
        infoFn(res.message || "Ngày công đã hoàn tất");
        break;
      }

      case "lunch_break": {
        const warnFn = Toast.warning || Toast.error;
        warnFn(res.message || "Đang trong giờ nghỉ trưa");
        break;
      }

      default: {
        if (res.type === "error") {
          Toast.error(res.message || "Có lỗi xảy ra");
        } else if (res.type === "warning") {
          const warnFn = Toast.warning || Toast.error;
          warnFn(res.message || "Yêu cầu xác nhận");
        } else if (res.message) {
          Toast.success(res.message);
          await this._reloadUI();
        }
        break;
      }
    }
  }

  // ── Hỏi OT decision ──────────────────────────────────────
  static async _askOvertimeDecision(qrText, simulatedNow) {
    const decision = await Swal.fire({
      icon:              "question",
      title:             "Đăng ký tăng ca?",
      text:              "Bạn có muốn đăng ký tăng ca hôm nay không?",
      showCancelButton:  true,
      confirmButtonText: "Có, đăng ký OT",
      cancelButtonText:  "Không, về thôi",
    });

    const otDecision = decision.isConfirmed ? "yes" : "no";
    const otRes      = await this.submit({
      qr_text:          qrText,
      simulated_now:    simulatedNow,
      overtime_decision: otDecision,
    });

    if (otRes.action === "overtime_request_created") {
      Toast.success(otRes.message || "Đã gửi yêu cầu tăng ca. Chờ phê duyệt.");
    } else if (otRes.action === "complete_without_overtime") {
      Toast.success(otRes.message || "Đã hoàn tất ngày công.");
    } else {
      Toast.success(otRes.message || "Đã ghi nhận lựa chọn.");
    }

    await this._reloadUI();
  }

  // ── Cập nhật ô trạng thái OT ─────────────────────────────
  static _updateOtStatusBox(message, status) {
    const box = document.getElementById("otRequestStatusBox");
    if (!box) return;
    box.style.display = "block";
    const icon        = status === "approved" ? "✅" : "⏳";
    box.innerHTML     = `<strong>${icon} ${message || ""}</strong>`;
  }

  // ── Cập nhật UI nút theo state ────────────────────────────
  // serverData: object từ /system/time (có button_text, button_enabled)
  static updateButtonUI(attendanceState, serverData = null) {
    const btn = document.getElementById("attendanceBtn");
    if (!btn) return;

    // Ưu tiên dữ liệu từ server (compute_attendance_state đã tính đúng)
    if (serverData && serverData.button_text) {
      btn.textContent = serverData.button_text;
      btn.disabled    = !serverData.button_enabled;
      btn.className   = "btn " + (
        serverData.button_enabled ? "btn-primary" : "btn-success"
      );
      if (!serverData.button_enabled) btn.classList.add("btn-disabled");

      // Gắn onclick nếu có thể scan
      if (serverData.can_scan && serverData.button_enabled) {
        btn.onclick = () => window.openScannerModal?.();
      } else {
        btn.onclick = null;
      }
    } else {
      // Fallback sang STATE_UI local
      const ui = STATE_UI[attendanceState] || STATE_UI["not_started"];
      btn.textContent = ui.btnText;
      btn.disabled    = ui.disabled;
      btn.className   = "btn " + (ui.btnClass || "btn-primary");
      if (ui.disabled) btn.classList.add("btn-disabled");
      if (!ui.disabled) btn.onclick = () => window.openScannerModal?.();
    }

    // Badge trạng thái
    const badgeEl = document.getElementById("attendanceStateBadge");
    if (badgeEl) {
      const ui = STATE_UI[attendanceState] || {};
      if (ui.badge) {
        badgeEl.className   = `status ${ui.badge.cls}`;
        badgeEl.textContent = ui.badge.text;
        badgeEl.style.display = "inline-block";
      } else {
        badgeEl.style.display = "none";
      }
    }
  }

  // ── updateUIRealtime — gọi sau khi /system/time trả về ───
  // FIXED: dùng server button_text thay vì switch cứng
  static updateUIRealtime(data) {
    const root = document.getElementById("attendanceRoot");
    if (root) {
      root.dataset.attendanceState = data.attendance_state;
      root.dataset.canCheckIn      = data.can_check_in  ? "1" : "0";
      root.dataset.canCheckOut     = data.can_check_out ? "1" : "0";
    }

    this.updateButtonUI(data.attendance_state, data);
    this._updateBadge(data.attendance_state);

    // Cập nhật giờ công
    const workText = document.getElementById("workHoursText");
    if (workText) {
      const reg = parseFloat(data.regular_hours  || 0);
      const ot  = parseFloat(data.overtime_hours || 0);
      let   text = `Công hôm nay: ${this._fmtH(reg)}`;
      if (ot > 0) text += ` + OT ${this._fmtH(ot)}`;
      workText.textContent = text;
    }

    // Cập nhật message nếu có
    if (data.message) this._updateOtStatusBox(data.message, data.overtime_status?.toLowerCase());
  }
  static updateBadgeUI(state) {
    this._updateBadge(state);
  }

  static _updateBadge(state) {
    const badge = document.getElementById("attendanceStateBadge");
    if (!badge) return;
    const ui = STATE_UI[state];
    if (ui?.badge) {
      badge.textContent     = ui.badge.text;
      badge.className       = `status ${ui.badge.cls}`;
      badge.style.display   = "inline-block";
    } else {
      badge.style.display   = "none";
    }
  }

  static _fmtH(h) {
    const hh = Math.floor(h);
    const mm = Math.round((h - hh) * 60);
    if (hh > 0 && mm > 0) return `${hh} giờ ${mm} phút`;
    if (hh > 0) return `${hh} giờ`;
    return `${mm} phút`;
  }

  // ── Cập nhật dòng giờ công ────────────────────────────────
  static updateWorkHours(regularHours = 0, overtimeHours = 0, otPreview = 0) {
    const el = document.getElementById("workHoursText");
    if (!el) return;

    const reg   = parseFloat(regularHours)  || 0;
    const ot    = parseFloat(overtimeHours) || parseFloat(otPreview) || 0;
    const total = reg + ot;

    let text = `Công hôm nay: ${this._fmtH(reg)}`;
    if (ot > 0) text += ` + OT ${this._fmtH(ot)}`;
    if (reg > 0 || ot > 0) text += ` = ${this._fmtH(total)}`;

    el.textContent = text;
  }

  // ── Xóa bản ghi chấm công ────────────────────────────────
  static async deleteRecord(dateIso) {
    try {
      const res = await AttendanceAPI.deleteEmployeeAttendance(dateIso);
      Toast.success(res.message || "Đã xóa bản ghi chấm công");
      return res;
    } catch (err) {
      Toast.error(err.message || "Không thể xóa bản ghi");
      return null;
    }
  }

  // ── Reload UI ─────────────────────────────────────────────
  static async _reloadUI() {
    window.location.reload();
  }
}