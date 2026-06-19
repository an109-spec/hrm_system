/**
 * SALARY SLIP (PAYSLIP) PAGE
 * Route: GET /payroll/payslip/<salary_id>
 * Hiển thị chi tiết phiếu lương, in PDF, gửi khiếu nại.
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── Lấy salary_id từ URL ─────────────────────────────────────────────
    const pathParts = window.location.pathname.split('/');
    const SALARY_ID = parseInt(pathParts[pathParts.length - 1]) || null;

    if (!SALARY_ID) {
        _showError('Không xác định được phiếu lương. Vui lòng quay lại trang lịch sử lương.');
        return;
    }

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const loader         = document.getElementById('slipLoader');
    const slipContainer  = document.getElementById('slipContainer');
    const printBtn       = document.getElementById('printBtn');
    const complaintBtn   = document.getElementById('openComplaintBtn');
    const closeBtn       = document.getElementById('closeComplaintBtn');
    const complaintModal = document.getElementById('complaintModal') 
                            ? new bootstrap.Modal('#complaintModal') 
                            : null;

    // ─── Init ─────────────────────────────────────────────────────────────
    loadPayslip();

    // ─── Events ───────────────────────────────────────────────────────────
    printBtn?.addEventListener('click', () => window.print());

    closeBtn?.addEventListener('click', handleCloseComplaint);

    document.getElementById('complaintForm')?.addEventListener('submit', handleSubmitComplaint);

    // ─── Load Data ────────────────────────────────────────────────────────
    async function loadPayslip() {
        _setLoading(true);

        try {
            const res = await PayrollAPI.getPayslipDetail(SALARY_ID);

            if (!res.ok) {
                _showError(res.data?.swal?.text || 'Không thể tải phiếu lương.');
                return;
            }

            const slip = res.data?.data || {};
            _renderSlip(slip);
            _setupComplaintUI(slip);

        } catch (err) {
            console.error('loadPayslip error:', err);
            _showError('Lỗi kết nối máy chủ.');
        } finally {
            _setLoading(false);
        }
    }

    function _renderSlip(d) {
        // Header
        _setText('empName',       d.employee_name);
        _setText('slipPeriod',    `Tháng ${String(d.month).padStart(2,'0')}/${d.year}`);
        _setText('slipStatus',    d.status_label);
        _setClass('slipStatusBadge', `badge ${_statusClass(d.status)}`);

        // Thu nhập
        _setText('basicSalary',          _fmt(d.basic_salary));
        _setText('standardWorkDays',     d.standard_work_days ?? '--');
        _setText('totalWorkDays',        d.total_work_days ?? '--');
        _setText('lunchAllowance',       _fmt(d.lunch_allowance));
        _setText('responsibilityAllow',  _fmt(d.responsibility_allowance));
        _setText('totalAllowance',       _fmt(d.total_allowance));
        _setText('bonus',                _fmt(d.bonus));
        _setText('overtimeSalary',       _fmt(d.overtime));

        // Khấu trừ
        _setText('deduction',   _fmt(d.deduction));
        _setText('insurance',   _fmt(d.insurance));
        _setText('tax',         _fmt(d.tax));

        // Giảm trừ gia cảnh
        _setText('numDependents',  d.number_of_dependents ?? 0);
        _setText('familyDeduct',   _fmt(d.family_deduction));

        // Thực lĩnh
        _setText('netSalary', _fmt(d.net_salary));

        // Ghi chú
        if (d.note) {
            _setText('slipNote', d.note);
            document.getElementById('noteRow')?.classList.remove('d-none');
        }

        // Trạng thái khiếu nại
        if (d.has_complaint) {
            const complaintInfo = document.getElementById('existingComplaint');
            if (complaintInfo) {
                complaintInfo.classList.remove('d-none');
                _setText('complaintStatusLabel', d.complaint_status_label);
                if (d.complaint_title) _setText('complaintTitle', d.complaint_title);
            }
        }

        slipContainer?.classList.remove('d-none');
    }

    function _setupComplaintUI(slip) {
        // Nếu không thể khiếu nại (đã có khiếu nại đang pending, hoặc đã paid + locked)
        const canComplain = !slip.has_complaint && 
                            ['sent', 'pending', 'approved', 'locked'].includes(slip.status);

        if (complaintBtn) {
            complaintBtn.style.display = canComplain ? '' : 'none';
        }

        // Nút đóng khiếu nại (chỉ hiển thị nếu có khiếu nại đang pending)
        if (closeBtn) {
            closeBtn.style.display = (slip.has_complaint && slip.complaint_status === 'pending') 
                ? '' : 'none';
        }

        // Lưu salary_id vào form khiếu nại
        const salaryIdInput = document.getElementById('complaintSalaryId');
        if (salaryIdInput) salaryIdInput.value = SALARY_ID;
    }

    // ─── Complaint Handlers ───────────────────────────────────────────────
    async function handleSubmitComplaint(e) {
        e.preventDefault();
        const form     = e.target;
        const formData = new FormData(form);

        const submitBtn  = form.querySelector('[type="submit"]');
        const origText   = submitBtn?.textContent;
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Đang gửi...'; }

        try {
            const res = await PayrollAPI.submitComplaint(formData);

            if (res.ok) {
                complaintModal?.hide();
                showNotification('success', res.data?.text || 'Gửi khiếu nại thành công!');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                showNotification('error', res.data?.text || 'Gửi khiếu nại thất bại.');
            }
        } catch (err) {
            console.error('submitComplaint error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        } finally {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText; }
        }
    }

    async function handleCloseComplaint() {
        const confirmed = await Swal.fire({
            title: 'Đóng khiếu nại?',
            text: 'Bạn có chắc muốn đóng khiếu nại này không?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Xác nhận đóng',
            cancelButtonText: 'Hủy',
            confirmButtonColor: '#d33',
        });

        if (!confirmed.isConfirmed) return;

        // Lấy complaint_id từ data attribute
        const complaintId = closeBtn?.dataset.complaintId;
        if (!complaintId) {
            showNotification('error', 'Không xác định được ID khiếu nại.');
            return;
        }

        try {
            const res = await PayrollAPI.closeComplaint(complaintId);

            if (res.ok) {
                showNotification('success', res.data?.text || 'Đã đóng khiếu nại thành công.');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                showNotification('error', res.data?.text || 'Không thể đóng khiếu nại.');
            }
        } catch (err) {
            console.error('closeComplaint error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        }
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _setLoading(state) {
        loader?.classList.toggle('d-none', !state);
        if (!state) return;
        slipContainer?.classList.add('d-none');
    }

    function _showError(msg) {
        loader?.classList.add('d-none');
        const err = document.getElementById('errorState');
        if (err) {
            err.classList.remove('d-none');
            const errMsg = err.querySelector('.error-message');
            if (errMsg) errMsg.textContent = msg;
        }
    }

    function _setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val ?? '--';
    }

    function _setClass(id, cls) {
        const el = document.getElementById(id);
        if (el) el.className = cls;
    }

    function _fmt(val) {
        if (val == null || val === 0) return '0 đ';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
    }

    function _statusClass(status) {
        const map = {
            draft: 'bg-secondary', pending: 'bg-warning text-dark',
            approved: 'bg-info', locked: 'bg-primary',
            paid: 'bg-success', rejected: 'bg-danger', complaint: 'bg-danger',
        };
        return map[status] || 'bg-secondary';
    }

});