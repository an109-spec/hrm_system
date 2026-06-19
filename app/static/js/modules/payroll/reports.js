/**
 * REPORTS.JS — Báo Cáo Chi Tiết Lương
 * Route page: /payroll/reports  (template: reports.html)
 * API chính: GET /payroll/all?month=&year=&status=&dept_id=
 * API phụ:   GET /payroll/<salary_id>  (chi tiết từng phiếu)
 *
 * Yêu cầu: payroll_api.js phải được load TRƯỚC file này trong HTML:
 *   <script src="{{ url_for('static', filename='js/payroll/payroll_api.js') }}"></script>
 *   <script src="{{ url_for('static', filename='js/payroll/reports.js') }}"></script>
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── State ────────────────────────────────────────────────────────────
    let allRows     = [];       // Dữ liệu gốc từ API (chưa lọc client-side)
    let filteredRows= [];       // Sau khi lọc bằng ô search
    let sortField   = 'employee_name';
    let sortAsc     = true;
    let slipModal   = null;     // Bootstrap Modal instance

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const rptMonth      = document.getElementById('rptMonth');
    const rptYear       = document.getElementById('rptYear');
    const rptDept       = document.getElementById('rptDept');
    const rptStatus     = document.getElementById('rptStatus');
    const rptSearch     = document.getElementById('rptSearch');
    const genBtn        = document.getElementById('btnGenReport');
    const exportCsvBtn  = document.getElementById('btnExportCSV');
    const printBtn      = document.getElementById('btnPrint');
    const tableBody     = document.getElementById('reportTableBody');
    const tableFoot     = document.getElementById('reportTableFoot');
    const recordCount   = document.getElementById('rptRecordCount');
    const tableTitle    = document.getElementById('rptTableTitle');
    const totalsSection = document.getElementById('reportTotals');

    // Sort buttons
    const sortByNameBtn = document.getElementById('sortByName');
    const sortByNetBtn  = document.getElementById('sortByNet');
    const sortByDeptBtn = document.getElementById('sortByDept');

    // Summary totals
    const rptTotalNet       = document.getElementById('rptTotalNet');
    const rptTotalGross     = document.getElementById('rptTotalGross');
    const rptTotalAllowance = document.getElementById('rptTotalAllowance');
    const rptTotalInsurance = document.getElementById('rptTotalInsurance');
    const rptTotalTax       = document.getElementById('rptTotalTax');
    const rptCount          = document.getElementById('rptCount');

    // ─── Init ─────────────────────────────────────────────────────────────
    _setDefaults();
    _loadDepartments();
    _initModal();

    // ─── Events ───────────────────────────────────────────────────────────
    genBtn?.addEventListener('click', handleGenReport);

    exportCsvBtn?.addEventListener('click', exportCSV);

    rptSearch?.addEventListener('input', _debounce(() => {
        _applyClientFilter();
        _renderTable(filteredRows);
    }, 300));

    sortByNameBtn?.addEventListener('click', () => _sortAndRender('employee_name', sortByNameBtn));
    sortByNetBtn?.addEventListener('click',  () => _sortAndRender('net_salary',    sortByNetBtn));
    sortByDeptBtn?.addEventListener('click', () => _sortAndRender('department',    sortByDeptBtn));

    // ─── Default values ───────────────────────────────────────────────────
    function _setDefaults() {
        const now = new Date();
        if (rptMonth) rptMonth.value = now.getMonth() + 1;
        if (rptYear)  rptYear.value  = now.getFullYear();
    }

    // ─── Load phòng ban cho dropdown ──────────────────────────────────────
    async function _loadDepartments() {
        if (!rptDept) return;
        try {
            // Lấy danh sách phòng ban từ dữ liệu lương tháng hiện tại (lazy approach)
            // Nếu dự án có API riêng /departments thì thay thế bằng fetch đó
            const now = new Date();
            const res = await PayrollAPI.getAllSalaries(now.getMonth() + 1, now.getFullYear());
            if (!res.ok) return;

            const items = res.data?.data?.items || [];
            const depts = [...new Set(items.map(i => i.department).filter(Boolean))].sort();

            rptDept.innerHTML = '<option value="">Tất cả</option>';
            depts.forEach(d => {
                const opt = document.createElement('option');
                opt.value       = d;   // dùng để lọc client-side vì /all không nhận dept name
                opt.textContent = d;
                rptDept.appendChild(opt);
            });
        } catch (_) { /* yên lặng nếu lỗi */ }
    }

    // ─── Bootstrap Modal ──────────────────────────────────────────────────
    function _initModal() {
        const modalEl = document.getElementById('slipModal');
        if (modalEl && window.bootstrap) {
            slipModal = new bootstrap.Modal(modalEl);
        }
    }

    // ─── Generate Report ──────────────────────────────────────────────────
    async function handleGenReport() {
        const month  = parseInt(rptMonth?.value);
        const year   = parseInt(rptYear?.value);

        if (!month || !year) {
            _notify('warning', 'Vui lòng chọn tháng và năm.');
            return;
        }

        _setLoading(true);

        try {
            const filters = {};
            if (rptStatus?.value) filters.status = rptStatus.value;

            const res = await PayrollAPI.getAllSalaries(month, year, filters);

            if (!res.ok) {
                _notify('error', res.data?.swal?.text || res.data?.text || 'Không tải được dữ liệu.');
                _setLoading(false);
                return;
            }

            const payload = res.data?.data || {};
            allRows       = payload.items  || [];

            // Lọc phòng ban phía client vì API /all nhận dept_id chứ không nhận dept name
            _applyClientFilter();
            _renderSummary(filteredRows);
            _renderTable(filteredRows);
            _renderFooter(filteredRows);

            // Cập nhật tiêu đề và bật nút
            if (tableTitle)   tableTitle.textContent  = `Báo cáo lương tháng ${String(month).padStart(2,'0')}/${year}`;
            if (exportCsvBtn) exportCsvBtn.disabled   = false;
            if (printBtn)     printBtn.disabled        = false;
            if (totalsSection) {
                totalsSection.style.display = '';
                totalsSection.classList.remove('d-none');
            }

        } catch (err) {
            console.error('handleGenReport error:', err);
            _notify('error', 'Lỗi kết nối máy chủ.');
        } finally {
            _setLoading(false);
        }
    }

    // ─── Client-side filter (tìm kiếm + phòng ban) ───────────────────────
    function _applyClientFilter() {
        const keyword  = (rptSearch?.value  || '').toLowerCase().trim();
        const deptName = (rptDept?.value    || '').toLowerCase().trim();

        filteredRows = allRows.filter(row => {
            const matchKeyword =
                !keyword ||
                (row.employee_name || '').toLowerCase().includes(keyword) ||
                (row.employee_id   || '').toString().includes(keyword);

            const matchDept =
                !deptName ||
                (row.department || '').toLowerCase() === deptName;

            return matchKeyword && matchDept;
        });
    }

    // ─── Sort ─────────────────────────────────────────────────────────────
    function _sortAndRender(field, activeBtn) {
        if (sortField === field) {
            sortAsc = !sortAsc;
        } else {
            sortField = field;
            sortAsc   = true;
        }

        // Update active button
        [sortByNameBtn, sortByNetBtn, sortByDeptBtn].forEach(btn => btn?.classList.remove('active'));
        activeBtn?.classList.add('active');

        filteredRows.sort((a, b) => {
            const av = a[field] ?? '';
            const bv = b[field] ?? '';
            if (typeof av === 'number') return sortAsc ? av - bv : bv - av;
            return sortAsc
                ? String(av).localeCompare(String(bv), 'vi')
                : String(bv).localeCompare(String(av), 'vi');
        });

        _renderTable(filteredRows);
    }

    // ─── Render Summary totals ────────────────────────────────────────────
    function _renderSummary(rows) {
        const totals = _calcTotals(rows);
        _setText('rptTotalNet',       _fmt(totals.net));
        _setText('rptTotalGross',     _fmt(totals.gross));
        _setText('rptTotalAllowance', _fmt(totals.allowance));
        _setText('rptTotalInsurance', _fmt(totals.insurance));
        _setText('rptTotalTax',       _fmt(totals.tax));
        _setText('rptCount',          rows.length);

        if (recordCount) recordCount.textContent = `${rows.length} phiếu lương`;
    }

    // ─── Render Table ─────────────────────────────────────────────────────
    function _renderTable(rows) {
        if (!tableBody) return;

        if (!rows.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="15" class="text-center py-5 text-muted">
                        <i class="fas fa-file-search fa-3x mb-3 d-block opacity-25"></i>
                        Không tìm thấy dữ liệu phù hợp
                    </td>
                </tr>`;
            if (tableFoot) tableFoot.style.display = 'none';
            return;
        }

        tableBody.innerHTML = rows.map((item, idx) => `
            <tr>
                <td class="text-muted small">${idx + 1}</td>
                <td>
                    <span class="badge bg-light text-dark border">
                        EMP${String(item.employee_id).padStart(5, '0')}
                    </span>
                </td>
                <td class="fw-semibold">${_escHtml(item.employee_name)}</td>
                <td>
                    <span class="badge bg-light text-secondary border">${_escHtml(item.department || '--')}</span>
                </td>
                <td class="text-end">${_fmt(item.basic_salary)}</td>
                <td class="text-end text-info">${_fmt(item.total_allowance)}</td>
                <td class="text-end text-secondary">${_fmt(item.overtime_salary)}</td>
                <td class="text-end text-warning">${_fmt(item.insurance)}</td>
                <td class="text-end text-danger">${_fmt(item.tax)}</td>
                <td class="text-end text-danger">${_fmt(item.penalty)}</td>
                <td class="text-end fw-bold text-success">${_fmt(item.net_salary)}</td>
                <td class="text-center">${item.number_of_dependents ?? 0}</td>
                <td>
                    <span class="badge ${_statusClass(item.status)}">${item.status_label}</span>
                </td>
                <td class="text-center">
                    ${item.has_complaint
                        ? `<span class="badge bg-warning text-dark" title="${_escHtml(item.complaint_status_label)}">
                               <i class="fas fa-exclamation-triangle"></i>
                           </span>`
                        : `<span class="text-muted small">--</span>`
                    }
                </td>
                <td class="no-print">
                    <button class="btn btn-sm btn-outline-primary"
                        onclick="openSlipDetail(${item.salary_id})"
                        title="Xem phiếu lương">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        if (tableFoot) tableFoot.style.display = '';
    }

    // ─── Render Footer totals ─────────────────────────────────────────────
    function _renderFooter(rows) {
        if (!tableFoot || !rows.length) return;

        const totals = _calcTotals(rows);
        _setText('ftBasic',     _fmt(totals.basic));
        _setText('ftAllowance', _fmt(totals.allowance));
        _setText('ftOT',        _fmt(totals.overtime));
        _setText('ftInsurance', _fmt(totals.insurance));
        _setText('ftTax',       _fmt(totals.tax));
        _setText('ftDeduction', _fmt(totals.deduction));
        _setText('ftNet',       _fmt(totals.net));
    }

    function _calcTotals(rows) {
        return rows.reduce((acc, r) => ({
            basic:     acc.basic     + (r.basic_salary    || 0),
            allowance: acc.allowance + (r.total_allowance || 0),
            overtime:  acc.overtime  + (r.overtime_salary || 0),
            insurance: acc.insurance + (r.insurance       || 0),
            tax:       acc.tax       + (r.tax             || 0),
            deduction: acc.deduction + (r.penalty         || 0),
            net:       acc.net       + (r.net_salary      || 0),
            gross:     acc.gross     + (r.basic_salary    || 0) + (r.total_allowance || 0),
        }), { basic: 0, allowance: 0, overtime: 0, insurance: 0, tax: 0, deduction: 0, net: 0, gross: 0 });
    }

    // ─── Open Slip Detail Modal ───────────────────────────────────────────
    window.openSlipDetail = async function(salaryId) {
        const bodyEl = document.getElementById('slipModalBody');
        if (bodyEl) bodyEl.innerHTML = '<div class="text-center py-5"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';

        slipModal?.show();

        try {
            const res = await PayrollAPI.getPayrollDetail(salaryId);

            if (!res.ok) {
                if (bodyEl) bodyEl.innerHTML = `<div class="alert alert-danger">${res.data?.swal?.text || 'Lỗi tải dữ liệu.'}</div>`;
                return;
            }

            const d = res.data?.data || {};
            if (bodyEl) bodyEl.innerHTML = _buildSlipHTML(d);

        } catch (err) {
            console.error('openSlipDetail error:', err);
            if (bodyEl) bodyEl.innerHTML = '<div class="alert alert-danger">Lỗi kết nối máy chủ.</div>';
        }
    };

    function _buildSlipHTML(d) {
        const emp    = d.employee    || {};
        const note   = d.note_data   || {};
        const manual = d.manual_adjustments || {};

        // Lấy breakdown từ note_data nếu có
        const bd = note.breakdown || {};

        // Hàm lấy ưu tiên từ breakdown, fallback về trường trực tiếp
        const _get = (bdKey, directVal) => bd[bdKey] ?? directVal ?? 0;

        return `
        <div class="row g-3">
            <!-- Thông tin nhân viên -->
            <div class="col-md-6">
                <h6 class="text-muted text-uppercase small fw-bold mb-2">Thông tin nhân viên</h6>
                <table class="table table-sm table-borderless mb-0">
                    <tr><td class="text-muted" style="width:140px">Mã NV</td>
                        <td class="fw-semibold">${_escHtml(d.employee_code || '')}</td></tr>
                    <tr><td class="text-muted">Họ tên</td>
                        <td class="fw-semibold">${_escHtml(d.employee_name || '')}</td></tr>
                    <tr><td class="text-muted">Phòng ban</td>
                        <td>${_escHtml(d.department || '--')}</td></tr>
                    <tr><td class="text-muted">Chức vụ</td>
                        <td>${_escHtml(d.position   || '--')}</td></tr>
                </table>
            </div>

            <!-- Tình trạng kỳ lương -->
            <div class="col-md-6">
                <h6 class="text-muted text-uppercase small fw-bold mb-2">Kỳ lương</h6>
                <table class="table table-sm table-borderless mb-0">
                    <tr><td class="text-muted" style="width:140px">Tháng/Năm</td>
                        <td class="fw-semibold">${String(d.month).padStart(2,'0')}/${d.year}</td></tr>
                    <tr><td class="text-muted">Trạng thái</td>
                        <td><span class="badge ${_statusClass(d.status)}">${d.status_label}</span></td></tr>
                    <tr><td class="text-muted">Ngày công TC</td>
                        <td>${_get('standard_work_days', d.standard_work_days) || '--'}</td></tr>
                    <tr><td class="text-muted">Ngày công TT</td>
                        <td>${_get('total_work_days',    d.total_work_days)    || '--'}</td></tr>
                </table>
            </div>

            <!-- Thu nhập -->
            <div class="col-md-6">
                <h6 class="text-muted text-uppercase small fw-bold mb-2">
                    <i class="fas fa-plus-circle text-success me-1"></i>Thu nhập
                </h6>
                <table class="table table-sm table-borderless mb-0">
                    <tr><td class="text-muted">Lương cơ bản</td>
                        <td class="text-end text-success">${_fmt(d.basic_salary)}</td></tr>
                    <tr><td class="text-muted">Phụ cấp</td>
                        <td class="text-end text-success">+${_fmt(d.allowance)}</td></tr>
                    <tr><td class="text-muted">Tăng ca</td>
                        <td class="text-end text-success">+${_fmt(d.overtime_hours)}</td></tr>
                    <tr class="border-top fw-bold">
                        <td>Tổng thu nhập gộp</td>
                        <td class="text-end text-success">
                            ${_fmt((d.basic_salary || 0) + (d.allowance || 0) + (d.overtime_hours || 0))}
                        </td>
                    </tr>
                </table>
            </div>

            <!-- Khấu trừ -->
            <div class="col-md-6">
                <h6 class="text-muted text-uppercase small fw-bold mb-2">
                    <i class="fas fa-minus-circle text-danger me-1"></i>Khấu trừ
                </h6>
                <table class="table table-sm table-borderless mb-0">
                    <tr><td class="text-muted">Bảo hiểm</td>
                        <td class="text-end text-danger">-${_fmt(d.penalty)}</td></tr>
                    <tr><td class="text-muted">Thuế TNCN</td>
                        <td class="text-end text-danger">-${_fmt(d.penalty)}</td></tr>
                    <tr><td class="text-muted">Phạt đi muộn</td>
                        <td class="text-end text-danger">-${_fmt(d.penalty)}</td></tr>
                    <tr class="border-top fw-bold">
                        <td>Tổng khấu trừ</td>
                        <td class="text-end text-danger">
                            -${_fmt((d.penalty || 0))}
                        </td>
                    </tr>
                </table>
            </div>
        </div>

        <!-- Thực lĩnh -->
        <div class="mt-3 p-3 rounded text-center"
             style="background:linear-gradient(135deg,#6366f1,#4f46e5); color:#fff;">
            <div class="small mb-1 opacity-75">THỰC LĨNH</div>
            <div class="fw-bold fs-3">${_fmt(d.net_salary)}</div>
        </div>

        <!-- Ghi chú điều chỉnh thủ công (nếu có) -->
        ${manual.note ? `
        <div class="alert alert-light border mt-3 mb-0">
            <i class="fas fa-sticky-note me-1 text-warning"></i>
            <strong>Ghi chú:</strong> ${_escHtml(manual.note)}
        </div>` : ''}
        `;
    }

    // ─── Export CSV ───────────────────────────────────────────────────────
    function exportCSV() {
        if (!filteredRows.length) {
            _notify('warning', 'Không có dữ liệu để xuất.');
            return;
        }

        const month = rptMonth?.value || '';
        const year  = rptYear?.value  || '';

        const headers = [
            'STT', 'Mã NV', 'Họ và tên', 'Phòng ban',
            'Lương CB', 'Phụ cấp', 'Tăng ca',
            'Bảo hiểm', 'Thuế TNCN', 'Khấu trừ',
            'Thực lĩnh', 'NPT', 'Trạng thái', 'Khiếu nại',
        ];

        const rows = filteredRows.map((r, i) => [
            i + 1,
            `EMP${String(r.employee_id).padStart(5, '0')}`,
            r.employee_name  || '',
            r.department     || '',
            r.basic_salary   || 0,
            r.total_allowance|| 0,
            r.overtime_salary|| 0,
            r.insurance      || 0,
            r.tax            || 0,
            r.penalty        || 0,
            r.net_salary     || 0,
            r.number_of_dependents ?? 0,
            r.status_label   || r.status || '',
            r.has_complaint ? r.complaint_status_label : 'Không có',
        ]);

        const csvContent = [headers, ...rows]
            .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
            .join('\n');

        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = `bao_cao_luong_${String(month).padStart(2,'0')}_${year}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _setLoading(state) {
        if (!tableBody) return;
        if (state) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="15" class="text-center py-5 text-muted">
                        <i class="fas fa-spinner fa-spin fa-2x mb-2 d-block"></i>
                        Đang tải dữ liệu...
                    </td>
                </tr>`;
        }
        if (genBtn) {
            genBtn.disabled  = state;
            genBtn.innerHTML = state
                ? '<i class="fas fa-spinner fa-spin"></i>'
                : '<i class="fas fa-search"></i>';
        }
    }

    function _statusClass(status) {
        const map = {
            draft:     'bg-secondary',
            pending:   'bg-warning text-dark',
            approved:  'bg-info text-dark',
            locked:    'bg-primary',
            paid:      'bg-success',
            rejected:  'bg-danger',
            complaint: 'bg-danger',
            sent:      'bg-info text-dark',
        };
        return map[status] || 'bg-secondary';
    }

    function _fmt(val) {
        if (val == null) return '--';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
    }

    function _setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val ?? '--';
    }

    function _escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

    function _notify(icon, msg) {
        if (window.Swal) {
            Swal.fire({ icon, text: msg, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
        } else {
            alert(msg);
        }
    }

    function _debounce(fn, delay) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    }

});