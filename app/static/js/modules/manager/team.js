/**
 * team.js — Manager Team Member List
 * Talks to: GET /manager/summary  |  GET /manager/  |  GET /manager/<id>
 */

const TeamPage = (() => {
    /* ── state ──────────────────────────────────────────────── */
    let _page = 1;
    let _filters = {};

    /* ── helpers ────────────────────────────────────────────── */
    const api = (url, opts = {}) =>
        fetch(url, { credentials: 'same-origin', ...opts })
            .then(r => r.json());

    function statusBadge(status) {
        const map = {
            active:   ['success',  'Đang làm'],
            resigned: ['danger',   'Đã nghỉ'],
            on_leave: ['warning',  'Nghỉ phép'],
        };
        const [cls, label] = map[status?.toLowerCase()] || ['neutral', status || '—'];
        return `<span class="mgr-badge ${cls}">${label}</span>`;
    }

    function contractBadge(type) {
        const map = {
            official:  ['primary', 'Chính thức'],
            probation: ['orange',  'Thử việc'],
            part_time: ['purple',  'Bán thời gian'],
        };
        const [cls, label] = map[type?.toLowerCase()] || ['neutral', type || '—'];
        return `<span class="mgr-badge ${cls}">${label}</span>`;
    }

    function avatarEl(name) {
        const initials = (name || '?').split(' ').slice(-2).map(w => w[0]).join('').toUpperCase();
        return `<div class="emp-avatar">${initials}</div>`;
    }

    /* ── load summary cards ─────────────────────────────────── */
    async function loadSummary() {
        try {
            const res = await api('/manager/summary');
            if (!res.success) return;
            const d = res.data;
            document.getElementById('stat-total').textContent     = d.total_employees    ?? '—';
            document.getElementById('stat-active').textContent    = d.active_employees   ?? '—';
            document.getElementById('stat-probation').textContent = d.probation_employees ?? '—';
            document.getElementById('stat-expiring').textContent  = d.expiring_contracts  ?? '—';
        } catch (e) {
            console.error('Summary load error', e);
        }
    }

    /* ── build table ─────────────────────────────────────────── */
    function renderTable(employees) {
        const tbody = document.getElementById('employee-tbody');
        document.getElementById('result-count').textContent = employees.length;

        if (!employees.length) {
            tbody.innerHTML = `
                <tr><td colspan="7">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon"><i class="bi bi-search"></i></div>
                        <div class="mgr-empty-title">Không tìm thấy nhân viên</div>
                        <div class="mgr-empty-text">Thử điều chỉnh bộ lọc và tìm lại.</div>
                    </div>
                </td></tr>`;
            return;
        }

        tbody.innerHTML = employees.map(emp => `
            <tr>
                <td>
                    <div class="emp-cell">
                        ${avatarEl(emp.full_name)}
                        <div>
                            <div class="emp-name">${emp.full_name}</div>
                            <div class="emp-code">${emp.employee_code}</div>
                        </div>
                    </div>
                </td>
                <td style="color:var(--mgr-muted); font-size:.83rem;">${emp.position || '—'}</td>
                <td style="font-size:.83rem;">${emp.department || '—'}</td>
                <td style="font-size:.83rem; white-space:nowrap;">
                    ${emp.hire_date ? new Date(emp.hire_date).toLocaleDateString('vi-VN') : '—'}
                </td>
                <td>${contractBadge(emp.contract_type)}</td>
                <td>${statusBadge(emp.working_status)}</td>
                <td class="text-center">
                    <div class="mgr-actions justify-content-center">
                        <button class="mgr-btn-icon" title="Xem hồ sơ"
                            onclick="TeamPage.showDetail(${emp.employee_id})">
                            <i class="bi bi-eye-fill"></i>
                        </button>
                    </div>
                </td>
            </tr>`).join('');
    }

    /* ── search / fetch list ────────────────────────────────── */
    async function fetchList() {
        const params = new URLSearchParams();
        const f = _filters;
        if (f.name)     params.set('name',           f.name);
        if (f.code)     params.set('employee_code',  f.code);
        if (f.position) params.set('position',       f.position);
        if (f.status)   params.set('working_status', f.status);
        if (f.contract) params.set('contract_type',  f.contract);

        const tbody = document.getElementById('employee-tbody');
        tbody.innerHTML = `<tr><td colspan="7">
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <span class="ms-2 text-muted" style="font-size:.85rem;">Đang tải…</span>
            </div></td></tr>`;

        try {
            const res = await api(`/manager/?${params}`);
            if (res.success) {
                renderTable(res.data?.employees || []);
            } else {
                tbody.innerHTML = `<tr><td colspan="7">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                        <div class="mgr-empty-title">Có lỗi xảy ra</div>
                        <div class="mgr-empty-text">${res.swal?.text || 'Vui lòng thử lại.'}</div>
                    </div></td></tr>`;
            }
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-wifi-off"></i></div>
                    <div class="mgr-empty-title">Không thể kết nối</div>
                    <div class="mgr-empty-text">Kiểm tra kết nối mạng và thử lại.</div>
                </div></td></tr>`;
        }
    }

    /* ── detail modal ───────────────────────────────────────── */
    async function showDetail(employeeId) {
        const modal = new bootstrap.Modal(document.getElementById('empDetailModal'));
        document.getElementById('modal-emp-name').textContent = 'Đang tải…';
        document.getElementById('modal-emp-code').textContent = '';
        document.getElementById('modal-detail-body').innerHTML = `
            <div class="text-center p-5">
                <div class="spinner-border text-primary" role="status"></div>
            </div>`;
        modal.show();

        try {
            const res = await api(`/manager/${employeeId}`);
            if (!res.success) throw new Error(res.swal?.text || 'Lỗi');
            const d = res.data;

            document.getElementById('modal-emp-name').textContent = d.full_name;
            document.getElementById('modal-emp-code').textContent = d.employee_code;

            const p = d.personal_info   || {};
            const o = d.organization    || {};
            const e = d.employment_info || {};
            const a = d.address_info    || {};

            document.getElementById('modal-detail-body').innerHTML = `
                <div class="row g-0">
                    <!-- Left: avatar + org -->
                    <div class="col-md-4 p-4 border-end" style="background:#f8fafc;">
                        <div class="text-center mb-4">
                            <div class="emp-avatar mx-auto mb-2"
                                style="width:64px;height:64px;font-size:1.4rem;border-radius:50%;">
                                ${(d.full_name||'?').split(' ').slice(-2).map(w=>w[0]).join('').toUpperCase()}
                            </div>
                            <div class="fw-700" style="font-size:.95rem;">${d.full_name}</div>
                            <div class="text-muted" style="font-size:.8rem;">${d.employee_code}</div>
                        </div>
                        <div class="mgr-detail-row flex-column gap-1">
                            <div class="mgr-detail-label">Phòng ban</div>
                            <div class="mgr-detail-value">${o.department || '—'}</div>
                        </div>
                        <div class="mgr-detail-row flex-column gap-1">
                            <div class="mgr-detail-label">Chức vụ</div>
                            <div class="mgr-detail-value">${o.position || '—'}</div>
                        </div>
                        <div class="mgr-detail-row flex-column gap-1">
                            <div class="mgr-detail-label">Loại HĐ</div>
                            <div class="mgr-detail-value">${contractBadge(e.type)}</div>
                        </div>
                        <div class="mgr-detail-row flex-column gap-1">
                            <div class="mgr-detail-label">Trạng thái</div>
                            <div class="mgr-detail-value">${statusBadge(e.status)}</div>
                        </div>
                    </div>

                    <!-- Right: personal details -->
                    <div class="col-md-8 p-4">
                        <p class="fw-semibold text-uppercase mb-3" style="font-size:.74rem; color:var(--mgr-muted); letter-spacing:.06em;">
                            Thông tin cá nhân
                        </p>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Giới tính</span>
                            <span class="mgr-detail-value">${p.gender || '—'}</span>
                        </div>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Ngày sinh</span>
                            <span class="mgr-detail-value">
                                ${p.dob ? new Date(p.dob).toLocaleDateString('vi-VN') : '—'}
                                ${p.age ? `<span class="text-muted ms-1" style="font-size:.8rem;">(${p.age} tuổi)</span>` : ''}
                            </span>
                        </div>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Điện thoại</span>
                            <span class="mgr-detail-value">${p.phone || '—'}</span>
                        </div>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Địa chỉ</span>
                            <span class="mgr-detail-value">${a.address_full || '—'}</span>
                        </div>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Ngày vào làm</span>
                            <span class="mgr-detail-value">
                                ${e.hire_date ? new Date(e.hire_date).toLocaleDateString('vi-VN') : '—'}
                            </span>
                        </div>
                        <div class="mgr-detail-row">
                            <span class="mgr-detail-label">Bắt buộc CC</span>
                            <span class="mgr-detail-value">
                                ${e.is_attendance_required
                                    ? '<span class="mgr-badge success"><i class="bi bi-check-circle-fill me-1"></i>Có</span>'
                                    : '<span class="mgr-badge neutral">Không</span>'}
                            </span>
                        </div>
                    </div>
                </div>`;
        } catch (err) {
            document.getElementById('modal-detail-body').innerHTML = `
                <div class="mgr-empty p-4">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                    <div class="mgr-empty-title">Không thể tải hồ sơ</div>
                    <div class="mgr-empty-text">${err.message}</div>
                </div>`;
        }
    }

    /* ── export Excel (re-uses attendance export endpoint) ──── */
    async function exportExcel() {
        try {
            showNotification('info', 'Đang chuẩn bị file Excel…');
            const res = await api('/manager/attendance/export');
            if (res.success && res.data?.file_url) {
                const a = document.createElement('a');
                a.href = res.data.file_url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                a.remove();
                showNotification('success', 'Đã tải file Excel thành công!');
            } else {
                showNotification('error', res.swal?.text || 'Xuất thất bại');
            }
        } catch (e) {
            showNotification('error', 'Không thể kết nối tới server.');
        }
    }

    /* ── public ─────────────────────────────────────────────── */
    function search() {
        _page = 1;
        _filters = {
            name:     document.getElementById('f-name').value.trim(),
            code:     document.getElementById('f-code').value.trim(),
            position: document.getElementById('f-position').value.trim(),
            status:   document.getElementById('f-status').value,
            contract: document.getElementById('f-contract').value,
        };
        fetchList();
    }

    function reset() {
        ['f-name','f-code','f-position'].forEach(id => document.getElementById(id).value = '');
        document.getElementById('f-status').value   = '';
        document.getElementById('f-contract').value = '';
        _filters = {};
        fetchList();
    }

    /* ── init ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        loadSummary();
        fetchList();

        // Search on Enter
        ['f-name','f-code','f-position'].forEach(id =>
            document.getElementById(id)?.addEventListener('keydown', e => {
                if (e.key === 'Enter') search();
            })
        );
    });

    return { search, reset, showDetail, exportExcel };
})();