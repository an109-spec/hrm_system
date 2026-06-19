/**
 * notification.js
 * Shared utilities + Notification Center page logic.
 *
 * API endpoints (prefix: /notification):
 *   GET    /notification           → danh sách (limit)
 *   GET    /notification/<id>      → chi tiết + tự đánh dấu đã đọc
 *   POST   /notification/mark-all-read
 *   GET    /notification/unread-count
 *   DELETE /notification/<id>
 *
 * Response shape (flat_swal_*):
 *   { icon, title, text, data: { ... } }
 */

/* ══ SHARED UTILITIES ══════════════════════════════════════════ */

const Noti = (() => {

    /* ── API helper ── */
    async function api(method, url, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };
        if (body) opts.body = JSON.stringify(body);
        const res  = await fetch(url, opts);
        const json = await res.json();
        return { ok: res.ok, status: res.status, data: json };
    }

    /* ── Toast ── */
    function toast(icon, title, timer = 3000) {
        if (typeof Swal === 'undefined') return;
        Swal.fire({
            icon, title,
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer,
            timerProgressBar: true,
        });
    }

    /* ── Confirm dialog ── */
    async function confirm(title, text, confirmText = 'Xác nhận') {
        if (typeof Swal === 'undefined') return window.confirm(title + '\n' + text);
        const r = await Swal.fire({
            icon: 'warning', title, text,
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor:  '#6b7280',
            confirmButtonText:  confirmText,
            cancelButtonText:   'Hủy',
        });
        return r.isConfirmed;
    }

    /* ── Time formatting ── */
    function formatTime(isoStr) {
        if (!isoStr) return '—';
        const dt   = new Date(isoStr);
        const now  = new Date();
        const diff = Math.floor((now - dt) / 1000); // seconds

        if (diff < 60)           return 'Vừa xong';
        if (diff < 3600)         return `${Math.floor(diff / 60)} phút trước`;
        if (diff < 86400)        return `${Math.floor(diff / 3600)} giờ trước`;
        if (diff < 86400 * 7)    return `${Math.floor(diff / 86400)} ngày trước`;
        return dt.toLocaleDateString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric' });
    }

    function formatFull(isoStr) {
        if (!isoStr) return '—';
        return new Date(isoStr).toLocaleString('vi-VN', {
            day:'2-digit', month:'2-digit', year:'numeric',
            hour:'2-digit', minute:'2-digit',
        });
    }

    /* ── Notification type → icon & class ── */
    const TYPE_MAP = {
        contract:    { icon: 'fa-file-contract',   cls: 'type-contract',   label: 'Hợp đồng'  },
        leave:       { icon: 'fa-calendar-xmark',  cls: 'type-leave',      label: 'Nghỉ phép' },
        payroll:     { icon: 'fa-money-bill-wave',  cls: 'type-payroll',    label: 'Lương'      },
        attendance:  { icon: 'fa-fingerprint',      cls: 'type-attendance', label: 'Chấm công' },
        info:        { icon: 'fa-circle-info',      cls: 'type-info',       label: 'Thông tin' },
        success:     { icon: 'fa-circle-check',     cls: 'type-success',    label: 'Thành công'},
        warning:     { icon: 'fa-triangle-exclamation', cls: 'type-warning', label: 'Cảnh báo'},
        danger:      { icon: 'fa-circle-xmark',    cls: 'type-danger',     label: 'Khẩn cấp'  },
    };

    function typeInfo(type) {
        return TYPE_MAP[type] || { icon: 'fa-bell', cls: 'type-default', label: type || 'Hệ thống' };
    }

    /* ── Build notification item HTML ── */
    function buildItem(n, opts = {}) {
        const { icon, cls, label } = typeInfo(n.type);
        const unreadCls = n.is_read ? '' : 'unread';
        const detailUrl = opts.detailUrl
            ? opts.detailUrl.replace('__ID__', n.id)
            : `/notification/${n.id}`;

        return `
        <a class="noti-item ${unreadCls}" href="${detailUrl}" data-id="${n.id}">
            <div class="noti-icon ${cls}">
                <i class="fa-solid ${icon}"></i>
            </div>
            <div class="noti-content">
                <div class="noti-title">${escHtml(n.title || '—')}</div>
                ${n.content
                    ? `<div class="noti-excerpt">${escHtml(n.content)}</div>`
                    : ''}
                <div class="noti-meta">
                    <span class="noti-time">
                        <i class="fa-regular fa-clock"></i>${formatTime(n.received_at)}
                    </span>
                    <span class="noti-type-tag">${label}</span>
                </div>
            </div>
            <div class="noti-actions">
                ${!n.is_read ? '<span class="unread-dot" title="Chưa đọc"></span>' : ''}
                <button class="btn-noti-delete" title="Xóa thông báo"
                        onclick="Noti.deleteItem(event, ${n.id})">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        </a>`;
    }

    /* ── Delete single notification ── */
    async function deleteItem(event, id) {
        event.preventDefault();
        event.stopPropagation();

        const ok = await confirm('Xóa thông báo này?', 'Thao tác không thể hoàn tác.', 'Xóa');
        if (!ok) return;

        const r = await api('DELETE', `/notification/${id}`);
        if (r.ok) {
            // Remove item from DOM
            const el = document.querySelector(`.noti-item[data-id="${id}"]`);
            if (el) {
                el.style.transition = 'opacity .25s, max-height .3s';
                el.style.overflow = 'hidden';
                el.style.opacity = '0';
                el.style.maxHeight = el.scrollHeight + 'px';
                setTimeout(() => { el.style.maxHeight = '0'; el.style.padding = '0'; }, 10);
                setTimeout(() => el.remove(), 320);
            }
            toast('success', 'Đã xóa thông báo');
            // Fire custom event so center can update counts
            document.dispatchEvent(new CustomEvent('noti:deleted', { detail: { id } }));
        } else {
            toast('error', r.data?.title || 'Không thể xóa thông báo');
        }
    }

    /* ── Escape HTML ── */
    function escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /* ── Debounce ── */
    function debounce(fn, ms = 250) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
    }

    return { api, toast, confirm, formatTime, formatFull, typeInfo, buildItem, deleteItem, escHtml, debounce };
})();

/* ══ NOTIFICATION CENTER PAGE ═══════════════════════════════════
   Only runs when #notiList is present (center page).
═══════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('notiList')) return;

    /* ── State ── */
    const PAGE_SIZE = 20;
    let allItems    = [];   // all fetched items
    let filtered    = [];   // after filter/type applied
    let displayed   = 0;    // how many are currently shown
    let activeFilter = 'all';
    let activeType   = '';

    /* ── DOM refs ── */
    const skeleton     = document.getElementById('notiSkeleton');
    const listEl       = document.getElementById('notiList');
    const emptyEl      = document.getElementById('notiEmpty');
    const loadMoreWrap = document.getElementById('loadMoreWrap');
    const btnLoadMore  = document.getElementById('btnLoadMore');
    const btnMarkAll   = document.getElementById('btnMarkAllRead');
    const btnRefresh   = document.getElementById('btnRefresh');
    const typeFilter   = document.getElementById('typeFilter');
    const filterBar    = document.getElementById('filterBar');

    const statTotal  = document.getElementById('statTotal');
    const statUnread = document.getElementById('statUnread');
    const statRead   = document.getElementById('statRead');
    const cntAll     = document.getElementById('cntAll');
    const cntUnread  = document.getElementById('cntUnread');
    const cntRead    = document.getElementById('cntRead');

    /* ── Load all notifications ── */
    async function load() {
        skeleton.style.display = '';
        listEl.style.display   = 'none';
        emptyEl.style.display  = 'none';
        loadMoreWrap.style.display = 'none';

        const r = await Noti.api('GET', '/notification?limit=200');
        skeleton.style.display = 'none';

        if (!r.ok) {
            listEl.style.display = 'none';
            emptyEl.style.display = '';
            emptyEl.querySelector('.noti-empty-title').textContent = 'Không tải được thông báo';
            emptyEl.querySelector('.noti-empty-sub').textContent = r.data?.text || 'Vui lòng thử lại.';
            return;
        }

        allItems = r.data?.data?.notifications || [];
        updateCounts();
        applyFilter();
    }

    /* ── Update count badges ── */
    function updateCounts() {
        const total   = allItems.length;
        const unread  = allItems.filter(n => !n.is_read).length;
        const read    = total - unread;

        statTotal.textContent  = total;
        statUnread.textContent = unread;
        statRead.textContent   = read;
        cntAll.textContent     = total;
        cntUnread.textContent  = unread;
        cntRead.textContent    = read;
    }

    /* ── Apply filter + type ── */
    function applyFilter() {
        filtered = allItems.filter(n => {
            const matchFilter =
                activeFilter === 'all'    ? true :
                activeFilter === 'unread' ? !n.is_read :
                activeFilter === 'read'   ? n.is_read  : true;

            const matchType = activeType ? (n.type || '') === activeType : true;
            return matchFilter && matchType;
        });

        displayed = 0;
        listEl.innerHTML = '';
        renderMore();
    }

    /* ── Render PAGE_SIZE more items ── */
    function renderMore() {
        const chunk = filtered.slice(displayed, displayed + PAGE_SIZE);
        displayed += chunk.length;

        if (chunk.length === 0 && displayed === 0) {
            listEl.style.display  = 'none';
            emptyEl.style.display = '';
            loadMoreWrap.style.display = 'none';
            return;
        }

        listEl.style.display  = '';
        emptyEl.style.display = 'none';

        const html = chunk.map(n => Noti.buildItem(n, {
            detailUrl: `/notification/detail/__ID__`
        })).join('');

        listEl.insertAdjacentHTML('beforeend', html);

        // Show/hide load more
        loadMoreWrap.style.display = displayed < filtered.length ? '' : 'none';
    }

    /* ── Mark all read ── */
    btnMarkAll.addEventListener('click', async () => {
        if (!allItems.some(n => !n.is_read)) {
            Noti.toast('info', 'Tất cả thông báo đã được đọc');
            return;
        }
        const r = await Noti.api('POST', '/notification/mark-all-read');
        if (r.ok) {
            Noti.toast('success', r.data?.title || 'Đã đánh dấu tất cả đã đọc');
            allItems.forEach(n => n.is_read = true);
            updateCounts();
            // Update DOM: remove unread class + dots
            document.querySelectorAll('.noti-item.unread').forEach(el => {
                el.classList.remove('unread');
                el.querySelector('.unread-dot')?.remove();
            });
        } else {
            Noti.toast('error', r.data?.title || 'Có lỗi xảy ra');
        }
    });

    /* ── Refresh ── */
    btnRefresh.addEventListener('click', () => {
        btnRefresh.querySelector('i').classList.add('fa-spin');
        load().finally(() => btnRefresh.querySelector('i').classList.remove('fa-spin'));
    });

    /* ── Load more ── */
    btnLoadMore.addEventListener('click', renderMore);

    /* ── Filter buttons ── */
    filterBar.addEventListener('click', e => {
        const btn = e.target.closest('[data-filter]');
        if (!btn) return;
        filterBar.querySelectorAll('.noti-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter;
        applyFilter();
    });

    /* ── Type dropdown ── */
    typeFilter.addEventListener('change', () => {
        activeType = typeFilter.value;
        applyFilter();
    });

    /* ── React to external delete ── */
    document.addEventListener('noti:deleted', ({ detail }) => {
        allItems = allItems.filter(n => n.id !== detail.id);
        updateCounts();
        // Don't re-render full list — DOM already updated by Noti.deleteItem
    });

    /* ── React to click: mark item as read in local state ── */
    listEl.addEventListener('click', e => {
        const item = e.target.closest('.noti-item');
        if (!item) return;
        const id = +item.dataset.id;
        const n  = allItems.find(x => x.id === id);
        if (n) n.is_read = true;
        updateCounts();
    });

    /* ── Init ── */
    load();
});