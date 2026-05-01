(function (global) {
  function createQRScanner({ modalId, readerId, panelId, onDecoded, onError }) {
    let scanEngine = null;
    let isOpen = false;
    let isProcessingDecode = false;
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
        { fps: 10, qrbox: { width: 260, height: 260 }, aspectRatio: 1.0 },
        async (decodedText) => {
            if (isProcessingDecode) return;
            isProcessingDecode = true;

            if (panelId) {
                const panel = document.getElementById(panelId);
                if (panel) panel.classList.add('success-flash');
            }

            try {
                // Thực hiện logic chấm công trước khi đóng hẳn camera
                await onDecoded(decodedText); 
                await close(); 
            } catch (err) {
                isProcessingDecode = false; // Reset nếu lỗi để cho phép quét lại
                if (onError) await onError(err);
            }
        }
      );
    }

async function open() {
  if (isOpen) return;
  const modal = document.getElementById(modalId);
  if (!modal) throw new Error('Không tìm thấy modal scanner.');

  if (modal.classList.contains('scanner-modal')) modal.classList.add('open');
  else modal.style.display = 'block';

  isOpen = true;
  isProcessingDecode = false;
  scanEngine = new Html5Qrcode(readerId);

  try {
    // 1. Thử dùng FacingMode nhưng KHÔNG dùng 'exact' để tránh crash trên PC/Laptop
    await startWithConfig({ facingMode: 'environment' }); 
  } catch (firstErr) {
    try {
      // 2. Nếu thất bại, liệt kê danh sách camera và chọn cái phù hợp nhất
      const devices = await Html5Qrcode.getCameras();
      if (!devices || devices.length === 0) throw new Error('Không tìm thấy camera nào.');

      // Ưu tiên camera sau nếu có, nếu không lấy camera đầu tiên (webcam)
      const backCam = devices.find((d) => /back|rear|sau/i.test(d.label || '')) || devices[0];
      
      await startWithConfig({ deviceId: { exact: backCam.id } });
    } catch (secondErr) {
      // Dọn dẹp nếu thất bại hoàn toàn
      isOpen = false;
      if (scanEngine) {
        try { await scanEngine.clear(); } catch(_) {}
        scanEngine = null;
      }

      const msg = String(secondErr.message || firstErr.message || secondErr || '').toLowerCase();
      if (msg.includes('permission') || msg.includes('notallowed') || msg.includes('denied')) {
        throw new Error('Bạn đã từ chối quyền camera. Vui lòng cấp quyền trong cài đặt trình duyệt.');
      }
      throw new Error('Không thể khởi động camera. Có thể camera đang bị ứng dụng khác sử dụng.');
    }
  }
}

    return { open, close, isOpen: () => isOpen };
  }

  global.HRMQRScanner = { createQRScanner };
})(window);