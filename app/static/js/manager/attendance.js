let allRows = [];
function formatStatus(status) {
  const map = {
    ON_TIME: '🟢 Đúng giờ',
    PRESENT: '🟢 Đúng giờ',
    LATE: '🟡 Đi muộn',
    ABSENT: '🔴 Chưa vào ca',
    LEAVE: '🌴 Nghỉ phép'
  };
  return map[status] || status;
}

function getFilters() {
  return {
    keyword: document.getElementById('filterKeyword')?.value || '',
    department: document.getElementById('filterDepartment')?.value || '',
    date: document.getElementById('filterDate')?.value || '',
    status: document.getElementById('filterStatus')?.value || '',
    overtime: document.getElementById('filterOvertime')?.checked ? '1' : '0',
    abnormal: document.getElementById('filterAbnormal')?.checked ? '1' : '0'
  };
}
function renderRows() {
  const body = document.getElementById('attendance-body');
  body.innerHTML = allRows.map((row) => `
      <tr>
        <td>${row.employee_code}</td>
        <td>${row.name}</td>
        <td>${row.department || '--'}</td>
        <td>${row.check_in || '--:--'}</td>
        <td>${row.check_out || '--:--'}</td>
        <td>${Number(row.regular_hours || 0).toFixed(2)}</td>
        <td>${Number(row.overtime_hours || 0).toFixed(2)}</td>
        <td><span class="status ${row.status}">${formatStatus(row.status)}</span></td>
        <td>${row.abnormal ? '⚠️' : '-'}</td>
        <td>
          <button data-att-detail="${row.employee_id}">Chi tiết</button>
          ${row.abnormal && row.attendance_id ? `<button data-att-confirm="${row.attendance_id}">Xác nhận hợp lệ</button><button data-att-hr="${row.attendance_id}">Yêu cầu HR</button>` : ''}
        </td>
      </tr>`).join('');
}
function renderSummary(summary) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val || 0);
  };
  set('sum_checked_in', summary.checked_in);
  set('sum_not_checked_in', summary.not_checked_in);
  set('sum_late', summary.late);
  set('sum_leave', summary.on_leave);
  set('sum_overtime', summary.overtime);
  set('sum_abnormal', summary.abnormal);
}

async function loadAttendance() {
  const filters = getFilters();
  allRows = await ManagerAPI.departmentAttendanceList(filters);
  renderRows();
  const summary = await ManagerAPI.departmentAttendanceSummary(filters);
  renderSummary(summary);
}

async function loadOvertimeRequests() {
  const list = document.getElementById('ot-requests');
  if (!list) return;
  const rows = await ManagerAPI.overtimeRequests();
  list.innerHTML = rows.map((r) => `<li>
    <strong>${r.employee_name}</strong> - ${r.overtime_date} (${r.overtime_hours}h)<br>
    Lý do: ${r.reason || '--'}
    <div>
      <button data-ot-action="approve" data-id="${r.id}">Duyệt</button>
      <button data-ot-action="reject" data-id="${r.id}">Từ chối</button>
    </div>
  </li>`).join('') || '<li>Không có yêu cầu OT chờ duyệt.</li>';
}



document.getElementById('btnFilter')?.addEventListener('click', async () => {
  try {
    await loadAttendance();
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không tải được dữ liệu attendance' });
  }
});

document.addEventListener('click', async (e) => {
  const btnDetail = e.target.closest('button[data-att-detail]');
  if (btnDetail) {
    try {
      const detail = await ManagerAPI.departmentAttendanceDetail(btnDetail.dataset.attDetail, getFilters());
      await Swal.fire({
        title: `Attendance - ${detail.employee_name}`,
        html: `
          <div style="text-align:left">
            <p>Check-in: ${detail.check_in || '--'}</p>
            <p>Check-out: ${detail.check_out || '--'}</p>
            <p>Tổng giờ làm: ${detail.worked_hours || 0}</p>
            <p>Overtime: ${detail.overtime_hours || 0}</p>
            <p>Leave liên quan: ${detail.leave_record ? `${detail.leave_record.from_date} → ${detail.leave_record.to_date}` : '--'}</p>
          </div>`
      });
    } catch (err) {
      await Swal.fire({ icon: 'error', title: err.message });
    }
    return;
  }

  const abnormalAction = e.target.closest('button[data-att-confirm],button[data-att-hr]');
  if (abnormalAction) {
    const attendanceId = abnormalAction.dataset.attConfirm || abnormalAction.dataset.attHr;
    const action = abnormalAction.dataset.attConfirm ? 'confirm_valid' : 'request_hr';
    const title = action === 'confirm_valid' ? 'Xác nhận hợp lệ?' : 'Yêu cầu HR xử lý?';
    const prompt = await Swal.fire({ title, input: 'text', inputPlaceholder: 'Ghi chú', showCancelButton: true });
    if (!prompt.isConfirmed) return;
    await ManagerAPI.reviewAbnormalAttendance(attendanceId, action, prompt.value || '');
    await Swal.fire({ icon: 'success', title: 'Đã xử lý bất thường' });
    await loadAttendance();
    return;
  }

  const btnOT = e.target.closest('button[data-ot-action]');
  if (!btnOT) return;
  const action = btnOT.dataset.otAction;
  const id = btnOT.dataset.id;
  let note = '';
  if (action === 'reject') {
    const result = await Swal.fire({ title: 'Lý do từ chối', input: 'text', showCancelButton: true });
    if (!result.isConfirmed) return;
    note = result.value || '';
  } else {
    const confirm = await Swal.fire({ icon: 'question', title: 'Duyệt yêu cầu OT này?', showCancelButton: true });
    if (!confirm.isConfirmed) return;
  }
  await ManagerAPI.reviewOvertime(id, action, note);
  await Swal.fire({ icon: 'success', title: 'Xử lý yêu cầu OT thành công' });
  await loadOvertimeRequests();
});

loadAttendance();
loadOvertimeRequests();