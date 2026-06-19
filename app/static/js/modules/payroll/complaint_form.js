/**
 * COMPLAINT FORM PAGE
 * POST /payroll/complaints
 * Cho phép nhân viên gửi khiếu nại lương, xem danh sách khiếu nại, đóng khiếu nại.
 *
 * Đã sửa đồng bộ với complaint_form.html:
 *  - complaintSubmitForm  → newComplaintForm
 *  - salarySelect         → selectSalary
 *  - issueTypeSelect      → select[name="issue_type"] (không có id riêng)
 *  - descInput            → textarea[name="description"] (không có id riêng)
 *  - attachInput          → fileInput
 *  - attachPreview        → filePreview
 *  - submitBtn            → btnSubmit
 *  - listContainer        → complaintListBody (tbody trong table)
 *  - listLoader / emptyComplaints → xử lý inline trong tbody
 *  - complaintDescription → không tồn tại, dùng querySelector
 *  - complaintsListContainer → không tồn tại, dùng #complaintListBody
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── DOM refs (đồng bộ với complaint_form.html) ───────────────────────
    const complaintForm   = document.getElementById('newComplaintForm');
    const salarySelect    = document.getElementById('selectSalary');
    const issueTypeSelect = complaintForm?.querySelector('select[name="issue_type"]');
    const descInput       = complaintForm?.querySelector('textarea[name="description"]');
    const charCount       = document.getElementById('charCount');
    const attachInput     = document.getElementById('fileInput');
    const attachPreview   = document.getElementById('filePreview');
    const submitBtn       = document.getElementById('btnSubmit');
    const listBody        = document.getElementById('complaintListBody');   // <tbody>

    // Modal chi tiết
    const detailModal     = document.getElementById('complaintDetailModal');
    const detailBody      = document.getElementById('complaintDetailBody');
    const btnCloseInModal = document.getElementById('btnCloseComplaint');

    // Dropzone
    const dropzone        = document.getElementById('dropzone');

    // ─── Init ─────────────────────────────────────────────────────────────
    _loadSalaryOptions();
    _loadComplaintsList();

    // Preselect salary từ URL query ?salary_id=xxx
    const urlParams = new URLSearchParams(window.location.search);
    const preselect = urlParams.get('salary_id');
    if (preselect && salarySelect) {
        setTimeout(() => { salarySelect.value = preselect; }, 300);
    }

    // ─── Events ───────────────────────────────────────────────────────────
    descInput?.addEventListener('input', () => {
        const len = descInput.value.length;
        if (charCount) charCount.textContent = len;
        if (len < 20) descInput.classList.add('is-invalid');
        else          descInput.classList.remove('is-invalid');
    });

    attachInput?.addEventListener('change', _previewAttachments);

    // Dropzone click → trigger file input
    dropzone?.addEventListener('click', () => attachInput?.click());
    dropzone?.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('border-primary'); });
    dropzone?.addEventListener('dragleave', () => dropzone.classList.remove('border-primary'));
    dropzone?.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.classList.remove('border-primary');
        if (attachInput && e.dataTransfer.files.length) {
            attachInput.files = e.dataTransfer.files;
            _previewAttachments();
        }
    });

    complaintForm?.addEventListener('submit', handleSubmit);

    // ─── Load salary options ──────────────────────────────────────────────
    async function _loadSalaryOptions() {
        if (!salarySelect) return;
        try {
            const year = new Date().getFullYear();
            const res  = await PayrollAPI.getMyPayrollHistory(year);
            if (!res.ok) return;

            const items    = res.data?.data?.items || [];
            const eligible = items.filter(i =>
                ['sent', 'pending', 'approved', 'locked'].includes(i.status)
            );

            salarySelect.innerHTML = '<option value="">-- Chọn kỳ lương --</option>';
            eligible.forEach(item => {
                const opt = document.createElement('option');
                opt.value       = item.id;
                opt.textContent = `Tháng ${String(item.month).padStart(2,'0')}/${item.year} — ${_fmt(item.net_salary)}`;
                salarySelect.appendChild(opt);
            });

            if (!eligible.length) {
                salarySelect.innerHTML = '<option value="">Không có kỳ lương nào có thể khiếu nại</option>';
                if (submitBtn) submitBtn.disabled = true;
            }
        } catch (err) {
            console.error('_loadSalaryOptions error:', err);
        }
    }

    // ─── Load complaints list → render vào <tbody id="complaintListBody"> ─
    async function _loadComplaintsList() {
        if (!listBody) return;

        listBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-3 text-muted">
                    <i class="fas fa-spinner fa-spin me-2"></i>Đang tải...
                </td>
            </tr>`;

        try {
            const res = await PayrollAPI.getMyComplaints();
            if (!res.ok) {
                listBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Không tải được dữ liệu.</td></tr>`;
                return;
            }

            const complaints = res.data?.data || [];

            if (!complaints.length) {
                listBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="text-center py-4 text-muted">
                            <i class="fas fa-inbox fa-2x mb-2 d-block opacity-25"></i>
                            Bạn chưa có đơn khiếu nại nào.
                        </td>
                    </tr>`;
                return;
            }

            listBody.innerHTML = complaints.map(c => _renderComplaintRow(c)).join('');

            // Gắn sự kiện nút đóng trong bảng
            listBody.querySelectorAll('[data-close-complaint]').forEach(btn => {
                btn.addEventListener('click', () => handleCloseComplaint(btn.dataset.closeComplaint));
            });

            // Gắn sự kiện xem chi tiết
            listBody.querySelectorAll('[data-view-complaint]').forEach(btn => {
                btn.addEventListener('click', () => handleViewComplaint(btn.dataset.viewComplaint));
            });

        } catch (err) {
            console.error('_loadComplaintsList error:', err);
            listBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-3">Lỗi tải danh sách.</td></tr>`;
        }
    }

    // Render từng hàng vào <tbody> (thay vì card div như cũ)
    function _renderComplaintRow(c) {
        const statusMap = {
            pending:     ['warning',   'Chờ xử lý'],
            in_progress: ['info',      'Đang xử lý'],
            resolved:    ['success',   'Đã giải quyết'],
            rejected:    ['danger',    'Bị từ chối'],
        };
        const [color, label] = statusMap[c.status] || ['secondary', c.status_label || c.status];

        return `
        <tr>
            <td><small class="text-muted">#${c.id}</small></td>
            <td><small>${_escHtml(c.salary_period || '')}</small></td>
            <td>${_escHtml(c.title || '')}</td>
            <td><span class="badge bg-${color}">${label}</span></td>
            <td><small>${_escHtml(c.created_at || '')}</small></td>
            <td>
                <div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-secondary py-0 px-1"
                        data-view-complaint="${c.id}" title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${c.status === 'pending' && !c.closed
                        ? `<button class="btn btn-sm btn-outline-danger py-0 px-1"
                               data-close-complaint="${c.id}" title="Đóng khiếu nại">
                               <i class="fas fa-times"></i>
                           </button>`
                        : ''
                    }
                </div>
            </td>
        </tr>`;
    }

    // ─── Submit Complaint ─────────────────────────────────────────────────
    async function handleSubmit(e) {
        e.preventDefault();
        if (!_validateForm()) return;

        const formData = new FormData(complaintForm);

        if (submitBtn) {
            submitBtn.disabled  = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang gửi...';
        }

        try {
            const res = await PayrollAPI.submitComplaint(formData);

            if (res.ok || res.data?.success) {
                await Swal.fire({
                    icon:  'success',
                    title: 'Gửi khiếu nại thành công!',
                    text:  res.data?.text || 'Khiếu nại của bạn đã được gửi đến quản lý.',
                    confirmButtonText: 'OK',
                });
                complaintForm.reset();
                if (attachPreview) attachPreview.innerHTML = '';
                if (charCount)     charCount.textContent = '0';
                _loadComplaintsList();
            } else {
                showNotification('error', res.data?.text || 'Gửi khiếu nại thất bại.');
            }

        } catch (err) {
            console.error('handleSubmit error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        } finally {
            if (submitBtn) {
                submitBtn.disabled  = false;
                submitBtn.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Gửi khiếu nại';
            }
        }
    }

    function _validateForm() {
        let valid = true;

        if (!salarySelect?.value) {
            salarySelect?.classList.add('is-invalid');
            valid = false;
        } else {
            salarySelect?.classList.remove('is-invalid');
        }

        if (!issueTypeSelect?.value) {
            issueTypeSelect?.classList.add('is-invalid');
            valid = false;
        } else {
            issueTypeSelect?.classList.remove('is-invalid');
        }

        const desc = descInput?.value?.trim() || '';
        if (desc.length < 20) {
            descInput?.classList.add('is-invalid');
            valid = false;
        } else {
            descInput?.classList.remove('is-invalid');
        }

        return valid;
    }

    // ─── View Complaint Detail (modal) ────────────────────────────────────
    async function handleViewComplaint(complaintId) {
        if (!detailModal || !detailBody) return;

        detailBody.innerHTML = `<div class="text-center py-4"><i class="fas fa-spinner fa-spin"></i></div>`;
        if (btnCloseInModal) btnCloseInModal.classList.add('d-none');

        const modal = new bootstrap.Modal(detailModal);
        modal.show();

        try {
            const res = await PayrollAPI.getComplaintDetail?.(complaintId);
            if (!res?.ok) {
                detailBody.innerHTML = `<div class="alert alert-danger">Không tải được chi tiết.</div>`;
                return;
            }
            const c = res.data?.data || {};
            detailBody.innerHTML = _renderComplaintDetail(c);

            if (c.status === 'pending' && !c.closed && btnCloseInModal) {
                btnCloseInModal.classList.remove('d-none');
                btnCloseInModal.onclick = () => {
                    modal.hide();
                    handleCloseComplaint(complaintId);
                };
            }
        } catch (err) {
            detailBody.innerHTML = `<div class="alert alert-danger">Lỗi tải chi tiết.</div>`;
        }
    }

    function _renderComplaintDetail(c) {
        return `
        <dl class="row mb-0">
            <dt class="col-sm-4">Kỳ lương</dt>
            <dd class="col-sm-8">${_escHtml(c.salary_period || '--')}</dd>
            <dt class="col-sm-4">Loại vấn đề</dt>
            <dd class="col-sm-8">${_escHtml(c.issue_type_label || c.issue_type || '--')}</dd>
            <dt class="col-sm-4">Nội dung</dt>
            <dd class="col-sm-8">${_escHtml(c.description || '--')}</dd>
            <dt class="col-sm-4">Ngày gửi</dt>
            <dd class="col-sm-8">${_escHtml(c.created_at || '--')}</dd>
            ${c.resolved_note ? `<dt class="col-sm-4">Phản hồi</dt><dd class="col-sm-8">${_escHtml(c.resolved_note)}</dd>` : ''}
        </dl>`;
    }

    // ─── Close Complaint ──────────────────────────────────────────────────
    async function handleCloseComplaint(complaintId) {
        const result = await Swal.fire({
            title:             'Đóng khiếu nại?',
            text:              'Hành động này không thể hoàn tác. Khiếu nại sẽ bị đóng và phiếu lương mở khóa.',
            icon:              'warning',
            showCancelButton:  true,
            confirmButtonText: 'Xác nhận đóng',
            cancelButtonText:  'Hủy',
            confirmButtonColor: '#d33',
        });

        if (!result.isConfirmed) return;

        try {
            const res = await PayrollAPI.closeComplaint(complaintId);
            if (res.ok) {
                showNotification('success', 'Đã đóng khiếu nại thành công.');
                _loadComplaintsList();
            } else {
                showNotification('error', res.data?.text || 'Không thể đóng khiếu nại.');
            }
        } catch (err) {
            console.error('handleCloseComplaint error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    }

    // ─── Attachment Preview ───────────────────────────────────────────────
    function _previewAttachments() {
        if (!attachPreview || !attachInput?.files) return;
        const files = Array.from(attachInput.files);
        if (!files.length) { attachPreview.innerHTML = ''; return; }

        attachPreview.innerHTML = files.map(f => `
            <span class="badge bg-light text-dark border me-1 mb-1">
                <i class="fas fa-paperclip me-1"></i>${_escHtml(f.name)}
                <small class="text-muted">(${(f.size / 1024).toFixed(1)} KB)</small>
            </span>
        `).join('');
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _fmt(val) {
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val || 0);
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

});