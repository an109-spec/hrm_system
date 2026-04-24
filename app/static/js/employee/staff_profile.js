document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((node) => node.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach((pane) => pane.classList.remove('active'));
    tab.classList.add('active');
    const pane = document.getElementById(tab.dataset.tab);
    if (pane) pane.classList.add('active');
  });
});

const avatarInput = document.getElementById('avatarInput');
const uploadAvatarBtn = document.getElementById('uploadAvatarBtn');
let selectedFile = null;

if (avatarInput) {
  avatarInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    selectedFile = file;

    const reader = new FileReader();
    reader.onload = function onLoad(event) {
      let avatar = document.querySelector('.profile-avatar');
      if (!avatar) {
        const wrapper = document.querySelector('.avatar-wrapper');
        wrapper.innerHTML = '<img class="profile-avatar" alt="avatar">';
        avatar = document.querySelector('.profile-avatar');
      }
      avatar.src = event.target.result;
    };
    reader.readAsDataURL(file);
  });
}

if (uploadAvatarBtn) {
  uploadAvatarBtn.addEventListener('click', async () => {
    if (!selectedFile) {
      alert('Vui lòng chọn ảnh trước khi cập nhật.');
      return;
    }

    const formData = new FormData();
    formData.append('avatar', selectedFile);

    try {
      uploadAvatarBtn.disabled = true;
      uploadAvatarBtn.textContent = 'Đang tải...';
      const res = await fetch('/employee/upload-avatar', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload thất bại');
      alert('Cập nhật ảnh thành công');
      location.reload();
    } catch (error) {
      alert('Không thể cập nhật ảnh. Vui lòng thử lại.');
    } finally {
      uploadAvatarBtn.disabled = false;
      uploadAvatarBtn.textContent = 'Cập nhật ảnh';
    }
  });
}

const profileForm = document.getElementById('profileForm');
if (profileForm) {
  const editInfoBtn = document.getElementById('editInfoBtn');
  const cancelInfoBtn = document.getElementById('cancelInfoBtn');
  const saveInfoBtn = document.getElementById('saveInfoBtn');
  const toggleAddressBtn = document.getElementById('toggleAddressBtn');
  const addressEditor = document.getElementById('addressEditor');
  const cancelAddressBtn = document.getElementById('cancelAddressBtn');

  const editableInputs = profileForm.querySelectorAll('input[name="full_name"], input[name="dob"], input[name="phone"]');
  const genderInputs = profileForm.querySelectorAll('input[name="gender"]');

  const setInfoEditMode = (isEditing) => {
    editableInputs.forEach((input) => {
      input.readOnly = !isEditing;
      input.classList.toggle('readonly-input', !isEditing);
    });
    genderInputs.forEach((input) => {
      input.disabled = !isEditing;
    });

    editInfoBtn.classList.toggle('hidden', isEditing);
    saveInfoBtn.classList.toggle('hidden', !isEditing);
    cancelInfoBtn.classList.toggle('hidden', !isEditing);
  };

  editInfoBtn?.addEventListener('click', () => setInfoEditMode(true));
  cancelInfoBtn?.addEventListener('click', () => location.reload());

  toggleAddressBtn?.addEventListener('click', () => {
    addressEditor?.classList.remove('hidden');
  });
  cancelAddressBtn?.addEventListener('click', () => {
    addressEditor?.classList.add('hidden');
    location.reload();
  });

  const host = 'https://provinces.open-api.vn/api/';
  const addressData = document.getElementById('addressData');

  const renderData = (items, selectId, firstText) => {
    const select = document.getElementById(selectId);
    if (!select) return;
    let html = `<option value="">${firstText}</option>`;
    items.forEach((item) => {
      html += `<option value="${item.code}">${item.name}</option>`;
    });
    select.innerHTML = html;
  };

  async function initAddress() {
    if (!addressData) return;
    const pCode = addressData.dataset.province;
    const dCode = addressData.dataset.district;
    const wCode = addressData.dataset.ward;

    const provinces = await fetch(`${host}?depth=1`).then((res) => res.json());
    renderData(provinces, 'province', 'Chọn Tỉnh/Thành');

    if (pCode) {
      document.getElementById('province').value = pCode;
      const districtData = await fetch(`${host}p/${pCode}?depth=2`).then((res) => res.json());
      renderData(districtData.districts || [], 'district', 'Chọn Quận/Huyện');
    }

    if (dCode) {
      document.getElementById('district').value = dCode;
      const wardData = await fetch(`${host}d/${dCode}?depth=2`).then((res) => res.json());
      renderData(wardData.wards || [], 'ward', 'Chọn Phường/Xã');
    }

    if (wCode) document.getElementById('ward').value = wCode;
  }

  initAddress();

  document.getElementById('province')?.addEventListener('change', async (e) => {
    const pCode = e.target.value;
    if (!pCode) {
      renderData([], 'district', 'Chọn Quận/Huyện');
      renderData([], 'ward', 'Chọn Phường/Xã');
      return;
    }
    const districtData = await fetch(`${host}p/${pCode}?depth=2`).then((res) => res.json());
    renderData(districtData.districts || [], 'district', 'Chọn Quận/Huyện');
    renderData([], 'ward', 'Chọn Phường/Xã');
  });

  document.getElementById('district')?.addEventListener('change', async (e) => {
    const dCode = e.target.value;
    if (!dCode) {
      renderData([], 'ward', 'Chọn Phường/Xã');
      return;
    }
    const wardData = await fetch(`${host}d/${dCode}?depth=2`).then((res) => res.json());
    renderData(wardData.wards || [], 'ward', 'Chọn Phường/Xã');
  });

  profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(profileForm);
    const payload = Object.fromEntries(formData.entries());

    try {
      const response = await fetch('/employee/update-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Không thể lưu thay đổi');
      }

      alert('Cập nhật thông tin thành công!');
      location.reload();
    } catch (error) {
      alert(error.message || 'Lỗi kết nối server');
    }
  });
}