document.addEventListener('DOMContentLoaded', () => {
  console.log('HRM System UI Loaded');

  // --- 1. HỆ THỐNG THÔNG BÁO (TOAST) ---
  const toastRoot = document.createElement('div');
  toastRoot.className = 'toast-container';
  document.body.appendChild(toastRoot);

  /**
   * Hiển thị thông báo Toast
   * @param {string} message - Nội dung thông báo
   * @param {string} type - Loại: success, danger, warning, info
   */
  const showToast = (message, type = 'info') => {
    if (!message) return;
    const toast = document.createElement('div');
    // Map lại category của Flask sang class CSS nếu cần
    const categoryMap = {
      'error': 'danger',
      'success': 'success',
      'warning': 'warning',
      'info': 'info'
    };
    const toastType = categoryMap[type] || type;
    
    toast.className = `toast toast--${toastType}`;
    toast.innerHTML = `
      <div class="toast__content">
        <i class="fas ${getIcon(toastType)}"></i>
        <span>${message}</span>
      </div>
    `;
    toastRoot.appendChild(toast);

    // Hiệu ứng hiển thị
    requestAnimationFrame(() => {
      toast.classList.add('is-visible');
    });

    // Tự động đóng sau 4 giây
    window.setTimeout(() => {
      toast.classList.remove('is-visible');
      window.setTimeout(() => toast.remove(), 300);
    }, 4000);
  };

  const getIcon = (type) => {
    switch(type) {
      case 'success': return 'fa-check-circle';
      case 'danger': return 'fa-exclamation-circle';
      case 'warning': return 'fa-exclamation-triangle';
      default: return 'fa-info-circle';
    }
  };

  window.showToast = showToast;
  const fireSafe = (options) => {
    if (window.Swal) return window.Swal.fire(options);
    if (options.icon === 'error') showToast(options.text || options.title || 'Có lỗi xảy ra', 'danger');
    else showToast(options.text || options.title || 'Thông báo', options.icon || 'info');
    return Promise.resolve({ isConfirmed: true });
  };

  window.appDialogs = {
    async confirm({ title, text, icon = 'question', confirmText = 'Xác nhận', cancelText = 'Hủy', requireReason = false, reasonLabel = 'Lý do' }) {
      const result = await fireSafe({
        title, text, icon,
        showCancelButton: true,
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        input: requireReason ? 'text' : undefined,
        inputLabel: requireReason ? reasonLabel : undefined,
      });
      return { confirmed: !!result.isConfirmed, reason: result.value || '' };
    },
    success({ title = 'Thành công', text = '' }) {
      return fireSafe({ icon: 'success', title, text, confirmButtonText: 'Đóng' });
    },
    error({ title = 'Thất bại', text = '' }) {
      return fireSafe({ icon: 'error', title, text, confirmButtonText: 'Đóng' });
    },
    async prompt({ title, label, placeholder = '', confirmText = 'Xác nhận' }) {
      const result = await fireSafe({
        title,
        input: 'text',
        inputLabel: label,
        inputPlaceholder: placeholder,
        showCancelButton: true,
        confirmButtonText: confirmText,
        cancelButtonText: 'Hủy',
      });
      return { confirmed: !!result.isConfirmed, value: result.value || '' };
    },
  };


  // Tự động bắt các tin nhắn flash từ Flask gửi xuống
  document.querySelectorAll('[data-flash-message]').forEach((item) => {
    const message = item.dataset.flashMessage;
    const type = item.dataset.flashCategory || 'info';
    showToast(message, type);
    item.remove();
  });


  // --- 2. XỬ LÝ DROPDOWN TÀI KHOẢN ---
  // Đảm bảo menu hoạt động mượt mà trên cả mobile/touch
  const accountTrigger = document.querySelector('.account-menu__trigger');
  const accountMenu = document.querySelector('.account-menu__dropdown');

  if (accountTrigger && accountMenu) {
    accountTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      // Logic toggle nếu muốn dùng click thay vì hover
      // accountMenu.classList.toggle('is-active');
    });
  }

  // Đóng các menu khi click ra ngoài
  document.addEventListener('click', () => {
    // Thêm logic đóng menu nếu cần
  });


  // --- 3. TÌM KIẾM NHÂN VIÊN ---
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        console.log('Đang tìm kiếm nhân sự:', searchInput.value);
      }
    });
  }

});