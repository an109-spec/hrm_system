/**
 * reports.js
 * Trang báo cáo danh sách nhân viên với lọc + phân trang + xem chi tiết.
 */
(function () {
    'use strict';

    const PAGE_SIZE_DEFAULT = 20;

    let allRows  = [];
    let filtered = [];
    let page     = 1;
    let pageSize = PAGE_SIZE_DEFAULT;

    /* ── Boot ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        loadDeptOptions();
        loadEmployees();

        document.getElementById('btnApplyFilter')
            ?.addEventListener('click', applyFilter);

        document.getElementById('btnResetFilter')
            ?.addEventListener('click', resetFilter);

        document.getElementById('btnExportCSV')
            ?.addEventListener('click', exportCSV);
    });

    /* ── Load dept options ──────────────────────────────────── */
    async function loadDeptOptions() {
        try {
            const res  = await fetch('/hr/stats/department');
            const json = await res.json();
            const depts = json.data?.departments ?? [];
            const sel   = document.getElementById('filterDept');
            if (!sel) return;
            depts.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.department_id;
                opt.textContent = d.name;
                sel.appendChild(opt);
            });
        } catch (_) {}
    }

    /* ── Load all employees ─────────────────────────────────── */
    async function loadEmployees() {
        setTableLoading(true);
        try {
            const res  = await fetch('/hr/employees');
            const json = await res.json();
            if (!json.swal || json.swal.icon !== 'success') throw new Error(json.swal?.text);

            allRows  = json.data?.employees ?? [];
            filtered = [...allRows];
            page     = 1;
            renderTable();
        } catch (err) {
            console.error('loadEmployees:', err);
            setTableLoading(false);
        }
    }

    /* ── Filter ─────────────────────────────────────────────── */
    function applyFilter() {
        const deptId   = document.getElementById('filterDept')?.value    || '';
        const status   = document.getElementById('filterStatus')?.value  || '';
        const contract = document.getElementById('filterContract')?.value || '';
        const name     = (document.getElementById('filterName')?.value   || '').trim().toLowerCase();

        filtered = allRows.filter(emp => {
            if (deptId   && String(emp.department_id) !== deptId)        return false;
            if (status   && emp.working_status !== status)               return false;
            if (contract && emp.employment_type !== contract)            return false;
            if (name     && !(emp.full_name || '').toLowerCase().includes(name)) return false;
            return true;
        });

        page = 1;
        renderTable();
    }

    function resetFilter() {
        ['filterDept','filterStatus','filterContract','filterName'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        filtered = [...allRows];
        page = 1;
        renderTable();
    }

    /* ── Render table ───────────────────────────────────────── */
    function renderTable() {
        const tbody = document.getElementById('reportTableBody');
        const total = filtered.length;

        document.getElementById('resultCount').textContent =
            `Tìm thấy ${total} nhân viên`;

        if (!total) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Không có kết quả</td></tr>';
            renderPagination(0);
            return;
        }

        const start  = (page - 1) * pageSize;
        const chunk  = filtered.slice(start, start + pageSize);

        tbody.innerHTML = chunk.map((emp, idx) => `
            <tr>
                <td class="text-muted small">${start + idx + 1}</td>
                <td class="fw-semibold">${emp.full_name || '–'}</td>
                <td>${emp.department || '–'}</td>
                <td>${emp.position   || '–'}</td>
                <td class="text-center">
                    <span class="hr-badge hr-badge-${emp.working_status || ''}">
                        ${labelStatus(emp.working_status)}
                    </span>
                </td>
                <td class="text-center">
                    <span class="hr-badge hr-badge-${emp.employment_type || ''}">
                        ${labelContract(emp.employment_type)}
                    </span>
                </td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-primary py-0"
                            onclick="HRReports.viewDetail(${emp.employee_id})">
                        <i class="bi bi-eye me-1"></i>Chi tiết
                    </button>
                </td>
            </tr>`).join('');

        renderPagination(total);
    }

    /* ── Pagination ─────────────────────────────────────────── */
    function renderPagination(total) {
        const pages   = Math.ceil(total / pageSize);
        const infoEl  = document.getElementById('paginationInfo');
        const listEl  = document.getElementById('paginationList');
        if (!infoEl || !listEl) return;

        const start = Math.min((page - 1) * pageSize + 1, total);
        const end   = Math.min(page * pageSize, total);
        infoEl.textContent = total ? `Hiển thị ${start}–${end} / ${total}` : '';

        if (pages <= 1) { listEl.innerHTML = ''; return; }

        const makeItem = (lbl, p, disabled = false, active = false) =>
            `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${p}">${lbl}</a>
             </li>`;

        let html = makeItem('«', 1, page === 1);
        html    += makeItem('‹', page - 1, page === 1);

        const from = Math.max(1, page - 2);
        const to   = Math.min(pages, page + 2);
        for (let i = from; i <= to; i++) html += makeItem(i, i, false, i === page);

        html += makeItem('›', page + 1, page === pages);
        html += makeItem('»', pages, page === pages);

        listEl.innerHTML = html;
        listEl.querySelectorAll('[data-page]').forEach(a => {
            a.addEventListener('click', e => {
                e.preventDefault();
                const p = parseInt(a.dataset.page);
                if (p >= 1 && p <= pages && !a.closest('.disabled')) {
                    page = p;
                    renderTable();
                }
            });
        });
    }

    /* ── Employee detail modal ──────────────────────────────── */
    async function viewDetail(id) {
        const modal = new bootstrap.Modal(document.getElementById('employeeDetailModal'));
        const body  = document.getElementById('employeeDetailBody');
        body.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div></div>';
        modal.show();

        try {
            const res  = await fetch(`/hr/employees/${id}`);
            const json = await res.json();
            if (!json.swal || json.swal.icon !== 'success') throw new Error(json.swal?.text);

            const d = json.data;
            body.innerHTML = buildDetailHtml(d);
        } catch (err) {
            body.innerHTML = `<div class="alert alert-danger">Không thể tải thông tin: ${err.message}</div>`;
        }
    }

    function buildDetailHtml(d) {
        const pi = d.personal_info   || {};
        const oi = d.organization    || {};
        const ei = d.employment_info || {};

        return `
        <div class="row g-3">
            <div class="col-md-4 text-center">
                <img src="${d.avatar || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(d.full_name || '') + '&background=4f46e5&color=fff&size=128'}"
                     class="rounded-circle mb-2" width="96" height="96" alt="avatar">
                <div class="fw-semibold">${d.full_name || '–'}</div>
                <div class="text-muted small">${d.employee_code || ''}</div>
            </div>
            <div class="col-md-8">
                <table class="table table-sm table-borderless mb-0">
                    <tbody>
                        <tr><th class="text-muted fw-normal" style="width:40%">Phòng ban</th><td>${oi.department || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Chức danh</th><td>${oi.position || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Giới tính</th><td>${pi.gender || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Ngày sinh</th><td>${pi.dob || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Điện thoại</th><td>${pi.phone || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Ngày vào</th><td>${ei.hire_date || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Loại HĐ</th><td>${ei.type || '–'}</td></tr>
                        <tr><th class="text-muted fw-normal">Trạng thái</th><td>${ei.status || '–'}</td></tr>
                    </tbody>
                </table>
            </div>
        </div>`;
    }

    /* ── Export CSV ─────────────────────────────────────────── */
    function exportCSV() {
        if (!filtered.length) {
            window.showNotification?.('warning', 'Không có dữ liệu để xuất.');
            return;
        }
        const headers = ['#', 'Họ và tên', 'Phòng ban', 'Chức danh', 'Trạng thái', 'Loại HĐ'];
        const rows    = filtered.map((emp, i) => [
            i + 1,
            emp.full_name      || '',
            emp.department     || '',
            emp.position       || '',
            labelStatus(emp.working_status),
            labelContract(emp.employment_type)
        ]);

        const csv  = [headers, ...rows]
            .map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
            .join('\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
        const url  = URL.createObjectURL(blob);
        const a    = Object.assign(document.createElement('a'), {
            href: url, download: `hr_employees_${datestamp()}.csv`
        });
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        window.showNotification?.('success', 'Đã xuất CSV thành công.');
    }

    /* ── Helpers ────────────────────────────────────────────── */
    function setTableLoading(on) {
        const tbody = document.getElementById('reportTableBody');
        if (tbody && on) tbody.innerHTML =
            '<tr><td colspan="7" class="text-center text-muted py-4">Đang tải…</td></tr>';
    }

    function labelStatus(s) {
        const map = { active:'Đang làm', probation:'Thử việc', resigned:'Đã nghỉ' };
        return map[s] || (s || '–');
    }

    function labelContract(t) {
        const map = { probation:'Thử việc', full_time:'Chính thức', part_time:'Bán thời gian' };
        return map[t] || (t || '–');
    }

    function datestamp() {
        return new Date().toISOString().slice(0, 10);
    }

    /* ── Public API ─────────────────────────────────────────── */
    window.HRReports = { viewDetail };

})();