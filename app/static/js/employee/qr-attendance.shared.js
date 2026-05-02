(function (global) {
  function createQRScanner({ modalId, readerId, panelId, onDecoded, onError }) {
    function getUserMediaCompat(constraints) {
      if (navigator?.mediaDevices?.getUserMedia) {
        return navigator.mediaDevices.getUserMedia(constraints);
      }
      const legacyGetUserMedia =
        navigator?.getUserMedia ||
        navigator?.webkitGetUserMedia ||
        navigator?.mozGetUserMedia ||
        navigator?.msGetUserMedia;

      if (!legacyGetUserMedia) {
        return Promise.reject(new Error('UNSUPPORTED_CAMERA_API'));
      }

      return new Promise((resolve, reject) => {
        legacyGetUserMedia.call(navigator, constraints, resolve, reject);
      });
    }

    let scanEngine = null;
    let isOpen = false;
    let isProcessingDecode = false;

    function stopStreamTracks(stream) {
      if (!stream) return;
      try {
        stream.getTracks().forEach((t) => t.stop());
      } catch (_) {}
    }

    function normalizeOpenError(err) {
      // In lỗi thực tế ra console để tiện debug khi phát triển
      console.error("QR Scanner Error Detail:", err);

      const msg = String(err?.message || err || '').toLowerCase();
      if (!global.isSecureContext) {
        return new Error('Camera chỉ hoạt động trên HTTPS hoặc localhost. Vui lòng mở hệ thống bằng đường dẫn bảo mật.');
      }
      if (msg.includes('unsupported_camera_api')) {
        return new Error('Thiết bị/trình duyệt hiện tại chưa hỗ trợ mở camera. Hãy dùng Chrome, Edge, Safari mới nhất hoặc mở bằng ứng dụng trình duyệt hệ thống.');
      }
      if (msg.includes('permission') || msg.includes('notallowed') || msg.includes('denied')) {
        return new Error('Bạn đã từ chối quyền camera. Vui lòng cấp quyền trong cài đặt trình duyệt.');
      }
      if (msg.includes('notfound') || msg.includes('devicesnotfound')) {
        return new Error('Không tìm thấy camera trên thiết bị này.');
      }
      // Thêm kiểm tra lỗi do thiết bị đang bận
      if (msg.includes('readable') || msg.includes('concurrent') || msg.includes('in use')) {
        return new Error('Camera đang bị ứng dụng khác hoặc tab khác sử dụng. Vui lòng tắt các ứng dụng đang dùng camera và thử lại.');
      }
      return new Error('Không thể khởi động camera. Vui lòng thử tải lại trang hoặc kiểm tra quyền camera.');
    }

    async function close() {
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.remove('open');
      if (modal && !modal.classList.contains('scanner-modal')) {
        modal.style.display = 'none';
      }

      if (scanEngine) {
        try {
          if (scanEngine.isScanning) {
            await scanEngine.stop();
          }
        } catch (_) {}
        try {
          await scanEngine.clear();
        } catch (_) {}
        scanEngine = null;
      }
      isProcessingDecode = false;
      isOpen = false;
    }

    async function startWithConfig(cameraConfig) {
      return scanEngine.start(
        cameraConfig,
        { fps: 10, qrbox: { width: 260, height: 260 } },
        async (decodedText) => {
          if (isProcessingDecode) return;
          isProcessingDecode = true;
          if (panelId) {
            const panel = document.getElementById(panelId);
            if (panel) panel.classList.add('success-flash');
          }
          try {
            await close();
            await onDecoded(decodedText);
          } catch (err) {
            isProcessingDecode = false;
            if (onError) await onError(err);
          }
        }
      );
    }

    async function open() {
      if (isOpen) return;
      const modal = document.getElementById(modalId);
      if (!modal) throw new Error('Không tìm thấy modal scanner.');
      if (!global.isSecureContext) {
        throw new Error('Camera chỉ hoạt động trên HTTPS hoặc localhost. Vui lòng mở hệ thống bằng đường dẫn bảo mật.');
      }

      // 1. Hiển thị modal trước
      if (modal.classList.contains('scanner-modal')) modal.classList.add('open');
      else modal.style.display = 'block';

      isOpen = true;
      isProcessingDecode = false;

      // 2. Thêm một khoảng trễ nhỏ (300ms) để modal render hoàn tất và camera cũ tắt hẳn
      await new Promise((resolve) => setTimeout(resolve, 300));

      // 3. Đảm bảo dọn dẹp sạch engine cũ trước khi tạo mới
      if (scanEngine) {
        try { await scanEngine.clear(); } catch (_) {}
      }
      scanEngine = new Html5Qrcode(readerId);

      try {
        // Thử lần 1: Camera sau mặc định
        await startWithConfig({ facingMode: 'environment' });
      } catch (firstErr) {
        // Nếu lỗi, thử lấy danh sách camera và mở lại
        try {
          const devices = await Html5Qrcode.getCameras();
          if (!devices || devices.length === 0) throw new Error('Không tìm thấy camera nào.');

          const sorted = [
            ...devices.filter((d) => /back|rear|sau|environment/i.test(d.label || '')),
            ...devices.filter((d) => !/back|rear|sau|environment/i.test(d.label || ''))
          ];

          let started = false;
          let lastDeviceErr = null;
          for (const cam of sorted) {
            try {
              await startWithConfig(cam.id);
              started = true;
              break;
            } catch (deviceErr) {
              lastDeviceErr = deviceErr;
            }
          }

          if (!started) throw lastDeviceErr || new Error('Không thể mở bất kỳ camera nào.');
        } catch (secondErr) {
          await close();
          throw normalizeOpenError(secondErr?.message ? secondErr : firstErr);
        }
      }
    }

    return { open, close, isOpen: () => isOpen };
  }

  global.HRMQRScanner = { createQRScanner };
})(window);