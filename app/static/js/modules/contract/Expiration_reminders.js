/**
 * expiration_reminders.js
 * Logic cho trang cảnh báo hợp đồng sắp hết hạn (expiration_reminders.html)
 * Đặt tại: app/static/js/modules/contract/expiration_reminders.js
 *
 * Phụ thuộc: contract_api.js, main.js (showNotification)
 */

(function () {
    'use strict';

    // ── Trạng thái module ──────────────────────────────────────────────
    let allReminders  = [];
    let activeLevel   = 'all';
    let searchTimer   = null;

    // ── DOM refs ───────────────────────────────────────────────────────
    const loadingEl       = document.getElementById('reminderLoading');
    const listEl          = document.getElementById('reminderList');
    const emptyEl         = document.getElementById('emptyState');
    const searchInput     = document.getElementById('searchInput');
    const btnRefresh      = document.getElementById('btnRefresh');
    const levelFilterTabs = document.querySelectorAll('#levelFilter .nav-link');

    // ── Helpers ────────────────────────────────────────────────────────
    function setStat(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value ?? 0;
    }

    // ── Load cảnh báo ──────────────────────────────────────────────────
    async function loadReminders() {
        loadingEl.style.display = 'block';
        listEl.style.display    = 'none';
        emptyEl.style.display   = 'none';
        loadingEl.innerHTML     = `
            <div class="contract-loading">
                <i class="fas fa-spinner fa-spin fa-2x"></i>
                <span>Đang tải cảnh báo hợp đồng...</span>
            </div>`;

        try {
            const json = await ContractAPI.getContractReminders();
            if (!json.success) throw new Error(json.text || json.swal?.text || 'Lỗi tải dữ liệu');

            allReminders = json.data.items || [];
            const summary = json.data.summary || {};

            setStat('sumCritical', summary.critical);
            setStat('sumWarning',  summary.warning);
            setStat('sumInfo',     summary.info);

            loadingEl.style.display = 'none';
            renderList();
        } catch (err) {
            loadingEl.innerHTML = `
                <div class="text-danger text-center py-4">
                    <i class="fas fa-exclamation-circle fa-2x d-block mb-2"></i>
                    ${err.message}
                    <div class="mt-3">
                        <button class="btn btn-sm btn-outline-secondary" onclick="location.reload()">
                            <i class="fas fa-sync me-1"></i>Thử lại
                        </button>
                    </div>
                </div>`;
        }
    }

    // ── Lọc & render danh sách ─────────────────────────────────────────
    function renderList() {
        const keyword = searchInput.value.toLowerCase().trim();

        const filtered = allReminders.filter(item => {
            const matchLevel  = activeLevel === 'all' || item.level === activeLevel;
            const matchSearch = !keyword
                || (item.employee_name || '').toLowerCase().includes(keyword)
                || (item.employee_code || '').toLowerCase().includes(keyword);
            return matchLevel && matchSearch;
        });

        if (!filtered.length) {
            listEl.style.display  = 'none';
            emptyEl.style.display = 'block';
            return;
        }

        listEl.style.display  = 'block';
        emptyEl.style.display = 'none';
        listEl.innerHTML = filtered.map(item => buildReminderCard(item)).join('');
    }

    // ── Build HTML cho 1 reminder card ────────────────────────────────
    function buildReminderCard(item) {
        const iconMap = {
            critical: 'fa-exclamation-circle',
            warning:  'fa-clock',
            info:     'fa-check-circle',
        };
        const icon = iconMap[item.level] || 'fa-info-circle';

        const daysBadge = buildDaysBadge(item.days_left);

        const actionBtns = buildActionButtons(item);

        return `
        <div class="reminder-card card mb-3 p-3 level-${item.level}">
            <div class="d-flex align-items-start gap-3">
                <div class="reminder-level-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="flex-grow-1 min-w-0">
                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-1 mb-1">
                        <div>
                            <span class="fw-semibold">${item.employee_name || '–'}</span>
                            <span class="text-muted small ms-2">${item.employee_code || ''}</span>
                        </div>
                        ${daysBadge}
                    </div>
                    <p class="text-muted small mb-2">${item.message || ''}</p>
                    <div class="d-flex gap-2 flex-wrap">
                        ${actionBtns}
                    </div>
                </div>
            </div>
        </div>`;
    }

    function buildDaysBadge(days_left) {
        if (days_left === null || days_left === undefined) {
            return `<span class="days-badge days-badge-none">Chưa có HĐ</span>`;
        }
        if (days_left < 0) {
            return `<span class="days-badge days-badge-critical">Quá hạn ${Math.abs(days_left)} ngày</span>`;
        }
        if (days_left <= 7) {
            return `<span class="days-badge days-badge-critical">Còn ${days_left} ngày</span>`;
        }
        if (days_left <= 30) {
            return `<span class="days-badge days-badge-warning">Còn ${days_left} ngày</span>`;
        }
        return `<span class="days-badge days-badge-info">Còn ${days_left} ngày</span>`;
    }

    function buildActionButtons(item) {
        let html = '';

        if (item.type === 'missing_contract') {
            html += `
                <a href="/contract/create" class="btn btn-sm btn-outline-danger quick-action-btn">
                    <i class="fas fa-plus me-1"></i>Tạo hợp đồng
                </a>`;
        } else if (item.contract_id) {
            html += `
                <a href="/contract/detail/${item.contract_id}"
                   class="btn btn-sm btn-outline-secondary quick-action-btn">
                    <i class="fas fa-eye me-1"></i>Xem HĐ
                </a>`;

            // Nút gia hạn nếu không phải terminated / info bình thường
            if (item.type !== 'normal') {
                html += `
                    <a href="/contract/renewal_request?contract_id=${item.contract_id}"
                       class="btn btn-sm btn-outline-warning quick-action-btn">
                        <i class="fas fa-redo me-1"></i>Gia hạn
                    </a>`;
            }
        }

        return html;
    }

    // ── Filter tab events ──────────────────────────────────────────────
    function initLevelFilter() {
        levelFilterTabs.forEach(link => {
            link.addEventListener('click', e => {
                e.preventDefault();
                levelFilterTabs.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
                activeLevel = link.dataset.level;
                renderList();
            });
        });
    }

    // ── Search event ───────────────────────────────────────────────────
    function initSearch() {
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(renderList, 300);
        });
    }

    // ── Init ───────────────────────────────────────────────────────────
    function init() {
        initLevelFilter();
        initSearch();
        btnRefresh.addEventListener('click', loadReminders);
        loadReminders();
    }

    document.addEventListener('DOMContentLoaded', init);
})();