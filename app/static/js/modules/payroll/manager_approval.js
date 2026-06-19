
/**
 * MANAGER APPROVAL PAGE
 * Xem danh sách lương phòng ban, duyệt từng phiếu, xử lý khiếu nại.
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── State ────────────────────────────────────────────────────────────
    let currentMonth = new Date().getMonth() + 1;
    let currentYear  = new Date().getFullYear();
    let allSalaries  = [];
    let selectedId   = null;

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const monthInput     = document.getElementById('filterMonth');
    const yearInput      = document.getElementById('filterYear');
    const searchInput    = document.getElementById('searchEmployee');
    const statusFilter   = document.getElementById('statusFilter');
    const applyBtn       = document.getElementById('applyFilterBtn');
    const tableBody      = document.getElementById('approvalTableBody');
    const summaryTotal   = document.getElementById('summaryTotal');
    const summaryPending = document.getElementById('summaryPending');
    const detailModal    = document.getElementById('detailModal') 
                            ? new bootstrap.Modal('#detailModal') 
                            : null;
    const complaintsTab  = document.getElementById('complaintsTab');

    // ─── Init ─────────────────────────────────────────────────────────────
    if (monthInput) monthInput.value = currentMonth;
    if (yearInput)  yearInput.value  = currentYear;

    loadPayrollReview();
    if (complaintsTab) loadComplaints();

    // ─── Events ───────────────────────────────────────────────────────────
    applyBtn?.addEventListener('click', loadPayrollReview);

    searchInput?.addEventListener('input', _debounce(() => {
        const kw = searchInput.value.toLowerCase().trim();
        _filterAndRender(kw);
    }, 300));

    // ─── Load Payroll Review ──────────────────────────────────────────────
    async function loadPayrollReview() {
        currentMonth = parseInt(monthInput?.value) || new Date().getMonth() + 1;
        currentYear  = parseInt(yearInput?.value)  || new Date().getFullYear();

        _setTableLoading(true);

        try {
            const filters = {};
            if (statusFilter?.value) filters.status = statusFilter.value;

            const res = await PayrollAPI.getManagerPayrollReview(currentMonth, currentYear, filters);

            if (!res.ok) {
                showNotification('error', res.data?.swal?.text || 'Không tải được danh sách lương.');
                return;
            }

            const payload = res.data?.data || {};
            allSalaries   = payload.items || [];

            const summary = payload.summary || {};
            if (summaryTotal)   summaryTotal.textContent   = summary.total_employees || 0;
            if (summaryPending) summaryPending.textContent = summary.pending_confirmation || 0;

            _renderTable(allSalaries);

        } catch (err) {
            console.error('loadPayrollReview error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        } finally {
            _setTableLoading(false);
        }
    }

    function _filterAndRender(keyword) {
        if (!keyword) { _renderTable(allSalaries); return; }
        const filtered = allSalaries.filter(s =>
            (s.employee_name || '').toLowerCase().includes(keyword) ||
            (s.employee_code || '').toLowerCase().includes(keyword)
        );
        _renderTable(filtered);
    }

    function _renderTable(items) {
        if (!tableBody) return;

        if (!items.length) {
            tableBody.innerHTML = `
                <tr><td colspan="8" class="text-center text-muted py-4">
                    <i class="fas fa-inbox fa-2x mb-2 d-block"></i>Không có dữ liệu
                </td></tr>`;
            return;
        }

        tableBody.innerHTML = items.map(item => {
            const ws     = item.work_stats    || {};
            const rp     = item.review_params || {};
            const isPending = item.status === 'pending';

            const warningIcon = rp.has_warning
                ? `<i class="fas fa-exclamation-triangle text-warning ms-1" title="Số người phụ thuộc thay đổi: ${rp.snapshot_dependents} -> ${rp.current_dependents}"></i>`
                : '';

            return `
            <tr class="${item.is_self ? 'table-light fw-semibold' : ''}">
                <td>
                    <span class="badge bg-secondary">${item.employee_code}</span>
                </td>
                <td>
                    ${_escHtml(item.employee_name)}
                    ${item.is_self ? '<span class="badge bg-info ms-1 small">Bạn</span>' : ''}
                    ${warningIcon}
                </td>
                <td>${_escHtml(item.position || '--')}</td>
                <td class="text-center">
                    ${ws.total_work_days ?? '--'}
                    <small class="text-muted d-block">${ws.reg_hours ?? 0}h + OT ${ws.ot_after_hours ?? 0}h</small>
                </td>
                <td class="text-danger text-end">${_fmt(rp.penalty_amount)}</td>
                <td>
                    <span class="badge ${_statusClass(item.status)}">${item.status_label}</span>
                </td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="openDetail(${item.salary_id})">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${isPending
                        ? `<button class="btn btn-sm btn-success" onclick="confirmPayroll(${item.salary_id})">
                               <i class="fas fa-check me-1"></i>Duyệt
                           </button>`
                        : ''
                    }
                </td>
            </tr>`;
        }).join('');
    }

    // ─── Open Detail Modal ────────────────────────────────────────────────
    window.openDetail = async function(salaryId) {
        selectedId = salaryId;

        const detailContent = document.getElementById('detailContent');
        if (detailContent) detailContent.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';

        detailModal?.show();

        try {
            const res = await PayrollAPI.getManagerPayrollDetail(salaryId);

            if (!res.ok) {
                if (detailContent) detailContent.innerHTML = `<div class="alert alert-danger">${res.data?.swal?.text || 'Lỗi tải dữ liệu.'}</div>`;
                return;
            }

            const d = res.data?.data || {};
            if (detailContent) detailContent.innerHTML = _buildDetailHTML(d);

        } catch (err) {
            console.error('openDetail error:', err);
            if (detailContent) detailContent.innerHTML = '<div class="alert alert-danger">Lỗi kết nối.</div>';
        }
    };

    function _buildDetailHTML(d) {
        const emp = d.employee     || {};
        const earn= d.earnings     || {};
        const ded = d.deductions   || {};
        const ws  = d.work_stats   || {};
        const allow = earn.allowances || {};

        const depWarn = ws.has_dep_warning
            ? `<div class="alert alert-warning small py-2">
                   <i class="fas fa-exclamation-triangle me-1"></i>
                   Số NPT thay đổi: <strong>${ws.snapshot_dependents}</strong> &rarr; <strong>${ws.current_dependents}</strong>
               </div>`
            : '';

        return `
        ${depWarn}
        <div class="row g-3">
            <div class="col-md-6">
                <h6 class="text-muted small fw-bold text-uppercase mb-2">Thông tin nhân viên</h6>
                <table class="table table-sm table-borderless">
                    <tr><td class="text-muted">Mã NV</td><td class="fw-semibold">${emp.code}</td></tr>
                    <tr><td class="text-muted">Họ tên</td><td class="fw-semibold">${_escHtml(emp.name)}</td></tr>
                    <tr><td class="text-muted">Chức vụ</td><td>${_escHtml(emp.position || '--')}</td></tr>
                    <tr><td class="text-muted">Kỳ lương</td><td>${ws.month_year}</td></tr>
                    <tr><td class="text-muted">Ngày công</td><td>${ws.total_work_days} / ${ws.standard_work_days}</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6 class="text-muted small fw-bold text-uppercase mb-2">Chi tiết lương</h6>
                <table class="table table-sm table-borderless">
                    <tr><td class="text-muted">Lương cơ bản</td><td class="text-end">${_fmt(earn.basic_salary)}</td></tr>
                    <tr><td class="text-muted">Phụ cấp cơm trưa</td><td class="text-end text-success">+${_fmt(allow.lunch)}</td></tr>
                    <tr><td class="text-muted">Phụ cấp trách nhiệm</td><td class="text-end text-success">+${_fmt(allow.responsibility)}</td></tr>
                    <tr><td class="text-muted">Lương tăng ca</td><td class="text-end text-success">+${_fmt(earn.overtime_salary)}</td></tr>
                    <tr class="border-top"><td class="text-muted">Bảo hiểm</td><td class="text-end text-danger">-${_fmt(ded.insurance)}</td></tr>
                    <tr><td class="text-muted">Thuế TNCN</td><td class="text-end text-danger">-${_fmt(ded.tax)}</td></tr>
                    <tr><td class="text-muted">Phạt</td><td class="text-end text-danger">-${_fmt(ded.penalty)}</td></tr>
                    <tr class="table-primary fw-bold border-top">
                        <td>Thực lĩnh</td>
                        <td class="text-end text-primary">${_fmt(d.net_salary)}</td>
                    </tr>
                </table>
            </div>
        </div>`;
    }

    // ─── Confirm (Approve) Payroll ────────────────────────────────────────
    window.confirmPayroll = async function(salaryId) {
        const { value: note, isConfirmed } = await Swal.fire({
            title:             'Xác nhận duyệt lương',
            input:             'textarea',
            inputLabel:        'Ghi chú (tuỳ chọn)',
            inputPlaceholder:  'Nhập ghi chú...',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận duyệt',
            cancelButtonText:  'Hủy',
            confirmButtonColor: '#198754',
        });

        if (!isConfirmed) return;

        try {
            const res = await PayrollAPI.confirmPayroll(salaryId, note || '');

            if (res.ok) {
                const icon = res.data?.swal?.icon === 'warning' ? 'warning' : 'success';
                showNotification(icon, res.data?.swal?.text || 'Đã duyệt lương thành công.');
                await loadPayrollReview();
            } else {
                showNotification('error', res.data?.swal?.text || 'Duyệt lương thất bại.');
            }
        } catch (err) {
            console.error('confirmPayroll error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    };

    // ─── Load Complaints Tab ──────────────────────────────────────────────
    async function loadComplaints() {
        const cBody = document.getElementById('complaintsBody');
        if (!cBody) return;

        try {
            const res = await PayrollAPI.getManagerComplaints({
                month: currentMonth,
                year:  currentYear,
            });

            if (!res.ok) return;

            const items = res.data?.data || [];

            if (!items.length) {
                cBody.innerHTML = '<div class="text-center text-muted py-3">Không có khiếu nại nào.</div>';
                return;
            }

            cBody.innerHTML = items.map(c => `
                <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                    <div>
                        <div class="fw-semibold">${_escHtml(c.employee)}</div>
                        <small class="text-muted">${_escHtml(c.title)}</small>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                        <span class="badge ${_complaintBadge(c.status)}">${c.status}</span>
                        ${c.status === 'pending'
                            ? `<button class="btn btn-sm btn-success" onclick="handleComplaint(${c.id}, 'approve')">
                                   <i class="fas fa-check"></i>
                               </button>
                               <button class="btn btn-sm btn-danger" onclick="handleComplaint(${c.id}, 'reject')">
                                   <i class="fas fa-times"></i>
                               </button>`
                            : ''
                        }
                    </div>
                </div>
            `).join('');

        } catch (err) {
            console.error('loadComplaints error:', err);
        }
    }

    window.handleComplaint = async function(complaintId, action) {
        const label = action === 'approve' ? 'phê duyệt' : 'từ chối';

        const { value: note, isConfirmed } = await Swal.fire({
            title:            `${label.charAt(0).toUpperCase() + label.slice(1)} khiếu nại`,
            input:            'textarea',
            inputLabel:       `Lý do ${label} (bắt buộc)`,
            inputPlaceholder: `Nhập lý do ${label}...`,
            showCancelButton: true,
            confirmButtonText: `Xác nhận ${label}`,
            cancelButtonText:  'Hủy',
            confirmButtonColor: action === 'approve' ? '#198754' : '#dc3545',
            inputValidator: v => !v?.trim() ? `Vui lòng nhập lý do ${label}` : null,
        });

        if (!isConfirmed) return;

        try {
            const res = await PayrollAPI.handleManagerComplaint(complaintId, action, note);

            if (res.ok) {
                showNotification('success', `Đã ${label} khiếu nại thành công.`);
                loadComplaints();
            } else {
                showNotification('error', res.data?.swal?.text || `${label} thất bại.`);
            }
        } catch (err) {
            console.error('handleComplaint error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    };

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _setTableLoading(state) {
        if (tableBody) tableBody.style.opacity = state ? '0.4' : '1';
    }

    function _fmt(val) {
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0);
    }

    function _statusClass(status) {
        const m = { pending: 'bg-warning text-dark', approved: 'bg-success', rejected: 'bg-danger', sent: 'bg-info', locked: 'bg-primary', paid: 'bg-success' };
        return m[status] || 'bg-secondary';
    }

    function _complaintBadge(status) {
        const m = { pending: 'bg-warning text-dark', in_progress: 'bg-info', resolved: 'bg-success', rejected: 'bg-danger' };
        return m[status] || 'bg-secondary';
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

    function _debounce(fn, delay) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    }

});
