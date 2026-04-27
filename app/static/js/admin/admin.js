async function api(url, options = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(e.error || 'Request failed');
  }
  return r.headers.get('content-type')?.includes('application/json') ? r.json() : r.text();
}

const now = new Date();
const LABELS = {
  employment: { probation: 'Thử việc', permanent: 'Chính thức', intern: 'Thực tập', contract: 'Hợp đồng' },
  working: { active: 'Đang làm việc', probation: 'Thử việc', on_leave: 'Tạm nghỉ', pending_resignation: 'Chờ nghỉ việc', resigned: 'Đã nghỉ việc', inactive: 'Inactive', terminated: 'Chấm dứt', retired: 'Nghỉ hưu' },
  account: { active: 'Active', locked: 'Locked', inactive: 'Inactive', pending: 'Pending' }
};

function setDefaults() {
  const m = document.getElementById('month');
  const y = document.getElementById('year');
  if (m && !m.value) m.value = now.getMonth() + 1;
  if (y && !y.value) y.value = now.getFullYear();
}

async function loadDepartmentsSelect() {
  const el = document.getElementById('department');
  if (!el) return;
  const rows = await api('/api/departments');
  el.innerHTML = '<option value="">Tất cả phòng ban</option>' + rows.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
}

function fmtDate(v) { return v ? new Date(v).toLocaleDateString('vi-VN') : '--'; }
function esc(v) { return (v ?? '').toString().replace(/[&<>"]/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[s])); }

async function loadDashboard() {
  setDefaults();
  const m = month.value, y = year.value, d = department?.value || '';
  const data = await api(`/api/dashboard/overview?month=${m}&year=${y}&department_id=${d}`);
  const employeeStats = document.getElementById('employeeStats'); const attendanceStats = document.getElementById('attendanceStats');
  const salaryStats = document.getElementById('salaryStats'); const activities = document.getElementById('activities');
  if (!employeeStats || !attendanceStats || !salaryStats || !activities) return;
  employeeStats.innerHTML = `<p><strong>👥 Nhân sự</strong></p><p>Tổng nhân sự: ${data.employee.total ?? 0}</p><p>Nhân viên mới: ${data.employee.new ?? 0}</p><p>Nghỉ việc: ${data.employee.resigned ?? 0}</p><p>Sắp hết hạn hợp đồng: ${data.employee.expiring_contract ?? 0}</p>`;
  attendanceStats.innerHTML = `<p>Tỉ lệ chuyên cần toàn công ty: ${data.attendance.attendance_rate ?? 0}%</p><p>Phòng ban đi muộn cao nhất: ${data.attendance.hotspot_department?.department_id ?? 'N/A'}</p><p>Tổng lượt đi muộn: ${data.attendance.late_count ?? 0}</p><p>Tổng lượt vắng mặt: ${data.attendance.absent_count ?? 0}</p>`;
  salaryStats.innerHTML = `<p>Tổng quỹ lương tháng hiện tại: ${Number(data.salary.total_salary ?? 0).toLocaleString('vi-VN')} VND</p><p>Số lượng bản ghi lương: ${data.salary.salary_records ?? 0}</p><p>Thuế & Bảo hiểm: Theo dữ liệu bảng lương hiện tại</p>`;
  activities.innerHTML = data.activities.map(a => `<li>[${a.time || '--'}] ${a.action}</li>`).join('') || '<li>Chưa có dữ liệu.</li>';
}

async function loadEmployeeMeta() {
  const meta = await api('/api/admin/employees/meta');
  const map = [
    ['filterDepartment', meta.departments || []],
    ['filterPosition', meta.positions || []],
    ['filterRole', meta.roles || []]
  ];
  map.forEach(([id, rows]) => {
    const el = document.getElementById(id); if (!el) return;
    const first = el.options[0]?.outerHTML || '<option value="">--</option>';
    el.innerHTML = first + rows.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('');
  });
}

function employeeFiltersAsQuery() {
  const get = (id) => document.getElementById(id)?.value?.trim() || '';
  const params = new URLSearchParams();
  const keyword = get('filterName');
  const mapping = {
    keyword,
    name: get('filterName'), employee_code: get('filterCode'), email: get('filterEmail'),
    department_id: get('filterDepartment'), position_id: get('filterPosition'), role_id: get('filterRole'),
    working_status: get('filterWorkingStatus'), employment_type: get('filterEmploymentType'), probation: get('filterProbation'),
    hire_date_from: get('filterHireFrom'), hire_date_to: get('filterHireTo'),
    month: get('month'), year: get('year'), top_department_id: get('department')
  };
  Object.entries(mapping).forEach(([k, v]) => { if (v) params.set(k, v); });
  return params.toString();
}

function renderSummaryCards(sum) {
  const wrap = document.getElementById('employeeSummaryCards'); if (!wrap) return;
  const cards = [
    ['Tổng nhân sự', sum.total], ['Đang làm việc', sum.working], ['Thử việc', sum.probation],
    ['Nghỉ hôm nay', sum.leave_today], ['Sắp hết hợp đồng', sum.expiring_contract], ['Inactive', sum.inactive]
  ];
  wrap.innerHTML = cards.map(([title, value]) => `<article class="summary-card"><h4>${title}</h4><p>${value ?? 0}</p></article>`).join('');
}

function renderAlertCards(items) {
  const wrap = document.getElementById('employeeAlertCards'); if (!wrap) return;
  wrap.innerHTML = items.map(n => `<article class="alert-card ${n.count > 0 ? 'is-active' : ''}"><h4>${esc(n.title)}</h4><p>${n.count}</p></article>`).join('');
}

function rowActions(employee) {
  if (!employee.user_id) return '<span class="muted">Chưa có tài khoản</span>';
  const lockBtn = employee.account_status === 'locked'
    ? `<button onclick="unlockEmployee(${employee.user_id})">Mở khóa</button>`
    : `<button onclick="lockEmployee(${employee.user_id})">Khóa tài khoản</button>`;
  return `
    <div class="table-actions">
      <button onclick="viewEmployeeDetail(${employee.id})">Xem chi tiết</button>
      <button onclick="editEmployee(${employee.id})">Chỉnh sửa</button>
      ${lockBtn}
      <button onclick="resetPassword(${employee.user_id})">Reset mật khẩu</button>
      <button onclick="transferEmployee(${employee.id})">Chuyển phòng ban</button>
      <button class="btn-danger" onclick="inactiveEmployee(${employee.id})">Set Inactive</button>
      <button onclick="reviewResignationAdmin(${employee.id})">Duyệt nghỉ việc</button>
    </div>`;
}

function renderEmployeeRows(rows) {
  const tr = document.getElementById('employeeRows'); if (!tr) return;
  tr.innerHTML = rows.length ? rows.map(e => `
    <tr>
      <td>${esc(e.employee_code)}</td>
      <td>${e.avatar ? `<img src="${esc(e.avatar)}" class="avatar">` : '<span class="avatar-fallback">👤</span>'}</td>
      <td>${esc(e.full_name)}</td>
      <td>${esc(e.email || '--')}</td>
      <td>${esc(e.phone || '--')}</td>
      <td>${esc(e.department || '--')}</td>
      <td>${esc(e.position || '--')}</td>
      <td>${esc(e.role || '--')}</td>
      <td>${fmtDate(e.hire_date)}</td>
      <td><span class="badge b-info">${esc(LABELS.employment[e.employment_type] || e.employment_type || '--')}</span></td>
      <td><span class="badge ${e.working_status === 'active' ? 'b-success' : e.working_status === 'on_leave' ? 'b-warning' : 'b-danger'}">${esc(LABELS.working[e.working_status] || e.working_status || '--')}</span></td>
      <td><span class="badge ${e.account_status === 'active' ? 'b-success' : e.account_status === 'locked' ? 'b-danger' : 'b-warning'}">${esc(LABELS.account[e.account_status] || e.account_status)}</span></td>
      <td>${rowActions(e)}</td>
    </tr>`).join('') : '<tr><td colspan="13">Không có dữ liệu nhân viên</td></tr>';
}
async function loadEmployees({ notify = false, isReset = false } = {}) {
  try {
    await Promise.allSettled([loadEmployeeMeta(), loadEmployeeSummary(), loadEmployeeAlerts()]);
    const q = employeeFiltersAsQuery();
    const rows = await api(`/api/admin/employees${q ? `?${q}` : ''}`);
    renderEmployeeRows(rows);
    if (rows.length === 0) {
      await Swal.fire({ icon: 'info', title: 'Không tìm thấy dữ liệu phù hợp' });
    } else if (notify) {
      await Swal.fire({ icon: 'success', title: isReset ? 'Đã xóa lọc và tải lại danh sách đầy đủ' : 'Lọc dữ liệu thành công' });
    }
  } catch (error) {
    await Swal.fire({ icon: 'error', title: 'Lỗi tải danh sách nhân viên', text: error.message || 'Query thất bại' });
  }
}

async function loadEmployeeSummary() { renderSummaryCards(await api('/api/admin/employees/summary')); }
async function loadEmployeeAlerts() { renderAlertCards(await api('/api/admin/employees/notifications')); }

async function addEmployee() {
  const html = `
    <div class="swal-form-grid">
      <input id="swFullName" class="swal2-input" placeholder="Họ tên">
      <input id="swDob" class="swal2-input" type="date" placeholder="Ngày sinh">
      <select id="swGender" class="swal2-input"><option value="male">Nam</option><option value="female">Nữ</option><option value="other">Khác</option></select>
      <input id="swAddress" class="swal2-input" placeholder="Địa chỉ">
      <input id="swEmail" class="swal2-input" placeholder="Email">
      <input id="swPhone" class="swal2-input" placeholder="Số điện thoại">
      <input id="swAvatar" class="swal2-input" placeholder="URL avatar">
      <input id="swEmpCode" class="swal2-input" placeholder="Mã nhân viên (optional)">
      <select id="swDepartment" class="swal2-input">${document.getElementById('filterDepartment').innerHTML}</select>
      <select id="swPosition" class="swal2-input">${document.getElementById('filterPosition').innerHTML}</select>
      <select id="swRole" class="swal2-input">${document.getElementById('filterRole').innerHTML}</select>
      <input id="swHireDate" class="swal2-input" type="date" placeholder="Ngày vào làm">
      <select id="swEmployment" class="swal2-input"><option value="probation">Thử việc</option><option value="permanent">Chính thức</option><option value="intern">Thực tập</option><option value="contract">Hợp đồng</option></select>
      <input id="swBasicSalary" class="swal2-input" type="number" placeholder="Lương cơ bản">
      <input id="swContractEnd" class="swal2-input" type="date" placeholder="Hạn hợp đồng">
      <input id="swUsername" class="swal2-input" placeholder="Username">
      <input id="swPassword" class="swal2-input" type="password" placeholder="Password khởi tạo">
      <select id="swAccountStatus" class="swal2-input"><option value="active">Active</option><option value="locked">Locked</option><option value="inactive">Inactive</option><option value="pending">Pending</option></select>
    </div>`;

  const { isConfirmed, value } = await Swal.fire({
    title: 'Thêm nhân viên mới', html, width: 900, showCancelButton: true,
    preConfirm: () => ({
      full_name: document.getElementById('swFullName').value,
      dob: document.getElementById('swDob').value,
      gender: document.getElementById('swGender').value,
      address: document.getElementById('swAddress').value,
      email: document.getElementById('swEmail').value,
      phone: document.getElementById('swPhone').value,
      avatar: document.getElementById('swAvatar').value,
      employee_code: document.getElementById('swEmpCode').value,
      department_id: Number(document.getElementById('swDepartment').value) || null,
      position_id: Number(document.getElementById('swPosition').value) || null,
      role_id: Number(document.getElementById('swRole').value) || null,
      hire_date: document.getElementById('swHireDate').value,
      employment_type: document.getElementById('swEmployment').value,
      basic_salary: document.getElementById('swBasicSalary').value,
      contract_end_date: document.getElementById('swContractEnd').value,
      username: document.getElementById('swUsername').value,
      password: document.getElementById('swPassword').value,
      account_status: document.getElementById('swAccountStatus').value
    })
  });
  if (!isConfirmed) return;
  await api('/api/admin/employees', { method: 'POST', body: JSON.stringify(value) });
  await Swal.fire({ icon: 'success', title: 'Đã thêm nhân viên' });
  loadEmployees();
}

async function viewEmployeeDetail(id) {
  const d = await api(`/api/admin/employees/${id}`);
  await Swal.fire({
    title: `Chi tiết: ${esc(d.full_name)}`,
    width: 920,
    html: `<div class="detail-grid">
      <div><b>Profile</b><p>Email: ${esc(d.email || '--')}</p><p>Phone: ${esc(d.phone || '--')}</p><p>Địa chỉ: ${esc(d.profile?.address || '--')}</p></div>
      <div><b>Attendance summary</b><p>Số ngày: ${d.attendance_summary?.total_days ?? 0}</p><p>Giờ làm: ${d.attendance_summary?.working_hours ?? 0}</p></div>
      <div><b>Leave summary</b><p>Pending: ${d.leave_summary?.pending ?? 0}</p><p>Approved: ${d.leave_summary?.approved ?? 0}</p></div>
      <div><b>Payroll summary</b><p>Lương net: ${(d.payroll_summary?.net_salary ?? 0).toLocaleString('vi-VN')}</p><p>Status: ${esc(d.payroll_summary?.status || '--')}</p></div>
      <div><b>Contract info</b><p>Mã: ${esc(d.contract_info?.contract_code || '--')}</p><p>Hiệu lực: ${fmtDate(d.contract_info?.start_date)} - ${fmtDate(d.contract_info?.end_date)}</p></div>
      <div><b>Complaint liên quan</b><p>${(d.complaints || []).length} complaint</p></div>
      <div class="detail-history"><b>History log</b><ul>${(d.history_log || []).map(h => `<li>${fmtDate(h.time)} - ${esc(h.action)}: ${esc(h.description || '')}</li>`).join('') || '<li>--</li>'}</ul></div>
    </div>`
  });
}

async function editEmployee(id) {
  const d = await api(`/api/admin/employees/${id}`);
  const { isConfirmed, value } = await Swal.fire({
    title: `Chỉnh sửa ${esc(d.full_name)}`,
    html: `<input id="edName" class="swal2-input" value="${esc(d.full_name)}"><input id="edEmail" class="swal2-input" value="${esc(d.email || '')}"><input id="edPhone" class="swal2-input" value="${esc(d.phone || '')}"><select id="edDepartment" class="swal2-input">${document.getElementById('filterDepartment').innerHTML}</select><select id="edPosition" class="swal2-input">${document.getElementById('filterPosition').innerHTML}</select><select id="edRole" class="swal2-input">${document.getElementById('filterRole').innerHTML}</select><select id="edWorking" class="swal2-input"><option value="active">Đang làm việc</option><option value="probation">Thử việc</option><option value="on_leave">Tạm nghỉ</option><option value="pending_resignation">Chờ nghỉ việc</option><option value="resigned">Đã nghỉ việc</option><option value="inactive">Inactive</option><option value="terminated">Chấm dứt</option><option value="retired">Nghỉ hưu</option></select><select id="edAccount" class="swal2-input"><option value="active">Active</option><option value="locked">Locked</option><option value="inactive">Inactive</option><option value="pending">Pending</option></select>`,
    didOpen: () => {
      document.getElementById('edDepartment').value = d.department_id || '';
      document.getElementById('edPosition').value = d.position_id || '';
      document.getElementById('edRole').value = d.role_id || '';
      document.getElementById('edWorking').value = d.working_status || 'active';
      document.getElementById('edAccount').value = d.account_status || 'active';
    },
    showCancelButton: true,
    preConfirm: () => ({
      full_name: document.getElementById('edName').value,
      email: document.getElementById('edEmail').value,
      phone: document.getElementById('edPhone').value,
      department_id: Number(document.getElementById('edDepartment').value) || null,
      position_id: Number(document.getElementById('edPosition').value) || null,
      role_id: Number(document.getElementById('edRole').value) || null,
      working_status: document.getElementById('edWorking').value,
      account_status: document.getElementById('edAccount').value,
    })
  });
  if (!isConfirmed) return;
  await api(`/api/admin/employees/${id}`, { method: 'PATCH', body: JSON.stringify(value) });
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật nhân viên' });
  loadEmployees();
}

async function lockEmployee(userId) {
  const { isConfirmed, value } = await Swal.fire({ title: 'Khóa tài khoản', input: 'text', inputLabel: 'Lý do khóa', showCancelButton: true });
  if (!isConfirmed) return;
  await api(`/api/admin/users/${userId}/lock`, { method: 'PATCH', body: JSON.stringify({ reason: value || 'Vi phạm chính sách' }) });
  await Swal.fire({ icon: 'success', title: 'Đã khóa tài khoản' });
  loadEmployees();
}
async function unlockEmployee(userId) {
  const c = await Swal.fire({ title: 'Mở khóa tài khoản?', icon: 'question', showCancelButton: true });
  if (!c.isConfirmed) return;
  await api(`/api/admin/users/${userId}/unlock`, { method: 'PATCH' });
  await Swal.fire({ icon: 'success', title: 'Đã mở khóa' });
  loadEmployees();
}
async function resetPassword(userId) {
  const { isConfirmed, value } = await Swal.fire({ title: 'Reset mật khẩu', input: 'password', inputLabel: 'Mật khẩu mới', showCancelButton: true });
  if (!isConfirmed) return;
  await api(`/api/admin/users/${userId}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password: value }) });
  await Swal.fire({ icon: 'success', title: 'Đã reset mật khẩu' });
}
async function transferEmployee(id) {
  const { isConfirmed, value } = await Swal.fire({
    title: 'Điều chuyển nhân sự',
    html: `<select id="trDepartment" class="swal2-input">${document.getElementById('filterDepartment').innerHTML}</select><select id="trPosition" class="swal2-input">${document.getElementById('filterPosition').innerHTML}</select>`,
    showCancelButton: true,
    preConfirm: () => ({
      department_id: Number(document.getElementById('trDepartment').value) || null,
      position_id: Number(document.getElementById('trPosition').value) || null,
    })
  });
  if (!isConfirmed) return;
  await api(`/api/admin/employees/${id}/transfer`, { method: 'PATCH', body: JSON.stringify(value) });
  await Swal.fire({ icon: 'success', title: 'Đã điều chuyển nhân sự' });
  loadEmployees();
}
async function inactiveEmployee(id) {
  const c = await Swal.fire({ title: 'Chuyển nhân viên sang Inactive?', text: 'Không xóa cứng dữ liệu.', icon: 'warning', showCancelButton: true });
  if (!c.isConfirmed) return;
  await api(`/api/admin/employees/${id}/inactive`, { method: 'PATCH' });
  await Swal.fire({ icon: 'success', title: 'Đã chuyển trạng thái Inactive' });
  loadEmployees();
}

async function loadDepartments() { const rows = await api('/api/departments'); departmentRows.innerHTML = rows.map(r => `<tr><td>${r.department_code}</td><td>${r.name}</td><td>${r.manager_name || ''}</td><td>${r.employee_count}</td><td><span class="badge ${r.status ? 'b-success' : 'b-danger'}">${r.status ? 'active' : 'inactive'}</span></td><td><button onclick="toggleDepartment(${r.id},${r.status})">${r.status ? 'Disable' : 'Enable'}</button></td></tr>`).join(''); }
async function toggleDepartment(id, status) { if (status) { await api(`/api/departments/${id}`, { method: 'DELETE' }); } else { await api(`/api/departments/${id}`, { method: 'PATCH', body: JSON.stringify({ status: true }) }); } loadDepartments(); }
async function createDepartmentPrompt() { const { value: name } = await Swal.fire({ title: 'Tên phòng ban', input: 'text', showCancelButton: true }); if (!name) return; await api('/api/departments', { method: 'POST', body: JSON.stringify({ name }) }); await Swal.fire({ icon: 'success', title: 'Đã tạo phòng ban' }); loadDepartments(); }

async function loadPositions() { const rows = await api('/api/positions'); positionRows.innerHTML = rows.map(r => `<tr><td>${r.id}</td><td>${r.job_title}</td><td>${r.salary_range}</td><td>${r.employee_count}</td><td>${r.status}</td><td><button onclick="togglePosition(${r.id},'${r.status}')">${r.status === 'inactive' ? 'Enable' : 'Disable'}</button></td></tr>`).join(''); }
async function togglePosition(id, status) { await api(`/api/positions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: status === 'inactive' ? 'active' : 'inactive' }) }); loadPositions(); }
async function createPositionPrompt() { const { value: job_title } = await Swal.fire({ title: 'Tên chức danh', input: 'text', showCancelButton: true }); if (!job_title) return; await api('/api/positions', { method: 'POST', body: JSON.stringify({ job_title, min_salary: 0, max_salary: 0, status: 'active' }) }); await Swal.fire({ icon: 'success', title: 'Đã tạo chức danh' }); loadPositions(); }

async function loadAttendanceSummary() { setDefaults(); const m = month.value, y = year.value; const rows = await api(`/api/admin/attendance/summary?month=${m}&year=${y}`); attendanceRows.innerHTML = rows.map(r => `<tr><td>${r.department_name}</td><td>${r.employee_count}</td><td>${r.total_work}</td><td>${r.late_count}</td><td>${r.absent_count}</td></tr>`).join(''); const logs = await api(`/api/admin/attendance/audit-log?month=${m}&year=${y}`); attendanceAudit.innerHTML = logs.map(l => `<li>${l.time || ''} | ${l.action} | ${l.description || ''}</li>`).join(''); }
async function lockMonth() { setDefaults(); await api('/api/admin/attendance/lock-month', { method: 'POST', body: JSON.stringify({ month: +month.value, year: +year.value }) }); loadAttendanceSummary(); }
async function reopenMonth() { setDefaults(); const { value: reason } = await Swal.fire({ title: 'Nhập lý do mở lại công', input: 'text', showCancelButton: true }); if (reason === undefined) return; await api('/api/admin/attendance/reopen-month', { method: 'POST', body: JSON.stringify({ month: +month.value, year: +year.value, reason: reason || '' }) }); await Swal.fire({ icon: 'success', title: 'Đã mở lại bảng công' }); loadAttendanceSummary(); }

async function loadSalaryAggregate() { setDefaults(); const g = document.getElementById('groupBy').value; const m = month.value, y = year.value; const res = await api(`/api/admin/salaries/aggregate?month=${m}&year=${y}&group_by=${g}`); salaryStatus.textContent = `Trạng thái: ${res.status}`; salaryRows.innerHTML = res.data.map(r => `<tr><td>${r.group_name}</td><td>${r.employee_count}</td><td>${r.total_salary}</td><td>${r.avg_salary}</td></tr>`).join(''); const logs = await api('/api/admin/salaries/audit'); salaryAudit.innerHTML = logs.map(l => `<li>${l.time || ''} | ${l.action} | ${l.description || ''}</li>`).join(''); }
async function lockSalary() { setDefaults(); await api('/api/admin/salaries/lock', { method: 'POST', body: JSON.stringify({ month: +month.value, year: +year.value }) }); loadSalaryAggregate(); }
async function unlockSalary() { setDefaults(); await api('/api/admin/salaries/unlock', { method: 'POST', body: JSON.stringify({ month: +month.value, year: +year.value }) }); loadSalaryAggregate(); }

document.addEventListener('DOMContentLoaded', async () => {
  setDefaults();
  await loadDepartmentsSelect();
  document.getElementById('btnAddEmployee')?.addEventListener('click', addEmployee);
  document.getElementById('btnFilterEmployees')?.addEventListener('click', () => loadEmployees({ notify: true }));
  document.getElementById('btnResetFilters')?.addEventListener('click', () => {
    ['filterName', 'filterCode', 'filterEmail', 'filterDepartment', 'filterPosition', 'filterRole', 'filterWorkingStatus', 'filterEmploymentType', 'filterProbation', 'filterHireFrom', 'filterHireTo']
      .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    const monthEl = document.getElementById('month');
    const yearEl = document.getElementById('year');
    const departmentEl = document.getElementById('department');
    if (monthEl) monthEl.value = now.getMonth() + 1;
    if (yearEl) yearEl.value = now.getFullYear();
    if (departmentEl) departmentEl.value = '';
    loadEmployees({ notify: true, isReset: true });
  });
  document.getElementById('btnTopFilter')?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (window.ADMIN_PAGE === 'employees') {
      await loadEmployees({ notify: true });
      return;
    }
    await loadDashboard();
  });
  if (window.ADMIN_PAGE === 'dashboard') await loadDashboard();
  if (window.ADMIN_PAGE === 'employees') await loadEmployees();
  if (window.ADMIN_PAGE === 'departments') await loadDepartments();
  if (window.ADMIN_PAGE === 'positions') await loadPositions();
  if (window.ADMIN_PAGE === 'attendance') await loadAttendanceSummary();
  if (window.ADMIN_PAGE === 'salary') await loadSalaryAggregate();
});


async function reviewResignationAdmin(employeeId) {
  const rows = await api(`/api/admin/resignations?status=pending_admin`)
  const matches = rows.filter((r) => Number(r.employee_id) === Number(employeeId))
  if (!matches.length) {
    await Swal.fire({ icon: 'info', title: 'Nhân viên chưa có resignation chờ duyệt cuối' })
    return
  }
  const current = matches[0]
  const { value, isConfirmed } = await Swal.fire({
    title: `Duyệt nghỉ việc: ${esc(current.employee_name || '')}`,
    html: `<p>Ngày dự kiến nghỉ: ${esc(current.expected_last_day || '--')}</p><p>Lý do: ${esc(current.reason_text || current.reason_category || '--')}</p><select id="ad-action" class="swal2-input"><option value="approve">Duyệt cuối + khóa tài khoản</option><option value="reject">Từ chối</option></select><textarea id="ad-note" class="swal2-textarea" placeholder="Ghi chú admin"></textarea>`,
    showCancelButton: true,
    preConfirm: () => ({
      action: document.getElementById('ad-action').value,
      note: document.getElementById('ad-note').value
    })
  })
  if (!isConfirmed) return
  const result = await api(`/api/admin/resignations/${current.id}/finalize`, { method: 'POST', body: JSON.stringify(value) })
  await Swal.fire({ icon: 'success', title: result.message || 'Đã cập nhật resignation' })
  loadEmployees()
}