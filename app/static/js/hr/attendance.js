(() => {
  const state = { rows: [], selectedAttendanceId: null, selectedEmployeeId: null };
  const $ = (s) => document.querySelector(s);

  const showToast = (message) => {
    const toast = $("#hrToast");
    toast.textContent = message;
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 2200);
  };

  const query = () => {
    const p = new URLSearchParams();
    ["search", "department_id", "status", "month", "year", "shift_type"].forEach((k) => {
      const el = {
        search: "#searchInput", department_id: "#departmentFilter", status: "#statusFilter",
        month: "#monthFilter", year: "#yearFilter", shift_type: "#shiftTypeFilter"
      }[k];
      const value = $(el)?.value;
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

  const fmtDateTime = (v) => v ? new Date(v).toLocaleString("vi-VN") : "--";

  const renderTable = () => {
    const body = $("#attendanceTableBody");
    body.innerHTML = state.rows.map((r) => `
      <tr>
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

  const renderBreakdown = (d) => {
    const b = d.breakdown || {};
    const root = $("#attendanceBreakdown");
    root.innerHTML = [
      ["Ngày công chuẩn", b.standard_work_days], ["Ngày công thực tế", b.actual_work_days], ["Ngày nghỉ phép", b.leave_days],
      ["Ngày nghỉ không phép", b.unpaid_leave_days], ["Tổng giờ làm", b.total_working_hours], ["Tổng giờ tăng ca", b.total_overtime_hours],
      ["Tổng số lần đi muộn", b.late_count], ["Tổng số lần về sớm", b.early_count], ["Tổng số ngày bị phạt công", b.penalty_days]
    ].map(([k, v]) => `<dt>${k}</dt><dd>${v ?? "--"}</dd>`).join("");
  };

  const loadDetail = async () => {
    if (!state.selectedEmployeeId) return;
    const p = new URLSearchParams({ month: $("#monthFilter").value, year: $("#yearFilter").value });
    const data = await api(`/hr/api/attendance/${state.selectedEmployeeId}/detail?${p}`);
    renderBreakdown(data);
  };

  const loadAudit = async () => {
    if (!state.selectedAttendanceId) return;
    const logs = await api(`/hr/api/attendance/${state.selectedAttendanceId}/audit`);
    $("#attendanceAuditList").innerHTML = logs.map((x) => `<li><strong>${x.action}</strong><div>${x.description || ""}</div><small>${fmtDateTime(x.created_at)}</small></li>`).join("") || "<li>Chưa có log</li>";
  };

  const loadOT = async () => {
    const p = new URLSearchParams({ month: $("#monthFilter").value, year: $("#yearFilter").value });
    const rows = await api(`/hr/api/attendance/overtime?${p}`);
    $("#otList").innerHTML = rows.map((x) => `<li><strong>${x.employee_name}</strong> (${x.employee_code}) - ${x.overtime_hours}h<br>Lý do: ${x.reason}<div class="actions"><button class="btn btn-sm" data-action="approve-ot" data-id="${x.attendance_id}">Duyệt</button> <button class="btn btn-sm" data-action="reject-ot" data-id="${x.attendance_id}">Từ chối</button></div></li>`).join("") || "<li>Không có yêu cầu OT</li>";
  };

  const loadAbnormal = async () => {
    const p = new URLSearchParams({ month: $("#monthFilter").value, year: $("#yearFilter").value });
    const rows = await api(`/hr/api/attendance/abnormal?${p}`);
    $("#abnormalList").innerHTML = rows.map((x) => `<li><strong>${x.employee_name}</strong> (${x.employee_code}) - ${x.work_date}<br>${x.status_label}<div class="actions"><button class="btn btn-sm" data-action="select" data-id="${x.attendance_id || ''}" data-emp="${x.employee_id}">Xác nhận hợp lệ</button></div></li>`).join("") || "<li>Không có bất thường</li>";
  };

  const loadMain = async () => {
    const data = await api(`/hr/api/attendance?${query()}`);
    state.rows = data.items || [];
    renderTable();
    renderSummary(data.summary || {});
    await loadOT();
    await loadAbnormal();
  };

  const initMeta = async () => {
    const meta = await api("/hr/api/attendance/meta");
    const dep = $("#departmentFilter");
    dep.innerHTML = '<option value="">Tất cả</option>' + (meta.departments || []).map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
    $("#statusFilter").innerHTML = (meta.attendance_statuses || []).map((s) => `<option value="${s.value}">${s.label}</option>`).join("");
    $("#shiftTypeFilter").innerHTML = (meta.shift_types || []).map((s) => `<option value="${s.value}">${s.label}</option>`).join("");

    const now = new Date();
    $("#monthFilter").innerHTML = Array.from({ length: 12 }, (_, i) => `<option value="${i+1}" ${i+1===now.getMonth()+1?"selected":""}>${i+1}</option>`).join("");
    $("#yearFilter").innerHTML = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 2 + i).map((y) => `<option value="${y}" ${y===now.getFullYear()?"selected":""}>${y}</option>`).join("");
  };

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    try {
      if (action === "select") {
        state.selectedAttendanceId = Number(btn.dataset.id) || null;
        state.selectedEmployeeId = Number(btn.dataset.emp);
        $("#attendanceId").value = state.selectedAttendanceId || "";
        await loadDetail();
        await loadAudit();
      }
      if (action === "approve-ot" || action === "reject-ot") {
        await api(`/hr/api/attendance/overtime/${btn.dataset.id}/review`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: action === "approve-ot" ? "approve" : "reject" })
        });
        showToast("Đã xử lý tăng ca");
        await loadMain();
      }
    } catch (err) { showToast(err.message); }
  });

  document.querySelectorAll("#searchInput,#departmentFilter,#statusFilter,#monthFilter,#yearFilter,#shiftTypeFilter").forEach((el) => {
    el.addEventListener(el.id === "searchInput" ? "input" : "change", () => loadMain().catch((e) => showToast(e.message)));
  });

  $("#attendanceAdjustForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.selectedAttendanceId) return showToast("Chọn bản ghi trước khi lưu");
    try {
      await api(`/hr/api/attendance/${state.selectedAttendanceId}/adjust`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          check_in: $("#adjustCheckIn").value ? new Date($("#adjustCheckIn").value).toISOString() : null,
          check_out: $("#adjustCheckOut").value ? new Date($("#adjustCheckOut").value).toISOString() : null,
          status: $("#adjustStatus").value,
          note: $("#adjustNote").value,
        })
      });
      showToast("Đã cập nhật chấm công");
      await loadMain();
      await loadAudit();
      await loadDetail();
    } catch (err) { showToast(err.message); }
  });

  $("#btnExportAttendance").addEventListener("click", () => {
    const p = new URLSearchParams({
      month: $("#monthFilter").value, year: $("#yearFilter").value,
      scope: $("#exportScopeFilter").value,
      format: $("#exportFormatFilter").value,
      department_id: $("#departmentFilter").value
    });
    window.open(`/hr/api/attendance/export?${p.toString()}`, "_blank");
  });

  ["#btnProcessNow", "#btnAbnormalShortcut"].forEach((id) => $(id)?.addEventListener("click", () => document.querySelector("#abnormalList")?.scrollIntoView({ behavior: "smooth" })));
  $("#btnApproveOTShortcut")?.addEventListener("click", () => document.querySelector("#otList")?.scrollIntoView({ behavior: "smooth" }));
  $("#btnSaveAudit")?.addEventListener("click", () => loadAudit().then(() => showToast("Đã tải lịch sử thay đổi")));

  initMeta().then(loadMain).catch((err) => showToast(err.message));
})();
