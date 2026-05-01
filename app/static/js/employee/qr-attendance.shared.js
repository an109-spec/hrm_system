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
            await close();
          } catch (_) {
            // ignore close errors and keep processing decoded value
          }

          try {
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

      if (modal.classList.contains('scanner-modal')) modal.classList.add('open');
      else modal.style.display = 'block';

      isOpen = true;
      isProcessingDecode = false;
      scanEngine = new Html5Qrcode(readerId);

      try {
        await startWithConfig({ facingMode: { exact: 'environment' } });
      } catch (firstErr) {
        try {
          const devices = await Html5Qrcode.getCameras();
          if (!devices || devices.length === 0) throw firstErr;
          const backCam = devices.find((d) => /back|rear|sau/i.test(d.label || '')) || devices[0];
          await startWithConfig({ deviceId: { exact: backCam.id } });
        } catch (secondErr) {
          isOpen = false;
          const msg = String(secondErr || firstErr || '').toLowerCase();
          if (msg.includes('permission') || msg.includes('notallowederror')) {
            throw new Error('Không có quyền truy cập camera. Hãy cho phép camera và thử lại.');
          }
          throw new Error('Không thể khởi động camera hoặc nhận diện QR. Vui lòng thử lại.');
        }
      }
    }

    return { open, close, isOpen: () => isOpen };
  }

  global.HRMQRScanner = { createQRScanner };
})(window);