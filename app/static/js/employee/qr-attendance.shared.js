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
        await scanEngine.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 220, height: 220 } },
          async (decodedText) => {
            if (isProcessingDecode) return;
            isProcessingDecode = true;
            try {
              if (panelId) {
                const panel = document.getElementById(panelId);
                if (panel) panel.classList.add('success-flash');
              }
              await close();
              await onDecoded(decodedText);
            } catch (err) {
              if (onError) onError(err);
            }
          }
        );
      } catch (err) {
        isOpen = false;
        const msg = String(err || '');
        if (msg.toLowerCase().includes('permission')) {
          throw new Error('Không có quyền truy cập camera. Hãy cho phép camera và thử lại.');
        }
        throw new Error('Không thể khởi động camera. Vui lòng thử lại.');
      }
    }

    return { open, close, isOpen: () => isOpen };
  }

  global.HRMQRScanner = { createQRScanner };
})(window);