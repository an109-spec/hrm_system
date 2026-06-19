/**
 * notification_detail.js
 * Notification detail page logic.
 *
 * Depends on: notification.js (Noti), SweetAlert2, Bootstrap 5
 *
 * Reads notification_id from:
 *   <span id="notificationId" data-id="..."></span>
 *
 * API used:
 *   GET    /notification/<id>   → chi tiết + tự đánh dấu đã đọc
 *   DELETE /notification/<id>   → xóa
 *   GET    /notification?limit=200 → lấy list để build Prev/Next nav
 */

document.addEventListener('DOMContentLoaded', async () => {

    /* ── Read notification ID from template ── */
    const idEl = document.getElementById('notificationId');
    const notiId = idEl ? parseInt(idEl.dataset.id, 10) : null;

    /* ── DOM refs ── */
    const skeleton    = document.getElementById('detailSkeleton');
    const card        = document.getElementById('detailCard');
    const errorPanel  = document.getElementById('detailError');
    const errorMsg    = document.getElementById('detailErrorMsg');
    const navCard     = document.getElementById('notiNav');

    const detailIcon  = document.getElementById('detailIcon');
    const detailTitle = document.getElementById('detailTitle');
    const detailTime  = document.getElementById('detailTime');
    const detailType  = document.getElementById('detailTypeBadge');
    const detailRead  = document.getElementById('detailReadStatus');
    const detailBody  = document.getElementById('detailBody');
    const detailLink  = document.getElementById('detailLink');
    const btnDelete   = document.getElementById('btnDeleteDetail');
    const btnPrev     = document.getElementById('btnNavPrev');
    const btnNext     = document.getElementById('btnNavNext');
    const navPos      = document.getElementById('navPosition');

    /* ── Show error state ── */
    function showError(msg = 'Không tìm thấy thông báo') {
        skeleton.style.display  = 'none';
        card.style.display      = 'none';
        navCard.style.display   = 'none';
        errorPanel.style.display = '';
        errorMsg.textContent = msg;
    }

    /* ── Validate ID ── */
    if (!notiId || isNaN(notiId)) {
        showError('ID thông báo không hợp lệ.');
        return;
    }

    /* ── Fetch notification detail ── */
    const r = await Noti.api('GET', `/notification/${notiId}`);
    skeleton.style.display = 'none';

    if (!r.ok) {
        const msg = r.status === 404
            ? 'Thông báo không tồn tại hoặc đã bị xóa.'
            : (r.data?.text || 'Không tải được thông báo. Vui lòng thử lại.');
        showError(msg);
        return;
    }

    const n = r.data?.data;
    if (!n) { showError('Dữ liệu thông báo không hợp lệ.'); return; }

    /* ── Populate card ── */
    const { icon, cls, label } = Noti.typeInfo(n.type);

    // Icon
    detailIcon.className = `noti-detail-icon ${cls}`;
    detailIcon.innerHTML = `<i class="fa-solid ${icon}"></i>`;

    // Title
    detailTitle.textContent = n.title || '—';

    // Type badge
    detailType.innerHTML = `<span class="noti-type-tag">${label}</span>`;

    // Time
    detailTime.innerHTML =
        `<i class="fa-regular fa-clock"></i>${Noti.formatFull(n.received_at)}
         <span class="text-muted ms-1">(${Noti.formatTime(n.received_at)})</span>`;

    // Read status
    detailRead.innerHTML = n.is_read
        ? `<span style="color:#16a34a;font-size:.75rem;">
               <i class="fa-solid fa-circle-check"></i> Đã đọc
           </span>`
        : `<span style="color:#2563eb;font-size:.75rem;">
               <i class="fa-solid fa-circle"></i> Mới
           </span>`;

    // Body content
    detailBody.textContent = n.content || '(Thông báo này không có nội dung chi tiết.)';

    // Action link to related module
    if (n.link) {
        detailLink.href = n.link;
        detailLink.style.display = '';
    } else {
        detailLink.style.display = 'none';
    }

    // Show card
    card.style.display = '';

    /* ── Delete button ── */
    btnDelete.addEventListener('click', async () => {
        const ok = await Noti.confirm(
            'Xóa thông báo này?',
            'Thao tác không thể hoàn tác.',
            'Xóa'
        );
        if (!ok) return;

        const btnOrig = btnDelete.innerHTML;
        btnDelete.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        btnDelete.disabled = true;

        const dr = await Noti.api('DELETE', `/notification/${notiId}`);

        if (dr.ok) {
            Noti.toast('success', 'Đã xóa thông báo');
            // Redirect to center after brief delay
            setTimeout(() => {
                window.location.href = '/notification/center';
            }, 1200);
        } else {
            btnDelete.innerHTML = btnOrig;
            btnDelete.disabled = false;
            Noti.toast('error', dr.data?.title || 'Không thể xóa thông báo');
        }
    });

    /* ── Prev / Next navigation ── */
    await buildNavigation(notiId);
});

/* ── Build Prev/Next from full list ── */
async function buildNavigation(currentId) {
    const btnPrev = document.getElementById('btnNavPrev');
    const btnNext = document.getElementById('btnNavNext');
    const navPos  = document.getElementById('navPosition');
    const navCard = document.getElementById('notiNav');

    const r = await Noti.api('GET', '/notification?limit=200');
    if (!r.ok) return;

    const list = r.data?.data?.notifications || [];
    const idx  = list.findIndex(n => n.id === currentId);
    if (idx === -1) return;

    navCard.style.display = '';

    const total   = list.length;
    const pos     = idx + 1;
    navPos.textContent = `${pos} / ${total}`;

    // Prev = earlier in time = higher index in desc-sorted list
    if (idx + 1 < total) {
        const prev = list[idx + 1];
        btnPrev.href = `/notification/detail/${prev.id}`;
        btnPrev.style.display = '';
        btnPrev.title = prev.title || '';
    }

    // Next = more recent = lower index
    if (idx - 1 >= 0) {
        const next = list[idx - 1];
        btnNext.href = `/notification/detail/${next.id}`;
        btnNext.style.display = '';
        btnNext.title = next.title || '';
    }
}