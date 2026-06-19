/**
 * resignation.js
 * Logic nghiệp vụ + UI cho module Nghỉ việc.
 * Phụ thuộc: resignation_api.js, SweetAlert2, Bootstrap 5.
 */

/* =========================================================
   HELPERS DÙNG CHUNG
   ========================================================= */

const STATUS_META = {
    PENDING_MANAGER: { label: 'Chờ Manager',   cls: 'pending-manager',  icon: 'fa-user-tie' },
    PENDING_HR:      { label: 'Chờ HR',         cls: 'pending-hr',       icon: 'fa-id-badge' },
    PENDING_ADMIN:   { label: 'Chờ Admin',       cls: 'pending-admin',    icon: 'fa-user-shield' },
    APPROVED:        { label: 'Đã duyệt',        cls: 'approved',         icon: 'fa-check-circle' },
    REJECTED:        { label: 'Từ chối',         cls: 'rejected',         icon: 'fa-times-circle' },
    CANCELLED:       { label: 'Đã huỷ',          cls: 'cancelled',        icon: 'fa-ban' },
};

function getStatusMeta(status) {
    return STATUS_META[status] || { label: status, cls: 'cancelled', icon: 'fa-circle' };
}

function badgeHtml(status) {
    const m = getStatusMeta(status);
    return `<span class="resign-badge ${m.cls}"><i class="fas ${m.icon}"></i>${m.label}</span>`;
}

function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function handleSwalResponse(result) {
    if (result && result.swal) {
        Swal.fire({
            icon:  result.swal.icon  || 'info',
            title: result.swal.title || '',
            text:  result.swal.text  || '',
            toast: false,
            confirmButtonText: 'Đóng',
        });
    }
}

function showLoading(el, text = 'Đang xử lý...') {
    if (!el) return;
    el.dataset.origHtml = el.innerHTML;
    el.disabled = true;
    el.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${text}`;
}

function restoreBtn(el) {
    if (!el || !el.dataset.origHtml) return;
    el.disabled = false;
    el.innerHTML = el.dataset.origHtml;
}

/* =========================================================
   STEPPER TRẠNG THÁI
   ========================================================= */
const STEPS = [
    { key: 'PENDING_MANAGER', label: 'Manager\nduyệt' },
    { key: 'PENDING_HR',      label: 'HR\nxử lý' },
    { key: 'PENDING_ADMIN',   label: 'Admin\nduyệt' },
    { key: 'APPROVED',        label: 'Hoàn tất' },
];

function renderStepper(containerEl, status) {
    if (!containerEl) return;

    const isRejected = status === 'REJECTED' || status === 'CANCELLED';
    const activeIdx  = STEPS.findIndex(s => s.key === status);

    containerEl.innerHTML = STEPS.map((step, i) => {
        let cls = '';
        if (isRejected && i < activeIdx) cls = 'done';
        else if (!isRejected && i < activeIdx) cls = 'done';
        else if (i === activeIdx) cls = isRejected ? 'rejected' : 'active';

        const icon = cls === 'done' ? 'fa-check' : (cls === 'rejected' ? 'fa-times' : `fa-${i + 1}`);
        const iconHtml = cls === 'done' ? '<i class="fas fa-check"></i>'
                       : cls === 'rejected' ? '<i class="fas fa-times"></i>'
                       : `<span>${i + 1}</span>`;

        return `
            <div class="resign-step ${cls}">
                <div class="step-circle">${iconHtml}</div>
                <div class="step-label">${step.label.replace('\n', '<br>')}</div>
            </div>`;
    }).join('');
}

/* =========================================================
   TRANG: DANH SÁCH ĐƠN (my_list & list_all)
   ========================================================= */

let _listState = { page: 1, per_page: 10, status: '', total: 0, pages: 1 };

async function loadResignationList(containerEl, paginationEl, opts = {}) {
    if (!containerEl) return;
    Object.assign(_listState, opts);

    containerEl.innerHTML = `
        <div class="text-center py-5 text-muted">
            <div class="spinner-border text-primary mb-2"></div>
            <div>Đang tải...</div>
        </div>`;

    const params = {
        page:     _listState.page,
        per_page: _listState.per_page,
    };
    if (_listState.status) params.status = _listState.status;

    const { ok, data } = await ResignationAPI.list(params);

    if (!ok) {
        containerEl.innerHTML = `<div class="alert alert-danger">${data?.swal?.text || 'Không tải được dữ liệu.'}</div>`;
        return;
    }

    const items = data.data?.items || [];
    _listState.total = data.data?.total || 0;
    _listState.pages = data.data?.pages || 1;

    if (!items.length) {
        containerEl.innerHTML = `
            <div class="resign-empty">
                <i class="fas fa-file-alt"></i>
                <p class="fw-semibold">Chưa có đơn nghỉ việc nào</p>
                <p class="small">Các đơn sẽ xuất hiện ở đây khi được tạo.</p>
            </div>`;
        if (paginationEl) paginationEl.innerHTML = '';
        return;
    }

    containerEl.innerHTML = items.map(r => resignCardHtml(r)).join('');
    if (paginationEl) renderPagination(paginationEl, _listState.page, _listState.pages);

    // Click vào card → tới trang detail
    containerEl.querySelectorAll('.resign-card').forEach(card => {
        card.addEventListener('click', () => {
            window.location.href = `/resignation/${card.dataset.id}`;
        });
    });
}

function resignCardHtml(r) {
    const m = getStatusMeta(r.status);
    return `
    <div class="resign-card border-${m.cls} mb-3" data-id="${r.id}">
        <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
            <div>
                <div class="fw-bold">${r.employee_name || '—'} <span class="text-muted fw-normal small">#${r.id}</span></div>
                <div class="card-meta mt-1">
                    <i class="fas fa-calendar-alt me-1"></i>Ngày dự kiến nghỉ: <strong>${fmtDate(r.expected_last_day)}</strong>
                    &nbsp;·&nbsp;
                    <i class="fas fa-tag me-1"></i>${r.reason_category || '—'}
                </div>
                <div class="card-meta mt-1">
                    <i class="fas fa-clock me-1"></i>Gửi lúc: ${fmtDate(r.created_at)}
                    ${r.request_type === 'manager_proposal' ? '<span class="ms-2 badge bg-info text-dark">Đề xuất bởi Manager</span>' : ''}
                </div>
            </div>
            <div>${badgeHtml(r.status)}</div>
        </div>
    </div>`;
}

function renderPagination(el, current, total) {
    if (total <= 1) { el.innerHTML = ''; return; }
    const pages = [];
    for (let i = 1; i <= total; i++) {
        pages.push(`<button class="page-btn ${i === current ? 'active' : ''}" data-page="${i}">${i}</button>`);
    }
    el.innerHTML = `<div class="resign-pagination">${pages.join('')}</div>`;
    el.querySelectorAll('.page-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            _listState.page = parseInt(btn.dataset.page);
            const listEl = document.getElementById('resignListContainer');
            const pageEl = document.getElementById('resignPagination');
            loadResignationList(listEl, pageEl);
        });
    });
}

/* =========================================================
   FORM GỬI ĐƠN (NHÂN VIÊN)
   ========================================================= */

function initSubmitForm() {
    const form = document.getElementById('resignSubmitForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('[type=submit]');
        showLoading(btn, 'Đang gửi...');

        const fd = new FormData(form);
        const payload = {
            expected_last_day:    fd.get('expected_last_day'),
            reason_category:      fd.get('reason_category'),
            reason_text:          fd.get('reason_text') || null,
            extra_note:           fd.get('extra_note') || null,
            attachment_url:       fd.get('attachment_url') || null,
            handover_employee_id: fd.get('handover_employee_id') ? parseInt(fd.get('handover_employee_id')) : null,
        };

        const { ok, data } = await ResignationAPI.submit(payload);
        restoreBtn(btn);
        handleSwalResponse(data);

        if (ok) {
            setTimeout(() => window.location.href = '/resignation/my-list', 1800);
        }
    });
}

/* =========================================================
   FORM ĐỀ XUẤT NGHỈ (MANAGER)
   ========================================================= */

function initProposeForm() {
    const form = document.getElementById('resignProposeForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('[type=submit]');
        showLoading(btn, 'Đang gửi...');

        const fd = new FormData(form);
        const payload = {
            employee_id:          parseInt(fd.get('employee_id')),
            expected_last_day:    fd.get('expected_last_day'),
            reason_category:      fd.get('reason_category'),
            reason_text:          fd.get('reason_text') || null,
            extra_note:           fd.get('extra_note') || null,
            attachment_url:       fd.get('attachment_url') || null,
            handover_employee_id: fd.get('handover_employee_id') ? parseInt(fd.get('handover_employee_id')) : null,
        };

        const { ok, data } = await ResignationAPI.propose(payload);
        restoreBtn(btn);
        handleSwalResponse(data);

        if (ok) {
            setTimeout(() => window.location.href = '/resignation/', 1800);
        }
    });
}

/* =========================================================
   TRANG DETAIL — ACTION PANELS
   ========================================================= */

/** Manager duyệt / từ chối */
function initManagerPanel(resignationId) {
    const panel = document.getElementById('managerActionPanel');
    if (!panel) return;

    panel.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            const note   = document.getElementById('managerNote')?.value?.trim() || null;

            if (action === 'reject' && !note) {
                Swal.fire({ icon: 'warning', title: 'Cần ghi chú', text: 'Vui lòng nhập lý do từ chối.' });
                return;
            }

            const confirmText = action === 'approve' ? 'Duyệt đơn nghỉ và chuyển sang HR?' : 'Từ chối đơn nghỉ này?';
            const { isConfirmed } = await Swal.fire({
                icon: action === 'approve' ? 'question' : 'warning',
                title: 'Xác nhận',
                text: confirmText,
                showCancelButton: true,
                confirmButtonText: 'Đồng ý',
                cancelButtonText: 'Huỷ',
                confirmButtonColor: action === 'approve' ? '#22c55e' : '#ef4444',
            });
            if (!isConfirmed) return;

            showLoading(btn);
            const { ok, data } = await ResignationAPI.managerReview(resignationId, action, note);
            restoreBtn(btn);
            handleSwalResponse(data);
            if (ok) setTimeout(() => location.reload(), 1800);
        });
    });
}

/** HR xử lý offboarding */
function initHRPanel(resignationId) {
    const panel = document.getElementById('hrActionPanel');
    if (!panel) return;

    panel.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;

            const payload = {
                hr_note:               document.getElementById('hr_note')?.value?.trim() || null,
                final_payroll_note:    document.getElementById('final_payroll_note')?.value?.trim() || null,
                final_attendance_note: document.getElementById('final_attendance_note')?.value?.trim() || null,
                leave_balance_note:    document.getElementById('leave_balance_note')?.value?.trim() || null,
                insurance_note:        document.getElementById('insurance_note')?.value?.trim() || null,
                asset_handover_note:   document.getElementById('asset_handover_note')?.value?.trim() || null,
            };

            const confirmText = action === 'forward_admin'
                ? 'Hoàn tất offboarding và chuyển Admin duyệt cuối?'
                : 'Từ chối hồ sơ nghỉ việc này?';

            const { isConfirmed } = await Swal.fire({
                icon: action === 'forward_admin' ? 'question' : 'warning',
                title: 'Xác nhận',
                text: confirmText,
                showCancelButton: true,
                confirmButtonText: 'Đồng ý',
                cancelButtonText: 'Huỷ',
                confirmButtonColor: action === 'forward_admin' ? '#3b82f6' : '#ef4444',
            });
            if (!isConfirmed) return;

            showLoading(btn);
            const { ok, data } = await ResignationAPI.hrProcess(resignationId, action, payload);
            restoreBtn(btn);
            handleSwalResponse(data);
            if (ok) setTimeout(() => location.reload(), 1800);
        });
    });
}

/** Admin phê duyệt cuối */
function initAdminPanel(resignationId) {
    const panel = document.getElementById('adminActionPanel');
    if (!panel) return;

    panel.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            const note   = document.getElementById('adminNote')?.value?.trim() || null;

            if (action === 'approve') {
                const { isConfirmed } = await Swal.fire({
                    icon: 'warning',
                    title: 'Xác nhận duyệt nghỉ',
                    html: '<p>Hành động này sẽ <strong>khoá tài khoản</strong> của nhân viên và cập nhật trạng thái nhân sự thành <strong>Đã nghỉ việc</strong>.</p><p>Tiếp tục?</p>',
                    showCancelButton: true,
                    confirmButtonText: 'Đồng ý duyệt',
                    cancelButtonText: 'Huỷ',
                    confirmButtonColor: '#22c55e',
                });
                if (!isConfirmed) return;
            } else {
                if (!note) {
                    Swal.fire({ icon: 'warning', title: 'Cần ghi chú', text: 'Vui lòng nhập lý do từ chối.' });
                    return;
                }
                const { isConfirmed } = await Swal.fire({
                    icon: 'warning',
                    title: 'Từ chối đơn',
                    text: 'Từ chối đơn nghỉ việc này?',
                    showCancelButton: true,
                    confirmButtonText: 'Đồng ý',
                    cancelButtonText: 'Huỷ',
                    confirmButtonColor: '#ef4444',
                });
                if (!isConfirmed) return;
            }

            showLoading(btn);
            const { ok, data } = await ResignationAPI.adminFinalize(resignationId, action, note);
            restoreBtn(btn);
            handleSwalResponse(data);
            if (ok) setTimeout(() => location.reload(), 1800);
        });
    });
}

/* =========================================================
   AUTO-INIT khi DOM sẵn sàng
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {
    // Danh sách đơn
    const listEl = document.getElementById('resignListContainer');
    const pageEl = document.getElementById('resignPagination');
    if (listEl) loadResignationList(listEl, pageEl);

    // Filter
    const filterForm = document.getElementById('resignFilterForm');
    if (filterForm) {
        filterForm.addEventListener('change', () => {
            _listState.page = 1;
            _listState.status = filterForm.querySelector('[name=status]')?.value || '';
            loadResignationList(listEl, pageEl);
        });
        filterForm.addEventListener('submit', e => e.preventDefault());
    }

    // Stepper
    const stepperEl = document.getElementById('resignStepper');
    if (stepperEl) renderStepper(stepperEl, stepperEl.dataset.status);

    // Forms
    initSubmitForm();
    initProposeForm();

    // Action panels (detail page)
    const resignationId = document.getElementById('resignationId')?.value;
    if (resignationId) {
        const rid = parseInt(resignationId);
        initManagerPanel(rid);
        initHRPanel(rid);
        initAdminPanel(rid);
    }
});