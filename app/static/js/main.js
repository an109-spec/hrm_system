// 1. Chạy khi DOM đã sẵn sàng (Đảm bảo code không chạy lỗi khi trang chưa tải xong)
document.addEventListener('DOMContentLoaded', function() {
    console.log("HRM System: JS Initialized");
    
    // Khởi tạo các thành phần toàn cục
    initTooltips();
    initSidebarToggle();
});

// 2. Hàm thông báo dùng chung (Thay thế Flash bằng SweetAlert2)
window.showNotification = function(type, message) {
    Swal.fire({
        icon: type, // 'success', 'error', 'info', 'warning'
        title: message,
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true
    });
};

// 3. Khởi tạo Bootstrap Tooltips (Nếu bạn dùng tính năng này)
function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// 4. Xử lý Sidebar (Nếu bạn muốn thêm hiệu ứng thu gọn/mở rộng)
function initSidebarToggle() {
    const sidebar = document.querySelector('.sidebar-wrapper');
    // Code xử lý toggle sidebar sẽ viết tại đây
}

// 5. Hàm xác nhận trước khi xóa (Cực kỳ cần thiết cho HRM - VD: xóa nhân viên)
window.confirmAction = function(message, callback) {
    Swal.fire({
        title: 'Bạn có chắc chắn?',
        text: message,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Đồng ý',
        cancelButtonText: 'Hủy'
    }).then((result) => {
        if (result.isConfirmed) {
            callback();
        }
    });
};