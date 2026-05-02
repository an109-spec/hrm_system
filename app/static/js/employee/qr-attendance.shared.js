(function (global) {
  function createQRScanner({ modalId, readerId, panelId, onDecoded, onError }) {
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
      const msg = String(err?.message || err || '').toLowerCase();
      if (!global.isSecureContext) {
        return new Error('Camera chỉ hoạt động trên HTTPS hoặc localhost. Vui lòng mở hệ thống bằng đường dẫn bảo mật.');
      }
      if (msg.includes('permission') || msg.includes('notallowed') || msg.includes('denied')) {
        return new Error('Bạn đã từ chối quyền camera. Vui lòng cấp quyền trong cài đặt trình duyệt.');
      }
      if (msg.includes('notfound') || msg.includes('devicesnotfound')) {
        return new Error('Không tìm thấy camera trên thiết bị này.');
      }
      return new Error('Không thể khởi động camera. Có thể camera đang bị ứng dụng khác sử dụng.');
    }

    async function close() {
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.remove('open');
      if (modal && !modal.classList.contains('scanner-modal')) {
        modal.style.display = 'none';
      }

      if (scanEngine) {
        try { await scanEngine.stop(); } catch (_) {}
        try { await scanEngine.clear(); } catch (_) {}
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
      if (!navigator?.mediaDevices?.getUserMedia) {
        throw new Error('Trình duyệt không hỗ trợ camera API. Vui lòng cập nhật trình duyệt.');
      }
      if (modal.classList.contains('scanner-modal')) modal.classList.add('open');
      else modal.style.display = 'block';

      isOpen = true;
      isProcessingDecode = false;
      scanEngine = new Html5Qrcode(readerId);

      // Xin quyền camera trước để đảm bảo getCameras có label đầy đủ (đặc biệt iOS/Safari)
      let warmupStream = null;
      try {
        warmupStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      } catch (permissionErr) {
        await close();
        throw normalizeOpenError(permissionErr);
      } finally {
        stopStreamTracks(warmupStream);
      }

      try {
        await startWithConfig({ facingMode: { ideal: 'environment' } });
      } catch (firstErr) {
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