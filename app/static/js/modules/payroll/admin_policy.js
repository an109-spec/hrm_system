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
    const btnEditPolicy   = document.getElementById('btnEditPolicy');
    const btnSavePolicy   = document.getElementById('btnSavePolicy');
    const policyEditForm  = document.getElementById('policyEditForm');
    const policyEditModalEl = document.getElementById('policyEditModal');
    const policyEditModal = policyEditModalEl && window.bootstrap ? new bootstrap.Modal(policyEditModalEl) : null;
    let currentPolicy = null;
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
            currentPolicy = policy;
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
        const isLocked = policy.is_locked ?? policy.config_edit_locked;
        _setLockBadge(isLocked);
        if (btnEditPolicy) btnEditPolicy.disabled = !!isLocked;
        if (btnSavePolicy) btnSavePolicy.disabled = !!isLocked;
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
    btnEditPolicy?.addEventListener('click', () => {
        if (!currentPolicy) return;
        if (currentPolicy.is_locked ?? currentPolicy.config_edit_locked) {
            showNotification('warning', 'Vui lòng mở khóa cấu hình trước khi chỉnh sửa.');
            return;
        }
        _renderEditForm(currentPolicy);
        policyEditModal?.show();
    });

    btnSavePolicy?.addEventListener('click', async () => {
        const payload = _collectEditPayload();
        if (!payload) return;
        btnSavePolicy.disabled = true;
        try {
            const res = await PayrollAPI.updatePolicy(payload);
            if (res?.ok) {
                showNotification('success', res.data?.swal?.text || 'Đã cập nhật chính sách lương.');
                policyEditModal?.hide();
                currentPolicy = res.data?.data || currentPolicy;
                _renderAll(currentPolicy);
            } else {
                showNotification('error', res?.data?.swal?.text || 'Không thể cập nhật chính sách lương.');
            }
        } catch (err) {
            console.error('updatePolicy error:', err);
            showNotification('error', 'Lỗi kết nối khi cập nhật chính sách.');
        } finally {
            btnSavePolicy.disabled = false;
        }
    });

    function _renderEditForm(policy) {
        if (!policyEditForm) return;
        const brackets = policy.tax?.brackets || [];
        policyEditForm.innerHTML = `
            ${_input('insurance.social_percent', 'BHXH NLĐ (%)', policy.insurance?.social_percent, 'number', '0.1')}
            ${_input('insurance.health_percent', 'BHYT NLĐ (%)', policy.insurance?.health_percent, 'number', '0.1')}
            ${_input('insurance.unemployment_percent', 'BHTN NLĐ (%)', policy.insurance?.unemployment_percent, 'number', '0.1')}
            ${_input('deduction.personal', 'Giảm trừ bản thân', policy.deduction?.personal)}
            ${_input('deduction.dependent_per_person', 'Giảm trừ người phụ thuộc', policy.deduction?.dependent_per_person)}
            ${_input('late_penalty.under_15', 'Phạt đi muộn dưới 15 phút', policy.late_penalty?.under_15)}
            ${_input('late_penalty.from_15_to_30', 'Phạt đi muộn 15-30 phút', policy.late_penalty?.from_15_to_30)}
            ${_input('late_penalty.from_31_to_59', 'Phạt đi muộn 31-59 phút', policy.late_penalty?.from_31_to_59)}
            ${_select('late_penalty.over_60_half_day', 'Trên 60 phút tính nửa ngày', policy.late_penalty?.over_60_half_day)}
            ${Object.entries(policy.tax_free_allowances || {}).map(([k, v]) => _input(`tax_free_allowances.${k}`, _formatKey(k), v)).join('')}
            <div class="col-12"><hr><h6 class="fw-bold mb-0">Biểu thuế TNCN</h6></div>
            ${brackets.map((b, i) => `
                <div class="col-12"><div class="border rounded p-3"><div class="fw-semibold mb-2">Bậc ${i + 1}</div><div class="row g-2">
                    ${_input(`tax.brackets.${i}.from`, 'Từ', b.from, 'number', '1', 'col-md-3')}
                    ${_input(`tax.brackets.${i}.to`, 'Đến', b.to, 'number', '1', 'col-md-3')}
                    ${_input(`tax.brackets.${i}.rate_percent`, 'Thuế suất (%)', b.rate_percent, 'number', '0.1', 'col-md-3')}
                    ${_input(`tax.brackets.${i}.quick_deduction`, 'Giảm trừ nhanh', b.quick_deduction, 'number', '1', 'col-md-3')}
                </div></div></div>`).join('')}
        `;
    }

    function _input(name, label, value, type = 'number', step = '1', col = 'col-md-4') {
        return `<div class="${col}"><label class="form-label small fw-semibold">${_escHtml(label)}</label><input class="form-control" data-policy-field="${name}" type="${type}" step="${step}" value="${value ?? ''}"></div>`;
    }

    function _select(name, label, value) {
        const selected = String(value) === 'true';
        return `<div class="col-md-4"><label class="form-label small fw-semibold">${_escHtml(label)}</label><select class="form-select" data-policy-field="${name}"><option value="true" ${selected ? 'selected' : ''}>Có</option><option value="false" ${!selected ? 'selected' : ''}>Không</option></select></div>`;
    }

    function _collectEditPayload() {
        const payload = { insurance: {}, deduction: {}, late_penalty: {}, tax_free_allowances: {}, tax: { brackets: [] } };
        policyEditForm?.querySelectorAll('[data-policy-field]').forEach(el => {
            const path = el.dataset.policyField.split('.');
            let value = el.value;
            if (value === '') value = null;
            else if (value === 'true' || value === 'false') value = value === 'true';
            else value = Number(value);
            if (path[0] === 'tax') {
                const idx = Number(path[2]);
                payload.tax.brackets[idx] ||= {};
                payload.tax.brackets[idx][path[3]] = value;
            } else {
                payload[path[0]][path[1]] = value;
            }
        });
        return payload;
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