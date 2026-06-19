/**
 * team_reports.js — Manager Team Reports
 * Talks to:
 *   GET  /manager/attendance          (chấm công table)
 *   GET  /manager/attendance/export   (Excel export)
 *   PUT  /manager/attendance/<id>     (edit correction)
 *   POST /manager/attendance/reminders (send reminder)
 *   GET  /manager/attendance/summary  (absence stats)
 */

const TeamReports = (() => {
    /* ── state ──────────────────────────────────────────────── */
    let _currentTab = 'attendance';
    let _attPage    = 1;
    let _attTotal   = 0;
    let _attPerPage = 15;
    let _absentTodayIds = []; // for reminder tab

    /* ── helpers ────────────────────────────────────────────── */
    const api = (url, opts = {}) =>
        fetch(url, { credentials: 'same-origin', ...opts }).then(r => r.json());

    function getFilters() {
        return {
            month:  document.getElementById('f-month').value,
            year:   document.getElementById('f-year').value,
            status: document.getElementById('f-status').value,
        };
    }

    function statusBadge(label) {
        if (!label) return '<span class="mgr-badge neutral">—</span>';
        const lower = label.toLowerCase();
        if (lower.includes('đúng') || lower.includes('on time') || lower.includes('completed'))
            return `<span class="mgr-badge success">${label}</span>`;
        if (lower.includes('muộn') || lower.includes('late'))
            return `<span class="mgr-badge warning">${label}</span>`;
        if (lower.includes('vắng') || lower.includes('absent'))
            return `<span class="mgr-badge danger">${label}</span>`;
        if (lower.includes('nghỉ') || lower.includes('leave'))
            return `<span class="mgr-badge info">${label}</span>`;
        if (lower.includes('overtime') || lower.includes('tăng ca'))
            return `<span class="mgr-badge purple">${label}</span>`;
        return `<span class="mgr-badge neutral">${label}</span>`;
    }

    function initSelects() {
        const now = new Date();
        const monthEl = document.getElementById('f-month');
        const yearEl  = document.getElementById('f-year');
        if (monthEl) monthEl.value = now.getMonth() + 1;
        if (yearEl)  yearEl.value  = now.getFullYear();
    }

    /* ── tab switching ───────────────────────────────────────── */
    function switchTab(el, tabName) {
        _currentTab = tabName;

        document.querySelectorAll('.mgr-tab').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        ['attendance','overtime','absence','reminders'].forEach(t => {
            const panel = document.getElementById(`tab-${t}`);
            if (panel) panel.style.display = (t === tabName) ? '' : 'none';
        });
    }

    /* ═══════════════════════════════════════════════════════════
       TAB: Chấm công
    ══════════════════════════════════════════════════════════ */
    async function loadAttendance(page = 1) {
        _attPage = page;
        const f = getFilters();
        const params = new URLSearchParams({
            month:    f.month,
            year:     f.year,
            page:     page,
            per_page: _attPerPage,
        });
        if (f.status) params.set('status', f.status);

        const tbody = document.getElementById('att-tbody');
        tbody.innerHTML = `<tr><td colspan="8"><div class="text-center py-4">
            <div class="spinner-border spinner-border-sm text-primary"></div>
            <span class="ms-2 text-muted">Đang tải…</span>
        </div></td></tr>`;

        try {
            const res = await api(`/manager/attendance?${params}`);
            if (!res.success) throw new Error(res.swal?.text);
            const d = res.data;
            _attTotal = d.total_items || 0;

            document.getElementById('att-total-items').textContent = _attTotal;

            if (!d.items?.length) {
                tbody.innerHTML = `<tr><td colspan="8">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon"><i class="bi bi-calendar2"></i></div>
                        <div class="mgr-empty-title">Không có dữ liệu</div>
                        <div class="mgr-empty-text">Thử chọn kỳ khác.</div>
                    </div></td></tr>`;
                renderAttPagination(d);
                return;
            }

            tbody.innerHTML = d.items.map(r => `
                <tr>
                    <td>
                        <div class="emp-cell">
                            <div class="emp-avatar">${(r.name||'?').split(' ').slice(-2).map(w=>w[0]).join('').toUpperCase()}</div>
                            <div>
                                <div class="emp-name">${r.name}</div>
                                <div class="emp-code">${r.department}</div>
                            </div>
                        </div>
                    </td>
                    <td style="white-space:nowrap; font-size:.84rem;">${r.date}</td>
                    <td class="text-center">
                        <span class="fw-semibold" style="font-size:.85rem; color:${r.check_in !== '--:--' ? 'var(--mgr-success)' : 'var(--mgr-muted)'};">
                            ${r.check_in}
                        </span>
                    </td>
                    <td class="text-center">
                        <span class="fw-semibold" style="font-size:.85rem; color:${r.check_out !== '--:--' ? 'var(--mgr-text)' : 'var(--mgr-muted)'};">
                            ${r.check_out}
                        </span>
                    </td>
                    <td class="text-center" style="font-size:.84rem;">${r.worked_hours}h</td>
                    <td class="text-center" style="font-size:.84rem;">
                        ${r.overtime_hours > 0 ? `<span class="mgr-badge purple">+${r.overtime_hours}h</span>` : '<span style="color:var(--mgr-muted);">—</span>'}
                    </td>
                    <td class="text-center">${statusBadge(r.status_label)}</td>
                    <td class="text-center">
                        <button class="mgr-btn-icon" title="Chỉnh sửa" onclick="TeamReports.openEdit(event, ${r.employee_id}, '${r.date}', '${r.check_in}', '${r.check_out}')">
                            <i class="bi bi-pencil-fill"></i>
                        </button>
                    </td>
                </tr>`).join('');

            renderAttPagination(d);

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                    <div class="mgr-empty-title">Lỗi tải dữ liệu</div>
                    <div class="mgr-empty-text">${err?.message || 'Thử lại sau.'}</div>
                </div></td></tr>`;
        }
    }

    function renderAttPagination(d) {
        const bar   = document.getElementById('att-pagination');
        const info  = document.getElementById('att-page-info');
        const btns  = document.getElementById('att-page-btns');
        if (!bar) return;

        if (!d.total_pages || d.total_pages <= 1) {
            bar.style.display = 'none'; return;
        }

        bar.style.display = '';
        const from = (d.current_page - 1) * _attPerPage + 1;
        const to   = Math.min(d.current_page * _attPerPage, d.total_items);
        info.textContent = `Hiển thị ${from}–${to} / ${d.total_items} bản ghi`;

        const pages = Array.from({ length: d.total_pages }, (_, i) => i + 1);
        btns.innerHTML = pages.map(p => `
            <button class="page-btn ${p === d.current_page ? 'active' : ''}"
                onclick="TeamReports.goAttPage(${p})">${p}</button>`).join('');
    }

    function goAttPage(p) { loadAttendance(p); }

    /* ─── Edit modal ────────────────────────────────────────── */
    let _editAttId = null;

    function openEdit(e, empId, date, checkIn, checkOut) {
        // We need the actual attendance_id — store from data if available
        // For now use empId + date as a reference (ideally pass att_id from server)
        _editAttId = `${empId}_${date}`; // placeholder; real flow passes att record id

        document.getElementById('edit-check-in').value  = checkIn  !== '--:--' ? checkIn  : '';
        document.getElementById('edit-check-out').value = checkOut !== '--:--' ? checkOut : '';
        document.getElementById('edit-reason').value    = '';

        new bootstrap.Modal(document.getElementById('editAttModal')).show();
    }

    async function saveEdit() {
        const checkIn  = document.getElementById('edit-check-in').value;
        const checkOut = document.getElementById('edit-check-out').value;
        const reason   = document.getElementById('edit-reason').value.trim();

        if (!reason) {
            showNotification('warning', 'Vui lòng nhập lý do chỉnh sửa.');
            return;
        }

        const attId = document.getElementById('edit-att-id').value;
        if (!attId) {
            showNotification('error', 'Không xác định được bản ghi chấm công.');
            return;
        }

        try {
            const res = await api(`/manager/attendance/${attId}`, {
                method:  'PUT',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({
                    new_check_in:  checkIn  || null,
                    new_check_out: checkOut || null,
                    reason,
                }),
            });

            bootstrap.Modal.getInstance(document.getElementById('editAttModal')).hide();

            if (res.success) {
                showNotification('success', res.swal?.text || 'Đã cập nhật chấm công.');
                loadAttendance(_attPage);
            } else {
                showNotification('error', res.swal?.text || 'Cập nhật thất bại.');
            }
        } catch (err) {
            showNotification('error', 'Không thể kết nối tới server.');
        }
    }

    /* ═══════════════════════════════════════════════════════════
       TAB: Tăng ca  (derived from attendance data with OT hours)
    ══════════════════════════════════════════════════════════ */
    async function loadOvertime() {
        const f = getFilters();
        const params = new URLSearchParams({ month: f.month, year: f.year, per_page: 200 });

        const tbody = document.getElementById('ot-tbody');
        tbody.innerHTML = `<tr><td colspan="5"><div class="text-center py-4">
            <div class="spinner-border spinner-border-sm text-primary"></div>
        </div></td></tr>`;

        try {
            const res = await api(`/manager/attendance?${params}`);
            if (!res.success) throw new Error(res.swal?.text);

            const all  = (res.data?.items || []).filter(r => r.overtime_hours > 0);
            const totalSessions = all.length;
            const totalHours    = all.reduce((s, r) => s + r.overtime_hours, 0).toFixed(1);
            const empSet        = new Set(all.map(r => r.employee_id));
            const avgHours      = empSet.size > 0 ? (totalHours / empSet.size).toFixed(1) : 0;

            document.getElementById('ot-total-sessions').textContent = totalSessions;
            document.getElementById('ot-total-hours').textContent    = totalHours + 'h';
            document.getElementById('ot-emp-count').textContent      = empSet.size;
            document.getElementById('ot-avg-hours').textContent      = avgHours + 'h';

            if (!all.length) {
                tbody.innerHTML = `<tr><td colspan="5">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon"><i class="bi bi-lightning-charge"></i></div>
                        <div class="mgr-empty-title">Không có tăng ca trong kỳ này</div>
                    </div></td></tr>`;
                return;
            }

            tbody.innerHTML = all.map(r => `
                <tr>
                    <td>
                        <div class="emp-cell">
                            <div class="emp-avatar">${(r.name||'?').split(' ').slice(-2).map(w=>w[0]).join('').toUpperCase()}</div>
                            <div class="emp-name">${r.name}</div>
                        </div>
                    </td>
                    <td style="font-size:.84rem; color:var(--mgr-muted);">${r.department}</td>
                    <td class="text-center" style="font-size:.84rem;">${r.date}</td>
                    <td class="text-center">
                        <span class="mgr-badge purple">+${r.overtime_hours}h</span>
                    </td>
                    <td style="font-size:.82rem; color:var(--mgr-muted);">${r.notes || '—'}</td>
                </tr>`).join('');

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                    <div class="mgr-empty-title">${err?.message || 'Lỗi tải dữ liệu'}</div>
                </div></td></tr>`;
        }
    }

    /* ═══════════════════════════════════════════════════════════
       TAB: Vắng & Nghỉ phép
    ══════════════════════════════════════════════════════════ */
    async function loadAbsence() {
        const f = getFilters();
        const params = new URLSearchParams({ month: f.month, year: f.year, per_page: 200 });

        const tbody = document.getElementById('abs-tbody');
        tbody.innerHTML = `<tr><td colspan="4"><div class="text-center py-4">
            <div class="spinner-border spinner-border-sm text-primary"></div>
        </div></td></tr>`;

        try {
            const [attRes, summaryRes] = await Promise.all([
                api(`/manager/attendance?${params}`),
                api(`/manager/attendance/summary?month=${f.month}&year=${f.year}`),
            ]);

            if (!attRes.success) throw new Error(attRes.swal?.text);

            const sumData = summaryRes?.data || {};
            document.getElementById('abs-absent-days').textContent  = sumData.not_checked_in || 0;
            document.getElementById('abs-leave-days').textContent   = sumData.on_leave       || 0;
            document.getElementById('abs-unexcused').textContent    = sumData.not_checked_in || 0;

            const all = (attRes.data?.items || []).filter(r => {
                const lbl = (r.status_label || '').toLowerCase();
                return lbl.includes('vắng') || lbl.includes('nghỉ') || lbl.includes('absent') || lbl.includes('leave');
            });

            if (!all.length) {
                tbody.innerHTML = `<tr><td colspan="4">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon"><i class="bi bi-calendar2-check"></i></div>
                        <div class="mgr-empty-title">Không có vắng/nghỉ trong kỳ này</div>
                    </div></td></tr>`;
                return;
            }

            tbody.innerHTML = all.map(r => `
                <tr>
                    <td>
                        <div class="emp-cell">
                            <div class="emp-avatar">${(r.name||'?').split(' ').slice(-2).map(w=>w[0]).join('').toUpperCase()}</div>
                            <div class="emp-name">${r.name}</div>
                        </div>
                    </td>
                    <td class="text-center" style="font-size:.84rem;">${r.date}</td>
                    <td class="text-center">${statusBadge(r.status_label)}</td>
                    <td style="font-size:.82rem; color:var(--mgr-muted);">${r.notes || '—'}</td>
                </tr>`).join('');

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="4">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                    <div class="mgr-empty-title">${err?.message || 'Lỗi tải dữ liệu'}</div>
                </div></td></tr>`;
        }
    }

    /* ═══════════════════════════════════════════════════════════
       TAB: Nhắc nhở
    ══════════════════════════════════════════════════════════ */
    async function loadAbsentToday() {
        const tbody = document.getElementById('reminder-tbody');
        tbody.innerHTML = `<tr><td colspan="5"><div class="text-center py-4">
            <div class="spinner-border spinner-border-sm text-primary"></div>
        </div></td></tr>`;

        const now = new Date();
        const params = new URLSearchParams({
            month:    now.getMonth() + 1,
            year:     now.getFullYear(),
            per_page: 200,
        });

        try {
            const res = await api(`/manager/attendance?${params}`);
            if (!res.success) throw new Error(res.swal?.text);

            const today = now.toLocaleDateString('vi-VN'); // dd/mm/yyyy
            const todayRows = (res.data?.items || []).filter(r => r.date === today && !r.check_in || r.check_in === '--:--');
            _absentTodayIds = todayRows.map(r => r.employee_id);

            if (!todayRows.length) {
                tbody.innerHTML = `<tr><td colspan="5">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon"><i class="bi bi-check-circle"></i></div>
                        <div class="mgr-empty-title">Tất cả nhân viên đã chấm công hôm nay</div>
                    </div></td></tr>`;
                return;
            }

            tbody.innerHTML = todayRows.map(r => `
                <tr>
                    <td class="text-center">
                        <input type="checkbox" class="form-check-input reminder-check"
                            value="${r.employee_id}" checked>
                    </td>
                    <td>
                        <div class="emp-cell">
                            <div class="emp-avatar">${(r.name||'?').split(' ').slice(-2).map(w=>w[0]).join('').toUpperCase()}</div>
                            <div class="emp-name">${r.name}</div>
                        </div>
                    </td>
                    <td style="font-size:.84rem; color:var(--mgr-muted);">${r.department}</td>
                    <td style="font-size:.84rem; color:var(--mgr-muted);">—</td>
                    <td class="text-center">
                        <span class="mgr-badge danger">Chưa chấm công</span>
                    </td>
                </tr>`).join('');

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                    <div class="mgr-empty-title">${err?.message || 'Lỗi tải dữ liệu'}</div>
                </div></td></tr>`;
        }
    }

    function toggleSelectAll(cb) {
        document.querySelectorAll('.reminder-check').forEach(el => el.checked = cb.checked);
    }

    async function sendReminders() {
        const checked = [...document.querySelectorAll('.reminder-check:checked')].map(el => parseInt(el.value));
        if (!checked.length) {
            showNotification('warning', 'Vui lòng chọn ít nhất một nhân viên.');
            return;
        }

        const message = document.getElementById('reminder-message').value.trim() || null;

        try {
            const res = await api('/manager/attendance/reminders', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ employee_ids: checked, message }),
            });

            if (res.success) {
                showNotification('success', res.swal?.text || `Đã gửi nhắc nhở tới ${checked.length} nhân viên.`);
            } else {
                showNotification('warning', res.swal?.text || 'Gửi không thành công.');
            }
        } catch (err) {
            showNotification('error', 'Không thể kết nối tới server.');
        }
    }

    /* ═══════════════════════════════════════════════════════════
       Export Excel
    ══════════════════════════════════════════════════════════ */
    async function exportExcel() {
        const f = getFilters();
        const params = new URLSearchParams({ month: f.month, year: f.year });
        if (f.status) params.set('status', f.status);

        const btn = document.getElementById('btn-export');
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang xuất…';

        try {
            const res = await api(`/manager/attendance/export?${params}`);
            if (res.success && res.data?.file_url) {
                const a = document.createElement('a');
                a.href     = res.data.file_url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                a.remove();
                showNotification('success', 'File Excel đã được tải về.');
            } else {
                showNotification('error', res.swal?.text || 'Xuất thất bại.');
            }
        } catch (err) {
            showNotification('error', 'Không thể kết nối tới server.');
        } finally {
            btn.disabled  = false;
            btn.innerHTML = orig;
        }
    }

    /* ── main load dispatcher ────────────────────────────────── */
    function load() {
        switch (_currentTab) {
            case 'attendance': loadAttendance(1); break;
            case 'overtime':   loadOvertime();    break;
            case 'absence':    loadAbsence();     break;
            case 'reminders':  loadAbsentToday(); break;
        }
    }

    /* ── init ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        initSelects();
        loadAttendance(1);
    });

    return {
        load,
        switchTab,
        goAttPage,
        openEdit,
        saveEdit,
        exportExcel,
        sendReminders,
        loadAbsentToday,
        toggleSelectAll,
    };
})();