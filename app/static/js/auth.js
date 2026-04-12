document.addEventListener("DOMContentLoaded", () => {
  // --- 1. XỬ LÝ HIỆU ỨNG LOADING KHI SUBMIT FORM ---
  const forms = document.querySelectorAll(".auth__form");

  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type='submit']");
      if (btn && !btn.disabled) {
        // Thêm class loading để CSS xử lý spinner nếu có
        btn.classList.add("btn--loading");
        
        // Cập nhật nội dung nút để người dùng không bấm nhiều lần
        const originalText = btn.innerHTML;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Đang xác thực...`;
        
        // Ngăn chặn bấm nhiều lần (Double-click)
        setTimeout(() => {
            btn.disabled = true;
        }, 50);
      }
    });
  });

  // --- 2. XỬ LÝ ĐẾM NGƯỢC OTP ---
  const timerEl = document.querySelector("[data-otp-expire-at]");
  if (!timerEl) return;

  const valueEl = timerEl.querySelector(".otp-timer__value");
  const resendBtn = document.querySelector("[data-resend-btn]");
  const rawExpireAt = timerEl.getAttribute("data-otp-expire-at");
  
  // Xử lý chuyển đổi thời gian an toàn hơn
  const expireAt = rawExpireAt ? new Date(rawExpireAt) : null;

  if (!expireAt || Number.isNaN(expireAt.getTime()) || !valueEl) return;

  const setResendState = (enabled) => {
    if (!resendBtn) return;
    resendBtn.disabled = !enabled;
    
    if (enabled) {
        resendBtn.classList.remove("btn--disabled");
        resendBtn.innerHTML = `<i class="fas fa-sync-alt"></i> Gửi lại mã mới`;
    } else {
        resendBtn.classList.add("btn--disabled");
        resendBtn.innerHTML = `<i class="fas fa-clock"></i> Gửi lại mã (đợi hết hạn)`;
    }
  };

  const updateCountdown = () => {
    const now = new Date();
    const diffMs = expireAt.getTime() - now.getTime();

    if (diffMs <= 0) {
      valueEl.textContent = "00:00";
      timerEl.classList.remove("otp-timer--warning");
      timerEl.classList.add("otp-timer--expired");
      setResendState(true);
      return false;
    }

    const totalSec = Math.floor(diffMs / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;

    // Cập nhật màu sắc cảnh báo theo thời gian thực
    timerEl.classList.remove("otp-timer--warning", "otp-timer--expired");
    if (totalSec <= 30) {
      timerAtoms(timerEl, "expired"); // Màu đỏ (Hết hạn đến nơi)
    } else if (totalSec <= 90) {
      timerAtoms(timerEl, "warning"); // Màu cam (Sắp hết hạn)
    }

    valueEl.textContent = `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    setResendState(false);
    return true;
  };

  // Hàm hỗ trợ đổi class màu sắc
  function timerAtoms(el, status) {
    el.classList.add(`otp-timer--${status}`);
  }

  // Khởi chạy đếm ngược
  updateCountdown();
  const intervalId = window.setInterval(() => {
    if (!updateCountdown()) {
      window.clearInterval(intervalId);
    }
  }, 1000);
});