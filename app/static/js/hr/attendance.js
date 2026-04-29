(() => {
  const state = {
    rows: [],
    selectedAttendanceId: null,
    selectedEmployeeId: null,
    selectedRecord: null,
    editMode: false,
    filters: { abnormalOnly: false, overtimeOnlyPending: false },
  };

  const $ = (s) => document.querySelector(s);
  const appDialogs = {
    confirm: (options) => {
      if (window.appDialogs?.confirm) return window.appDialogs.confirm(options);
      return Promise.resolve({ confirmed: window.confirm(options?.text || options?.title || "Xác nhận thao tác?"), reason: "" });
    },
    success: (options) => {
      if (window.appDialogs?.success) return window.appDialogs.success(options);
      return showMessage(options?.text || options?.title || "Thành công", "success");
    },
    error: (options) => {
      if (window.appDialogs?.error) return window.appDialogs.error(options);
      return showMessage(options?.text || options?.title || "Có lỗi xảy ra", "error");
    },
    prompt: (options) => {
      if (window.appDialogs?.prompt) return window.appDialogs.prompt(options);
      const value = window.prompt(options?.label || options?.title || "Nhập dữ liệu", "");
      return Promise.resolve({ confirmed: value !== null, value: value || "" });
    },
  };
  const showMessage = (message, type = "info") => {
    if (window.Swal) {
      return Swal.fire({ icon: type, text: message, confirmButtonText: "Đã hiểu" });
    }
    if (window.showToast) window.showToast(message, type === "error" ? "danger" : type);
  };

  const toLocalInputDateTime = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  };

  const query = () => {
    const p = new URLSearchParams();
    const map = {
      search: "#searchInput", department_id: "#departmentFilter", status: "#statusFilter",
      month: "#monthFilter", year: "#yearFilter", shift_type: "#shiftTypeFilter",
    };
    Object.entries(map).forEach(([k, sel]) => {
      const value = $(sel)?.value;
      if (value) p.set(k, value);
    });
    return p.toString();
  };

  const api = async (url, options = {}) => {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Yêu cầu thất bại");
    return data;
  };
  const fmtDateTime = (v) => (v ? new Date(v).toLocaleString("vi-VN") : "--");

  const toggleAdjustForm = (enabled) => {
    ["#adjustCheckIn", "#adjustCheckOut", "#adjustStatus", "#adjustNote"].forEach((id) => {
      const el = $(id);
      if (el) el.disabled = !enabled;
    });
    state.editMode = enabled;
  };

  const renderTable = () => {
    const body = $("#attendanceTableBody");
    let rows = state.rows;
    if (state.filters.abnormalOnly) rows = rows.filter((x) => x.is_abnormal);
    body.innerHTML = rows.map((r) => `
      <tr data-attendance-id="${r.attendance_id || ''}" class="${state.selectedAttendanceId === r.attendance_id ? 'is-selected' : ''}">
        <td>${r.employee_code}</td><td>${r.employee_name}</td><td>${r.department}</td><td>${r.position}</td>
        <td>${r.work_date}</td><td>${fmtDateTime(r.check_in)}</td><td>${fmtDateTime(r.check_out)}</td>
        <td>${r.working_hours}</td><td>${r.overtime_hours}</td><td>${r.late_or_early ? "Có" : "Không"}</td>
        <td><span class="badge ${r.status_badge}">${r.status_label}</span></td>
        <td><button class="btn btn-sm" data-action="select" data-id="${r.attendance_id || ''}" data-emp="${r.employee_id}">Chọn</button></td>
      </tr>
    `).join("");
  };

  const renderSummary = (sum) => {
    $("#sumPresent").textContent = sum.today_present || 0;
    $("#sumLate").textContent = sum.late_count || 0;
    $("#sumLeave").textContent = sum.leave_count || 0;
    $("#sumOtPending").textContent = sum.overtime_pending || 0;
    $("#sumAbnormal").textContent = sum.abnormal_count || 0;
    $("#abnormalShortcutCard").hidden = !sum.has_abnormal;
  };

  const renderBreakdown = (data) => {
    const b = data.breakdown || {};
    $("#attendanceBreakdown").innerHTML = [
      ["Ngày công chuẩn", b.standard_work_days], ["Ngày công thực tế", b.actual_work_days], ["Ngày nghỉ phép", b.leave_days],
      ["Ngày nghỉ không phép", b.unpaid_leave_days], ["Tổng số giờ làm", b.total_working_hours], ["Tổng số giờ tăng ca", b.total_overtime_hours],
      ["Số lần đi muộn", b.late_count], ["Số lần về sớm", b.early_count], ["Số ngày bị phạt công", b.penalty_days],
    ].map(([k, v]) => `<dt>${k}</dt><dd>${v ?? '--'}</dd>`).join("");
  };

  const renderRecordToPanelA = (record) => {
    state.selectedRecord = record;
    $("#attendanceId").value = record?.attendance_id || "";
    $("#adjustCheckIn").value = toLocalInputDateTime(record?.check_in);
    $("#adjustCheckOut").value = toLocalInputDateTime(record?.check_out);
    $("#adjustStatus").value = record?.status || "normal";
    $("#adjustNote").value = "";
    toggleAdjustForm(false);
  };

  const loadDetailPanels = async () => {
    if (!state.selectedAttendanceId || !state.selectedEmployeeId) return;
    const month = $("#monthFilter").value;
    const year = $("#yearFilter").value;

    const [record, detail, logs] = await Promise.all([
      api(`/hr/api/attendance/${state.selectedAttendanceId}/record`),
      api(`/hr/api/attendance/${state.selectedEmployeeId}/detail?${new URLSearchParams({ month, year })}`),
      api(`/hr/api/attendance/${state.selectedAttendanceId}/audit`),
    ]);

    renderRecordToPanelA(record);
    renderBreakdown(detail);
    $("#attendanceAuditList").innerHTML = logs.map((x) =>
      `<li><strong>${x.action}</strong><div>${x.description || ''}</div><small>${fmtDateTime(x.created_at)}</small></li>`
    ).join("") || "<li>Chưa có log</li>";
  };

  const loadOT = async () => {
    const p = new URLSearchParams({ month: $("#monthFilter").value, year: $("#yearFilter").value });
    const rows = await api(`/hr/api/attendance/overtime?${p}`);
    const isPendingHr = (status) => status === "pending_hr";
    const hrStatusLabel = (status) => {
      if (status === "pending_hr") return "Chờ HR duyệt";
      if (status === "pending_admin") return "HR đã duyệt (chờ Admin)";
      if (status === "approved") return "Đã duyệt";
      if (status === "rejected") return "Đã từ chối";
      return status || "--";
    };
    const filtered = state.filters.overtimeOnlyPending ? rows.filter((x) => isPendingHr(x.hr_status)) : rows;
    const fmtDateTime = (value) => {
      if (!value) return "--";
      const d = new Date(value);
      return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()} - ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    };
    const fmtHM = (value) => value ? new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }) : "--";
    $("#otList").innerHTML = filtered.map((x) => `
      <li>
        <strong>${x.employee_name}</strong> (${x.employee_code})<br>
        Phòng ban: ${x.department || "--"}<br>
        Ngày OT: ${x.date} • Gửi lúc: ${fmtDateTime(x.created_at)}<br>
        OT dự kiến: ${fmtHM(x.start_ot_time)} → ${fmtHM(x.end_ot_time)} • Số giờ OT: ${Number(x.overtime_hours || 0).toFixed(2)}h<br>
        Lý do: ${x.reason}<br>
        Quản lý duyệt: ${x.manager_approved ? 'Đã duyệt' : 'Chưa duyệt'} • Trạng thái: ${hrStatusLabel(x.hr_status)}
        <div class="actions">
          ${isPendingHr(x.hr_status)
            ? `<button class="btn btn-sm" data-action="approve-ot" data-id="${x.attendance_id}">Duyệt</button>
               <button class="btn btn-sm" data-action="reject-ot" data-id="${x.attendance_id}">Từ chối</button>
               <button class="btn btn-sm btn-danger" data-action="reset-ot" data-id="${x.attendance_id}">Xóa</button>`
            : `<span>${x.hr_status === "rejected" ? "Đã từ chối" : "Đã duyệt"}</span> <button class="btn btn-sm btn-danger" data-action="reset-ot" data-id="${x.attendance_id}">Xóa</button>`}
        </div>
      </li>
    `).join("") || "<li>Không có yêu cầu OT</li>";
  };

  const loadAbnormal = async () => {
    const p = new URLSearchParams({ month: $("#monthFilter").value, year: $("#yearFilter").value });
    const rows = await api(`/hr/api/attendance/abnormal?${p}`);
    $("#abnormalList").innerHTML = rows.map((x) => `
      <li>
        <strong>${x.employee_name}</strong> (${x.employee_code}) - ${x.work_date}<br>
        ${x.status_label}
        <div class="actions">
          <button class="btn btn-sm" data-action="confirm-abnormal" data-id="${x.attendance_id}">Xác nhận hợp lệ</button>
          <button class="btn btn-sm" data-action="manual-abnormal" data-id="${x.attendance_id}" data-emp="${x.employee_id}">Chỉnh sửa thủ công</button>
          <button class="btn btn-sm" data-action="reject-abnormal" data-id="${x.attendance_id}">Từ chối xác nhận</button>
        </div>
      </li>
    `).join("") || "<li>Không có bất thường</li>";
  };

  const loadMain = async () => {
    const data = await api(`/hr/api/attendance?${query()}`);
    state.rows = data.items || [];

    renderSummary(data.summary || {});
    renderTable();
    await Promise.all([loadOT(), loadAbnormal()]);
    if (state.selectedAttendanceId) await loadDetailPanels();
  };

  const initMeta = async () => {
    const meta = await api("/hr/api/attendance/meta");
    $("#departmentFilter").innerHTML = '<option value="">Tất cả</option>' + (meta.departments || []).map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
    $("#statusFilter").innerHTML = (meta.attendance_statuses || []).map((s) => `<option value="${s.value}">${s.label}</option>`).join("");
    $("#shiftTypeFilter").innerHTML = (meta.shift_types || []).map((s) => `<option value="${s.value}">${s.label}</option>`).join("");

    const now = new Date();
    $("#monthFilter").innerHTML = Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${i + 1 === now.getMonth() + 1 ? 'selected' : ''}>${i + 1}</option>`).join("");
    $("#yearFilter").innerHTML = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 2 + i).map((y) => `<option value="${y}" ${y === now.getFullYear() ? 'selected' : ''}>${y}</option>`).join("");
  };

  const reviewOvertime = async (attendanceId, action) => {
    const confirm = await appDialogs.confirm({
      title: action === "approve" ? "Duyệt tăng ca" : "Từ chối tăng ca",
      text: action === "approve" ? "Bạn có chắc muốn duyệt yêu cầu tăng ca này?" : "Bạn có chắc muốn từ chối yêu cầu tăng ca này?",
      icon: "question",
      confirmText: action === "approve" ? "Xác nhận duyệt" : "Xác nhận từ chối",
      requireReason: action === "reject",
      reasonLabel: "Lý do từ chối",
    });
    if (!confirm.confirmed) return;

    await api(`/hr/api/attendance/overtime/${attendanceId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, note: confirm.reason || null }),
    });
    await appDialogs.success({ title: action === "approve" ? "Duyệt thành công" : "Từ chối thành công" });
    await loadMain();
  };

  const resolveAbnormal = async (attendanceId, action) => {
    const config = {
      confirm_valid: { title: "Xác nhận hợp lệ", text: "Xác nhận bản ghi bất thường này là hợp lệ?", confirmText: "Xác nhận" },
      manual_edit: { title: "Chỉnh sửa thủ công", text: "Áp dụng dữ liệu chỉnh sửa ở Panel A cho bản ghi bất thường?", confirmText: "Áp dụng" },
      reject: { title: "Từ chối xác nhận", text: "Bạn có chắc muốn từ chối xác nhận bản ghi bất thường này?", confirmText: "Từ chối" },
    }[action];
    const result = await appDialogs.confirm({
      ...config,
      icon: "warning",
      requireReason: action === "reject",
      reasonLabel: "Lý do từ chối",
    });
    if (!result.confirmed) return;

    const payload = {
      action,
      note: result.reason || $("#adjustNote").value || null,
      check_in: action === "manual_edit" && $("#adjustCheckIn").value ? new Date($("#adjustCheckIn").value).toISOString() : null,
      check_out: action === "manual_edit" && $("#adjustCheckOut").value ? new Date($("#adjustCheckOut").value).toISOString() : null,
      status: action === "manual_edit" ? $("#adjustStatus").value : null,
    };

    await api(`/hr/api/attendance/abnormal/${attendanceId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await appDialogs.success({ title: "Xử lý bất thường thành công" });
    await loadMain();
  };

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    try {
      if (action === "select") {
        state.selectedAttendanceId = Number(btn.dataset.id) || null;
        state.selectedEmployeeId = Number(btn.dataset.emp);
        renderTable();
        await loadDetailPanels();
      } else if (action === "approve-ot") {
        await reviewOvertime(btn.dataset.id, "approve");
      } else if (action === "reject-ot") {
        await reviewOvertime(btn.dataset.id, "reject");
      } else if (action === "reset-ot") {
        const confirm = await Swal.fire({
          title: "Xóa yêu cầu tăng ca?",
          text: "Toàn bộ request, notification và trạng thái duyệt sẽ bị reset để test lại từ đầu.",
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "Xóa",
          cancelButtonText: "Hủy"
        });
        if (!confirm.isConfirmed) return;
        await api(`/hr/api/attendance/overtime/${btn.dataset.id}/reset`, { method: "POST" });
        await Swal.fire({ icon: "success", title: "Đã xóa OT request để test lại" });
        await loadMain();
      } else if (action === "confirm-abnormal") {
        await resolveAbnormal(btn.dataset.id, "confirm_valid");
      } else if (action === "manual-abnormal") {
        state.selectedAttendanceId = Number(btn.dataset.id) || null;
        state.selectedEmployeeId = Number(btn.dataset.emp);
        renderTable();
        await loadDetailPanels();
        toggleAdjustForm(true);
      } else if (action === "reject-abnormal") {
        await resolveAbnormal(btn.dataset.id, "reject");
      }
    } catch (err) {
      await showMessage(err.message, "error");
    }
  });

  const withDebounce = (fn, delay = 350) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  };

  document.querySelectorAll("#searchInput,#departmentFilter,#statusFilter,#monthFilter,#yearFilter,#shiftTypeFilter")
    .forEach((el) => el.addEventListener(el.id === "searchInput" ? "input" : "change", withDebounce(() => loadMain().catch((x) => showMessage(x.message, "error")))));

  $("#btnEditAttendance").addEventListener("click", async () => {
    if (!state.selectedAttendanceId) return showMessage("Vui lòng chọn bản ghi trước", "warning");
    toggleAdjustForm(true);
    await showMessage("Đã bật chế độ chỉnh sửa", "info");
  });

  $("#attendanceAdjustForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.selectedAttendanceId) return showMessage("Chọn bản ghi trước khi lưu", "warning");

    const confirmed = await appDialogs.confirm({
      title: "Lưu chỉnh sửa chấm công",
      text: "Bạn có chắc muốn cập nhật bản ghi chấm công này?",
      icon: "question",
      confirmText: "Lưu thay đổi",
    });
    if (!confirmed.confirmed) return;

    try {
      await api(`/hr/api/attendance/${state.selectedAttendanceId}/adjust`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          check_in: $("#adjustCheckIn").value ? new Date($("#adjustCheckIn").value).toISOString() : null,
          check_out: $("#adjustCheckOut").value ? new Date($("#adjustCheckOut").value).toISOString() : null,
          status: $("#adjustStatus").value,
          note: $("#adjustNote").value,
        }),
      });
      toggleAdjustForm(false);
      await appDialogs.success({ title: "Cập nhật thành công" });
      await loadMain();
    } catch (err) {
      await appDialogs.error({ title: "Cập nhật thất bại", text: err.message });
    }
  });

  $("#btnSaveAudit").addEventListener("click", async () => {
    if (!state.selectedAttendanceId) return showMessage("Chọn bản ghi trước khi lưu lịch sử", "warning");
    const input = await appDialogs.prompt({
      title: "Lưu lịch sử thay đổi",
      label: "Mô tả thay đổi",
      placeholder: "Ví dụ: cập nhật giờ vào theo biên bản xác minh...",
      confirmText: "Lưu lịch sử",
    });
    if (!input.confirmed) return;
    await api(`/hr/api/attendance/${state.selectedAttendanceId}/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: input.value }),
    });
    await appDialogs.success({ title: "Đã lưu lịch sử thay đổi" });
    await loadDetailPanels();
  });

  $("#btnExportAttendance").addEventListener("click", async () => {
    const confirm = await appDialogs.confirm({
      title: "Xuất bảng chấm công",
      text: "Hệ thống sẽ chuẩn bị file export theo bộ lọc hiện tại.",
      icon: "info",
      confirmText: "Bắt đầu export",
    });
    if (!confirm.confirmed) return;

    Swal.fire({ icon: "info", title: "Đang chuẩn bị file export...", timer: 1200, showConfirmButton: false });
    const p = new URLSearchParams({
      month: $("#monthFilter").value,
      year: $("#yearFilter").value,
      scope: $("#exportScopeFilter").value,
      format: $("#exportFormatFilter").value,
      department_id: $("#departmentFilter").value,
    });
    window.open(`/hr/api/attendance/export?${p.toString()}`, "_blank");
    await appDialogs.success({ title: "Đã tạo yêu cầu export" });
  });

  $("#btnApproveOTShortcut")?.addEventListener("click", async () => {
    state.filters.overtimeOnlyPending = true;
    await loadOT();
    $("#otList")?.scrollIntoView({ behavior: "smooth" });
  });
  ["#btnProcessNow", "#btnAbnormalShortcut"].forEach((id) => {
    $(id)?.addEventListener("click", async () => {
      state.filters.abnormalOnly = true;
      renderTable();
      $("#abnormalList")?.scrollIntoView({ behavior: "smooth" });
    });
  });

  initMeta().then(loadMain).catch((err) => showMessage(err.message, "error"));
})();
