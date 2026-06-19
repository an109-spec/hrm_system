/**
 * employee_management.js
 * Handles: stats, employee list, filter, transfer modal
 */

(() => {
    /* ── State ── */
    let employees    = [];
    let transferEmpId = null;
    const transferModal = new bootstrap.Modal(document.getElementById('transferModal'));

    /* ── DOM refs ── */
    const body        = document.getElementById('employeeBody');
    const searchInput = document.getElementById('searchInput');
    const deptFilter  = document.getElementById('deptFilter');
    const posFilter   = document.getElementById('posFilter');
    const btnSearch   = document.getElementById('btnSearch');
    const transferDept = document.getElementById('transferDept');
    const transferPos  = document.getElementById('transferPos');
    const btnTransfer  = document.getElementById('btnTransferSave');

    /* ── Init ── */
    async function init() {
        await loadMeta();
        await loadStats();
        await loadEmployees();
        bindEvents();
    }

    async function loadMeta() {
        const meta = await Admin.getMeta();
        if (!meta) return;
        Admin.fillSelect(deptFilter, meta.departments, 'name', 'Tất cả phòng ban');
        Admin.fillSelect(posFilter,  meta.positions,   'name', 'Tất cả chức danh');
        Admin.fillSelect(transferDept, meta.departments, 'name', 'Giữ nguyên');
        Admin.fillSelect(transferPos,  meta.positions,   'name', 'Giữ nguyên');
    }

    async function loadStats() {
        const r = await Admin.api('GET', '/admin/api/admin/employees/summary');
        if (!r.ok) return;
        const d = r.data?.data || {};
        document.getElementById('statTotal').textContent    = d.total    ?? '—';
        document.getElementById('statWorking').textContent  = d.working  ?? '—';
        document.getElementById('statProbation').textContent = d.probation ?? '—';
        document.getElementById('statExpiring').textContent = d.expiring_contract ?? '—';
    }

    async function loadEmployees() {
        const dept = deptFilter.value;
        const pos  = posFilter.value;
        let url = '/admin/api/employees?';
        if (dept) url += `department_id=${dept}&`;
        if (pos)  url += `position_id=${pos}&`;

        body.innerHTML = `<tr><td colspan="6" class="admin-loading">
            <span class="spinner-border spinner-border-sm me-2"></span>Đang tải...</td></tr>`;

        const r = await Admin.api('GET', url);
        if (!r.ok) {
            body.innerHTML = `<tr><td colspan="6" class="admin-empty">
                <i class="fa-solid fa-circle-exclamation"></i><p>Không tải được dữ liệu.</p></td></tr>`;
            return;
        }

        employees = r.data?.data?.items || [];
        renderTable(employees);
    }

    function renderTable(list) {
        const q = searchInput.value.trim().toLowerCase();
        const filtered = q
            ? list.filter(e => e.full_name.toLowerCase().includes(q)
                            || (e.phone || '').includes(q))
            : list;

        if (!filtered.length) {
            body.innerHTML = `<tr><td colspan="6">
                <div class="admin-empty">
                    <i class="fa-solid fa-users-slash"></i>
                    <p>Không tìm thấy nhân viên nào.</p>
                </div></td></tr>`;
            return;
        }

        body.innerHTML = filtered.map(e => `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="avatar-circle">${Admin.initials(e.full_name)}</div>
                        <div>
                            <div class="fw-semibold" style="font-size:.875rem;">${e.full_name}</div>
                            <div style="font-size:.75rem;color:var(--admin-muted);">${e.phone || '—'}</div>
                        </div>
                    </div>
                </td>
                <td>${e.department_name || '<span class="text-muted">Chưa gán</span>'}</td>
                <td>${e.position_name   || '<span class="text-muted">Chưa gán</span>'}</td>
                <td>${employmentBadge(e.employment_type)}</td>
                <td>${statusBadge(e.working_status)}</td>
                <td style="text-align:right;">
                    <button class="btn-icon primary me-1" title="Điều chuyển"
                            onclick="openTransfer(${e.id}, '${e.full_name.replace(/'/g,"\\'")}')">
                        <i class="fa-solid fa-arrows-left-right-to-line"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    function statusBadge(s) {
        const map = {
            active:   ['badge-active',    'Đang làm'],
            resigned: ['badge-resigned',  'Đã nghỉ'],
        };
        const [cls, label] = map[s] || ['badge-status', s || '—'];
        return `<span class="badge-status ${cls}">${label}</span>`;
    }

    function employmentBadge(t) {
        const map = {
            probation: ['badge-probation', 'Thử việc'],
            official:  ['badge-active',    'Chính thức'],
            contract:  ['badge-pending',   'Hợp đồng'],
        };
        const [cls, label] = map[t] || ['badge-status', t || '—'];
        return `<span class="badge-status ${cls}">${label}</span>`;
    }

    /* ── Transfer modal ── */
    window.openTransfer = function(id, name) {
        transferEmpId = id;
        document.getElementById('transferEmpName').textContent = name;
        transferDept.value = '';
        transferPos.value  = '';
        transferModal.show();
    };

    btnTransfer.addEventListener('click', async () => {
        if (!transferEmpId) return;
        const body_ = {};
        if (transferDept.value) body_.department_id = +transferDept.value;
        if (transferPos.value)  body_.position_id   = +transferPos.value;

        if (!Object.keys(body_).length) {
            Admin.toast('warning', 'Chọn ít nhất phòng ban hoặc chức danh mới');
            return;
        }

        Admin.btnLoading(btnTransfer, true);
        const r = await Admin.api('PATCH', `/admin/api/employees/${transferEmpId}/transfer`, body_);
        Admin.btnLoading(btnTransfer, false);
        Admin.swalResponse(r);

        if (r.ok) {
            transferModal.hide();
            await loadEmployees();
        }
    });

    /* ── Events ── */
    function bindEvents() {
        btnSearch.addEventListener('click', loadEmployees);
        searchInput.addEventListener('input', Admin.debounce(() => renderTable(employees)));
    }

    init();
})();