/**
 * attendance.js
 * Centralized JavaScript cho toàn bộ module Attendance
 * Sử dụng window.showNotification / window.confirmAction từ main.js
 */

'use strict';

/* ============================================================
   A. API HELPERS
   ============================================================ */
const AttendanceAPI = {
    _baseUrl: '/attendance',

    /**
     * Generic AJAX wrapper — trả về JSON response
     * Tự động xử lý swal notification từ backend
     */
    async _request(method, path, body = null, opts = {}) {
        const config = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) config.body = JSON.stringify(body);

        try {
            const res  = await fetch(this._baseUrl + path, config);
            const data = await res.json();

            // Hiển thị swal nếu backend trả về
            if (data.swal && !opts.silent) {
                const s = data.swal;
                if (s.timer) {
                    Swal.fire({ icon: s.icon, title: s.title, text: s.text,
                                timer: s.timer, showConfirmButton: false, toast: false });
                } else {
                    // Chỉ toast với success nhanh
                    if (s.icon === 'success') {
                        window.showNotification('success', s.title);
                    } else {
                        Swal.fire({ icon: s.icon, title: s.title, text: s.text });
                    }
                }
            }

            return { ok: res.ok, status: res.status, data };
        } catch (err) {
            console.error('[AttendanceAPI] Error:', err);
            window.showNotification('error', 'Lỗi kết nối máy chủ');
            return { ok: false, status: 0, data: null };
        }
    },

    // ── State & Today ──────────────────────────────────────
    getState()                { return this._request('GET', '/state'); },
    getToday(employeeId = '') {
        const q = employeeId ? `?employee_id=${employeeId}` : '';
        return this._request('GET', `/today${q}`);
    },

    // ── Actions ─────────────────────────────────────────────
    action(payload)           { return this._request('POST', '/action', payload); },
    checkIn(payload = {})     { return this._request('POST', '/check-in', payload); },
    checkOut(payload = {})    { return this._request('POST', '/check-out', payload); },
    checkInOT(payload = {})   { return this._request('POST', '/overtime/check-in', payload); },
    checkOutOT(payload = {})  { return this._request('POST', '/overtime/check-out', payload); },

    // ── History ─────────────────────────────────────────────
    getHistory(params = {}) {
        const q = new URLSearchParams(params).toString();
        return this._request('GET', `/history${q ? '?' + q : ''}`);
    },
    deleteAttendance(date, employeeId = '') {
        const q = employeeId ? `?employee_id=${employeeId}` : '';
        return this._request('DELETE', `/${date}${q}`);
    },

    // ── Summary ─────────────────────────────────────────────
    getDailySummary(params = {}) {
        const q = new URLSearchParams(params).toString();
        return this._request('GET', `/daily-summary${q ? '?' + q : ''}`);
    },

    // ── OT ──────────────────────────────────────────────────
    getOTRequests(managerId = '') {
        const q = managerId ? `?manager_id=${managerId}` : '';
        return this._request('GET', `/overtime/requests${q}`);
    },
    createOTRequest(payload)  { return this._request('POST', '/overtime/request', payload); },
    approveOT(payload)        { return this._request('POST', '/overtime/approve', payload); },
    rejectOT(payload)         { return this._request('POST', '/overtime/reject', payload); },
    calcOT(payload)           { return this._request('POST', '/overtime/calc', payload); },

    // ── QR ──────────────────────────────────────────────────
    processQR(qrContent)      { return this._request('POST', '/qr/process', { qr_content: qrContent }); },

    // ── Team (Today list) ───────────────────────────────────
    getTodayList(params = {}) {
        const q = new URLSearchParams(params).toString();
        return this._request('GET', `/today/list${q ? '?' + q : ''}`);
    },
};

/* ============================================================
   B. UI UTILITIES
   ============================================================ */
const AttendanceUI = {

    /** Render attendance status badge */
    renderBadge(shiftStatus) {
        const MAP = {
            'working_regular':                    ['working',    'Dang lam viec'],
            'completed':                          ['completed',  'Hoan thanh'],
            'absent':                             ['absent',     'Vang mat'],
            'leave':                              ['leave',      'Nghi phep'],
            'holiday_off':                        ['holiday',    'Nghi le'],
            'weekend_off':                        ['weekend',    'Cuoi tuan'],
            'working_overtime':                   ['overtime',   'Tang ca'],
            'regular_done_pending_ot_decision':   ['pending',    'Cho OT'],
            'not_started':                        ['not-started','Chua bat dau'],
            'pre_ot_rest':                        ['pending',    'Nghi truoc OT'],
            'regular_done':                       ['completed',  'Xong ca chinh'],
        };
        const norm  = (shiftStatus || '').toLowerCase();
        const [cls, label] = MAP[norm] || ['not-started', shiftStatus || 'N/A'];
        return `<span class="att-badge ${cls}">${label}</span>`;
    },

    /** Format ISO datetime → HH:MM:SS */
    formatTime(iso) {
        if (!iso) return '<span class="no-data">--:--:--</span>';
        try {
            return new Date(iso).toLocaleTimeString('vi-VN');
        } catch { return iso; }
    },

    /** Format ISO date → DD/MM/YYYY */
    formatDate(iso) {
        if (!iso) return '--';
        try {
            return new Date(iso).toLocaleDateString('vi-VN');
        } catch { return iso; }
    },

    /** Render loading spinner */
    showLoading(containerId) {
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2 text-muted">Dang tai du lieu...</p>
            </div>`;
    },

    /** Render empty state */
    showEmpty(containerId, msg = 'Khong co du lieu') {
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                <p>${msg}</p>
            </div>`;
    },

    /** Live clock */
    startClock(elementId) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const tick = () => {
            const now = new Date();
            el.textContent = now.toLocaleTimeString('vi-VN', { hour12: false });
        };
        tick();
        return setInterval(tick, 1000);
    },

    /** Render pagination */
    renderPagination(containerId, pagination, onPageClick) {
        const el = document.getElementById(containerId);
        if (!el || !pagination) return;
        const { page, pages } = pagination;
        if (pages <= 1) { el.innerHTML = ''; return; }

        let html = '<nav><ul class="pagination pagination-sm mb-0">';
        html += `<li class="page-item${page <= 1 ? ' disabled' : ''}">
                   <a class="page-link" href="#" data-page="${page - 1}">Truoc</a></li>`;
        for (let i = 1; i <= pages; i++) {
            html += `<li class="page-item${i === page ? ' active' : ''}">
                       <a class="page-link" href="#" data-page="${i}">${i}</a></li>`;
        }
        html += `<li class="page-item${page >= pages ? ' disabled' : ''}">
                   <a class="page-link" href="#" data-page="${page + 1}">Sau</a></li>`;
        html += '</ul></nav>';
        el.innerHTML = html;

        el.querySelectorAll('[data-page]').forEach(a => {
            a.addEventListener('click', e => {
                e.preventDefault();
                const p = parseInt(a.dataset.page);
                if (p >= 1 && p <= pages) onPageClick(p);
            });
        });
    },
};

/* ============================================================
   C. PAGE MODULES
   ============================================================ */

/** attendance.html — Main page widget */
const AttendanceMain = {
    _stateInterval: null,

    init() {
        this.loadState();
        AttendanceUI.startClock('att-clock');
        this._stateInterval = setInterval(() => this.loadState(), 30000);
        this.bindActions();
    },

    async loadState() {
        const { ok, data } = await AttendanceAPI.getState();
        if (!ok || !data) return;
        this.renderState(data);
    },

    renderState(data) {
        const state   = data.state || {};
        const att     = data.attendance || {};
        const emp     = data;

        // Name
        const nameEl = document.getElementById('att-emp-name');
        if (nameEl) nameEl.textContent = emp.full_name || '';

        // Status badge
        const badgeEl = document.getElementById('att-status-badge');
        if (badgeEl) badgeEl.innerHTML = AttendanceUI.renderBadge(state.state);

        // Message
        const msgEl = document.getElementById('att-state-message');
        if (msgEl) msgEl.textContent = state.message || '';

        // Button
        const btn = document.getElementById('att-main-btn');
        if (btn) {
            btn.textContent = (state.button_text || 'XAC THUC').replace(/[^\w\s]/g, '').trim();
            btn.disabled    = !state.button_enabled;
        }

        // Check-in / check-out times
        if (att.check_in)  {
            const ciEl = document.getElementById('att-checkin-time');
            if (ciEl) ciEl.textContent = AttendanceUI.formatTime(att.check_in);
        }
        if (att.check_out) {
            const coEl = document.getElementById('att-checkout-time');
            if (coEl) coEl.textContent = AttendanceUI.formatTime(att.check_out);
        }

        // Hours
        const whEl = document.getElementById('att-working-hours');
        if (whEl) whEl.textContent = (att.working_hours || '0.00') + 'h';
    },

    bindActions() {
        const btn = document.getElementById('att-main-btn');
        if (btn) {
            btn.addEventListener('click', () => this.doAction({}));
        }

        // Overtime decision buttons
        document.getElementById('btn-ot-yes')?.addEventListener('click', () =>
            this.doAction({ overtime_decision: 'yes' }));
        document.getElementById('btn-ot-no')?.addEventListener('click', () =>
            this.doAction({ overtime_decision: 'no' }));
    },

    async doAction(extraPayload = {}) {
        const btn = document.getElementById('att-main-btn');
        if (btn) btn.disabled = true;

        const { ok, data } = await AttendanceAPI.action(extraPayload);

        // Nếu cần confirm offday
        if (ok && data) {
            const action = data.action || '';
            if (action === 'holiday_work_prompt' || action === 'weekend_work_prompt') {
                const label = action === 'holiday_work_prompt' ? 'ngay le' : 'cuoi tuan';
                const result = await Swal.fire({
                    title: 'Xac nhan lam viec',
                    text: `Hom nay la ngay nghi ${label}. Ban co muon di lam khong?`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Vang, toi di lam',
                    cancelButtonText: 'Khong, nghi',
                });
                if (result.isConfirmed) {
                    await AttendanceAPI.action({ confirm_work_on_offday: true });
                } else {
                    await AttendanceAPI.action({ decline_offday_work: true });
                }
                await this.loadState();
                return;
            }

            if (action === 'early_checkout_prompt') {
                const flags = data.flags || {};
                const result = await Swal.fire({
                    title: 'Xac nhan tan ca som',
                    text: `Ban muon tan ca som ${flags.early_minutes || ''} phut?`,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Co, tan ca som',
                    cancelButtonText: 'Huy',
                });
                if (result.isConfirmed) {
                    await AttendanceAPI.action({ early_checkout_confirmed: true });
                    await this.loadState();
                }
                if (btn) btn.disabled = false;
                return;
            }

            if (data.requires_overtime_decision) {
                document.getElementById('ot-decision-panel')?.classList.remove('d-none');
            }
        }

        await this.loadState();
        if (btn) btn.disabled = false;
    },

    destroy() {
        if (this._stateInterval) clearInterval(this._stateInterval);
    },
};

/** history.html */
const AttendanceHistory = {
    _params: { page: 1, per_page: 31 },

    init() {
        this.bindFilters();
        this.load();
    },

    bindFilters() {
        document.getElementById('btn-filter')?.addEventListener('click', () => {
            this._params.page      = 1;
            this._params.from_date = document.getElementById('from_date')?.value || '';
            this._params.to_date   = document.getElementById('to_date')?.value   || '';
            this._params.employee_id = document.getElementById('employee_id_filter')?.value || '';
            this.load();
        });
    },

    async load() {
        AttendanceUI.showLoading('history-table-body');
        const { ok, data } = await AttendanceAPI.getHistory(this._params);
        if (!ok || !data) return;
        this.render(data);
        AttendanceUI.renderPagination('history-pagination', data.pagination, p => {
            this._params.page = p;
            this.load();
        });
    },

    render(data) {
        const tbody = document.getElementById('history-table-body');
        if (!tbody) return;
        const rows  = data.data || [];
        if (!rows.length) {
            AttendanceUI.showEmpty('history-table-body', 'Khong co ban ghi cham cong nao');
            return;
        }
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td>${AttendanceUI.formatDate(r.date)}</td>
                <td>${r.full_name || '--'}</td>
                <td class="check-time">${r.check_in || '<span class="no-data">--</span>'}</td>
                <td class="check-time">${r.check_out || '<span class="no-data">--</span>'}</td>
                <td>${AttendanceUI.renderBadge(r.attendance_type)}</td>
                <td>${parseFloat(r.regular_hours || 0).toFixed(2)}h</td>
                <td>${r.late_minutes > 0 ? '<span class="text-danger">' + r.late_minutes + ' phut</span>' : '<span class="text-success">Dung gio</span>'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger btn-delete-att"
                        data-date="${r.date}" data-emp="${r.employee_id}">
                        Xoa
                    </button>
                </td>
            </tr>`).join('');

        tbody.querySelectorAll('.btn-delete-att').forEach(btn => {
            btn.addEventListener('click', () => {
                const d = btn.dataset.date;
                const e = btn.dataset.emp;
                window.confirmAction(`Huy ban ghi cham cong ngay ${d}?`, async () => {
                    const { ok } = await AttendanceAPI.deleteAttendance(d, e);
                    if (ok) this.load();
                });
            });
        });
    },
};

/** summary.html */
const AttendanceSummary = {
    init() {
        this.bindFilters();
        this.load();
    },
    bindFilters() {
        document.getElementById('btn-load-summary')?.addEventListener('click', () => this.load());
    },
    async load() {
        const params = {};
        const dateEl = document.getElementById('summary_date');
        const empEl  = document.getElementById('summary_employee_id');
        if (dateEl?.value) params.date = dateEl.value;
        if (empEl?.value)  params.employee_id = empEl.value;

        AttendanceUI.showLoading('summary-container');
        const { ok, data } = await AttendanceAPI.getDailySummary(params);
        if (!ok || !data) return;
        this.render(data);
    },
    render(data) {
        const container = document.getElementById('summary-container');
        if (!container) return;
        const rows = data.data || [];
        if (!rows.length) {
            AttendanceUI.showEmpty('summary-container', 'Khong co du lieu cham cong');
            return;
        }
        container.innerHTML = `
        <div class="table-responsive">
        <table class="table att-table table-hover align-middle">
            <thead><tr>
                <th>Ho ten</th><th>Gio vao</th><th>Gio ra</th>
                <th>Gio lam</th><th>Don vi cong</th><th>Di muon</th><th>Loai ngay</th>
            </tr></thead>
            <tbody>${rows.map(r => `<tr>
                <td>${r.full_name || '--'}</td>
                <td class="check-time">${r.check_in || '--'}</td>
                <td class="check-time">${r.check_out || '--'}</td>
                <td>${parseFloat(r.worked_hours || 0).toFixed(2)}h</td>
                <td>${parseFloat(r.work_units || 0).toFixed(2)}</td>
                <td>${r.late_minutes > 0 ? '<span class="text-danger">' + r.late_minutes + 'p</span>' : 'Dung gio'}</td>
                <td>${AttendanceUI.renderBadge(r.attendance_type)}</td>
            </tr>`).join('')}</tbody>
        </table></div>`;
    },
};

/** overtime_request.html */
const OvertimeRequest = {
    init() {
        document.getElementById('btn-calc-ot')?.addEventListener('click', () => this.calcOT());
        document.getElementById('form-ot-request')?.addEventListener('submit', e => {
            e.preventDefault();
            this.submit();
        });
    },
    async calcOT() {
        const payload = {
            overtime_check_in:  document.getElementById('ot_start_datetime')?.value,
            overtime_check_out: document.getElementById('ot_end_datetime')?.value,
        };
        if (!payload.overtime_check_in || !payload.overtime_check_out) {
            window.showNotification('warning', 'Vui long nhap thoi gian OT');
            return;
        }
        const { ok, data } = await AttendanceAPI.calcOT(payload);
        if (ok && data?.data) {
            const el = document.getElementById('ot-calc-result');
            if (el) el.textContent = `Gio OT uoc tinh: ${parseFloat(data.data.overtime_hours || 0).toFixed(2)} gio`;
        }
    },
    async submit() {
        const form    = document.getElementById('form-ot-request');
        const payload = {
            overtime_date: form.querySelector('[name=overtime_date]')?.value,
            start_time:    form.querySelector('[name=start_time]')?.value,
            end_time:      form.querySelector('[name=end_time]')?.value,
            reason:        form.querySelector('[name=reason]')?.value,
            note:          form.querySelector('[name=note]')?.value,
        };
        const btn = form.querySelector('[type=submit]');
        if (btn) btn.disabled = true;
        const { ok } = await AttendanceAPI.createOTRequest(payload);
        if (ok && btn) btn.disabled = false;
    },
};

/** manager_ot_approval.html */
const ManagerOTApproval = {
    init() {
        this.load();
    },
    async load() {
        AttendanceUI.showLoading('ot-requests-container');
        const { ok, data } = await AttendanceAPI.getOTRequests();
        if (!ok || !data) return;
        this.render(data.data?.requests || []);
    },
    render(requests) {
        const container = document.getElementById('ot-requests-container');
        if (!container) return;
        if (!requests.length) {
            AttendanceUI.showEmpty('ot-requests-container', 'Khong co don tang ca cho duyet');
            return;
        }
        container.innerHTML = requests.map(r => `
            <div class="ot-request-card mb-3">
                <div class="ot-header">
                    <div>
                        <h6 class="mb-0">${r.employee_name}</h6>
                        <small class="text-muted">Ngay: ${AttendanceUI.formatDate(r.overtime_date)}</small>
                    </div>
                    ${AttendanceUI.renderBadge(r.status)}
                </div>
                <div class="row g-2 mb-3">
                    <div class="col-6"><small class="text-muted">So gio yeu cau</small>
                        <div class="fw-bold">${parseFloat(r.requested_hours || 0).toFixed(2)}h</div>
                    </div>
                    <div class="col-6"><small class="text-muted">Ngay le OT</small>
                        <div>${r.is_holiday_ot ? 'Co' : 'Khong'}</div>
                    </div>
                </div>
                <p class="small text-muted mb-3">${r.reason || ''}</p>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-success btn-approve-ot" data-id="${r.id}">
                        Duyet
                    </button>
                    <button class="btn btn-sm btn-danger btn-reject-ot" data-id="${r.id}">
                        Tu choi
                    </button>
                </div>
            </div>`).join('');

        container.querySelectorAll('.btn-approve-ot').forEach(btn => {
            btn.addEventListener('click', () => this.approve(parseInt(btn.dataset.id)));
        });
        container.querySelectorAll('.btn-reject-ot').forEach(btn => {
            btn.addEventListener('click', () => this.reject(parseInt(btn.dataset.id)));
        });
    },
    async approve(id) {
        window.confirmAction('Duyet don tang ca nay?', async () => {
            const { ok } = await AttendanceAPI.approveOT({ overtime_request_id: id });
            if (ok) this.load();
        });
    },
    async reject(id) {
        const { value: reason } = await Swal.fire({
            title: 'Ly do tu choi',
            input: 'textarea',
            inputPlaceholder: 'Nhap ly do...',
            showCancelButton: true,
            confirmButtonText: 'Tu choi',
            cancelButtonText: 'Huy',
        });
        const { ok } = await AttendanceAPI.rejectOT({
            overtime_request_id: id,
            reason: reason || '',
        });
        if (ok) this.load();
    },
};

/** team_attendance.html */
const TeamAttendance = {
    _params: { page: 1 },
    init() {
        this.bindFilters();
        this.load();
    },
    bindFilters() {
        document.getElementById('btn-team-filter')?.addEventListener('click', () => {
            this._params.page = 1;
            this._params.from_date   = document.getElementById('team_from')?.value || '';
            this._params.to_date     = document.getElementById('team_to')?.value   || '';
            this._params.employee_id = document.getElementById('team_emp_id')?.value || '';
            this.load();
        });
    },
    async load() {
        AttendanceUI.showLoading('team-table-body');
        const { ok, data } = await AttendanceAPI.getHistory(this._params);
        if (!ok || !data) return;
        this.render(data);
        AttendanceUI.renderPagination('team-pagination', data.pagination, p => {
            this._params.page = p;
            this.load();
        });
    },
    render(data) {
        const tbody = document.getElementById('team-table-body');
        if (!tbody) return;
        const rows  = data.data || [];
        if (!rows.length) {
            AttendanceUI.showEmpty('team-table-body', 'Khong co du lieu');
            return;
        }
        tbody.innerHTML = rows.map(r => `<tr>
            <td>${AttendanceUI.formatDate(r.date)}</td>
            <td>${r.full_name || '--'}</td>
            <td class="check-time">${r.check_in || '--'}</td>
            <td class="check-time">${r.check_out || '--'}</td>
            <td>${AttendanceUI.renderBadge(r.attendance_type)}</td>
            <td>${parseFloat(r.regular_hours || 0).toFixed(2)}h</td>
            <td>${r.late_minutes > 0
                ? '<span class="text-danger fw-bold">' + r.late_minutes + ' phut</span>'
                : '<span class="text-success">Dung gio</span>'}</td>
        </tr>`).join('');
    },
};

/** qr_scanner.html */
const QRScanner = {
    _stream: null,
    _scanning: false,

    init() {
        document.getElementById('btn-start-scan')?.addEventListener('click', () => this.start());
        document.getElementById('btn-stop-scan')?.addEventListener('click',  () => this.stop());
        document.getElementById('btn-manual-qr')?.addEventListener('click',  () => this.manualSubmit());
    },

    async start() {
        const videoEl = document.getElementById('qr-video');
        if (!videoEl) return;
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            videoEl.srcObject = this._stream;
            await videoEl.play();
            this._scanning = true;

            document.getElementById('btn-start-scan')?.classList.add('d-none');
            document.getElementById('btn-stop-scan')?.classList.remove('d-none');

            // Polling every 500ms via jsQR
            this._scanLoop(videoEl);
        } catch {
            window.showNotification('error', 'Khong the truy cap camera');
        }
    },

    _scanLoop(videoEl) {
        const canvas = document.createElement('canvas');
        const ctx    = canvas.getContext('2d');
        const tick   = () => {
            if (!this._scanning) return;
            if (videoEl.readyState === videoEl.HAVE_ENOUGH_DATA) {
                canvas.width  = videoEl.videoWidth;
                canvas.height = videoEl.videoHeight;
                ctx.drawImage(videoEl, 0, 0);
                const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                // jsQR must be loaded on the page
                if (typeof jsQR === 'function') {
                    const code = jsQR(imgData.data, imgData.width, imgData.height);
                    if (code?.data) {
                        this.handleQR(code.data);
                        return;
                    }
                }
            }
            requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    },

    async handleQR(content) {
        this.stop();
        const resultEl = document.getElementById('qr-result');
        if (resultEl) resultEl.textContent = 'QR: ' + content;
        await AttendanceAPI.processQR(content);
    },

    stop() {
        this._scanning = false;
        if (this._stream) {
            this._stream.getTracks().forEach(t => t.stop());
            this._stream = null;
        }
        const videoEl = document.getElementById('qr-video');
        if (videoEl) videoEl.srcObject = null;
        document.getElementById('btn-start-scan')?.classList.remove('d-none');
        document.getElementById('btn-stop-scan')?.classList.add('d-none');
    },

    async manualSubmit() {
        const input = document.getElementById('manual-qr-input');
        const val   = input?.value?.trim();
        if (!val) { window.showNotification('warning', 'Vui long nhap ma QR'); return; }
        await AttendanceAPI.processQR(val);
        if (input) input.value = '';
    },
};

/* ============================================================
   D. AUTO-INIT based on data-page attribute
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
    const page = document.body.dataset.page;
    switch (page) {
        case 'attendance-main':     AttendanceMain.init();      break;
        case 'attendance-history':  AttendanceHistory.init();   break;
        case 'attendance-summary':  AttendanceSummary.init();   break;
        case 'attendance-ot-req':   OvertimeRequest.init();     break;
        case 'attendance-ot-mgr':   ManagerOTApproval.init();   break;
        case 'attendance-team':     TeamAttendance.init();      break;
        case 'attendance-qr':       QRScanner.init();           break;
    }
});

// Expose for inline handlers if needed
window.AttendanceAPI  = AttendanceAPI;
window.AttendanceMain = AttendanceMain;
