/**
 * contract_create.js
 * Logic cho trang tạo hợp đồng mới (create.html) – Admin only
 * Đặt tại: app/static/js/modules/contract/contract_create.js
 *
 * Phụ thuộc: contract_api.js, main.js (showNotification)
 */

(function () {
    'use strict';

    // ── DOM refs ───────────────────────────────────────────────────────
    const empIdInput      = document.getElementById('empIdInput');
    const btnLookup       = document.getElementById('btnLookup');
    const empPreview      = document.getElementById('empPreview');
    const previewInitial  = document.getElementById('previewInitial');
    const previewName     = document.getElementById('previewName');
    const previewDetail   = document.getElementById('previewDetail');
    const selectedEmpId   = document.getElementById('selectedEmpId');

    const durationOptions = document.querySelectorAll('.duration-option');
    const selectedDuration = document.getElementById('selectedDuration');

    const contractTypeEl  = document.getElementById('contractType');
    const basicSalaryEl   = document.getElementById('basicSalary');
    const contractNoteEl  = document.getElementById('contractNote');
    const btnSubmit       = document.getElementById('btnSubmit');

    // Preview sidebar elements
    const pvName     = document.getElementById('pvName');
    const pvDuration = document.getElementById('pvDuration');
    const pvType     = document.getElementById('pvType');
    const pvSalary   = document.getElementById('pvSalary');

    // Step bars
    const step1bar = document.getElementById('step1bar');
    const step2bar = document.getElementById('step2bar');
    const step3bar = document.getElementById('step3bar');

    // ── Duration label map ─────────────────────────────────────────────
    const DURATION_LABELS = {
        '2m': '2 tháng', '6m': '6 tháng', '12m': '1 năm',
        '24m': '2 năm',  '36m': '3 năm',  'permanent': 'Vô thời hạn',
    };
    const TYPE_LABELS = {
        probation: 'Thử việc', official: 'Chính thức', part_time: 'Bán thời gian',
    };

    // ── Step bar helper ────────────────────────────────────────────────
    function updateStepBars() {
        const hasEmp = !!selectedEmpId.value;
        const hasDur = !!selectedDuration.value;

        step1bar.className = `step-bar ${hasEmp ? 'done' : 'active'}`;
        step2bar.className = `step-bar ${hasDur ? 'done' : (hasEmp ? 'active' : '')}`;
        step3bar.className = `step-bar ${(hasEmp && hasDur) ? 'active' : ''}`;
    }

    // ── Employee lookup ────────────────────────────────────────────────
    async function lookupEmployee() {
        const empId = empIdInput.value.trim();
        if (!empId) {
            showNotification('warning', 'Vui lòng nhập ID nhân viên');
            return;
        }

        btnLookup.disabled = true;
        btnLookup.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            // Dùng API admin lấy hợp đồng theo employee_id để lấy tên
            const json = await ContractAPI.adminGetContracts({ employee_id: parseInt(empId), per_page: 1 });

            let name, detail;
            if (json.success && json.data.contracts.length > 0) {
                name   = json.data.contracts[0].employee_name || `Nhân viên #${empId}`;
                detail = 'Đã có hợp đồng trong hệ thống';
            } else {
                name   = `Nhân viên #${empId}`;
                detail = 'Nhân viên mới – chưa có hợp đồng';
            }

            showEmployeePreview(empId, name, detail);
        } catch (e) {
            // Vẫn cho phép chọn dù không tra được tên
            showEmployeePreview(empId, `Nhân viên #${empId}`, 'Không thể tải thông tin – kiểm tra lại ID');
        } finally {
            btnLookup.disabled = false;
            btnLookup.innerHTML = '<i class="fas fa-search me-1"></i> Tra cứu';
        }
    }

    function showEmployeePreview(id, name, detail) {
        selectedEmpId.value          = id;
        previewInitial.textContent   = name.charAt(0).toUpperCase();
        previewName.textContent      = name;
        previewDetail.textContent    = detail;
        pvName.textContent           = name;
        empPreview.classList.add('show');
        updateStepBars();
    }

    // ── Duration options ───────────────────────────────────────────────
    function initDurationOptions() {
        durationOptions.forEach(opt => {
            opt.addEventListener('click', () => {
                durationOptions.forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
                const val = opt.dataset.value;
                selectedDuration.value  = val;
                pvDuration.textContent  = DURATION_LABELS[val] || val;
                updateStepBars();
            });
        });
    }

    // ── Live preview updates ───────────────────────────────────────────
    function initPreviewUpdates() {
        contractTypeEl.addEventListener('change', function () {
            pvType.textContent = TYPE_LABELS[this.value] || this.value;
        });

        basicSalaryEl.addEventListener('input', function () {
            const v = parseInt(this.value);
            pvSalary.textContent = v ? v.toLocaleString('vi-VN') + ' ₫' : 'Tự động';
        });
    }

    // ── Submit ─────────────────────────────────────────────────────────
    async function handleSubmit() {
        const empId    = selectedEmpId.value;
        const duration = selectedDuration.value;

        if (!empId) {
            showNotification('warning', 'Vui lòng tra cứu và chọn nhân viên');
            return;
        }
        if (!duration) {
            showNotification('warning', 'Vui lòng chọn thời hạn hợp đồng');
            return;
        }

        const body = {
            employee_id:   parseInt(empId),
            duration,
            contract_type: contractTypeEl.value,
            note:          contractNoteEl.value,
        };
        const salary = basicSalaryEl.value;
        if (salary) body.basic_salary = parseFloat(salary);

        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';

        try {
            const json = await ContractAPI.adminCreateContract(body);

            if (json.success) {
                await Swal.fire({
                    icon: 'success',
                    title: json.swal?.title || 'Tạo hợp đồng thành công!',
                    text:  json.swal?.text  || `Mã hợp đồng: ${json.data?.contract_code || ''}`,
                    confirmButtonText: 'Xem danh sách',
                });
                window.location.href = '/contract/list';
            } else {
                showNotification('error', json.swal?.text || 'Tạo thất bại. Vui lòng kiểm tra lại.');
                resetSubmitBtn();
            }
        } catch (e) {
            showNotification('error', 'Lỗi kết nối máy chủ');
            resetSubmitBtn();
        }
    }

    function resetSubmitBtn() {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = '<i class="fas fa-save me-1"></i>Tạo hợp đồng';
    }

    // ── Init ───────────────────────────────────────────────────────────
    function init() {
        btnLookup.addEventListener('click', lookupEmployee);
        empIdInput.addEventListener('keydown', e => { if (e.key === 'Enter') lookupEmployee(); });
        btnSubmit.addEventListener('click', handleSubmit);

        initDurationOptions();
        initPreviewUpdates();
        updateStepBars();
    }

    document.addEventListener('DOMContentLoaded', init);
})();