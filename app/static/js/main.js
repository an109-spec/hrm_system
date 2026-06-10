document.addEventListener('DOMContentLoaded', () => {
    // 1. Tự động ẩn flash message sau 3 giây
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.display = 'none';
        }, 3000);
    });

    // 2. Xử lý các nút bấm chung (Ví dụ: nút đóng sidebar)
    const toggleBtn = document.querySelector('#sidebarToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('hidden');
        });
    }
});