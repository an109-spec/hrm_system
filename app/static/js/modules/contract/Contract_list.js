/**
 * contract_list.js
 * Logic cho trang danh sách hợp đồng (list.html)
 * Đặt tại: app/static/js/modules/contract/contract_list.js
 *
 * Phụ thuộc: contract_api.js, main.js (showNotification, confirmAction)
 */

(function () {
    'use strict';

    // ── Trạng thái module ──────────────────────────────────────────────
    let debounceTimer = null;
    const ROLE = document.body.dataset.role || '';   // set từ Jinja: <body data-role="{{ current_user.role.name }}">

    // ── DOM refs ───────────────────────────────────────────────────────
    const searchInput   = document.getElementById('searchInput');
    const statusFilter  = document.getElementById('statusFilter');
    const typeFilter    = document.getElementById('typeFilter');
    const btnReset      = document.getElementById('btnReset');
    const tableBody     = document.getElementById('contractTableBody');
    const btnCreate     = document.getElementById('btnCreateContract');   // Admin only, có thể null

    // ── Helpers ────────────────────────────────────────────────────────
    function formatDate(iso) {
        if (!iso) return '–';
        const [y, m, d] = iso.split('T')[0].split('-');
        return `${d}/${m}/${y}`;
    }

    function statusBadge(status) {
        const map = {
            active:     ['badge-active',     '<i class="fas fa-check-circle me-1"></i>Hiệu lực'],
            expiring:   ['badge-expiring',   '<i class="fas fa-clock me-1"></i>Sắp hết hạn'],
            expired:    ['badge-expired',    '<i class="fas fa-times-circle me-1"></i>Hết hạn'],
            terminated: ['badge-terminated', '<i class="fas fa-ban me-1"></i>Chấm dứt'],
        };
        const [cls, label] = map[status] || ['badge-terminated', status];
        return `<span class="contract-status-badge ${cls}">${label}</span>`;
    }

    // ── Cập nhật thẻ tóm tắt ──────────────────────────────────────────
    function updateSummary(summary = {}) {
        document.getElementById('sumTotal').textContent    = summary.total    ?? 0;
        document.getElementById('sumActive').textContent   = summary.active   ?? 0;
        document.getElementById('sumExpiring').textContent = summary.expiring ?? 0;
        document.getElementById('sumExpired').textContent  = summary.expired  ?? 0;
    }

    // ── Render bảng ────────────────────────────────────────────────────
    function renderTable(items = []) {
        if (!items.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-5">
                        <div class="contract-empty">
                            <i class="fas fa-folder-open fa-2x"></i>
                            <span>Không tìm thấy hợp đồng nào</span>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tableBody.innerHTML = items.map(c => `
            <tr onclick="window.location.href='/contract/detail/${c.id}'" title="Xem chi tiết">
                <td class="ps-4">
                    <span class="fw-semibold text-primary">${c.contract_code || '–'}</span>
                </td>
                <td>${c.employee_name || '–'}</td>
                <td class="text-nowrap">${formatDate(c.start_date)}</td>
                <td class="text-nowrap">
                    ${c.end_date
                        ? formatDate(c.end_date)
                        : '<span class="text-muted fst-italic">Vô thời hạn</span>'}
                </td>
                <td>${statusBadge(c.contract_status)}</td>
                <td class="text-center">
                    <a href="/contract/detail/${c.id}"
                       class="btn btn-icon btn-outline-primary"
                       onclick="event.stopPropagation()"
                       title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </a>
                </td>
            </tr>
        `).join('');
    }

    // ── Loading state ──────────────────────────────────────────────────
    function showLoading() {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-5 text-muted">
                    <i class="fas fa-spinner fa-spin fa-2x d-block mb-2"></i>
                    Đang tải dữ liệu...
                </td>
            </tr>`;
    }

    // ── Tải danh sách ─────────────────────────────────────────────────
    async function loadContracts() {
        showLoading();

        const filters = {
            search:          searchInput.value.trim(),
            contract_status: statusFilter.value,
            contract_type:   typeFilter.value,
        };

        try {
            const json = await ContractAPI.getContracts(filters);

            if (!json.success) throw new Error(json.swal?.text || 'Lỗi tải dữ liệu');

            const { items, summary } = json.data;
            updateSummary(summary);
            renderTable(items);
        } catch (err) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-5 text-danger">
                        <i class="fas fa-exclamation-circle fa-2x d-block mb-2"></i>
                        ${err.message}
                    </td>
                </tr>`;
        }
    }

    // ── Tạo hợp đồng (Admin) ──────────────────────────────────────────
    async function handleCreateContract() {
        const empId = document.getElementById('newEmpId').value;
        if (!empId) {
            showNotification('warning', 'Vui lòng nhập ID nhân viên');
            return;
        }

        const salary = document.getElementById('newSalary').value;
        const body = {
            employee_id:   parseInt(empId),
            duration:      document.getElementById('newDuration').value,
            contract_type: document.getElementById('newContractType').value,
            note:          document.getElementById('newNote').value,
        };
        if (salary) body.basic_salary = parseFloat(salary);

        const btn = document.getElementById('btnCreateContract');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';

        try {
            const json = await ContractAPI.adminCreateContract(body);
            if (json.success) {
                bootstrap.Modal.getInstance(document.getElementById('createContractModal')).hide();
                showNotification('success', json.swal?.title || 'Tạo hợp đồng thành công');
                loadContracts();
            } else {
                showNotification('error', json.swal?.text || 'Tạo thất bại');
            }
        } catch (e) {
            showNotification('error', 'Lỗi kết nối máy chủ');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save me-1"></i>Tạo hợp đồng';
        }
    }

    // ── Event Listeners ────────────────────────────────────────────────
    function initEvents() {
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(loadContracts, 400);
        });

        [statusFilter, typeFilter].forEach(el =>
            el.addEventListener('change', loadContracts)
        );

        btnReset.addEventListener('click', () => {
            searchInput.value   = '';
            statusFilter.value  = 'all';
            typeFilter.value    = 'all';
            loadContracts();
        });

        if (btnCreate) {
            btnCreate.addEventListener('click', handleCreateContract);
        }
    }

    // ── Init ───────────────────────────────────────────────────────────
    function init() {
        initEvents();
        loadContracts();
    }

    document.addEventListener('DOMContentLoaded', init);
})();