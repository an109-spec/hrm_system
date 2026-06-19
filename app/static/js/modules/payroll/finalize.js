/**
 * FINALIZE PAYROLL (HR/ADMIN)
 * Quy trình: DRAFT -> PENDING -> APPROVED -> LOCKED -> PAID
 * Cho phép HR submit duyệt, Admin approve/finalize/reject/paid.
 *
 * Đã sửa đồng bộ với finalize.html:
 *  - filterMonth: <input type="month"> (YYYY-MM) — chỉ 1 trường, không có filterYear
 *  - filterYear / yearInput   → không tồn tại, parse từ filterMonth
 *  - applyBtn                 → btnLoad
 *  - summaryCards (div chung) → 6 phần tử riêng: cntDraft/cntPending/cntApproved/cntLocked/cntPaid/cntComplaint
 *  - bulkActionBar            → không có trong HTML (dùng btnBulkSubmit/btnNotifyReview thay thế)
 *  - bulkCount                → không có trong HTML (hiển thị count qua Swal)
 *  - tableInfo / totalFund    → có sẵn trong HTML, thêm logic cập nhật
 *  - searchInput              → có sẵn, thêm filter client-side
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── State ────────────────────────────────────────────────────────────
    let allItems     = [];   // cache để filter client-side
    let currentMonth = new Date().getMonth() + 1;
    let currentYear  = new Date().getFullYear();

    // ─── DOM refs (đồng bộ với finalize.html) ────────────────────────────
    const monthInput    = document.getElementById('filterMonth');   // <input type="month">
    const statusFilter  = document.getElementById('statusFilter');
    const deptFilter    = document.getElementById('deptFilter');
    const searchInput   = document.getElementById('searchInput');
    const btnLoad       = document.getElementById('btnLoad');          // "Tìm kiếm"
    const tableBody     = document.getElementById('finalizeTableBody');
    const checkAll      = document.getElementById('checkAll');
    const tableInfo     = document.getElementById('tableInfo');
    const totalFund     = document.getElementById('totalFund');

    // Summary cards — mỗi card có id riêng
    const cntDraft     = document.getElementById('cntDraft');
    const cntPending   = document.getElementById('cntPending');
    const cntApproved  = document.getElementById('cntApproved');
    const cntLocked    = document.getElementById('cntLocked');
    const cntPaid      = document.getElementById('cntPaid');
    const cntComplaint = document.getElementById('cntComplaint');

    // Bulk & notify buttons (thay thế bulkActionBar/bulkCount không có trong HTML)
    const btnBulkSubmit  = document.getElementById('btnBulkSubmit');
    const btnNotifyReview= document.getElementById('btnNotifyReview');

    // ─── Init ─────────────────────────────────────────────────────────────
    // Set giá trị mặc định cho <input type="month"> → format YYYY-MM
    if (monthInput) {
        const yyyy = String(currentYear);
        const mm   = String(currentMonth).padStart(2, '0');
        monthInput.value = `${yyyy}-${mm}`;
    }

    _loadDepartments();
    loadPayrollList();

    // ─── Events ───────────────────────────────────────────────────────────
    btnLoad?.addEventListener('click', loadPayrollList);

    // Filter client-side khi đổi status / search (không cần reload API)
    statusFilter?.addEventListener('change', _applyClientFilter);
    searchInput?.addEventListener('input',   _applyClientFilter);

    checkAll?.addEventListener('change', () => {
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = checkAll.checked);
    });

    btnBulkSubmit?.addEventListener('click',   () => bulkAction('approve'));
    btnNotifyReview?.addEventListener('click', () => _bulkNotifyReview());

    // ─── Load Departments ─────────────────────────────────────────────────
    async function _loadDepartments() {
        try {
            const res = await PayrollAPI.getDepartments?.();
            if (!res?.ok || !deptFilter) return;
            const depts = res.data?.data || [];
            depts.forEach(d => {
                const opt = document.createElement('option');
                opt.value       = d.id;
                opt.textContent = d.name;
                deptFilter.appendChild(opt);
            });
        } catch (_) { /* không bắt buộc */ }
    }

    // ─── Load Payroll List ────────────────────────────────────────────────
    async function loadPayrollList() {
        // Parse tháng/năm từ <input type="month"> (value = "YYYY-MM")
        const [year, month] = _parseMonthInput(monthInput?.value);
        currentMonth = month || (new Date().getMonth() + 1);
        currentYear  = year  || new Date().getFullYear();

        _setLoading(true);

        try {
            const filters = { month: currentMonth, year: currentYear };
            if (deptFilter?.value) filters.department_id = deptFilter.value;

            const res = await PayrollAPI.getPayrollList(filters);

            if (!res.ok) {
                showNotification('error', res.data?.swal?.text || 'Không tải được danh sách.');
                _setLoading(false);
                return;
            }

            const payload = res.data?.data || {};
            allItems      = payload.items   || [];
            const summary = payload.summary || {};

            _renderSummary(summary, allItems);
            _applyClientFilter();   // render table với filter hiện tại

        } catch (err) {
            console.error('loadPayrollList error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        } finally {
            _setLoading(false);
        }
    }

    // ─── Render Summary cards ─────────────────────────────────────────────
    function _renderSummary(s, items) {
        // Đếm từ items nếu API không trả summary riêng
        const count = (status) => items.filter(i => i.status === status).length;

        if (cntDraft)     cntDraft.textContent     = s.draft_count     ?? count('draft');
        if (cntPending)   cntPending.textContent   = s.pending_count   ?? count('pending');
        if (cntApproved)  cntApproved.textContent  = s.approved_count  ?? count('approved');
        if (cntLocked)    cntLocked.textContent    = s.locked_count    ?? count('locked');
        if (cntPaid)      cntPaid.textContent      = s.paid_count      ?? count('paid');
        if (cntComplaint) cntComplaint.textContent = s.complaint_count ?? count('complaint');

        // Tổng quỹ lương
        if (totalFund) {
            const fund = s.payroll_fund ?? items.reduce((sum, i) => sum + (i.net_salary || 0), 0);
            totalFund.textContent = `Quỹ lương: ${_fmt(fund)}`;
        }
    }

    // ─── Client-side filter + render table ───────────────────────────────
    function _applyClientFilter() {
        const status  = statusFilter?.value  || '';
        const keyword = searchInput?.value?.trim().toLowerCase() || '';

        let filtered = allItems;

        if (status) {
            filtered = filtered.filter(i => i.status === status);
        }
        if (keyword) {
            filtered = filtered.filter(i =>
                (i.employee_name || '').toLowerCase().includes(keyword) ||
                (i.employee_code || '').toLowerCase().includes(keyword)
            );
        }

        _renderTable(filtered);

        if (tableInfo) {
            tableInfo.textContent = `Hiển thị ${filtered.length} / ${allItems.length} bản ghi`;
        }
    }

    // ─── Render Table ─────────────────────────────────────────────────────
    function _renderTable(items) {
        if (!tableBody) return;

        if (!items.length) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">Không có dữ liệu.</td></tr>`;
            if (checkAll) checkAll.checked = false;
            return;
        }

        tableBody.innerHTML = items.map(item => `
            <tr>
                <td class="text-center">
                    <input type="checkbox" class="form-check-input row-check" value="${item.id}">
                </td>
                <td><span class="badge bg-light text-dark border">${_escHtml(item.employee_code || '')}</span></td>
                <td class="fw-semibold">${_escHtml(item.employee_name || '')}</td>
                <td>${_escHtml(item.department || '')}</td>
                <td><small>${_escHtml(item.position || '--')}</small></td>
                <td class="text-end">${_fmt(item.basic_salary)}</td>
                <td class="text-end fw-bold text-primary">${_fmt(item.net_salary)}</td>
                <td>
                    <span class="badge ${_statusClass(item.status)}">${_escHtml(item.status_label || item.status)}</span>
                    ${item.has_complaint
                        ? `<span class="badge bg-danger ms-1"><i class="fas fa-exclamation"></i></span>`
                        : ''}
                </td>
                <td>${_buildActionButtons(item)}</td>
            </tr>
        `).join('');

        // Đồng bộ checkAll khi re-render
        if (checkAll) checkAll.checked = false;
    }

    function _buildActionButtons(item) {
        const btns = [];

        // Xem chi tiết
        btns.push(`<a href="/payroll/${item.id}" class="btn btn-sm btn-outline-secondary" title="Chi tiết">
            <i class="fas fa-eye"></i>
        </a>`);

        // HR: Gửi duyệt
        if (['draft', 'rejected', 'complaint'].includes(item.status)) {
            btns.push(`<button class="btn btn-sm btn-outline-primary" onclick="submitApproval(${item.id})" title="Gửi duyệt">
                <i class="fas fa-paper-plane"></i>
            </button>`);
        }

        // Admin: Phê duyệt
        if (item.status === 'pending') {
            btns.push(`<button class="btn btn-sm btn-success" onclick="processFlow(${item.id}, 'approve')" title="Phê duyệt">
                <i class="fas fa-check"></i>
            </button>`);
        }

        // Admin: Chốt sổ
        if (item.status === 'approved') {
            btns.push(`<button class="btn btn-sm btn-primary" onclick="processFlow(${item.id}, 'finalize')" title="Chốt sổ">
                <i class="fas fa-lock"></i>
            </button>`);
        }

        // Admin: Thanh toán
        if (item.status === 'locked') {
            btns.push(`<button class="btn btn-sm btn-success" onclick="processFlow(${item.id}, 'paid')" title="Thanh toán">
                <i class="fas fa-money-bill-wave"></i>
            </button>`);
        }

        // Admin: Từ chối
        if (['pending', 'approved'].includes(item.status)) {
            btns.push(`<button class="btn btn-sm btn-danger" onclick="processFlow(${item.id}, 'reject')" title="Từ chối">
                <i class="fas fa-times"></i>
            </button>`);
        }

        return `<div class="btn-group btn-group-sm">${btns.join('')}</div>`;
    }

    // ─── HR: Submit for Approval ──────────────────────────────────────────
    window.submitApproval = async function(salaryId) {
        const confirm = await Swal.fire({
            title:             'Gửi duyệt bảng lương?',
            text:              'Bảng lương sẽ được chuyển sang "Chờ duyệt" và thông báo Admin.',
            icon:              'question',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận gửi',
            cancelButtonText:  'Hủy',
        });
        if (!confirm.isConfirmed) return;

        try {
            const res = await PayrollAPI.submitPayrollApproval(salaryId);
            if (res.ok) {
                showNotification('success', 'Đã gửi duyệt thành công.');
                loadPayrollList();
            } else {
                showNotification('error', res.data?.swal?.text || 'Gửi duyệt thất bại.');
            }
        } catch (_) { showNotification('error', 'Lỗi kết nối máy chủ.'); }
    };

    // ─── Admin: Process Flow ──────────────────────────────────────────────
    window.processFlow = async function(salaryId, action) {
        const actionConfig = {
            approve:  { label: 'Phê duyệt',  color: '#198754', needNote: false },
            finalize: { label: 'Chốt sổ',    color: '#0d6efd', needNote: false },
            paid:     { label: 'Thanh toán',  color: '#198754', needNote: false },
            reject:   { label: 'Từ chối',     color: '#dc3545', needNote: true  },
        };

        const cfg = actionConfig[action] || { label: action, color: '#6c757d', needNote: false };
        let note  = '';

        if (cfg.needNote) {
            const { value, isConfirmed } = await Swal.fire({
                title:            `${cfg.label} bảng lương`,
                input:            'textarea',
                inputLabel:       'Lý do (bắt buộc)',
                inputPlaceholder: `Nhập lý do ${cfg.label.toLowerCase()}...`,
                showCancelButton: true,
                confirmButtonText: 'Xác nhận',
                cancelButtonText:  'Hủy',
                confirmButtonColor: cfg.color,
                inputValidator: v => !v?.trim() ? 'Vui lòng nhập lý do' : null,
            });
            if (!isConfirmed) return;
            note = value;
        } else {
            const result = await Swal.fire({
                title:             `${cfg.label} bảng lương?`,
                icon:              'question',
                showCancelButton:  true,
                confirmButtonText: 'Xác nhận',
                cancelButtonText:  'Hủy',
                confirmButtonColor: cfg.color,
            });
            if (!result.isConfirmed) return;
        }

        try {
            const res = await PayrollAPI.processPayrollFlow(salaryId, action, note);
            if (res.ok) {
                showNotification(res.data?.swal?.icon || 'success', res.data?.swal?.text || `${cfg.label} thành công.`);
                loadPayrollList();
            } else {
                showNotification('error', res.data?.swal?.text || `${cfg.label} thất bại.`);
            }
        } catch (err) {
            console.error('processFlow error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    };

    // ─── Bulk Actions ─────────────────────────────────────────────────────
    window.bulkAction = async function(action) {
        const checked = Array.from(document.querySelectorAll('.row-check:checked'))
                             .map(cb => parseInt(cb.value));

        if (!checked.length) {
            showNotification('warning', 'Vui lòng chọn ít nhất một bảng lương.');
            return;
        }

        const actionLabels = { approve: 'Phê duyệt', finalize: 'Chốt sổ', paid: 'Thanh toán' };
        const label = actionLabels[action] || action;

        const confirm = await Swal.fire({
            title:             `${label} ${checked.length} bảng lương?`,
            icon:              'warning',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận',
            cancelButtonText:  'Hủy',
        });
        if (!confirm.isConfirmed) return;

        let success = 0, failed = 0;
        for (const id of checked) {
            try {
                const res = await PayrollAPI.processPayrollFlow(id, action);
                if (res.ok) success++; else failed++;
            } catch { failed++; }
        }

        showNotification(
            failed ? 'warning' : 'success',
            `Đã xử lý ${success}/${checked.length}. Lỗi: ${failed}.`
        );
        loadPayrollList();
    };

    // Nút "Thông báo NV kiểm tra" → bulk notify_review cho draft
    async function _bulkNotifyReview() {
        const drafts = allItems.filter(i => i.status === 'draft').map(i => i.id);
        if (!drafts.length) {
            showNotification('warning', 'Không có bảng lương Draft nào để thông báo.');
            return;
        }

        const confirm = await Swal.fire({
            title:             `Gửi thông báo cho ${drafts.length} nhân viên?`,
            text:              'Hệ thống sẽ gửi thông báo yêu cầu nhân viên kiểm tra phiếu lương.',
            icon:              'info',
            showCancelButton:  true,
            confirmButtonText: 'Gửi thông báo',
            cancelButtonText:  'Hủy',
        });
        if (!confirm.isConfirmed) return;

        let success = 0, failed = 0;
        for (const id of drafts) {
            try {
                const res = await PayrollAPI.processPayrollFlow(id, 'notify_review');
                if (res.ok) success++; else failed++;
            } catch { failed++; }
        }
        showNotification(failed ? 'warning' : 'success', `Đã gửi thông báo ${success}/${drafts.length}.`);
    }

    // ─── Helpers ──────────────────────────────────────────────────────────

    /** Parse "YYYY-MM" → [year(int), month(int)] */
    function _parseMonthInput(val) {
        if (!val) return [null, null];
        const parts = val.split('-');
        if (parts.length !== 2) return [null, null];
        return [parseInt(parts[0], 10), parseInt(parts[1], 10)];
    }

    function _setLoading(state) {
        if (tableBody) tableBody.style.opacity = state ? '0.4' : '1';
        if (btnLoad)   { btnLoad.disabled = state; btnLoad.innerHTML = state ? '<i class="fas fa-spinner fa-spin me-1"></i>Đang tải...' : '<i class="fas fa-search me-1"></i>Tìm kiếm'; }
    }

    function _fmt(val) {
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0);
    }

    function _statusClass(status) {
        const m = {
            draft:     'bg-secondary',
            pending:   'bg-warning text-dark',
            approved:  'bg-info',
            locked:    'bg-primary',
            paid:      'bg-success',
            rejected:  'bg-danger',
            complaint: 'bg-danger',
            sent:      'bg-info',
        };
        return m[status] || 'bg-secondary';
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

});