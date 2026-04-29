async function api(url, options = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(e.error || 'Request failed');
  }
  return r.headers.get('content-type')?.includes('application/json') ? r.json() : r.text();
}

const now = new Date();
let currentUser = null;
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
    const previousValue = el.value;
    const first = el.options[0]?.outerHTML || '<option value="">--</option>';
    el.innerHTML = first + rows.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('');
    if (previousValue && Array.from(el.options).some((opt) => opt.value === previousValue)) {
      el.value = previousValue;
    }
  });
}

function employeeFiltersAsQuery() {
  const get = (id) => document.getElementById(id)?.value?.trim() || '';
  const params = new URLSearchParams();
  const keyword = get('filterName');
  const mapping = {
    keyword,
    name: get('filterName'), employee_code: get('filterCode'), email: get('filterEmail'),
    phone: get('filterPhone'),
    department_id: get('filterDepartment'), position_id: get('filterPosition'), role_id: get('filterRole'),
    working_status: get('filterWorkingStatus'), account_status: get('filterAccountStatus'),
    employment_type: get('filterEmploymentType'), probation: get('filterProbation'),
    hire_date_from: get('filterHireFrom'), hire_date_to: get('filterHireTo'),
    top_department_id: get('department')
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
  if (!employee.id) {
    return `
      <div class="table-actions">
        <span class="muted">Chưa có hồ sơ nhân sự</span>
        <button onclick="resetPassword(${employee.user_id})">Reset mật khẩu</button>
      </div>`;
  }
  const lockBtn = employee.account_status === 'locked'
    ? `<button onclick="unlockEmployee(${employee.user_id})">Mở khóa</button>`
    : `<button onclick="lockEmployee(${employee.user_id})">Khóa tài khoản</button>`;
  const disableSelf = currentUser && Number(currentUser.user_id) === Number(employee.user_id);
  const selfAttr = disableSelf ? 'disabled title="Không thao tác trên chính mình"' : '';
  return `
    <div class="table-actions">
      <button onclick="viewEmployeeDetail(${employee.id})">Xem chi tiết</button>
      <button onclick="openRolePanel(${employee.user_id})" ${selfAttr}>Phân quyền</button>
      ${lockBtn.replace('<button ', `<button ${selfAttr} `)}
      <button onclick="resetPassword(${employee.user_id})">Reset mật khẩu</button>
      <button onclick="transferEmployee(${employee.id})">Chuyển phòng ban</button>
      <button class="btn-danger" onclick="inactiveEmployee(${employee.id})" ${selfAttr}>Set Inactive</button>
      <button onclick="reviewResignationAdmin(${employee.id})">Duyệt nghỉ việc</button>
    </div>`;
}

function renderEmployeeRows(rows) {
  const tr = document.getElementById('employeeRows'); if (!tr) return;
  tr.innerHTML = rows.length ? rows.map(e => `
    <tr>
      <td>${esc(e.employee_code)}</td>
      <td>${e.avatar ? `<img src="${esc(e.avatar)}" class="avatar"> ${esc(e.full_name)}` : esc(e.full_name)}</td>
      <td>${esc(e.email || '--')}</td>
      <td>${esc(e.phone || '--')}</td>
      <td>${esc(e.department || '--')}</td>
      <td>${esc(e.position || '--')}</td>
      <td>${esc(e.username || '--')}</td>
      <td><span class="badge ${e.working_status ? (e.working_status === 'active' ? 'b-success' : e.working_status === 'on_leave' ? 'b-warning' : 'b-danger') : 'b-warning'}">${esc(LABELS.working[e.working_status] || e.working_status || '--')}</span></td>
      <td><span class="badge ${e.account_status === 'active' ? 'b-success' : e.account_status === 'locked' ? 'b-danger' : 'b-warning'}">${esc(LABELS.account[e.account_status] || e.account_status)}</span></td>
      <td>${rowActions(e)}</td>
    </tr>`).join('') : '<tr><td colspan="10">Không tìm thấy nhân viên phù hợp</td></tr>';
}
async function loadEmployees({ notify = false, isReset = false } = {}) {
  try {
    await Promise.allSettled([loadEmployeeMeta(), loadEmployeeSummary(), loadEmployeeAlerts()]);
    const q = employeeFiltersAsQuery();
    const rows = await api(`/api/admin/employees${q ? `?${q}` : ''}`);
    renderEmployeeRows(rows);
    if (rows.length === 0) {
      await Swal.fire({
        icon: 'info',
        title: 'Không có dữ liệu phù hợp',
        text: 'Không tìm thấy nhân viên thuộc bộ lọc đã chọn'
      });
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
  const panel = document.getElementById('employeeDetailPanel');
  const content = document.getElementById('employeeDetailContent');
  if (!panel || !content) return;
  content.innerHTML = `
    <div class="detail-grid">
      <div><h4>Thông tin cá nhân</h4><p>Họ tên: ${esc(d.full_name || '--')}</p><p>Tuổi: ${esc(d.profile?.age || '--')}</p><p>Giới tính: ${esc(d.profile?.gender || '--')}</p><p>SĐT: ${esc(d.phone || '--')}</p><p>Email: ${esc(d.email || '--')}</p><p>Địa chỉ: ${esc(d.profile?.address || '--')}</p></div>
      <div><h4>Thông tin công việc</h4><p>Phòng ban: ${esc(d.work_info?.department || '--')}</p><p>Chức vụ: ${esc(d.work_info?.position || '--')}</p><p>Manager: ${esc(d.work_info?.manager || '--')}</p><p>Ngày vào làm: ${fmtDate(d.work_info?.hire_date)}</p><p>Loại hợp đồng: ${esc(LABELS.employment[d.work_info?.employment_type] || d.work_info?.employment_type || '--')}</p><p>Trạng thái làm việc: ${esc(LABELS.working[d.work_info?.working_status] || d.work_info?.working_status || '--')}</p></div>
      <div><h4>Hợp đồng</h4><p>Loại hợp đồng: ${esc(LABELS.employment[d.contract_info?.type] || d.contract_info?.type || '--')}</p><p>Ngày bắt đầu: ${fmtDate(d.contract_info?.start_date)}</p><p>Ngày kết thúc: ${fmtDate(d.contract_info?.end_date)}</p></div>
      <div><h4>Thu nhập</h4><p>Lương cơ bản: ${(d.income_info?.basic_salary || 0).toLocaleString('vi-VN')} VND</p><p>Phụ cấp: ${(d.income_info?.allowance_total || 0).toLocaleString('vi-VN')} VND</p></div>
    </div>`;
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function openRolePanel(userId) {
  const rows = await api(`/api/admin/employees?user_id=${userId}`).catch(() => []);
  const employee = (rows || []).find((item) => Number(item.user_id) === Number(userId));
  const roleOptions = Array.from(document.getElementById('filterRole')?.options || [])
    .filter((opt) => opt.value)
    .map((opt) => `<option value="${opt.value}">${esc(opt.textContent || '')}</option>`)
    .join('');
  const { isConfirmed, value } = await Swal.fire({
    title: 'Phân quyền tài khoản',
    html: `
      <p><b>${esc(employee?.full_name || employee?.username || '--')}</b></p>
      <p>${esc(employee?.email || '--')}</p>
      <p>Role hiện tại: <b>${esc(employee?.role || '--')}</b></p>
      <select id="roleAssign" class="swal2-input">${roleOptions}</select>
    `,
    showCancelButton: true,
    confirmButtonText: 'Save',
    cancelButtonText: 'Cancel',
    didOpen: () => {
      const select = document.getElementById('roleAssign');
      if (select && employee?.role_id) select.value = String(employee.role_id);
    },
    preConfirm: async () => {
      const roleId = Number(document.getElementById('roleAssign').value);
      const ask = await Swal.fire({
        title: 'Xác nhận phân quyền?',
        text: 'Thay đổi role sẽ ảnh hưởng phạm vi truy cập của nhân viên.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Xác nhận',
        cancelButtonText: 'Hủy'
      });
      if (!ask.isConfirmed) return false;
      return { role_id: roleId };
    }
  });
  if (!isConfirmed || !value) return;
  await api(`/api/admin/users/${userId}/role`, { method: 'PATCH', body: JSON.stringify(value) });
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật role' });
  loadEmployees();
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

let currentDepartmentDetailId = null;

function departmentActionCell(row) {
  return `<select class="department-action-select" onchange="handleDepartmentAction(${row.id}, this.value); this.value='';">
    <option value="">Chọn thao tác</option>
    <option value="detail">Xem chi tiết</option>
    <option value="edit">Chỉnh sửa</option>
    <option value="${row.status ? 'inactive' : 'active'}">${row.status ? 'Ngưng hoạt động' : 'Kích hoạt lại'}</option>
    <option value="transfer">Chuyển nhân sự</option>
    <option value="change_manager">Đổi trưởng phòng</option>
  </select>`;
}

function renderDepartmentRows(rows) {
  const body = document.getElementById('departmentRows');
  if (!body) return;
  body.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${esc(r.department_code)}</td>
      <td>${esc(r.name)}</td>
      <td>${esc(r.manager_name || '--')}</td>
      <td>${r.employee_count || 0}</td>
      <td><span class="department-status ${r.status ? 'active' : 'inactive'}">${r.status ? '🟢 Active' : '🔴 Inactive'}</span></td>
      <td>${departmentActionCell(r)}</td>
    </tr>
  `).join('') : '<tr><td colspan="6">Không có phòng ban phù hợp điều kiện tìm kiếm.</td></tr>';
}

async function loadDepartmentStats() {
  const stats = await api('/api/departments/stats');
  document.getElementById('departmentTotal').textContent = stats.total ?? 0;
  document.getElementById('departmentActive').textContent = stats.active ?? 0;
  document.getElementById('departmentInactive').textContent = stats.inactive ?? 0;
}

async function loadDepartments() {
  const keyword = document.getElementById('search-department')?.value?.trim() || '';
  const params = new URLSearchParams();
  if (keyword) params.set('q', keyword);
  const rows = await api(`/api/departments${params.toString() ? `?${params.toString()}` : ''}`);
  renderDepartmentRows(rows);
  await loadDepartmentStats();
}

async function loadDepartmentDetail(id) {
  const detail = await api(`/api/departments/${id}`);
  currentDepartmentDetailId = id;
  const body = document.getElementById('departmentDetailBody');
  const card = document.getElementById('department-detail-card');
  if (!body || !card) return;
  body.innerHTML = `
    <div>
      <h4>Cột 1 — Thông tin cơ bản</h4>
      <p><strong>Tên phòng ban:</strong> ${esc(detail.name)}</p>
      <p><strong>Mã phòng ban:</strong> ${esc(detail.department_code)}</p>
      <p><strong>Trạng thái:</strong> ${detail.status ? '🟢 Active' : '🔴 Inactive'}</p>
      <p><strong>Ngày thành lập:</strong> ${fmtDate(detail.created_at)}</p>
      <p><strong>Mô tả:</strong> ${esc(detail.description || '--')}</p>
    </div>
    <div>
      <h4>Cột 2 — Nhân sự chủ chốt</h4>
      <p><strong>Trưởng phòng:</strong> ${esc(detail.manager_name || '--')}</p>
      <p><strong>Số điện thoại:</strong> ${esc(detail.manager_phone || '--')}</p>
      <p><strong>Email:</strong> ${esc(detail.manager_email || '--')}</p>
      <p><strong>Chức vụ:</strong> ${esc(detail.manager_role || '--')}</p>
    </div>
    <div>
      <h4>Cột 3 — Thống kê</h4>
      <p><strong>Tổng nhân viên:</strong> ${detail.employee_count || 0}</p>
      <p><strong>Tỷ lệ Nam / Nữ:</strong> ${(detail.male_count || 0)} / ${(detail.female_count || 0)}</p>
      <p><strong>Nhân viên đang nghỉ phép:</strong> ${detail.on_leave_count || 0}</p>
      <p><strong>Hợp đồng sắp hết hạn:</strong> ${detail.contract_expiring_count || 0}</p>
    </div>`;
  card.style.display = 'block';
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function fetchManagerOptions(selectedId = null) {
  const rows = await api('/api/departments/managers');
  return rows.map((m) => `<option value="${m.id}" ${Number(selectedId) === Number(m.id) ? 'selected' : ''}>${esc(m.name)} (${esc(m.role)})</option>`).join('');
}

async function openDepartmentForm(mode, departmentId = null) {
  const isEdit = mode === 'edit';
  const detail = isEdit ? await api(`/api/departments/${departmentId}`) : null;
  const managerOptions = await fetchManagerOptions(detail?.manager_id);
  const title = isEdit ? '📝 CHỈNH SỬA PHÒNG BAN' : '➕ THÊM PHÒNG BAN MỚI';
  const { isConfirmed, dismiss, value } = await Swal.fire({
    title,
    width: 760,
    showDenyButton: !isEdit,
    denyButtonText: '📑 Tạo và tiếp tục thêm',
    confirmButtonText: isEdit ? '💾 Lưu thay đổi' : '💾 Lưu',
    cancelButtonText: '❌ Hủy bỏ',
    showCancelButton: true,
    html: `
      <input id="dpName" class="swal2-input" placeholder="Tên phòng ban" value="${esc(detail?.name || '')}">
      <textarea id="dpDesc" class="swal2-textarea" placeholder="Mô tả">${esc(detail?.description || '')}</textarea>
      <select id="dpManager" class="swal2-input"><option value="">-- Chọn trưởng phòng --</option>${managerOptions}</select>
      <div style="text-align:left;padding:6px 10px;">
        <label><input type="radio" name="dpStatus" value="active" ${detail?.status !== false ? 'checked' : ''}> Active</label>
        <label style="margin-left:14px;"><input type="radio" name="dpStatus" value="inactive" ${detail?.status === false ? 'checked' : ''}> Inactive</label>
      </div>
      ${isEdit ? `
      <div class="impact-warning">
        Việc thay đổi Trưởng phòng sẽ ảnh hưởng tới:
        <ul>
          <li>Leave Request Approval</li>
          <li>Payroll Approval</li>
          <li>Attendance Approval</li>
          <li>Department Permission Flow</li>
        </ul>
      </div>` : `
      <div style="text-align:left;padding:6px 10px;">
        <label><input type="radio" name="dpInitialStatus" value="active" checked> Kích hoạt ngay</label>
        <label style="margin-left:14px;"><input type="radio" name="dpInitialStatus" value="inactive"> Chờ kích hoạt</label>
      </div>`}
    `,
    preConfirm: () => ({
      name: document.getElementById('dpName').value.trim(),
      description: document.getElementById('dpDesc').value.trim(),
      manager_id: Number(document.getElementById('dpManager').value) || null,
      status: (isEdit
        ? document.querySelector('input[name="dpStatus"]:checked')?.value
        : document.querySelector('input[name="dpInitialStatus"]:checked')?.value) !== 'inactive'
    })
  });
  if (!isConfirmed && dismiss !== Swal.DismissReason.deny) return;
  if (!value?.name) {
    await Swal.fire({ icon: 'error', title: 'Tên phòng ban là bắt buộc' });
    return;
  }
  if (isEdit) {
    await api(`/api/departments/${departmentId}`, { method: 'PATCH', body: JSON.stringify(value) });
    await Swal.fire({ icon: 'success', title: 'Đã lưu thay đổi phòng ban' });
  } else {
    await api('/api/departments', { method: 'POST', body: JSON.stringify(value) });
    await Swal.fire({ icon: 'success', title: 'Đã tạo phòng ban mới' });
  }
  await loadDepartments();
  if (isEdit && currentDepartmentDetailId === departmentId) await loadDepartmentDetail(departmentId);
  if (dismiss === Swal.DismissReason.deny) await openDepartmentForm('create');
}

async function openDepartmentTransferGuide(id) {
  const detail = await api(`/api/departments/${id}`);
  await Swal.fire({
    icon: 'info',
    title: 'Chuyển nhân sự',
    html: `Phòng ban <b>${esc(detail.name)}</b> đang còn <b>${detail.employee_count || 0}</b> nhân sự.<br>Vui lòng dùng chức năng <b>Admin → Quản lý nhân viên → Chuyển phòng ban</b> trước khi ngưng hoạt động.`,
    confirmButtonText: 'Đã hiểu'
  });
}

async function deactivateDepartmentWithChecks(id) {
  const impact = await api(`/api/departments/${id}/impact`);
  if ((impact.employee_count || 0) > 0) {
    const ask = await Swal.fire({
      icon: 'warning',
      title: 'Phòng ban này vẫn còn nhân viên.',
      text: 'Vui lòng chuyển nhân sự sang phòng ban khác trước khi ngưng hoạt động.',
      showCancelButton: true,
      confirmButtonText: 'Chuyển nhân sự ngay'
    });
    if (ask.isConfirmed) await openDepartmentTransferGuide(id);
    return;
  }
  if ((impact.pending_leave_count || 0) > 0 || (impact.pending_approval_count || 0) > 0) {
    await Swal.fire({
      icon: 'warning',
      title: 'Không thể ngưng hoạt động',
      html: `Đang có request/approval chờ xử lý.<br>Leave pending: <b>${impact.pending_leave_count || 0}</b><br>Approval pending: <b>${impact.pending_approval_count || 0}</b>`
    });
    return;
  }
  if (impact.has_manager) {
    await Swal.fire({
      icon: 'info',
      title: 'Yêu cầu bàn giao quyền duyệt',
      text: 'Phòng ban hiện có trưởng phòng. Hãy đổi trưởng phòng hoặc bàn giao quyền duyệt trước khi ngưng hoạt động.'
    });
  }
  const confirm = await Swal.fire({
    title: 'Xác nhận ngưng hoạt động phòng ban?',
    text: 'Phòng ban sẽ không thể nhận thêm nhân sự mới',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Xác nhận'
  });
  if (!confirm.isConfirmed) return;
  await api(`/api/departments/${id}`, { method: 'DELETE' });
  await Swal.fire({ icon: 'success', title: 'Đã ngưng hoạt động phòng ban' });
  await loadDepartments();
}

async function activateDepartment(id) {
  const confirm = await Swal.fire({ title: 'Kích hoạt lại phòng ban?', icon: 'question', showCancelButton: true, confirmButtonText: 'Kích hoạt' });
  if (!confirm.isConfirmed) return;
  await api(`/api/departments/${id}`, { method: 'PATCH', body: JSON.stringify({ status: true }) });
  await Swal.fire({ icon: 'success', title: 'Đã kích hoạt lại phòng ban' });
  await loadDepartments();
}

async function handleDepartmentAction(id, action) {
  if (!action) return;
  if (action === 'detail') return loadDepartmentDetail(id);
  if (action === 'edit') return openDepartmentForm('edit', id);
  if (action === 'inactive') return deactivateDepartmentWithChecks(id);
  if (action === 'active') return activateDepartment(id);
  if (action === 'transfer') return openDepartmentTransferGuide(id);
  if (action === 'change_manager') return openDepartmentForm('edit', id);
}
window.handleDepartmentAction = handleDepartmentAction;
window.createDepartmentPrompt = () => openDepartmentForm('create');

let currentPositionDetailId = null;

function formatCurrency(value) {
  return `${Number(value || 0).toLocaleString('vi-VN')} VNĐ`;
}

function positionStatusBadge(status) {
  if (status === 'active') return '<span class="position-status active">🟢 Active</span>';
  if (status === 'hiring') return '<span class="position-status hiring">🟡 Hiring</span>';
  return '<span class="position-status inactive">🔴 Inactive</span>';
}

function positionActionCell(row) {
  const statusAction = row.status === 'inactive'
    ? '<option value="active">Kích hoạt lại</option>'
    : '<option value="inactive">Ngừng sử dụng</option>';
  return `
    <select class="position-action-select" onchange="handlePositionAction(${row.id}, this.value); this.value='';">
      <option value="">Chọn thao tác</option>
      <option value="detail">Xem chi tiết</option>
      <option value="edit">Chỉnh sửa</option>
      ${statusAction}
      <option value="employees">Xem nhân sự đang giữ</option>
    </select>`;
}

function renderPositionRows(rows) {
  const body = document.getElementById('positionRows');
  if (!body) return;
  body.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${esc(r.position_code || `POS${r.id}`)}</td>
      <td>${esc(r.job_title)}</td>
      <td>${formatCurrency(r.min_salary)} - ${formatCurrency(r.max_salary)}</td>
      <td>${r.employee_count || 0}</td>
      <td>${positionStatusBadge(r.status)}</td>
      <td>${positionActionCell(r)}</td>
    </tr>
  `).join('') : '<tr><td colspan="6">Không có chức danh phù hợp điều kiện tìm kiếm.</td></tr>';
}

async function loadPositionStats() {
  const stats = await api('/api/positions/stats');
  document.getElementById('positionTotal').textContent = stats.total_positions || 0;
  document.getElementById('positionHolding').textContent = `${stats.holding_employees || 0} nhân sự`;
  document.getElementById('positionAvgSalary').textContent = formatCurrency(stats.average_salary || 0);
}

function positionFiltersAsQuery() {
  const keyword = document.getElementById('search-job-title')?.value?.trim() || '';
  const status = document.getElementById('positionStatusFilter')?.value?.trim() || '';
  const salaryFrom = document.getElementById('positionSalaryFrom')?.value?.trim() || '';
  const salaryTo = document.getElementById('positionSalaryTo')?.value?.trim() || '';
  const params = new URLSearchParams();
  if (keyword) params.set('q', keyword);
  if (status) params.set('status', status);
  if (salaryFrom) params.set('min_salary', salaryFrom);
  if (salaryTo) params.set('max_salary', salaryTo);
  return params.toString();
}

async function loadPositions() {
  const q = positionFiltersAsQuery();
  const rows = await api(`/api/positions${q ? `?${q}` : ''}`);
  renderPositionRows(rows);
  await loadPositionStats();
}

async function loadPositionDetail(id) {
  const detail = await api(`/api/positions/${id}`);
  currentPositionDetailId = id;
  const body = document.getElementById('jobTitleDetailBody');
  const card = document.getElementById('job-title-detail-card');
  if (!body || !card) return;
  body.innerHTML = `
    <div>
      <h4>Thông tin chức danh</h4>
      <p><strong>Tên chức danh:</strong> ${esc(detail.job_title)}</p>
      <p><strong>Mã chức danh:</strong> ${esc(detail.position_code || `POS${detail.id}`)}</p>
      <p><strong>Trạng thái:</strong> ${positionStatusBadge(detail.status)}</p>
      <p><strong>Số nhân sự đang giữ:</strong> ${detail.employees?.length || 0}</p>
      <p><strong>Lương cơ bản đề xuất:</strong> ${formatCurrency(detail.min_salary)} - ${formatCurrency(detail.max_salary)}</p>
    </div>
    <div>
      <h4>Audit & nghiệp vụ</h4>
      <p><strong>Ngày tạo:</strong> ${fmtDate(detail.created_at)}</p>
      <p><strong>Người tạo:</strong> ${esc(detail.created_by || '--')}</p>
      <p><strong>Ghi chú nghiệp vụ:</strong> ${esc(detail.notes || '--')}</p>
      <p><strong>Yêu cầu công việc (Requirements):</strong> ${esc(detail.requirements || '--')}</p>
    </div>`;
  card.style.display = 'block';
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function positionStatusRadio(name, current = 'active') {
  return `
    <div style="text-align:left;padding:6px 10px;">
      <div style="margin-bottom:4px;">Trạng thái hoạt động</div>
      <label><input type="radio" name="${name}" value="active" ${current === 'active' ? 'checked' : ''}> Active</label>
      <label style="margin-left:14px;"><input type="radio" name="${name}" value="hiring" ${current === 'hiring' ? 'checked' : ''}> Hiring</label>
      <label style="margin-left:14px;"><input type="radio" name="${name}" value="inactive" ${current === 'inactive' ? 'checked' : ''}> Inactive</label>
    </div>`;
}

async function openPositionForm(mode, positionId = null) {
  const isEdit = mode === 'edit';
  const detail = isEdit ? await api(`/api/positions/${positionId}`) : null;
  const title = isEdit ? '📝 CẬP NHẬT CHỨC DANH' : '➕ THÊM CHỨC DANH MỚI';
  const { isConfirmed, dismiss, value } = await Swal.fire({
    title,
    width: 760,
    showCancelButton: true,
    showDenyButton: !isEdit,
    denyButtonText: '📑 Tạo và tiếp tục thêm',
    confirmButtonText: isEdit ? '💾 Lưu chức danh' : '💾 Lưu',
    cancelButtonText: isEdit ? '❌ Hủy và quay lại' : '❌ Hủy',
    html: `
      <input id="jtName" class="swal2-input" placeholder="Tên chức danh" value="${esc(detail?.job_title || '')}">
      <div class="swal-form-grid">
        <input id="jtMinSalary" class="swal2-input" type="number" placeholder="Min Salary" value="${detail?.min_salary ?? 0}">
        <input id="jtMaxSalary" class="swal2-input" type="number" placeholder="Max Salary" value="${detail?.max_salary ?? 0}">
      </div>
      ${positionStatusRadio('jtStatus', detail?.status || 'active')}
      <textarea id="jtRequirements" class="swal2-textarea" placeholder="Yêu cầu công việc (Requirements)">${esc(detail?.requirements || '')}</textarea>
      <div class="impact-warning">
        Mức lương này dùng để làm cơ sở gợi ý khi tạo Hợp đồng lao động (Contract) cho nhân viên.
        Không phải là mức lương cố định cuối cùng.
      </div>
    `,
    preConfirm: () => ({
      job_title: document.getElementById('jtName').value.trim(),
      min_salary: Number(document.getElementById('jtMinSalary').value || 0),
      max_salary: Number(document.getElementById('jtMaxSalary').value || 0),
      status: document.querySelector('input[name="jtStatus"]:checked')?.value || 'active',
      requirements: document.getElementById('jtRequirements').value.trim()
    })
  });
  if (!isConfirmed && dismiss !== Swal.DismissReason.deny) return;
  if (!value?.job_title) {
    await Swal.fire({ icon: 'error', title: 'Tên chức danh là bắt buộc' });
    return;
  }
  if ((value.min_salary || 0) > (value.max_salary || 0)) {
    await Swal.fire({ icon: 'error', title: 'Mức lương tối thiểu không được lớn hơn mức lương tối đa' });
    return;
  }
  try {
    if (isEdit) {
      await api(`/api/positions/${positionId}`, { method: 'PATCH', body: JSON.stringify(value) });
      await Swal.fire({ icon: 'success', title: 'Đã cập nhật chức danh' });
      if (currentPositionDetailId === positionId) await loadPositionDetail(positionId);
    } else {
      await api('/api/positions', { method: 'POST', body: JSON.stringify(value) });
      await Swal.fire({ icon: 'success', title: 'Đã thêm chức danh mới' });
    }
    await loadPositions();
    if (dismiss === Swal.DismissReason.deny) await openPositionForm('create');
  } catch (error) {
    await Swal.fire({ icon: 'error', title: 'Không thể lưu chức danh', text: error.message || 'Vui lòng kiểm tra lại dữ liệu' });
  }
}

async function showPositionEmployees(id) {
  const detail = await api(`/api/positions/${id}`);
  await Swal.fire({
    icon: 'info',
    title: 'Nhân sự đang giữ chức danh',
    html: detail.employees?.length
      ? `<ul style="text-align:left">${detail.employees.map((e) => `<li>${esc(e.name)}</li>`).join('')}</ul>`
      : 'Hiện chưa có nhân sự nào đang giữ chức danh này.',
    confirmButtonText: 'Đã hiểu'
  });
}

async function deactivatePositionWithChecks(id) {
  const impact = await api(`/api/positions/${id}/impact`);
  if ((impact.employee_count || 0) > 0) {
    const ask = await Swal.fire({
      icon: 'warning',
      title: 'Chức danh này vẫn đang được sử dụng bởi nhân viên.',
      text: 'Vui lòng điều chuyển hoặc cập nhật chức danh khác trước khi ngừng sử dụng.',
      showCancelButton: true,
      confirmButtonText: 'Cập nhật chức danh ngay'
    });
    if (ask.isConfirmed) {
      await Swal.fire({ icon: 'info', title: 'Đi tới Admin → Quản lý nhân viên để cập nhật chức danh hàng loạt.' });
    }
    return;
  }
  if ((impact.active_contract_count || 0) > 0) {
    await Swal.fire({
      icon: 'warning',
      title: 'Không thể ngừng sử dụng chức danh',
      html: `Đang có hợp đồng active sử dụng chức danh này: <b>${impact.active_contract_count || 0}</b><br>Ảnh hưởng: Contract + Payroll + Salary Calculation`
    });
    return;
  }
  if ((impact.pending_payroll_count || 0) > 0) {
    await Swal.fire({
      icon: 'warning',
      title: 'Không thể ngừng sử dụng chức danh',
      html: `Đang có payroll chưa chốt theo chức danh này: <b>${impact.pending_payroll_count || 0}</b>`
    });
    return;
  }
  const confirm = await Swal.fire({
    title: 'Xác nhận ngừng sử dụng chức danh?',
    text: 'Chức danh này sẽ không thể gán cho nhân sự mới',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Xác nhận'
  });
  if (!confirm.isConfirmed) return;
  await api(`/api/positions/${id}`, { method: 'DELETE' });
  await Swal.fire({ icon: 'success', title: 'Đã ngừng sử dụng chức danh' });
  await loadPositions();
  if (currentPositionDetailId === id) await loadPositionDetail(id);
}

async function activatePosition(id) {
  const confirm = await Swal.fire({ title: 'Kích hoạt lại chức danh?', icon: 'question', showCancelButton: true, confirmButtonText: 'Kích hoạt' });
  if (!confirm.isConfirmed) return;
  await api(`/api/positions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: 'active' }) });
  await Swal.fire({ icon: 'success', title: 'Đã kích hoạt lại chức danh' });
  await loadPositions();
  if (currentPositionDetailId === id) await loadPositionDetail(id);
}

async function handlePositionAction(id, action) {
  if (!action) return;
  if (action === 'detail') return loadPositionDetail(id);
  if (action === 'edit') return openPositionForm('edit', id);
  if (action === 'inactive') return deactivatePositionWithChecks(id);
  if (action === 'active') return activatePosition(id);
  if (action === 'employees') return showPositionEmployees(id);
}
window.handlePositionAction = handlePositionAction;
window.createPositionPrompt = () => openPositionForm('create');

function attendanceFilterPayload() {
  return {
    keyword: document.getElementById('attendanceSearch')?.value?.trim() || '',
    department_id: document.getElementById('attendanceDepartment')?.value || '',
    status: document.getElementById('attendanceStatus')?.value || '',
    month: document.getElementById('attendanceMonth')?.value || (now.getMonth() + 1),
    year: document.getElementById('attendanceYear')?.value || now.getFullYear(),
    lock_status: document.getElementById('attendanceLockStatus')?.value || '',
    ot_status: document.getElementById('attendanceOtStatus')?.value || ''
  };
}

function attendanceStatusBadge(status) {
  if (status === 'normal') return '<span class="badge badge-normal">Bình thường</span>';
  if (status === 'late_early') return '<span class="badge badge-late">Đi muộn / Về sớm</span>';
  if (status === 'ot_pending') return '<span class="badge badge-ot">Chờ duyệt OT</span>';
  return '<span class="badge badge-abnormal">Bất thường / Vắng không phép</span>';
}

function attendanceRowActions(row) {
  const disabled = row.lock_status === 'locked' ? 'disabled' : '';
  return `
    <select class="attendance-action-select" onchange="handleAttendanceAction('${row.employee_id}', this.value)" ${disabled}>
      <option value="">Chọn hành động</option>
      <option value="detail">Xem chi tiết</option>
      <option value="edit">Điều chỉnh công bất thường</option>
      <option value="approve_ot">Duyệt OT</option>
      <option value="abnormal">Đánh dấu bất thường</option>
      <option value="reopen">Mở lại công</option>
      <option value="lock_employee">Khóa dữ liệu nhân viên</option>
    </select>
  `;
}

function renderAttendanceSummaryCards(stats) {
  const wrap = document.getElementById('attendanceSummaryCards');
  if (!wrap) return;
  const cards = [
    ['Tổng nhân viên đi làm', stats.present_total],
    ['Đi muộn', stats.late_total],
    ['Nghỉ phép', stats.leave_total],
    ['OT chờ duyệt', stats.ot_pending],
    ['Chấm công bất thường', stats.abnormal_total],
    ['Đã chốt công', stats.locked_total],
    ['Chưa chốt công', stats.unlocked_total]
  ];
  wrap.innerHTML = cards.map(([title, value]) => `<article class="summary-card"><h4>${title}</h4><p>${value || 0}</p></article>`).join('');
}

function fillAttendanceRows(rows) {
  const body = document.getElementById('attendanceRows');
  if (!body) return;
  body.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${esc(r.employee_name)}<br><small>${esc(r.employee_code)}</small></td>
      <td>${esc(r.department)}</td>
      <td>${r.working_days || 0}</td>
      <td>${Number(r.total_hours || 0).toFixed(2)}</td>
      <td>${Number(r.overtime_hours || 0).toFixed(2)}</td>
      <td>${r.late_count || 0}</td>
      <td>${r.early_count || 0}</td>
      <td>${r.leave_days || 0}</td>
      <td>${r.unpaid_leave_days || 0}</td>
      <td>${attendanceStatusBadge(r.attendance_status)}</td>
      <td>${r.lock_status === 'locked' ? '<span class="badge badge-lock">Đã chốt công</span>' : '<span class="badge b-warning">Chưa chốt</span>'}</td>
      <td>${attendanceRowActions(r)}</td>
    </tr>
  `).join('') : '<tr><td colspan="11">Không có dữ liệu attendance phù hợp.</td></tr>';
}

async function loadAttendanceSummary() {
  const f = attendanceFilterPayload();
  const query = new URLSearchParams(f).toString();
  const [rows, stats, logs] = await Promise.all([
    api(`/api/admin/attendance/records?${query}`),
    api(`/api/admin/attendance/stats?month=${f.month}&year=${f.year}`),
    api(`/api/admin/attendance/audit-log?month=${f.month}&year=${f.year}`)
  ]);
  fillAttendanceRows(rows);
  renderAttendanceSummaryCards(stats);
  const logEl = document.getElementById('attendanceAudit');
  if (logEl) logEl.innerHTML = logs.map(l => `<li>${fmtDate(l.time)} ${l.action} | ${esc(l.description || '')}</li>`).join('') || '<li>Chưa có log.</li>';
}

async function lockMonth() {
  const f = attendanceFilterPayload();
  const confirm = await Swal.fire({
    title: `Xác nhận chốt công tháng ${String(f.month).padStart(2, '0')}/${f.year}?`,
    html: 'Sau khi chốt:<br>- không thể chỉnh sửa attendance<br>- dữ liệu sẽ chuyển sang tính lương<br>- chỉ Admin mới có thể mở lại',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Chốt công',
    cancelButtonText: 'Hủy'
  });
  if (!confirm.isConfirmed) return;
  await api('/api/admin/attendance/lock-month', { method: 'POST', body: JSON.stringify({ month: +f.month, year: +f.year }) });
  await Swal.fire({ icon: 'success', title: 'Đã chốt công tháng' });
  await loadAttendanceSummary();
}

async function reopenMonth() {
  const f = attendanceFilterPayload();
  const { isConfirmed, value } = await Swal.fire({
    title: 'Lý do mở lại công:',
    input: 'text',
    inputPlaceholder: 'Nhập lý do bắt buộc',
    showCancelButton: true,
    confirmButtonText: 'Mở lại công',
    preConfirm: (v) => {
      if (!v || !v.trim()) {
        Swal.showValidationMessage('Vui lòng nhập lý do mở lại công');
        return false;
      }
      return v.trim();
    }
  });
  if (!isConfirmed) return;
  await api('/api/admin/attendance/reopen-month', { method: 'POST', body: JSON.stringify({ month: +f.month, year: +f.year, reason: value }) });
  await Swal.fire({ icon: 'success', title: 'Đã mở lại bảng công' });
  await loadAttendanceSummary();
}

async function openAttendanceDetailPanel(employeeId) {
  const f = attendanceFilterPayload();
  const details = await api(`/api/admin/attendance/records/${employeeId}/details?month=${f.month}&year=${f.year}`);
  const panel = document.getElementById('attendanceDetailPanel');
  const content = document.getElementById('attendanceDetailContent');
  if (!panel || !content) return;
  content.innerHTML = details.length ? `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ngày</th><th>Giờ vào</th><th>Giờ ra</th><th>Giờ công</th><th>Giờ OT</th><th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          ${details.map((d) => `
            <tr>
              <td>${fmtDate(d.work_date)}</td>
              <td>${d.check_in ? new Date(d.check_in).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '--'}</td>
              <td>${d.check_out ? new Date(d.check_out).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '--'}</td>
              <td>${Number(d.working_hours || 0).toFixed(2)}</td>
              <td>${Number(d.overtime_hours || 0).toFixed(2)}</td>
              <td>${esc(d.status_label || '--')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  ` : '<p>Không có dữ liệu chi tiết trong kỳ công này.</p>';
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function handleAttendanceAction(employeeId, action) {
  if (!action) return;
  const record = await api(`/api/admin/attendance/records?month=${attendanceFilterPayload().month}&year=${attendanceFilterPayload().year}`)
    .then((rows) => rows.find((x) => Number(x.employee_id) === Number(employeeId)));
  if (!record) return;
  if (action === 'detail') {
    await openAttendanceDetailPanel(employeeId);
  } else if (action === 'edit') {
    const details = await api(`/api/admin/attendance/records/${employeeId}/details?month=${attendanceFilterPayload().month}&year=${attendanceFilterPayload().year}`);
    if (!details.length) {
      await Swal.fire({ icon: 'info', title: 'Không có bản ghi để điều chỉnh' });
      return;
    }
    const latest = details[0];
    const { isConfirmed, value } = await Swal.fire({
      title: 'Chỉnh sửa công thủ công',
      html: `
        <input id="adCheckIn" class="swal2-input" type="datetime-local">
        <input id="adCheckOut" class="swal2-input" type="datetime-local">
        <input id="adOvertimeHours" class="swal2-input" type="number" min="0" step="0.5" placeholder="Số giờ OT">
        <select id="adAttendanceType" class="swal2-input"><option value="normal">Bình thường</option><option value="late_early">Đi muộn / Về sớm</option><option value="abnormal">Bất thường</option></select>
        <textarea id="adNote" class="swal2-textarea" placeholder="Ghi chú điều chỉnh: Quên check-in / Máy chấm công lỗi / Đi công tác..."></textarea>
      `,
      showCancelButton: true,
      confirmButtonText: 'Lưu chỉnh sửa',
      preConfirm: () => ({
        check_in: document.getElementById('adCheckIn').value || null,
        check_out: document.getElementById('adCheckOut').value || null,
        overtime_hours: Number(document.getElementById('adOvertimeHours').value || 0),
        attendance_type: document.getElementById('adAttendanceType').value,
        note: document.getElementById('adNote').value
      })
    });
    if (!isConfirmed) return;
    await api(`/api/admin/attendance/${latest.attendance_id}/manual-update`, { method: 'POST', body: JSON.stringify(value) });
    await Swal.fire({ icon: 'success', title: 'Đã cập nhật chấm công' });
  } else if (action === 'approve_ot') {
    await openPendingOvertimePanel();
  } else if (action === 'abnormal') {
    const { isConfirmed, value } = await Swal.fire({ title: 'Đánh dấu bất thường', input: 'text', inputLabel: 'Lý do xử lý bất thường', showCancelButton: true, confirmButtonText: 'Xác nhận' });
    if (!isConfirmed) return;
    const details = await api(`/api/admin/attendance/records/${employeeId}/details?month=${attendanceFilterPayload().month}&year=${attendanceFilterPayload().year}`);
    if (!details.length) return;
    await api(`/api/admin/attendance/${details[0].attendance_id}/mark-abnormal`, { method: 'POST', body: JSON.stringify({ note: value || '' }) });
    await Swal.fire({ icon: 'success', title: 'Đã đánh dấu bất thường' });
  } else if (action === 'reopen') {
    await reopenMonth();
  } else if (action === 'lock_employee') {
    const details = await api(`/api/admin/attendance/records/${employeeId}/details?month=${attendanceFilterPayload().month}&year=${attendanceFilterPayload().year}`);
    if (!details.length) return;
    await api(`/api/admin/attendance/${details[0].attendance_id}/manual-update`, { method: 'POST', body: JSON.stringify({ attendance_type: 'locked', note: 'Admin khóa công nhân viên' }) });
    await Swal.fire({ icon: 'success', title: 'Đã khóa công nhân viên' });
  }
  await loadAttendanceSummary();
}

async function openPendingOvertimePanel() {
  const f = attendanceFilterPayload();
  const pending = await api(`/api/admin/attendance/overtime/pending?month=${f.month}&year=${f.year}`);
  if (!pending.length) {
    await Swal.fire({ icon: 'info', title: 'Không có yêu cầu OT chờ Admin duyệt' });
    return;
  }
  const fmtDateTime = (value) => {
    if (!value) return '--';
    const d = new Date(value);
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} - ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };
  const html = `<div style="text-align:left;max-height:320px;overflow:auto">${pending.map((r) => `
    <div id="ot-row-${r.id}" style="padding:8px;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:8px">
      <b>${esc(r.employee_name)}</b> (${esc(r.employee_code)}) - ${esc(r.department)}<br>
      Ngày OT: ${fmtDate(r.date)} • Gửi lúc: ${fmtDateTime(r.created_at)}<br>
      OT dự kiến: ${r.start_ot_time ? new Date(r.start_ot_time).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '--'} → ${r.end_ot_time ? new Date(r.end_ot_time).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '--'}<br>
      Số giờ OT: ${Number(r.hours || 0).toFixed(2)} giờ<br>
      Lý do: ${esc(r.reason || '')}
      <div id="ot-status-${r.id}" style="margin-top:8px">${renderOtStatus(r.status)}</div>
      <div id="ot-actions-${r.id}" style="margin-top:8px">${renderOtActions(r.id, r.status)}</div>
    </div>`).join('')}</div>`;
  await Swal.fire({ title: 'Duyệt tăng ca cuối cùng', html, width: 800, showConfirmButton: false, showCancelButton: true });
}
function renderOtStatus(status) {
  const fieldSource = "overtime.status";
  if (status === 'approved') return '✅ Trạng thái: Đã duyệt';
  if (status === 'rejected') return '❌ Trạng thái: Đã từ chối';
  return `⏳ Trạng thái: Chờ duyệt <br><small style="color:#6b7280">[DEBUG] UI đọc field: ${fieldSource} = ${esc(status || '--')}</small>`;
}

function renderOtActions(id, status) {
  const fieldSource = "overtime.status";
  if (status === 'approved') return '<span class="badge badge-success">Đã duyệt</span>';
  if (status === 'rejected') return '<span class="badge badge-danger">Đã từ chối</span>';
  return `<div><small style="color:#6b7280">[DEBUG] Nút dựa trên ${fieldSource} = ${esc(status || '--')}</small></div><button onclick="finalReviewOt(${id}, 'approve')">Duyệt</button> <button onclick="finalReviewOt(${id}, 'reject')">Từ chối</button> <button onclick="resetOtRequest(${id})">Xóa</button>`;
}

async function finalReviewOt(id, action) {
  const confirmText = action === 'approve' ? 'Xác nhận duyệt tăng ca?' : 'Xác nhận từ chối tăng ca?';
  const confirm = await Swal.fire({
    title: confirmText,
    icon: 'question',
    input: 'text',
    inputPlaceholder: action === 'approve' ? 'Ghi chú duyệt OT (tuỳ chọn)' : 'Lý do từ chối (tuỳ chọn)',
    showCancelButton: true,
    confirmButtonText: 'Xác nhận'
  });
  if (!confirm.isConfirmed) return;

  await api(`/api/admin/attendance/overtime/${id}/final-review`, {
    method: 'POST',
    body: JSON.stringify({ action, note: confirm.value || '' })
  });

  const statusEl = document.getElementById(`ot-status-${id}`);
  const actionsEl = document.getElementById(`ot-actions-${id}`);
  if (statusEl) {
    statusEl.innerHTML = renderOtStatus(action === 'approve' ? 'approved' : 'rejected');
  }
  if (actionsEl) {
    actionsEl.innerHTML = renderOtActions(id, action === 'approve' ? 'approved' : 'rejected');
  }
  await Swal.fire({
    icon: 'success',
    title: action === 'approve' ? 'Đã duyệt yêu cầu tăng ca thành công' : 'Đã từ chối yêu cầu tăng ca thành công'
  });
  await loadAttendanceSummary();
}
window.handleAttendanceAction = handleAttendanceAction;
window.finalReviewOt = finalReviewOt;
window.resetOtRequest = resetOtRequest;

async function resetOtRequest(id) {
  const confirm = await Swal.fire({
    title: "Xóa yêu cầu tăng ca?",
    text: "Toàn bộ request, notification và trạng thái duyệt sẽ bị reset để test lại từ đầu.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "Xóa",
    cancelButtonText: "Hủy"
  });
  if (!confirm.isConfirmed) return;
  await api(`/api/admin/attendance/overtime/${id}/reset`, { method: 'POST' });
  const rowEl = document.getElementById(`ot-row-${id}`);
  if (rowEl) rowEl.remove();
  await Swal.fire({ icon: 'success', title: 'Đã xóa OT request để test lại' });
  await loadAttendanceSummary();
}
let selectedPayrollId = null;
let selectedComplaintId = null;

function payrollFilterPayload() {
  return new URLSearchParams({
    month: String(document.getElementById('month')?.value || now.getMonth() + 1),
    year: String(document.getElementById('year')?.value || now.getFullYear()),
    keyword: document.getElementById('payrollSearch')?.value?.trim() || '',
    department_id: document.getElementById('payrollDepartment')?.value || '',
    status: document.getElementById('payrollStatus')?.value || '',
    role: document.getElementById('payrollRole')?.value || '',
    has_complaint: document.getElementById('payrollComplaint')?.value || '',
    locked: document.getElementById('payrollLocked')?.value || '',
  });
}

function payrollStatusBadge(status, label) {
  const css = status === 'draft' ? 'badge-payroll-draft'
    : status === 'pending' || status === 'pending_approval' ? 'badge-payroll-pending'
    : status === 'approved' || status === 'paid' ? 'badge-payroll-approved'
    : status === 'locked' || status === 'finalized' ? 'badge-payroll-locked'
    : 'badge-payroll-complaint';
  return `<span class="badge ${css}">${esc(label || status)}</span>`;
}

function renderPayrollSummary(summary) {
  const wrap = document.getElementById('payrollSummaryCards'); if (!wrap) return;
  const cards = [
    ['Tổng payroll tháng này', summary.total_payroll],
    ['Đang chờ duyệt', summary.pending],
    ['Đã duyệt', summary.approved],
    ['Đã chốt', summary.locked],
    ['Khiếu nại đang xử lý', summary.complaint],
    ['Payroll bất thường', summary.abnormal],
  ];
  wrap.innerHTML = cards.map(([title, value]) => `<article class="summary-card"><h4>${title}</h4><p>${value || 0}</p></article>`).join('');
}

function renderPayrollRows(rows) {
  const tbody = document.getElementById('payrollRows'); if (!tbody) return;
  tbody.innerHTML = rows.length ? rows.map((r) => `
    <tr>
      <td>${esc(r.employee_code)}</td><td>${esc(r.employee_name)}</td><td>${esc(r.department)}</td><td>${esc(r.position)}</td>
      <td>${formatCurrency(r.basic_salary)}</td><td>${formatCurrency(r.allowance)}</td><td>${formatCurrency(r.deduction)}</td>
      <td>${formatCurrency(r.ot)}</td><td>${formatCurrency(r.tax)}</td><td>${formatCurrency(r.net_salary)}</td>
      <td>${payrollStatusBadge(r.status, r.status_label)}</td>
      <td>${r.has_complaint ? '<span class="badge badge-payroll-complaint">Có</span>' : '<span class="muted">Không</span>'}</td>
      <td class="table-actions">
        <button onclick="selectPayroll(${r.id})">Chi tiết</button>
        <button onclick="approvePayrollById(${r.id})">Duyệt</button>
      </td>
    </tr>
  `).join('') : '<tr><td colspan="13">Không có dữ liệu payroll</td></tr>';
}

async function loadPayrollOverview() {
  const params = payrollFilterPayload();
  const payload = await api(`/api/admin/payroll/overview?${params.toString()}`);
  renderPayrollSummary(payload.summary || {});
  renderPayrollRows(payload.items || []);
  const logs = await api('/api/admin/payroll/audit');
  document.getElementById('payrollAuditLog').innerHTML = (logs || []).slice(0, 30).map((l) => `<li>${fmtDate(l.time)} ${esc(l.action)} | ${esc(l.description || '')}</li>`).join('') || '<li>Chưa có log.</li>';
}

async function selectPayroll(id) {
  selectedPayrollId = Number(id);
  const d = await api(`/api/admin/payroll/${id}/detail`);
  document.getElementById('payrollDetailPanel').innerHTML = `
    <p><b>Kỳ lương:</b> ${esc(d.payroll_period)}</p>
    <p><b>Lương cơ bản:</b> ${formatCurrency(d.basic_salary)}</p>
    <p><b>Allowance:</b> ${formatCurrency(d.allowance)}</p>
    <p><b>Insurance:</b> ${formatCurrency(d.insurance)}</p>
    <p><b>OT:</b> ${formatCurrency(d.ot)}</p>
    <p><b>Late penalty:</b> ${formatCurrency(d.late_penalty)}</p>
    <p><b>Thuế TNCN:</b> ${formatCurrency(d.tax)}</p>
    <p><b>Dependent deduction:</b> ${formatCurrency(d.dependent_deduction)} (${d.number_of_dependents} người phụ thuộc)</p>
    <p><b>Net salary:</b> ${formatCurrency(d.net_salary)}</p>
    <p><b>Người tính lương:</b> ${esc(d.calculated_by)}</p>
    <p><b>Cập nhật:</b> ${fmtDate(d.updated_at)}</p>`;
}

async function payrollApproval(action, id = selectedPayrollId) {
  if (!id) return Swal.fire({ icon: 'info', title: 'Chọn payroll trước khi thao tác' });
  let reason = '';
  if (action !== 'approve') {
    const ask = await Swal.fire({ title: action === 'reject' ? 'Lý do từ chối bắt buộc' : 'Lý do yêu cầu HR tính lại', input: 'textarea', inputValidator: (v) => (!v ? 'Bắt buộc nhập lý do' : undefined), showCancelButton: true });
    if (!ask.isConfirmed) return;
    reason = ask.value || '';
  } else {
    const c = await Swal.fire({ title: 'Xác nhận phê duyệt payroll?', icon: 'question', showCancelButton: true });
    if (!c.isConfirmed) return;
  }
  await api(`/api/admin/payroll/${id}/approval`, { method: 'POST', body: JSON.stringify({ action, reason }) });
  await Swal.fire({ icon: 'success', title: 'Thao tác thành công' });
  await loadPayrollOverview();
  await selectPayroll(id);
}

async function approvePayrollById(id) { return payrollApproval('approve', id); }

async function finalizePayrollMonth() {
  const m = Number(document.getElementById('month')?.value || now.getMonth() + 1);
  const y = Number(document.getElementById('year')?.value || now.getFullYear());
  const c = await Swal.fire({
    title: `Xác nhận chốt lương tháng ${String(m).padStart(2, '0')}/${y}?`,
    html: 'Sau khi chốt:<br>- không thể sửa payroll<br>- không thể sửa allowance<br>- không thể sửa deduction<br>- không thể sửa attendance ảnh hưởng lương<br>- phiếu lương được phép phát hành',
    showCancelButton: true, confirmButtonText: 'Chốt lương', cancelButtonText: 'Hủy', icon: 'warning',
  });
  if (!c.isConfirmed) return;
  await api('/api/admin/payroll/finalize-month', { method: 'POST', body: JSON.stringify({ month: m, year: y }) });
  await Swal.fire({ icon: 'success', title: 'Đã chốt lương tháng' });
  await loadPayrollOverview();
}

async function reopenPayrollMonth() {
  const { isConfirmed, value } = await Swal.fire({ title: 'Lý do mở lại payroll', input: 'textarea', inputValidator: (v) => (!v ? 'Bắt buộc nhập lý do mở lại payroll' : undefined), showCancelButton: true });
  if (!isConfirmed) return;
  const m = Number(document.getElementById('month')?.value || now.getMonth() + 1);
  const y = Number(document.getElementById('year')?.value || now.getFullYear());
  await api('/api/admin/payroll/reopen-month', { method: 'POST', body: JSON.stringify({ month: m, year: y, reason: value }) });
  await Swal.fire({ icon: 'success', title: 'Đã mở lại payroll' });
  await loadPayrollOverview();
}

async function openPayrollComplaints() {
  const m = Number(document.getElementById('month')?.value || now.getMonth() + 1);
  const y = Number(document.getElementById('year')?.value || now.getFullYear());
  const rows = await api(`/api/admin/payroll/complaints?month=${m}&year=${y}`);
  const panel = document.getElementById('payrollComplaintPanel');
  if (!rows.length) { panel.innerHTML = 'Không có complaint payroll kỳ này.'; return; }
  selectedComplaintId = rows[0].id;
  panel.innerHTML = rows.map((r) => `
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:8px;margin-bottom:8px">
      <b>${esc(r.employee_name)}</b> - ${esc(r.title)}<br>
      ${esc(r.content)}<br>
      Trạng thái: ${esc(r.status)} | HR phản hồi: ${r.hr_replied ? 'Đã có' : 'Chưa'}
      <div class="table-actions" style="margin-top:8px">
        <button onclick="handlePayrollComplaint(${r.id}, 'reply')">Phản hồi</button>
        <button onclick="handlePayrollComplaint(${r.id}, 'transfer_hr')">Chuyển HR xử lý</button>
        <button onclick="handlePayrollComplaint(${r.id}, 'resolve')">Đánh dấu đã giải quyết</button>
        <button onclick="handlePayrollComplaint(${r.id}, 'reopen_payroll')">Mở lại payroll</button>
      </div>
    </div>`).join('');
}

async function handlePayrollComplaint(id, action) {
  const ask = await Swal.fire({ title: 'Nhập nội dung xử lý', input: 'textarea', showCancelButton: true, inputPlaceholder: 'Nội dung phản hồi / lý do thao tác' });
  if (!ask.isConfirmed) return;
  await api(`/api/admin/payroll/complaints/${id}/handle`, { method: 'POST', body: JSON.stringify({ action, message: ask.value || '' }) });
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật complaint' });
  await openPayrollComplaints();
  await loadPayrollOverview();
}

window.selectPayroll = selectPayroll;
window.approvePayrollById = approvePayrollById;
window.handlePayrollComplaint = handlePayrollComplaint;


document.addEventListener('DOMContentLoaded', async () => {
  setDefaults();
  await loadDepartmentsSelect();
  document.getElementById('btnAddEmployee')?.addEventListener('click', addEmployee);
  document.getElementById('btnFilterEmployees')?.addEventListener('click', () => loadEmployees({ notify: true }));
  document.getElementById('btnResetFilters')?.addEventListener('click', () => {
    ['filterName', 'filterCode', 'filterEmail', 'filterPhone', 'filterDepartment', 'filterPosition', 'filterRole', 'filterWorkingStatus', 'filterAccountStatus', 'filterEmploymentType', 'filterProbation', 'filterHireFrom', 'filterHireTo']
      .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    const monthEl = document.getElementById('month');
    const yearEl = document.getElementById('year');
    const departmentEl = document.getElementById('department');
    if (monthEl) monthEl.value = now.getMonth() + 1;
    if (yearEl) yearEl.value = now.getFullYear();
    if (departmentEl) departmentEl.value = '';
    loadEmployees({ notify: true, isReset: true });
  });
  currentUser = await api('/api/auth/me').catch(() => null);
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
  if (window.ADMIN_PAGE === 'departments') {
    await loadDepartments();
    document.getElementById('add-department-btn')?.addEventListener('click', () => openDepartmentForm('create'));
    document.getElementById('search-department')?.addEventListener('input', () => loadDepartments());
    document.getElementById('closeDepartmentDetailBtn')?.addEventListener('click', () => {
      const card = document.getElementById('department-detail-card');
      if (card) card.style.display = 'none';
    });
    document.getElementById('editDepartmentFromDetailBtn')?.addEventListener('click', () => {
      if (currentDepartmentDetailId) openDepartmentForm('edit', currentDepartmentDetailId);
    });
    document.getElementById('disableDepartmentFromDetailBtn')?.addEventListener('click', () => {
      if (currentDepartmentDetailId) deactivateDepartmentWithChecks(currentDepartmentDetailId);
    });
  }
  if (window.ADMIN_PAGE === 'positions') {
    await loadPositions();
    document.getElementById('add-job-title-btn')?.addEventListener('click', () => openPositionForm('create'));
    document.getElementById('search-job-title')?.addEventListener('input', () => loadPositions());
    document.getElementById('positionStatusFilter')?.addEventListener('change', () => loadPositions());
    document.getElementById('positionSalaryFrom')?.addEventListener('change', () => loadPositions());
    document.getElementById('positionSalaryTo')?.addEventListener('change', () => loadPositions());
    document.getElementById('closeJobTitleDetailBtn')?.addEventListener('click', () => {
      const card = document.getElementById('job-title-detail-card');
      if (card) card.style.display = 'none';
    });
    document.getElementById('editJobTitleFromDetailBtn')?.addEventListener('click', () => {
      if (currentPositionDetailId) openPositionForm('edit', currentPositionDetailId);
    });
    document.getElementById('disableJobTitleFromDetailBtn')?.addEventListener('click', () => {
      if (currentPositionDetailId) deactivatePositionWithChecks(currentPositionDetailId);
    });
  }
  if (window.ADMIN_PAGE === 'attendance') {
    const monthEl = document.getElementById('attendanceMonth');
    const yearEl = document.getElementById('attendanceYear');
    if (monthEl) {
      monthEl.innerHTML = '<option value="">Tháng</option>' + Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">Tháng ${i + 1}</option>`).join('');
      monthEl.value = String(now.getMonth() + 1);
    }
    if (yearEl) {
      const currentYear = now.getFullYear();
      yearEl.innerHTML = '<option value="">Năm</option>' + [currentYear - 1, currentYear, currentYear + 1].map((y) => `<option value="${y}">${y}</option>`).join('');
      yearEl.value = String(currentYear);
    }
    const depSelect = document.getElementById('attendanceDepartment');
    if (depSelect) {
      const deps = await api('/api/departments').catch(() => []);
      depSelect.innerHTML = '<option value="">Phòng ban</option>' + deps.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
    }
    document.getElementById('btnAttendanceFilter')?.addEventListener('click', () => loadAttendanceSummary());
    ['attendanceMonth', 'attendanceYear', 'attendanceDepartment', 'attendanceStatus', 'attendanceLockStatus', 'attendanceOtStatus'].forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => loadAttendanceSummary());
    });
    document.getElementById('attendanceSearch')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadAttendanceSummary(); });
    document.getElementById('btnLockAttendanceMonth')?.addEventListener('click', () => lockMonth());
    document.getElementById('btnExportAttendance')?.addEventListener('click', () => {
      const f = attendanceFilterPayload();
      window.location.href = `/api/admin/attendance/export?month=${f.month}&year=${f.year}`;
    });
    document.getElementById('btnApproveOt')?.addEventListener('click', () => openPendingOvertimePanel());
    document.getElementById('btnHandleAbnormal')?.addEventListener('click', async () => {
      const { isConfirmed, value } = await Swal.fire({ title: 'Xử lý bất thường', input: 'text', inputLabel: 'Nhập mã nhân viên cần xử lý', showCancelButton: true });
      if (!isConfirmed || !value) return;
      await handleAttendanceAction(value, 'abnormal');
    });
    await loadAttendanceSummary();
  }
  if (window.ADMIN_PAGE === 'salary') {
    const deps = await api('/api/departments').catch(() => []);
    const depSelect = document.getElementById('payrollDepartment');
    if (depSelect) depSelect.innerHTML = '<option value="">Phòng ban</option>' + deps.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
    const roleRows = (await api('/api/admin/employees/meta').catch(() => ({ roles: [] }))).roles || [];
    const roleSelect = document.getElementById('payrollRole');
    if (roleSelect) roleSelect.innerHTML = '<option value="">Role</option>' + roleRows.map((r) => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
    document.getElementById('btnPayrollSearch')?.addEventListener('click', () => loadPayrollOverview());
    ['payrollDepartment', 'payrollStatus', 'payrollRole', 'payrollComplaint', 'payrollLocked', 'month', 'year'].forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => loadPayrollOverview());
    });
    document.getElementById('payrollSearch')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadPayrollOverview(); });
    document.getElementById('btnApprovePayroll')?.addEventListener('click', () => payrollApproval('approve'));
    document.getElementById('btnRejectPayroll')?.addEventListener('click', () => payrollApproval('reject'));
    document.getElementById('btnRequestRecalcPayroll')?.addEventListener('click', () => payrollApproval('recalculate'));
    document.getElementById('btnFinalizePayrollMonth')?.addEventListener('click', () => finalizePayrollMonth());
    document.getElementById('btnBulkApprovePayroll')?.addEventListener('click', async () => {
      const rows = await api(`/api/admin/payroll/overview?${payrollFilterPayload().toString()}`);
      const pending = (rows.items || []).filter((r) => ['pending', 'pending_approval'].includes(r.status));
      for (const row of pending) {
        await api(`/api/admin/payroll/${row.id}/approval`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) });
      }
      await Swal.fire({ icon: 'success', title: `Đã duyệt ${pending.length} payroll chờ duyệt` });
      await loadPayrollOverview();
    });
    document.getElementById('btnOpenComplaints')?.addEventListener('click', () => openPayrollComplaints());
    document.getElementById('btnExportPayroll')?.addEventListener('click', () => {
      window.location.href = `/api/admin/payroll/export?${payrollFilterPayload().toString()}`;
    });
    document.getElementById('btnTopFilter')?.addEventListener('click', (e) => { e.preventDefault(); loadPayrollOverview(); });
    document.getElementById('btnFinalizePayrollMonth')?.insertAdjacentHTML('afterend', '<button id="btnReopenPayrollMonth">Mở lại payroll</button>');
    document.getElementById('btnReopenPayrollMonth')?.addEventListener('click', () => reopenPayrollMonth());
    await loadPayrollOverview();
    await openPayrollComplaints();
  }
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