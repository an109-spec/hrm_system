const api = {
  profile: '/hr/api/profile',
  updatePersonal: '/hr/api/profile/personal-info',
  changePassword: '/hr/api/profile/change-password',
  uploadAvatar: '/hr/api/profile/avatar',
  dependents: '/hr/api/profile/dependents',
  history: '/hr/api/profile/history'
};

const relMap = { con: 'Con', vo_chong: 'Vợ/Chồng', bo_me: 'Bố/Mẹ' };

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Có lỗi xảy ra');
  return data;
}

function renderWorkInfo(work) {
  const fields = {
    'Mã nhân viên': work.employee_code,
    'Phòng ban': work.department,
    'Chức danh': work.position,
    'Quản lý trực tiếp': work.manager,
    'Loại nhân sự': work.employment_type,
    'Loại hợp đồng': work.contract_type || '--',
    'Bắt đầu HĐ': work.contract_start_date || '--',
    'Kết thúc HĐ': work.contract_end_date || '--',
    'Lương cơ bản': work.basic_salary ?? '--',
    'Phụ cấp hiện tại': work.allowance ?? '--',
    'Trạng thái tài khoản': work.account_status,
  };
  document.getElementById('workInfo').innerHTML = Object.entries(fields).map(([k,v]) => `<div class="item"><small>${k}</small><div><b>${v}</b></div></div>`).join('');
}

function renderDependents(items, count) {
  document.getElementById('dependentCount').textContent = count;
  const body = document.getElementById('dependentTableBody');
  body.innerHTML = items.map(d => `
    <tr>
      <td>${d.full_name}</td><td>${d.dob || '--'}</td><td>${relMap[d.relationship] || d.relationship}</td>
      <td>${d.tax_code || '--'}</td><td>${d.is_valid ? 'Hợp lệ' : 'Không hợp lệ'}</td>
      <td><button class="btn" data-edit='${JSON.stringify(d)}'>Sửa</button></td>
    </tr>`).join('');

  body.querySelectorAll('[data-edit]').forEach(btn => btn.onclick = () => openDependentModal(JSON.parse(btn.dataset.edit)));
}

function renderHistory(items) {
  const list = document.getElementById('historyList');
  list.innerHTML = items.map(it => `<li><b>${it.action}</b> - ${it.description || '--'}<br><small>${it.created_at || ''}</small></li>`).join('');
}

async function loadProfile() {
  const data = await fetchJSON(api.profile);
  const h = data.header;
  document.getElementById('avatarPreview').src = h.avatar || 'https://via.placeholder.com/120';
  document.getElementById('headerFullName').textContent = h.full_name;
  document.getElementById('headerCode').textContent = h.employee_code;
  document.getElementById('headerDepartment').textContent = h.department;
  document.getElementById('headerPosition').textContent = h.position;
  document.getElementById('headerHireDate').textContent = h.hire_date || '--';
  document.getElementById('headerWorkingStatus').textContent = h.working_status || '--';

  const form = document.getElementById('personalInfoForm');
  Object.entries(data.personal_info).forEach(([k,v]) => form.elements[k] && (form.elements[k].value = v || ''));
  renderWorkInfo(data.work_info);
  renderDependents(data.dependents, data.number_of_dependents);
  renderHistory(data.history);
}

async function confirmAndRun(title, callback) {
  const confirm = await Swal.fire({ icon:'question', title, showCancelButton:true, confirmButtonText:'Xác nhận', cancelButtonText:'Hủy' });
  if (!confirm.isConfirmed) return;
  try {
    await callback();
    await Swal.fire({ icon:'success', title:'Thành công', text:'Cập nhật thành công' });
    await loadProfile();
  } catch (e) {
    Swal.fire({ icon:'error', title:'Lỗi', text:e.message });
  }
}

document.getElementById('personalInfoForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = Object.fromEntries(new FormData(e.target).entries());
  await confirmAndRun('Bạn có chắc muốn cập nhật hồ sơ cá nhân?', async () => {
    await fetchJSON(api.updatePersonal, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(formData) });
  });
});

document.getElementById('btnChangePassword').addEventListener('click', async () => {
  const { value } = await Swal.fire({
    title:'Đổi mật khẩu',
    html:`<input id='cur' class='swal2-input' type='password' placeholder='Mật khẩu hiện tại'>
    <input id='new' class='swal2-input' type='password' placeholder='Mật khẩu mới'>
    <input id='cfm' class='swal2-input' type='password' placeholder='Xác nhận mật khẩu'>`,
    preConfirm: () => ({
      current_password: document.getElementById('cur').value,
      new_password: document.getElementById('new').value,
      confirm_password: document.getElementById('cfm').value,
    }),
    showCancelButton:true
  });
  if (!value) return;
  await confirmAndRun('Xác nhận đổi mật khẩu?', async () => {
    await fetchJSON(api.changePassword, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(value) });
  });
});

document.getElementById('btnChangeAvatar').addEventListener('click', () => document.getElementById('avatarInput').click());
document.getElementById('avatarInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData(); fd.append('avatar', file);
  await confirmAndRun('Xác nhận cập nhật ảnh đại diện?', async () => {
    await fetchJSON(api.uploadAvatar, { method:'POST', body: fd });
  });
});

async function openDependentModal(existing = null) {
  const { value } = await Swal.fire({
    title: existing ? 'Cập nhật người phụ thuộc' : 'Thêm người phụ thuộc',
    html:`<input id='name' class='swal2-input' placeholder='Họ tên' value='${existing?.full_name || ''}'>
    <input id='dob' class='swal2-input' type='date' value='${existing?.dob || ''}'>
    <select id='rel' class='swal2-input'><option value='con'>Con</option><option value='vo_chong'>Vợ/Chồng</option><option value='bo_me'>Bố/Mẹ</option></select>
    <input id='tax' class='swal2-input' placeholder='MST cá nhân' value='${existing?.tax_code || ''}'>
    <label style='display:flex;gap:6px;justify-content:center'><input id='valid' type='checkbox' ${existing?.is_valid !== false ? 'checked' : ''}> Hợp lệ</label>`,
    didOpen: () => { if (existing?.relationship) document.getElementById('rel').value = existing.relationship; },
    preConfirm: () => ({
      full_name: document.getElementById('name').value,
      dob: document.getElementById('dob').value,
      relationship: document.getElementById('rel').value,
      tax_code: document.getElementById('tax').value,
      is_valid: document.getElementById('valid').checked,
    }),
    showCancelButton:true
  });
  if (!value) return;

  const url = existing ? `${api.dependents}/${existing.id}` : api.dependents;
  const method = existing ? 'PUT' : 'POST';
  await confirmAndRun('Bạn có chắc muốn lưu người phụ thuộc?', async () => {
    await fetchJSON(url, { method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(value) });
  });
}

document.getElementById('btnAddDependent').addEventListener('click', () => openDependentModal());
document.getElementById('btnEditProfile').addEventListener('click', () => document.getElementById('personalInfoForm').scrollIntoView({behavior:'smooth'}));

loadProfile().catch(e => Swal.fire({ icon:'error', title:'Không thể tải hồ sơ', text:e.message }));