/**
 * renewal_request.js
 * Logic cho trang gửi yêu cầu gia hạn hợp đồng (renewal_request.html) – Manager
 * Đặt tại: app/static/js/modules/contract/renewal_request.js
 *
 * Phụ thuộc: contract_api.js, main.js (showNotification)
 */

(function () {
    'use strict';

    // ── Lấy contract_id từ URL param ──────────────────────────────────
    const CONTRACT_ID = (() => {
        const params = new URLSearchParams(window.location.search);
        return params.get('contract_id') || params.get('id');
    })();

    // ── DOM refs ───────────────────────────────────────────────────────
    const loadingEl    = document.getElementById('contractInfoLoading');
    const infoCardEl   = document.getElementById('contractInfoCard');
    const monthBtns    = document.querySelectorAll('.month-btn');
    const customMonths = document.getElementById('customMonths');
    const selectedMonthsEl = document.getElementById('selectedMonths');
    const reasonEl     = document.getElementById('reason');
    const noteEl       = document.getElementById('professionalNote');
    const reasonCount  = document.getElementById('reasonCount');
    const noteCount    = document.getElementById('noteCount');
    const btnSubmit    = document.getElementById('btnSubmitRenewal');

    // ── Helpers ────────────────────────────────────────────────────────
    function formatDate(iso) {
        if (!iso) return '–';
        const [y, m, d] = iso.split('T')[0].split('-');
        return `${d}/${m}/${y}`;
    }

    function setText(id, value, fallback = '–') {
        const el = document.getElementById(id);
        if (el) el.textContent = value || fallback;
    }

    // ── Load thông tin hợp đồng ────────────────────────────────────────
    async function loadContractInfo() {
        if (!CONTRACT_ID) {
            loadingEl.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-1"></i>
                    Không tìm thấy ID hợp đồng trong URL. Vui lòng quay lại trang danh sách và chọn hợp đồng.
                </div>`;
            return;
        }

        try {
            const json = await ContractAPI.managerGetContractDetail(CONTRACT_ID);
            if (!json.success) throw new Error(json.swal?.text || 'Không tải được thông tin');
            renderContractInfo(json.data);
        } catch (err) {
            loadingEl.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-1"></i>${err.message}
                </div>`;
        }
    }

    function renderContractInfo(c) {
        loadingEl.style.display  = 'none';
        infoCardEl.style.display = 'block';

        setText('ciCode',  c.contract_code);
        setText('ciName',  c.employee_name);
        setText('ciStart', formatDate(c.start_date));
        setText('ciEnd',   c.end_date ? formatDate(c.end_date) : 'Vô thời hạn');

        // Status badge
        const statusEl = document.getElementById('ciStatus');
        if (statusEl) {
            const statusMap = {
                active:   ['status-badge-active',   'Đang hiệu lực'],
                expiring: ['status-badge-expiring',  'Sắp hết hạn'],
                expired:  ['status-badge-expired',   'Đã hết hạn'],
            };
            const [cls, label] = statusMap[c.contract_status] || ['status-badge-active', c.contract_status];
            statusEl.className  = cls;
            statusEl.textContent = label;
        }

        // Days left
        const daysEl = document.getElementById('ciDays');
        if (daysEl) {
            if (c.days_left === null || c.days_left === undefined) {
                daysEl.textContent = 'Vô thời hạn';
            } else if (c.days_left < 0) {
                daysEl.textContent = `Quá hạn ${Math.abs(c.days_left)} ngày`;
            } else {
                daysEl.textContent = `Còn ${c.days_left} ngày`;
            }
        }
    }

    // ── Month buttons ──────────────────────────────────────────────────
    function initMonthButtons() {
        monthBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                monthBtns.forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedMonthsEl.value = btn.dataset.months;
                customMonths.value     = '';
            });
        });

        customMonths.addEventListener('input', function () {
            monthBtns.forEach(b => b.classList.remove('selected'));
            selectedMonthsEl.value = this.value;
        });
    }

    // ── Character counters ─────────────────────────────────────────────
    function initCharCounters() {
        reasonEl.addEventListener('input', function () {
            reasonCount.textContent = this.value.length;
        });
        noteEl.addEventListener('input', function () {
            noteCount.textContent = this.value.length;
        });
    }

    // ── Submit ─────────────────────────────────────────────────────────
    async function handleSubmit() {
        const reason = reasonEl.value.trim();
        const months = parseInt(selectedMonthsEl.value);
        const note   = noteEl.value.trim();

        if (!reason) {
            showNotification('warning', 'Vui lòng nhập lý do gia hạn');
            return;
        }
        if (!months || months <= 0) {
            showNotification('warning', 'Vui lòng chọn số tháng gia hạn hợp lệ (tối thiểu 1 tháng)');
            return;
        }

        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang gửi...';

        try {
            const json = await ContractAPI.managerRequestRenewal(CONTRACT_ID, {
                reason,
                proposed_duration_months: months,
                professional_note: note || null,
            });

            if (json.success) {
                await Swal.fire({
                    icon: 'success',
                    title: 'Đã gửi yêu cầu gia hạn!',
                    text:  json.swal?.text || 'HR sẽ xem xét và phản hồi trong 1–3 ngày làm việc.',
                    confirmButtonText: 'Về danh sách hợp đồng',
                });
                window.location.href = '/contract/list';
            } else {
                showNotification('error', json.swal?.text || 'Gửi yêu cầu thất bại');
                resetBtn();
            }
        } catch (e) {
            showNotification('error', 'Lỗi kết nối máy chủ');
            resetBtn();
        }
    }

    function resetBtn() {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Gửi yêu cầu gia hạn';
    }

    // ── Init ───────────────────────────────────────────────────────────
    function init() {
        loadContractInfo();
        initMonthButtons();
        initCharCounters();
        btnSubmit.addEventListener('click', handleSubmit);
    }

    document.addEventListener('DOMContentLoaded', init);
})();