(function () {
  const tabs = document.querySelectorAll('.tab');
  const panes = document.querySelectorAll('.tab-pane');
  const switchTab = (tabId) => {
    tabs.forEach((t) => t.classList.toggle('active', t.dataset.tab === tabId));
    panes.forEach((p) => p.classList.toggle('active', p.id === tabId));
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));

  document.querySelectorAll('[data-quick-tab]').forEach((btn) => {
    btn.addEventListener('click', () => switchTab(btn.dataset.quickTab));
  });

  const personalForm = document.getElementById('personalForm');
  const editableNames = ['phone', 'personal_email', 'address_detail', 'emergency_contact_name', 'emergency_contact_phone', 'marital_status'];
  const btnEdit = document.getElementById('btnEditPersonal');
  const btnSave = document.getElementById('btnSavePersonal');
  const btnCancel = document.getElementById('btnCancelPersonal');

  const setEditMode = (enabled) => {
    editableNames.forEach((name) => {
      const input = personalForm?.querySelector(`[name="${name}"]`);
      if (input) input.readOnly = !enabled;
    });
    if (btnSave) btnSave.hidden = !enabled;
    if (btnCancel) btnCancel.hidden = !enabled;
    if (btnEdit) btnEdit.hidden = enabled;
  };

  btnEdit?.addEventListener('click', () => setEditMode(true));
  btnCancel?.addEventListener('click', () => window.location.reload());

  personalForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = await Swal.fire({
      icon: 'question',
      title: 'Xác nhận cập nhật hồ sơ?',
      text: 'Chỉ các trường được phép sẽ được cập nhật.',
      showCancelButton: true,
      confirmButtonText: 'Cập nhật',
      cancelButtonText: 'Hủy',
    });
    if (!result.isConfirmed) return;

    const payload = Object.fromEntries(new FormData(personalForm).entries());
    const response = await fetch('/admin/profile/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      await Swal.fire({ icon: 'error', title: 'Cập nhật thất bại', text: data.error || 'Lỗi hệ thống' });
      return;
    }
    await Swal.fire({ icon: 'success', title: 'Cập nhật thành công', text: data.message || 'Thông tin cá nhân đã được lưu' });
    window.location.reload();
  });

  const avatarInput = document.getElementById('avatarInput');
  const avatarTrigger = document.getElementById('avatarPreviewTrigger');
  const btnUploadAvatar = document.getElementById('btnUploadAvatar');
  const btnQuickUpload = document.getElementById('btnQuickUpload');
  let selectedAvatar = null;

  avatarTrigger?.addEventListener('click', () => avatarInput?.click());
  btnQuickUpload?.addEventListener('click', () => {
    switchTab('personal');
    avatarInput?.click();
  });

  avatarInput?.addEventListener('change', (event) => {
    selectedAvatar = event.target.files?.[0] || null;
    if (!selectedAvatar) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      let avatar = document.querySelector('.profile-avatar');
      if (!avatar) {
        avatarTrigger.innerHTML = '<img class="profile-avatar" alt="avatar">';
        avatar = document.querySelector('.profile-avatar');
      }
      avatar.src = ev.target?.result;
    };
    reader.readAsDataURL(selectedAvatar);
  });

  async function uploadAvatarAction() {
    if (!selectedAvatar) {
      await Swal.fire({ icon: 'warning', title: 'Bạn chưa chọn ảnh avatar' });
      return;
    }
    const ask = await Swal.fire({
      icon: 'question',
      title: 'Xác nhận upload avatar?',
      showCancelButton: true,
      confirmButtonText: 'Upload',
      cancelButtonText: 'Hủy',
    });
    if (!ask.isConfirmed) return;

    const formData = new FormData();
    formData.append('avatar', selectedAvatar);
    const res = await fetch('/admin/profile/upload-avatar', { method: 'POST', body: formData });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      await Swal.fire({ icon: 'error', title: 'Upload thất bại', text: data.error || 'Không thể upload avatar' });
      return;
    }
    await Swal.fire({ icon: 'success', title: 'Cập nhật thành công', text: data.message || 'Avatar đã được cập nhật' });
    window.location.reload();
  }

  btnUploadAvatar?.addEventListener('click', uploadAvatarAction);

  const passwordForm = document.getElementById('passwordForm');
  passwordForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(passwordForm).entries());

    const ask = await Swal.fire({
      icon: 'question',
      title: 'Cập nhật mật khẩu?',
      text: 'Sau khi đổi mật khẩu, bạn nên đăng nhập lại trên các thiết bị khác.',
      showCancelButton: true,
      confirmButtonText: 'Cập nhật mật khẩu',
      cancelButtonText: 'Hủy',
    });
    if (!ask.isConfirmed) return;

    const res = await fetch('/admin/profile/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      await Swal.fire({ icon: 'error', title: 'Không thể đổi mật khẩu', text: data.error || 'Lỗi hệ thống' });
      return;
    }
    await Swal.fire({ icon: 'success', title: 'Đổi mật khẩu thành công', text: data.message || 'Mật khẩu đã được cập nhật' });
    passwordForm.reset();
  });

  const btnLogoutAllSessions = document.getElementById('btnLogoutAllSessions');
  const btnQuickLogoutAll = document.getElementById('btnQuickLogoutAll');
  async function logoutAllSessionsAction() {
    const ask = await Swal.fire({
      icon: 'warning',
      title: 'Đăng xuất tất cả phiên?',
      text: 'Tài khoản Admin sẽ bị đăng xuất khỏi phiên hiện tại.',
      showCancelButton: true,
      confirmButtonText: 'Đăng xuất tất cả',
      cancelButtonText: 'Hủy',
    });
    if (!ask.isConfirmed) return;

    const res = await fetch('/admin/profile/logout-all-sessions', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      await Swal.fire({ icon: 'error', title: 'Không thể đăng xuất phiên', text: data.error || 'Lỗi hệ thống' });
      return;
    }
    await Swal.fire({ icon: 'success', title: 'Thành công', text: data.message || 'Đã đăng xuất mọi phiên' });
    window.location.href = '/login';
  }
  btnLogoutAllSessions?.addEventListener('click', logoutAllSessionsAction);
  btnQuickLogoutAll?.addEventListener('click', logoutAllSessionsAction);
})();