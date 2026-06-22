/**
 * HR GENERATE PAYROLL
 * Chức năng: Tính lương hàng loạt + xem danh sách bảng lương.
 * Trang: hr_generate.html
 * API sử dụng: calculatePayroll, getPayrollList, submitPayrollApproval,
 *              getDepartments, getPolicy (chỉ đọc trạng thái)
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const monthInput      = document.getElementById('payrollMonth');
    const deptSelect      = document.getElementById('departmentSelect');
    const generateBtn     = document.getElementById('btnGenerate');
    const confirmCheck    = document.getElementById('confirmCheck');

    // Progress
    const progressSection = document.getElementById('progressSection');
    const progressBar     = document.getElementById('progressBar');
    const progressText    = document.getElementById('progressText');

    // Result summary
    const resultSummary   = document.getElementById('resultSummary');
    const resProcessed    = document.getElementById('resProcessed');
    const resFailed       = document.getElementById('resFailed');
    const resTotal        = document.getElementById('resTotal');

    // Error section
    const errorSection    = document.getElementById('errorSection');
    const errorList       = document.getElementById('errorList');
    const initState       = document.getElementById('initState');

    // Payroll list
    const btnLoadList     = document.getElementById('btnLoadList');
    const listStatusFilter = document.getElementById('listStatusFilter');
    const payrollListBody  = document.getElementById('payrollListBody');

    // Policy status (read-only)
    const lockStatusBadge = document.getElementById('lockStatusBadge');
    const policyInfo      = document.getElementById('policyInfo');

    // ─── Init ─────────────────────────────────────────────────────────────
    const now = new Date();
    if (monthInput) {
        const yyyy = now.getFullYear();
        const mm   = String(now.getMonth() + 1).padStart(2, '0');
        monthInput.value = `${yyyy}-${mm}`;
    }

    _loadDepartments();
    _loadPolicyStatus();
    _loadPayrollList();

    // ─── Enable/Disable nút Chạy tính lương ──────────────────────────────
    function _updateGenerateBtn() {
        const hasMonth  = monthInput && monthInput.value;
        const isChecked = confirmCheck && confirmCheck.checked;
        if (generateBtn) generateBtn.disabled = !(hasMonth && isChecked);
    }

    monthInput?.addEventListener('change', _updateGenerateBtn);
    confirmCheck?.addEventListener('change', _updateGenerateBtn);
    _updateGenerateBtn();

    // ─── Chạy tính lương ──────────────────────────────────────────────────
    generateBtn?.addEventListener('click', handleGenerate);

    async function handleGenerate() {
        const [year, month] = _parseMonthInput(monthInput?.value);
        const deptId = deptSelect?.value ? parseInt(deptSelect.value) : null;

        if (!month || !year) {
            showNotification('warning', 'Vui lòng chọn tháng tính lương.');
            return;
        }

        const confirmed = await Swal.fire({
            title:   `Tính lương tháng ${String(month).padStart(2,'0')}/${year}?`,
            text:    deptId
                ? 'Sẽ tính lương cho nhân viên thuộc phòng ban đã chọn.'
                : 'Sẽ tính lương cho toàn bộ nhân viên. Hệ thống bỏ qua nhân viên đã có bản ghi trong tháng này.',
            icon:    'warning',
            showCancelButton:   true,
            confirmButtonText:  'Xác nhận tính lương',
            cancelButtonText:   'Hủy',
            confirmButtonColor: '#198754',
        });

        if (!confirmed.isConfirmed) return;

        _setGenerating(true);
        _resetResultUI();

        try {
            const res  = await PayrollAPI.calculatePayroll(month, year, deptId);
            const data = res.data?.data || {};
            _renderResult(data, res.data?.swal);
            _loadPayrollList();
        } catch (err) {
            console.error('handleGenerate error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ khi tính lương.');
        } finally {
            _setGenerating(false);
        }
    }

    // ─── Load phòng ban ───────────────────────────────────────────────────
    async function _loadDepartments() {
        try {
            const res   = await PayrollAPI.getDepartments?.();
            if (!res?.ok || !deptSelect) return;
            const depts = res.data?.data || [];
            depts.forEach(d => {
                const opt       = document.createElement('option');
                opt.value       = d.id;
                opt.textContent = d.name;
                deptSelect.appendChild(opt);
            });
        } catch (_) { /* không bắt buộc */ }
    }

    // ─── Load trạng thái chính sách (chỉ đọc) ────────────────────────────
    async function _loadPolicyStatus() {
        try {
            const res = await PayrollAPI.getPolicy?.();
            if (!res?.ok) {
                if (lockStatusBadge) {
                    lockStatusBadge.textContent = 'Không tải được';
                    lockStatusBadge.className   = 'badge bg-danger ms-2 float-end';
                }
                return;
            }
            const policy = res.data?.data || {};
            _renderPolicyReadOnly(policy);
        } catch (_) {
            if (lockStatusBadge) {
                lockStatusBadge.textContent = 'Lỗi';
                lockStatusBadge.className   = 'badge bg-danger ms-2 float-end';
            }
        }
    }

    function _renderPolicyReadOnly(policy) {
        if (!policyInfo) return;
        const isLocked = policy.is_locked;

        if (lockStatusBadge) {
            lockStatusBadge.textContent = isLocked ? 'Đã khóa' : 'Đang mở';
            lockStatusBadge.className   = `badge ${isLocked ? 'bg-danger' : 'bg-success'} ms-2 float-end`;
        }

        policyInfo.innerHTML = `
            <div class="col-6">
                <div class="small text-muted">Lương cơ bản tối thiểu</div>
                <div class="fw-semibold">${_fmt(policy.base_salary_min)}</div>
            </div>
            <div class="col-6">
                <div class="small text-muted">Trạng thái</div>
                <div class="fw-semibold ${isLocked ? 'text-danger' : 'text-success'}">
                    <i class="fas fa-${isLocked ? 'lock' : 'lock-open'} me-1"></i>
                    ${isLocked ? 'Đã khóa' : 'Đang mở'}
                </div>
            </div>
            ${policy.note ? `<div class="col-12"><small class="text-muted">${_escHtml(policy.note)}</small></div>` : ''}
        `;
    }

    // ─── Load danh sách bảng lương ────────────────────────────────────────
    async function _loadPayrollList() {
        const [year, month] = _parseMonthInput(monthInput?.value);
        const status = listStatusFilter?.value || '';

        if (!payrollListBody) return;
        payrollListBody.innerHTML = `<tr><td colspan="6" class="text-center py-3"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>`;

        try {
            const filters = {};
            if (month && year) { filters.month = month; filters.year = year; }
            if (status) filters.status = status;

            const res   = await PayrollAPI.getPayrollList(filters);
            const items = res.data?.data?.items || [];
            _renderPayrollList(items);
        } catch (_) {
            payrollListBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Lỗi tải danh sách</td></tr>`;
        }
    }

    function _renderPayrollList(items) {
        if (!payrollListBody) return;
        if (!items.length) {
            payrollListBody.innerHTML = `<tr><td colspan="6" class="text-center py-3 text-muted">Chưa có dữ liệu</td></tr>`;
            return;
        }
        payrollListBody.innerHTML = items.map(item => `
            <tr>
                <td><small>${_escHtml(item.employee_code || '')}</small></td>
                <td>${_escHtml(item.employee_name || item.full_name || '')}</td>
                <td><small>${_escHtml(item.department || '')}</small></td>
                <td class="text-end fw-semibold text-primary">${_fmt(item.net_salary)}</td>
                <td><span class="badge ${_statusClass(item.status)}">${_escHtml(item.status_label || item.status || '')}</span></td>
                <td>
                    ${item.status === 'draft'
                        ? `<button class="btn btn-xs btn-outline-primary py-0 px-1" onclick="submitForApproval(${item.id})">
                               <i class="fas fa-paper-plane"></i>
                           </button>`
                        : '—'}
                </td>
            </tr>
        `).join('');
    }

    btnLoadList?.addEventListener('click', _loadPayrollList);
    listStatusFilter?.addEventListener('change', _loadPayrollList);
    monthInput?.addEventListener('change', _loadPayrollList);

    // ─── Gửi duyệt ────────────────────────────────────────────────────────
    window.submitForApproval = async function(salaryId) {
        try {
            const res = await PayrollAPI.submitPayrollApproval(salaryId);
            if (res.ok) {
                showNotification('success', 'Đã gửi duyệt thành công.');
                _loadPayrollList();
            } else {
                showNotification('error', res.data?.swal?.text || 'Gửi duyệt thất bại.');
            }
        } catch (_) {
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    };

    // ─── Render kết quả tính lương ────────────────────────────────────────
    function _renderResult(data, swal) {
        const processed = data.processed || 0;
        const failed    = data.failed    || 0;
        const total     = processed + failed;
        const pct       = total > 0 ? Math.round((processed / total) * 100) : 0;

        if (progressSection) progressSection.style.display = '';
        if (progressBar) {
            progressBar.style.width = `${pct}%`;
            progressBar.className   = `progress-bar progress-bar-striped ${failed > 0 ? 'bg-warning' : 'bg-success'}`;
        }
        if (progressText) progressText.textContent = `${pct}%`;

        if (resultSummary)  resultSummary.style.display  = '';
        if (resProcessed)   resProcessed.textContent     = processed;
        if (resFailed)      resFailed.textContent        = failed;
        if (resTotal)       resTotal.textContent         = total;

        if (data.errors?.length) {
            if (errorSection) errorSection.style.display = '';
            if (errorList) {
                errorList.innerHTML = data.errors.map(e => `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span><i class="fas fa-times-circle text-danger me-1"></i>
                            ${_escHtml(e.full_name || String(e.employee_id))}
                        </span>
                        <small class="text-muted">${_escHtml(e.reason || '')}</small>
                    </div>
                `).join('');
            }
        }

        if (initState) initState.style.display = 'none';

        const icon = swal?.icon || (failed > 0 ? 'warning' : 'success');
        const msg  = swal?.text || `Đã tính lương cho ${processed}/${total} nhân viên.`;
        showNotification(icon, msg);
    }

    function _resetResultUI() {
        if (progressSection) progressSection.style.display = 'none';
        if (resultSummary)   resultSummary.style.display   = 'none';
        if (errorSection)    errorSection.style.display    = 'none';
        if (initState)       initState.style.display       = '';
        if (progressBar)     progressBar.style.width       = '0%';
        if (progressText)    progressText.textContent      = '0%';
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _parseMonthInput(val) {
        if (!val) return [null, null];
        const parts = val.split('-');
        if (parts.length !== 2) return [null, null];
        return [parseInt(parts[0], 10), parseInt(parts[1], 10)];
    }

    function _setGenerating(state) {
        if (!generateBtn) return;
        generateBtn.disabled  = state;
        generateBtn.innerHTML = state
            ? '<i class="fas fa-spinner fa-spin me-2"></i>Đang tính lương...'
            : '<i class="fas fa-calculator me-2"></i>Chạy Tính Lương';
    }

    function _fmt(val) {
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0);
    }

    function _statusClass(status) {
        const m = {
            draft:    'bg-secondary',
            pending:  'bg-warning text-dark',
            approved: 'bg-info',
            locked:   'bg-primary',
            paid:     'bg-success',
            rejected: 'bg-danger',
        };
        return m[status] || 'bg-secondary';
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str ?? ''));
        return d.innerHTML;
    }

});