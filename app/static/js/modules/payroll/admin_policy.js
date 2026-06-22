/**
 * ADMIN POLICY
 * Chức năng: Xem và quản lý cấu hình chính sách lương (khóa/mở khóa).
 * Trang: admin_policy.html
 * API sử dụng: getPolicy, setEditLock
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const lockStatusBadge = document.getElementById('lockStatusBadge');
    const lockInfoBox     = document.getElementById('lockInfoBox');
    const btnLockPolicy   = document.getElementById('btnLockPolicy');
    const btnUnlockPolicy = document.getElementById('btnUnlockPolicy');

    // Policy sections
    const insuranceInfo   = document.getElementById('insuranceInfo');
    const deductionInfo   = document.getElementById('deductionInfo');
    const taxBracketBody  = document.getElementById('taxBracketBody');
    const allowanceInfo   = document.getElementById('allowanceInfo');
    const latePenaltyInfo = document.getElementById('latePenaltyInfo');

    // ─── Init ─────────────────────────────────────────────────────────────
    _loadPolicy();

    // ─── Load & render toàn bộ chính sách ────────────────────────────────
    async function _loadPolicy() {
        try {
            const res = await PayrollAPI.getPolicy?.();
            if (!res?.ok) {
                _setLockBadge(null, /* error */ true);
                showNotification('error', res?.data?.swal?.text || 'Không tải được chính sách lương.');
                return;
            }
            const policy = res.data?.data || {};
            _renderAll(policy);
        } catch (_) {
            _setLockBadge(null, true);
            showNotification('error', 'Lỗi kết nối khi tải chính sách.');
        }
    }

    function _renderAll(policy) {
        _renderLockStatus(policy);
        _renderInsurance(policy.insurance || {});
        _renderDeduction(policy.deduction || {});
        _renderTaxBrackets(policy.tax?.brackets || []);
        _renderAllowances(policy.tax_free_allowances || {});
        _renderLatePenalty(policy.late_penalty || {});
    }

    // ─── Lock status ──────────────────────────────────────────────────────
    function _renderLockStatus(policy) {
        const isLocked = policy.is_locked;
        _setLockBadge(isLocked);

        if (lockInfoBox) {
            lockInfoBox.className = `alert ${isLocked ? 'alert-danger' : 'alert-success'} mb-3`;
            lockInfoBox.innerHTML = isLocked
                ? `<i class="fas fa-lock me-2"></i><strong>Đang bị khóa.</strong>
                   Cấu hình lương hiện không thể chỉnh sửa. Nhấn "Mở Khóa" để cho phép thay đổi.`
                : `<i class="fas fa-lock-open me-2"></i><strong>Đang mở.</strong>
                   Cấu hình lương có thể được chỉnh sửa. Nhấn "Khóa" sau khi hoàn tất thiết lập.`;
        }
    }

    function _setLockBadge(isLocked, isError = false) {
        if (!lockStatusBadge) return;
        if (isError) {
            lockStatusBadge.className   = 'badge fs-6 px-3 py-2 bg-danger';
            lockStatusBadge.innerHTML   = '<i class="fas fa-times me-1"></i>Lỗi tải';
            return;
        }
        if (isLocked === null) {
            lockStatusBadge.className   = 'badge fs-6 px-3 py-2 bg-secondary';
            lockStatusBadge.innerHTML   = '<i class="fas fa-spinner fa-spin me-1"></i>Đang tải...';
            return;
        }
        lockStatusBadge.className = `badge fs-6 px-3 py-2 ${isLocked ? 'bg-danger' : 'bg-success'}`;
        lockStatusBadge.innerHTML = isLocked
            ? '<i class="fas fa-lock me-1"></i>Đã khóa'
            : '<i class="fas fa-lock-open me-1"></i>Đang mở';
    }

    // ─── Khóa / Mở khóa ──────────────────────────────────────────────────
    btnLockPolicy?.addEventListener('click', async () => {
        const confirmed = await Swal.fire({
            title:             'Khóa cấu hình lương?',
            text:              'Sau khi khóa, hệ thống sẽ không cho phép chỉnh sửa cho đến khi mở khóa.',
            icon:              'warning',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận khóa',
            cancelButtonText:  'Hủy',
            confirmButtonColor: '#dc3545',
        });
        if (!confirmed.isConfirmed) return;
        await _setLock(true);
    });

    btnUnlockPolicy?.addEventListener('click', async () => {
        const confirmed = await Swal.fire({
            title:             'Mở khóa cấu hình lương?',
            text:              'Vui lòng cẩn thận khi thực hiện thay đổi sau khi mở khóa.',
            icon:              'question',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận mở khóa',
            cancelButtonText:  'Hủy',
            confirmButtonColor: '#198754',
        });
        if (!confirmed.isConfirmed) return;
        await _setLock(false);
    });

    async function _setLock(locked) {
        try {
            const res = await PayrollAPI.setEditLock?.(locked);
            if (res?.ok) {
                showNotification('success', locked ? 'Đã khóa cấu hình lương.' : 'Đã mở khóa cấu hình lương.');
                _loadPolicy();
            } else {
                showNotification('error', res?.data?.swal?.text || 'Thao tác thất bại.');
            }
        } catch (_) {
            showNotification('error', 'Lỗi kết nối.');
        }
    }

    // ─── Render sections ──────────────────────────────────────────────────
    function _renderInsurance(ins) {
        if (!insuranceInfo) return;
        insuranceInfo.innerHTML = `
            <div class="row g-2">
                ${_policyRow('Bảo hiểm xã hội (NLĐ)', `${ins.social_percent ?? '—'}%`)}
                ${_policyRow('Bảo hiểm y tế (NLĐ)',   `${ins.health_percent ?? '—'}%`)}
                ${_policyRow('Bảo hiểm thất nghiệp',  `${ins.unemployment_percent ?? '—'}%`)}
            </div>
        `;
    }

    function _renderDeduction(ded) {
        if (!deductionInfo) return;
        deductionInfo.innerHTML = `
            <div class="row g-2">
                ${_policyRow('Giảm trừ bản thân',     _fmt(ded.personal))}
                ${_policyRow('Giảm trừ người phụ thuộc / người', _fmt(ded.dependent_per_person))}
            </div>
        `;
    }

    function _renderTaxBrackets(brackets) {
        if (!taxBracketBody) return;
        if (!brackets.length) {
            taxBracketBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">Chưa có dữ liệu bậc thuế</td></tr>`;
            return;
        }
        taxBracketBody.innerHTML = brackets.map((b, i) => `
            <tr>
                <td class="fw-semibold text-center">${i + 1}</td>
                <td class="text-end">${_fmt(b.from)}</td>
                <td class="text-end">${b.to ? _fmt(b.to) : '∞'}</td>
                <td class="text-center">
                    <span class="badge bg-primary">${b.rate_percent ?? 0}%</span>
                </td>
                <td class="text-end">${_fmt(b.quick_deduction)}</td>
            </tr>
        `).join('');
    }

    function _renderAllowances(allowances) {
        if (!allowanceInfo) return;
        const entries = Object.entries(allowances);
        if (!entries.length) {
            allowanceInfo.innerHTML = `<p class="text-muted mb-0">Chưa có phụ cấp miễn thuế.</p>`;
            return;
        }
        allowanceInfo.innerHTML = `
            <div class="row g-2">
                ${entries.map(([key, val]) => _policyRow(_formatKey(key), _fmt(val))).join('')}
            </div>
        `;
    }

    function _renderLatePenalty(penalty) {
        if (!latePenaltyInfo) return;
        latePenaltyInfo.innerHTML = `
            <div class="row g-2">
                ${_policyRow('Dưới 15 phút',    _fmt(penalty.under_15))}
                ${_policyRow('15 – 30 phút',    _fmt(penalty.from_15_to_30))}
                ${_policyRow('Trên 60 phút (nửa ngày)', _fmt(penalty.over_60_half_day))}
            </div>
        `;
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _policyRow(label, value) {
        return `
            <div class="col-7">
                <div class="small text-muted">${_escHtml(label)}</div>
            </div>
            <div class="col-5 text-end">
                <div class="fw-semibold">${value}</div>
            </div>
        `;
    }

    /** Chuyển snake_case key thành label dễ đọc */
    function _formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    function _fmt(val) {
        if (val === undefined || val === null) return '—';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str ?? ''));
        return d.innerHTML;
    }

});