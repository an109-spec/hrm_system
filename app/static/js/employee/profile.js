// TAB SWITCH
const appDialogs = window.appDialogs || {};

// TAB SWITCH
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  });
});

let selectedFile = null;

const input = document.getElementById('avatarInput');
const uploadBtn = document.getElementById('uploadAvatarBtn');
if (input) {
  input.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    selectedFile = file;

    const reader = new FileReader();

    reader.onload = function (ev) {
      let avatar = document.querySelector('.profile-avatar');
      if (!avatar) {
        const wrapper = document.querySelector('.avatar-wrapper');
        wrapper.innerHTML = '<img class="profile-avatar">';
        avatar = document.querySelector('.profile-avatar');
      }

      avatar.src = ev.target.result;
    };

    reader.readAsDataURL(file);
  });
}

// UPLOAD ẢNH (QUAN TRỌNG)
if (uploadBtn) {
  uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return appDialogs.error({ title: 'Bạn chưa chọn ảnh' });
    const confirm = await appDialogs.confirm({ title: 'Xác nhận cập nhật ảnh đại diện?', text: 'Ảnh mới sẽ thay thế ảnh cũ.', confirmText: 'Cập nhật' });
    if (!confirm.confirmed) return;

    const formData = new FormData();
    formData.append('avatar', selectedFile);

    try {
      uploadBtn.innerText = 'Đang upload...';
      uploadBtn.disabled = true;

      const res = await fetch('/employee/upload-avatar', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload thất bại');
      await appDialogs.success({ title: 'Cập nhật ảnh thành công' });
      location.reload();
    } catch (err) {
      await appDialogs.error({ title: 'Không thể cập nhật ảnh', text: err.message });
    } finally {
      uploadBtn.innerText = 'Cập nhật ảnh';
      uploadBtn.disabled = false;
    }
  });
}


const profileForm = document.getElementById('profileForm');
const editBtn = document.getElementById('editBtn');
const cancelBtn = document.getElementById('cancelBtn');
const saveCancelActions = document.getElementById('saveCancelActions');
const inputs = profileForm ? profileForm.querySelectorAll('input, select') : [];

function toggleEditMode(isEditing) {
  inputs.forEach((input) => {
    if (!input.readOnly || input.tagName === 'SELECT' || input.id === 'detailAddress') {
      if (input.getAttribute('name') !== 'email') {
        if (input.tagName === 'SELECT') input.disabled = !isEditing;
        else input.readOnly = !isEditing;
        input.classList.toggle('readonly-input', !isEditing);
      }
    }
  });
  if (editBtn) editBtn.style.display = isEditing ? 'none' : 'block';
  if (saveCancelActions) saveCancelActions.style.display = isEditing ? 'flex' : 'none';
}

if (editBtn) editBtn.addEventListener('click', () => toggleEditMode(true));
if (cancelBtn) cancelBtn.addEventListener('click', () => location.reload());

if (profileForm) {
  profileForm.addEventListener('submit', async (e) => {
    const submitter = e.submitter;
    if (submitter && submitter.value === 'change_password') return;
    e.preventDefault();

    const confirm = await appDialogs.confirm({ title: 'Xác nhận lưu thay đổi hồ sơ?', confirmText: 'Lưu thay đổi' });
    if (!confirm.confirmed) return;

    inputs.forEach((i) => (i.disabled = false));
    const data = Object.fromEntries(new FormData(profileForm).entries());
    inputs.forEach((i) => {
      if (i.tagName === 'SELECT') i.disabled = true;
    });

    const response = await fetch('/employee/update-profile', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    });
    if (response.ok) {
      await appDialogs.success({ title: 'Cập nhật thông tin thành công' });
      location.reload();
      return;
    }
    const err = await response.json().catch(() => ({}));
    await appDialogs.error({ title: 'Không thể lưu hồ sơ', text: err.error || 'Lỗi hệ thống' });
  });
}

const REL_MAP = { con: 'Con', vo_chong: 'Vợ/Chồng', bo: 'Bố', me: 'Mẹ', khac: 'Khác' };
function dependentRow(item) {
  return `<tr>
    <td>${item.full_name}</td><td>${item.dob || '--'}</td><td>${REL_MAP[item.relationship] || item.relationship}</td>
    <td>${item.tax_code || '--'}</td><td>${item.is_valid ? '✅ Hợp lệ' : '❌ Không hợp lệ'}</td>
    <td>
      <button data-action="edit-dependent" data-id="${item.id}">Sửa</button>
      <button data-action="delete-dependent" data-id="${item.id}">Xóa</button>
    </td>
  </tr>`;
}

async function fetchDependents() {
  const body = document.getElementById('dependentTableBody');
  if (!body) return [];
  const res = await fetch('/employee/profile/dependents');
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Không tải được người phụ thuộc');
  body.innerHTML = (data.items || []).map(dependentRow).join('') || '<tr><td colspan="6">Chưa có dữ liệu</td></tr>';
  document.getElementById('dependentCount').textContent = data.number_of_dependents || 0;
  return data.items || [];
}


async function upsertDependent(id = null) {
  const { value: formValues } = await Swal.fire({
    title: id ? 'Cập nhật người phụ thuộc' : 'Thêm người phụ thuộc',
    html: `<input id="swal-name" class="swal2-input" placeholder="Họ tên">
      <input id="swal-dob" type="date" class="swal2-input">
      <select id="swal-rel" class="swal2-select"><option value="con">Con</option><option value="vo_chong">Vợ/Chồng</option><option value="bo">Bố</option><option value="me">Mẹ</option><option value="khac">Khác</option></select>
      <input id="swal-tax" class="swal2-input" placeholder="Mã số thuế cá nhân">
      <label style="display:flex;gap:8px;justify-content:center;margin-top:8px"><input id="swal-valid" type="checkbox" checked>Trạng thái hợp lệ</label>`,
    focusConfirm: false,
    showCancelButton: true,
    preConfirm: () => ({
      full_name: document.getElementById('swal-name').value,
      dob: document.getElementById('swal-dob').value,
      relationship: document.getElementById('swal-rel').value,
      tax_code: document.getElementById('swal-tax').value,
      is_valid: document.getElementById('swal-valid').checked,
    }),
  });
  if (!formValues) return;
  const url = id ? `/employee/profile/dependents/${id}` : '/employee/profile/dependents';
  const method = id ? 'PUT' : 'POST';
  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formValues) });
  const data = await res.json();
  if (!res.ok) return appDialogs.error({ title: 'Lưu thất bại', text: data.error || 'Lỗi hệ thống' });
  await appDialogs.success({ title: data.message || 'Thành công' });
  await fetchDependents();
}

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-action]');
  if (!btn) return;
  const id = btn.dataset.id;
  if (btn.dataset.action === 'edit-dependent') return upsertDependent(id);
  if (btn.dataset.action === 'delete-dependent') {
    const confirm = await appDialogs.confirm({ title: 'Xóa người phụ thuộc?', text: 'Thao tác này không thể hoàn tác.', icon: 'warning', confirmText: 'Xóa' });
    if (!confirm.confirmed) return;
    const res = await fetch(`/employee/profile/dependents/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) return appDialogs.error({ title: 'Không thể xóa', text: data.error || '' });
    await appDialogs.success({ title: data.message || 'Đã xóa' });
    await fetchDependents();
  }
});

document.getElementById('btnAddDependent')?.addEventListener('click', () => upsertDependent(null));
fetchDependents().catch(() => {});
const RESIGN_REASON_LABELS = {
  transfer: 'Chuyển công tác',
  personal: 'Lý do cá nhân',
  health: 'Sức khỏe',
  study: 'Học tập',
  other: 'Khác'
}

async function loadMyResignationRequests() {
  const wrap = document.getElementById('resignationHistory')
  if (!wrap) return
  const res = await fetch('/employee/resignation/my')
  const rows = await res.json()
  if (!res.ok) return
  if (!rows.length) {
    wrap.innerHTML = '<p><strong>Resignation:</strong> chưa có đơn nghỉ việc.</p>'
    return
  }
  wrap.innerHTML = `<p><strong>Lịch sử nghỉ việc:</strong></p><ul>${rows.slice(0, 5).map((row) => `<li>#${row.id} - ${row.status} - Dự kiến nghỉ: ${row.expected_last_day || '--'} - ${RESIGN_REASON_LABELS[row.reason_category] || row.reason_category}</li>`).join('')}</ul>`
}

async function openResignationForm() {
  const { value: formValues } = await Swal.fire({
    title: 'Gửi đơn nghỉ việc',
    html: `
      <input id="resign-date" type="date" class="swal2-input">
      <select id="resign-reason" class="swal2-input">
        <option value="transfer">Chuyển công tác</option>
        <option value="personal">Lý do cá nhân</option>
        <option value="health">Sức khỏe</option>
        <option value="study">Học tập</option>
        <option value="other">Khác</option>
      </select>
      <input id="resign-handover" type="number" class="swal2-input" placeholder="ID người nhận bàn giao (nếu có)">
      <textarea id="resign-note" class="swal2-textarea" placeholder="Ghi chú thêm"></textarea>
      <textarea id="resign-detail" class="swal2-textarea" placeholder="Mô tả lý do chi tiết"></textarea>
      <input id="resign-attachment" type="file" class="swal2-file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg">
    `,
    focusConfirm: false,
    showCancelButton: true,
    confirmButtonText: 'Gửi đơn',
    preConfirm: () => ({
      expected_last_day: document.getElementById('resign-date').value,
      reason_category: document.getElementById('resign-reason').value,
      handover_employee_id: document.getElementById('resign-handover').value,
      extra_note: document.getElementById('resign-note').value,
      reason_text: document.getElementById('resign-detail').value,
      attachment: document.getElementById('resign-attachment').files[0] || null
    })
  })

  if (!formValues) return
  if (!formValues.expected_last_day) {
    await Swal.fire({ icon: 'warning', title: 'Vui lòng chọn ngày dự kiến nghỉ' })
    return
  }

  const payload = new FormData()
  payload.append('expected_last_day', formValues.expected_last_day)
  payload.append('reason_category', formValues.reason_category)
  payload.append('handover_employee_id', formValues.handover_employee_id || '')
  payload.append('extra_note', formValues.extra_note || '')
  payload.append('reason_text', formValues.reason_text || '')
  if (formValues.attachment) payload.append('attachment', formValues.attachment)

  const submitResult = await fetch('/employee/resignation', { method: 'POST', body: payload })
  const submitData = await submitResult.json().catch(() => ({}))
  if (!submitResult.ok) {
    await Swal.fire({ icon: 'error', title: submitData.error || 'Không thể gửi đơn nghỉ việc' })
    return
  }
  await Swal.fire({ icon: 'success', title: submitData.message || 'Đã gửi đơn nghỉ việc' })
  await loadMyResignationRequests()
}

document.getElementById('btnSubmitResignation')?.addEventListener('click', openResignationForm)
loadMyResignationRequests().catch(() => {})