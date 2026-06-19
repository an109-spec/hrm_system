/**
 * contract_detail.js
 * Logic cho trang chi tiết hợp đồng (detail.html)
 * Đặt tại: app/static/js/modules/contract/contract_detail.js
 *
 * Phụ thuộc: contract_api.js, main.js (showNotification, confirmAction)
 */

(function () {
    'use strict';

    // ── Lấy context từ DOM (set bởi Jinja) ────────────────────────────
    // Trang detail cần 2 thứ: role và contract_id
    // contract_id lấy từ URL path: /contract/detail/<id>
    const ROLE        = document.body.dataset.role || '';
    const CONTRACT_ID = (() => {
        const parts = window.location.pathname.split('/').filter(Boolean);
        const last  = parseInt(parts[parts.length - 1]);
        return isNaN(last) ? null : last;
    })();

    // ── DOM refs ───────────────────────────────────────────────────────
    const loadingEl  = document.getElementById('loadingState');
    const mainEl     = document.getElementById('mainContent');
    const terminateModal = document.getElementById('terminateModal');

    // ── Helpers ────────────────────────────────────────────────────────
    function formatDate(iso) {
        if (!iso) return null;
        const [y, m, d] = iso.split('T')[0].split('-');
        return `${d}/${m}/${y}`;
    }

    function setText(id, value, fallback = '–') {
        const el = document.getElementById(id);
        if (el) el.textContent = value || fallback;
    }

    // ── Render header ──────────────────────────────────────────────────
    function renderHeader(c) {
        setText('dContractCode', c.contract_code);

        const statusMap = {
            active:     ['Đang hiệu lực', 'active'],
            expiring:   ['Sắp hết hạn',   'expiring'],
            expired:    ['Đã hết hạn',     'expired'],
            terminated: ['Đã chấm dứt',   'terminated'],
        };
        const [label, cls] = statusMap[c.contract_status] || ['–', ''];
        const badge = document.getElementById('dStatusBadge');
        if (badge) { badge.textContent = label; badge.className = `header-status-badge ${cls}`; }

        // Days left indicator
        const daysEl = document.getElementById('dDaysLeft');
        if (!daysEl) return;

        if (c.days_left === null || c.days_left === undefined) {
            daysEl.innerHTML = '<i class="fas fa-infinity me-1"></i>Vô thời hạn';
            daysEl.className = 'days-left-indicator days-ok';
        } else if (c.days_left < 0) {
            daysEl.innerHTML = `<i class="fas fa-exclamation-circle me-1"></i>Quá hạn ${Math.abs(c.days_left)} ngày`;
            daysEl.className = 'days-left-indicator days-danger';
        } else if (c.days_left <= 30) {
            daysEl.innerHTML = `<i class="fas fa-clock me-1"></i>Còn ${c.days_left} ngày`;
            daysEl.className = 'days-left-indicator days-warn';
        } else {
            daysEl.innerHTML = `<i class="fas fa-calendar-check me-1"></i>Còn ${c.days_left} ngày`;
            daysEl.className = 'days-left-indicator days-ok';
        }
    }

    // ── Render thông tin nhân viên ─────────────────────────────────────
    function renderEmployee(c) {
        setText('dEmpName',    c.employee_name  || c.employee?.full_name);
        setText('dEmpCode',    c.employee_code);
        setText('dDepartment', c.department);
        setText('dPosition',   c.position);
        setText('dEmpType',    c.employment_type || c.employee?.employment_type?.label);
    }

    // ── Render thông tin hợp đồng ──────────────────────────────────────
    function renderContractInfo(c) {
        setText('dStartDate', formatDate(c.start_date));
        setText('dEndDate',   c.end_date ? formatDate(c.end_date) : 'Vô thời hạn');
        setText('dSalary',
            c.basic_salary
                ? parseInt(c.basic_salary).toLocaleString('vi-VN') + ' ₫'
                : '–'
        );
        setText('dNote', c.note || 'Không có ghi chú');
    }

    // ── Render timeline ────────────────────────────────────────────────
    function renderTimeline(c) {
        setText('tStartDate', formatDate(c.start_date));
        setText('tEndDate',   c.end_date ? formatDate(c.end_date) : 'Vô thời hạn');

        const endDot = document.getElementById('tEndDot');
        if (endDot && c.contract_status === 'active' && c.days_left > 0) {
            endDot.classList.remove('inactive');
        } else if (endDot) {
            endDot.classList.add('inactive');
        }
    }

    // ── Render nút thao tác theo role ──────────────────────────────────
    function renderActions(c) {
        const container = document.getElementById('actionButtons');
        if (!container) return;

        const backBtn = `
            <a href="/contract/list" class="btn btn-outline-secondary action-btn">
                <i class="fas fa-arrow-left me-1"></i>Quay lại danh sách
            </a>`;

        let html = backBtn;

        if (ROLE === 'ADMIN') {
            if (c.contract_status !== 'terminated') {
                html += `
                    <button class="btn btn-danger action-btn"
                            data-bs-toggle="modal" data-bs-target="#terminateModal">
                        <i class="fas fa-ban me-1"></i>Chấm dứt hợp đồng
                    </button>`;
            }
        } else if (ROLE === 'HR') {
            if (c.contract_status !== 'terminated') {
                html += `
                    <button class="btn btn-success action-btn" id="btnExtendDirect">
                        <i class="fas fa-redo me-1"></i>Gia hạn hợp đồng
                    </button>`;
            }
        } else if (ROLE === 'MANAGER') {
            if (c.contract_status !== 'terminated') {
                html += `
                    <a href="/contract/renewal_request?contract_id=${CONTRACT_ID}"
                       class="btn btn-warning action-btn">
                        <i class="fas fa-paper-plane me-1"></i>Yêu cầu gia hạn
                    </a>`;
            }
        }

        container.innerHTML = html;

        // HR – gia hạn trực tiếp (mở prompt đơn giản)
        const btnExtend = document.getElementById('btnExtendDirect');
        if (btnExtend) {
            btnExtend.addEventListener('click', () => handleHrExtend(c));
        }
    }

    // ── Chấm dứt hợp đồng (Admin) ─────────────────────────────────────
    function initTerminateModal() {
        const dateInput = document.getElementById('terminateDate');
        if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];

        const btnConfirm = document.getElementById('btnConfirmTerminate');
        if (!btnConfirm) return;

        btnConfirm.addEventListener('click', async () => {
            const endDate = document.getElementById('terminateDate').value;
            const note    = document.getElementById('terminateNote').value;

            if (!endDate) {
                showNotification('warning', 'Vui lòng chọn ngày chấm dứt');
                return;
            }

            btnConfirm.disabled = true;
            btnConfirm.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';

            try {
                const json = await ContractAPI.adminTerminateContract(CONTRACT_ID, { end_date: endDate, note });
                if (json.success) {
                    bootstrap.Modal.getInstance(terminateModal)?.hide();
                    showNotification('success', json.swal?.title || 'Chấm dứt thành công');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showNotification('error', json.swal?.text || 'Thao tác thất bại');
                    btnConfirm.disabled = false;
                    btnConfirm.innerHTML = '<i class="fas fa-ban me-1"></i>Xác nhận chấm dứt';
                }
            } catch (e) {
                showNotification('error', 'Lỗi kết nối máy chủ');
                btnConfirm.disabled = false;
                btnConfirm.innerHTML = '<i class="fas fa-ban me-1"></i>Xác nhận chấm dứt';
            }
        });
    }

    // ── Gia hạn trực tiếp (HR) ────────────────────────────────────────
    async function handleHrExtend(c) {
        const { value: duration } = await Swal.fire({
            title: 'Gia hạn hợp đồng',
            text: `Hợp đồng: ${c.contract_code} – ${c.employee_name || ''}`,
            input: 'select',
            inputOptions: {
                '3m':  '3 tháng',
                '6m':  '6 tháng',
                '12m': '1 năm',
                '24m': '2 năm',
            },
            inputPlaceholder: 'Chọn thời hạn gia hạn',
            showCancelButton: true,
            confirmButtonText: 'Gia hạn',
            cancelButtonText: 'Hủy',
        });

        if (!duration) return;

        try {
            const json = await ContractAPI.hrExtendContract(CONTRACT_ID, { duration });
            if (json.success) {
                showNotification('success', json.swal?.title || 'Gia hạn thành công');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('error', json.swal?.text || 'Gia hạn thất bại');
            }
        } catch (e) {
            showNotification('error', 'Lỗi kết nối máy chủ');
        }
    }

    // ── Load & render toàn trang ───────────────────────────────────────
    async function loadDetail() {
        if (!CONTRACT_ID) {
            loadingEl.innerHTML = `
                <div class="text-danger">
                    <i class="fas fa-exclamation-circle fa-2x d-block mb-2"></i>
                    Không tìm thấy ID hợp đồng trong URL.
                </div>
                <a href="/contract/list" class="btn btn-outline-secondary mt-3">Quay lại danh sách</a>`;
            return;
        }

        try {
            // Dùng API tương ứng theo role
            let json;
            if (ROLE === 'MANAGER') {
                json = await ContractAPI.managerGetContractDetail(CONTRACT_ID);
            } else if (ROLE === 'EMPLOYEE') {
                json = await ContractAPI.employeeGetMyContract(CONTRACT_ID);
            } else {
                json = await ContractAPI.getContractDetail(CONTRACT_ID);
            }

            const ok = json.success || json.status === 'success';
            if (!ok) throw new Error(json.swal?.text || json.message || 'Không tải được dữ liệu');

            const data = json.data || json;

            // Render từng phần
            renderHeader(data);
            renderEmployee(data);
            renderContractInfo(data);
            renderTimeline(data);
            renderActions(data);

            // Hiện nội dung
            loadingEl.style.display = 'none';
            mainEl.style.display    = 'block';

            // Init modal terminate nếu có (Admin)
            if (ROLE === 'ADMIN' && terminateModal) {
                initTerminateModal();
            }

        } catch (err) {
            loadingEl.innerHTML = `
                <div class="text-danger">
                    <i class="fas fa-exclamation-circle fa-2x d-block mb-2"></i>
                    ${err.message}
                </div>
                <a href="/contract/list" class="btn btn-outline-secondary mt-3">Quay lại</a>`;
        }
    }

    // ── Init ───────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', loadDetail);
})();