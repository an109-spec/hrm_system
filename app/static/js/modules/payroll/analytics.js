/**
 * ANALYTICS.JS — Phân Tích Quỹ Lương
 * Route page: /payroll/analytics
 * API: GET /payroll/analytics/total-fund
 *
 * Yêu cầu: payroll_api.js phải được load TRƯỚC file này trong HTML:
 *   <script src="{{ url_for('static', filename='js/payroll/payroll_api.js') }}"></script>
 *   <script src="{{ url_for('static', filename='js/payroll/analytics.js') }}"></script>
 */
document.addEventListener('DOMContentLoaded', () => {

    // ─── State ────────────────────────────────────────────────────────────
    let trendChart   = null;
    let costPieChart = null;
    let deptChart    = null;
    let roleChart    = null;
    let lastResult   = null;        // Cache kết quả API để switch view không cần gọi lại
    let currentView  = 'dept';      // 'dept' | 'role' | 'month'

    // ─── DOM refs ─────────────────────────────────────────────────────────
    const periodTypeSelect = document.getElementById('periodType');
    const yearSelect       = document.getElementById('yearSelect');
    const monthSelect      = document.getElementById('monthSelect');
    const quarterSelect    = document.getElementById('quarterSelect');
    const analyzeBtn       = document.getElementById('btnAnalyze');
    const emptyState       = document.getElementById('emptyState');
    const kpiSection       = document.getElementById('kpiSection');
    const chartsSection    = document.getElementById('chartsSection');
    const breakdownSection = document.getElementById('breakdownSection');
    const tableSection     = document.getElementById('tableSection');
    const tableHead        = document.getElementById('analyticsTableHead');
    const tableBody        = document.getElementById('analyticsTableBody');
    const viewByDeptBtn    = document.getElementById('viewByDept');
    const viewByRoleBtn    = document.getElementById('viewByRole');
    const viewByMonthBtn   = document.getElementById('viewByMonth');

    // ─── Init ─────────────────────────────────────────────────────────────
    _syncPeriodControls();
    _setDefaultSelects();

    // ─── Events ───────────────────────────────────────────────────────────
    periodTypeSelect?.addEventListener('change', _syncPeriodControls);
    analyzeBtn?.addEventListener('click', handleAnalyze);

    viewByDeptBtn?.addEventListener('click',  () => _switchTableView('dept'));
    viewByRoleBtn?.addEventListener('click',  () => _switchTableView('role'));
    viewByMonthBtn?.addEventListener('click', () => _switchTableView('month'));

    // ─── Đồng bộ hiển thị tháng / quý theo period_type ───────────────────
    function _syncPeriodControls() {
        const type = periodTypeSelect?.value;
        if (!monthSelect || !quarterSelect) return;

        monthSelect.classList.toggle('d-none',   type !== 'month');
        quarterSelect.classList.toggle('d-none', type !== 'quarter');
    }

    function _setDefaultSelects() {
        const now = new Date();
        if (yearSelect)  yearSelect.value  = now.getFullYear();
        if (monthSelect) monthSelect.value = now.getMonth() + 1;
    }

    // ─── Handler chính ────────────────────────────────────────────────────
    async function handleAnalyze() {
        const periodType = periodTypeSelect?.value || 'month';
        const year       = parseInt(yearSelect?.value);
        const month      = periodType === 'month'   ? parseInt(monthSelect?.value)   : undefined;
        const quarter    = periodType === 'quarter' ? parseInt(quarterSelect?.value) : undefined;

        if (!year) { _notify('warning', 'Vui lòng chọn năm.'); return; }
        if (periodType === 'month'   && !month)   { _notify('warning', 'Vui lòng chọn tháng.');  return; }
        if (periodType === 'quarter' && !quarter) { _notify('warning', 'Vui lòng chọn quý.');    return; }

        _setAnalyzing(true);

        try {
            const filters = { period_type: periodType, year };
            if (month)   filters.month   = month;
            if (quarter) filters.quarter = quarter;

            const res = await PayrollAPI.getTotalPayrollFund(filters);

            if (!res.ok) {
                const msg = res.data?.text || res.data?.swal?.text || 'Không lấy được dữ liệu phân tích.';
                _notify('error', msg);
                return;
            }

            lastResult   = res.data?.data || {};
            currentView  = 'dept';

            _renderKPICards(lastResult);
            _renderTrendChart(lastResult);
            _renderCostPieChart(lastResult);
            _renderDeptBarChart(lastResult);
            _renderRoleBarChart(lastResult);
            _renderTable(lastResult, 'dept');
            _showSections();

        } catch (err) {
            console.error('handleAnalyze error:', err);
            _notify('error', 'Lỗi kết nối máy chủ.');
        } finally {
            _setAnalyzing(false);
        }
    }

    // ─── KPI Cards ────────────────────────────────────────────────────────
    function _renderKPICards(data) {
        const s = data.summary || {};

        _setText('kpiLaborCost',          _fmt(s.total_labor_cost));
        _setText('kpiNetPaid',            _fmt(s.total_net));
        _setText('kpiInsuranceEmployer',  _fmt(s.total_insurance_employer));
        _setText('kpiTax',                _fmt(s.total_pit_tax));
        _setText('kpiAllowance',          _fmt(s.total_allowance));
        _setText('kpiPenalty',            _fmt(s.total_penalty));
        _setText('kpiEmployeeCount',      data.employee_count ?? '--');
        _setText('kpiSalaryCount',        data.salary_count   ?? '--');
    }

    // ─── Trend Chart (Labor Cost theo tháng) ──────────────────────────────
    function _renderTrendChart(data) {
        const canvas = document.getElementById('trendChart');
        if (!canvas || !window.Chart) return;

        const byPeriod = data.by_period || [];

        // Nếu chỉ có 1 điểm (period=month) thì ẩn chart này, không có gì để trend
        if (byPeriod.length <= 1 && data.period?.type === 'month') {
            canvas.closest('.chart-card')?.classList.add('d-none');
            return;
        }
        canvas.closest('.chart-card')?.classList.remove('d-none');

        const labels    = byPeriod.map(p => p.label);
        const laborCost = byPeriod.map(p => p.total_labor_cost);
        const netData   = byPeriod.map(p => p.total_net);
        const grossData = byPeriod.map(p => p.total_gross);

        if (trendChart) trendChart.destroy();

        trendChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Tổng chi phí nhân sự',
                        data: laborCost,
                        backgroundColor: 'rgba(99, 102, 241, 0.75)',
                        borderRadius: 5,
                        order: 2,
                    },
                    {
                        label: 'Lương thực nhận',
                        data: netData,
                        type: 'line',
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16,185,129,0.08)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        order: 1,
                    },
                    {
                        label: 'Gross',
                        data: grossData,
                        type: 'line',
                        borderColor: '#f59e0b',
                        backgroundColor: 'transparent',
                        borderDash: [5, 3],
                        tension: 0.4,
                        pointRadius: 3,
                        order: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.dataset.label}: ${_fmt(ctx.raw)}`,
                        },
                    },
                },
                scales: {
                    y: { ticks: { callback: v => _fmtShort(v) } },
                },
            },
        });
    }

    // ─── Cost Pie Chart (phân bổ chi phí) ────────────────────────────────
    function _renderCostPieChart(data) {
        const canvas = document.getElementById('costPieChart');
        if (!canvas || !window.Chart) return;

        const s = data.summary || {};

        const netSalary    = s.total_net                 || 0;
        const insEmployer  = s.total_insurance_employer  || 0;
        const insEmployee  = s.total_insurance_employee  || 0;
        const tax          = s.total_pit_tax             || 0;
        const allowance    = s.total_allowance           || 0;
        const penalty      = s.total_penalty             || 0;

        if (costPieChart) costPieChart.destroy();

        costPieChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: [
                    'Lương thực nhận',
                    'BH NSDLĐ đóng thêm',
                    'BH người lao động',
                    'Thuế TNCN',
                    'Phụ cấp',
                    'Tiền phạt (thu về)',
                ],
                datasets: [{
                    data: [netSalary, insEmployer, insEmployee, tax, allowance, penalty],
                    backgroundColor: [
                        '#6366f1', '#f59e0b', '#10b981',
                        '#ef4444', '#0ea5e9', '#6b7280',
                    ],
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct   = total ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${_fmt(ctx.raw)} (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    // ─── Dept Bar Chart ───────────────────────────────────────────────────
    function _renderDeptBarChart(data) {
        const canvas = document.getElementById('deptChart');
        if (!canvas || !window.Chart) return;

        const byDept = (data.by_department || []).slice(0, 10);   // top 10

        if (deptChart) deptChart.destroy();

        deptChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: byDept.map(d => d.department),
                datasets: [
                    {
                        label: 'Chi phí nhân sự',
                        data: byDept.map(d => d.total_labor_cost),
                        backgroundColor: 'rgba(99,102,241,0.8)',
                        borderRadius: 4,
                    },
                    {
                        label: 'Lương thực nhận',
                        data: byDept.map(d => d.total_net),
                        backgroundColor: 'rgba(16,185,129,0.7)',
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                indexAxis: 'y',          // horizontal bar
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: { label: ctx => ` ${ctx.dataset.label}: ${_fmt(ctx.raw)}` },
                    },
                },
                scales: {
                    x: { ticks: { callback: v => _fmtShort(v) } },
                },
            },
        });
    }

    // ─── Role Bar Chart ───────────────────────────────────────────────────
    function _renderRoleBarChart(data) {
        const canvas = document.getElementById('roleChart');
        if (!canvas || !window.Chart) return;

        const byRole = data.by_role || [];

        if (roleChart) roleChart.destroy();

        roleChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: byRole.map(r => r.role),
                datasets: [
                    {
                        label: 'Chi phí nhân sự',
                        data: byRole.map(r => r.total_labor_cost),
                        backgroundColor: [
                            '#6366f1', '#f59e0b', '#10b981', '#ef4444',
                        ],
                        borderRadius: 5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const row = byRole[ctx.dataIndex] || {};
                                return [
                                    ` Chi phí: ${_fmt(ctx.raw)}`,
                                    ` Gross:   ${_fmt(row.total_gross)}`,
                                    ` Net:     ${_fmt(row.total_net)}`,
                                    ` Số phiếu: ${row.salary_count}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    y: { ticks: { callback: v => _fmtShort(v) } },
                },
            },
        });
    }

    // ─── Detail Table ─────────────────────────────────────────────────────
    function _renderTable(data, view) {
        if (!tableHead || !tableBody) return;

        if (view === 'dept') {
            _renderDeptTable(data.by_department || []);
        } else if (view === 'role') {
            _renderRoleTable(data.by_role || []);
        } else {
            _renderMonthTable(data.by_period || []);
        }
    }

    function _renderDeptTable(rows) {
        tableHead.innerHTML = `<tr>
            <th>Phòng ban</th>
            <th class="text-center">Số phiếu</th>
            <th class="text-end">Gross</th>
            <th class="text-end">Phụ cấp</th>
            <th class="text-end">BH NLĐ</th>
            <th class="text-end">Thuế TNCN</th>
            <th class="text-end text-success">Net</th>
            <th class="text-end">BH NSDLĐ</th>
            <th class="text-end fw-bold">Tổng CP</th>
        </tr>`;

        if (!rows.length) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-muted">Không có dữ liệu</td></tr>`;
            return;
        }

        tableBody.innerHTML = rows.map(r => `
            <tr>
                <td class="fw-semibold">${_escHtml(r.department)}</td>
                <td class="text-center">${r.salary_count}</td>
                <td class="text-end">${_fmt(r.total_gross)}</td>
                <td class="text-end text-info">${_fmt(r.total_allowance)}</td>
                <td class="text-end text-warning">${_fmt(r.total_insurance_employee)}</td>
                <td class="text-end text-danger">${_fmt(r.total_pit_tax)}</td>
                <td class="text-end text-success fw-semibold">${_fmt(r.total_net)}</td>
                <td class="text-end text-secondary">${_fmt(r.total_insurance_employer)}</td>
                <td class="text-end fw-bold text-primary">${_fmt(r.total_labor_cost)}</td>
            </tr>
        `).join('');
    }

    function _renderRoleTable(rows) {
        tableHead.innerHTML = `<tr>
            <th>Role</th>
            <th class="text-center">Số phiếu</th>
            <th class="text-end">Gross</th>
            <th class="text-end">BH NLĐ</th>
            <th class="text-end">Thuế TNCN</th>
            <th class="text-end text-success">Net</th>
            <th class="text-end">BH NSDLĐ</th>
            <th class="text-end fw-bold">Tổng CP</th>
        </tr>`;

        if (!rows.length) {
            tableBody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">Không có dữ liệu</td></tr>`;
            return;
        }

        tableBody.innerHTML = rows.map(r => `
            <tr>
                <td><span class="badge bg-secondary">${_escHtml(r.role)}</span></td>
                <td class="text-center">${r.salary_count}</td>
                <td class="text-end">${_fmt(r.total_gross)}</td>
                <td class="text-end text-warning">${_fmt(r.total_insurance_employee)}</td>
                <td class="text-end text-danger">${_fmt(r.total_pit_tax)}</td>
                <td class="text-end text-success fw-semibold">${_fmt(r.total_net)}</td>
                <td class="text-end text-secondary">${_fmt(r.total_insurance_employer)}</td>
                <td class="text-end fw-bold text-primary">${_fmt(r.total_labor_cost)}</td>
            </tr>
        `).join('');
    }

    function _renderMonthTable(rows) {
        tableHead.innerHTML = `<tr>
            <th>Kỳ</th>
            <th class="text-center">Số phiếu</th>
            <th class="text-end">Gross</th>
            <th class="text-end">Phụ cấp</th>
            <th class="text-end">BH NLĐ</th>
            <th class="text-end">Thuế</th>
            <th class="text-end text-success">Net</th>
            <th class="text-end">BH NSDLĐ</th>
            <th class="text-end fw-bold">Tổng CP</th>
        </tr>`;

        if (!rows.length) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-muted">Không có dữ liệu</td></tr>`;
            return;
        }

        tableBody.innerHTML = rows.map(r => `
            <tr>
                <td class="fw-semibold">${_escHtml(r.label)}</td>
                <td class="text-center">${r.salary_count}</td>
                <td class="text-end">${_fmt(r.total_gross)}</td>
                <td class="text-end text-info">${_fmt(r.total_allowance)}</td>
                <td class="text-end text-warning">${_fmt(r.total_insurance_employee)}</td>
                <td class="text-end text-danger">${_fmt(r.total_pit_tax)}</td>
                <td class="text-end text-success fw-semibold">${_fmt(r.total_net)}</td>
                <td class="text-end text-secondary">${_fmt(r.total_insurance_employer)}</td>
                <td class="text-end fw-bold text-primary">${_fmt(r.total_labor_cost)}</td>
            </tr>
        `).join('');
    }

    // ─── Switch table view (không gọi lại API) ────────────────────────────
    function _switchTableView(view) {
        if (!lastResult) return;
        currentView = view;

        // Cập nhật active button
        [viewByDeptBtn, viewByRoleBtn, viewByMonthBtn].forEach(btn => btn?.classList.remove('active'));
        if (view === 'dept')  viewByDeptBtn?.classList.add('active');
        if (view === 'role')  viewByRoleBtn?.classList.add('active');
        if (view === 'month') viewByMonthBtn?.classList.add('active');

        _renderTable(lastResult, view);
    }

    // ─── Show / Hide sections ─────────────────────────────────────────────
    function _showSections() {
        emptyState?.classList.add('d-none');

        // Dùng removeAttribute thay vì style.display để không xung đột với Bootstrap d-none
        [kpiSection, chartsSection, breakdownSection, tableSection].forEach(el => {
            if (!el) return;
            el.style.display = '';          // bỏ inline display:none từ HTML
            el.classList.remove('d-none');
        });
    }

    // ─── UI helpers ───────────────────────────────────────────────────────
    function _setAnalyzing(state) {
        if (!analyzeBtn) return;
        analyzeBtn.disabled  = state;
        analyzeBtn.innerHTML = state
            ? '<i class="fas fa-spinner fa-spin me-1"></i>Đang phân tích...'
            : '<i class="fas fa-chart-bar me-1"></i>Phân tích';
    }

    function _notify(icon, msg) {
        if (window.Swal) {
            Swal.fire({ icon, text: msg, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
        } else {
            alert(msg);
        }
    }

    // ─── Format helpers ───────────────────────────────────────────────────
    function _fmt(val) {
        if (val == null) return '--';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
    }

    function _fmtShort(val) {
        if (val >= 1_000_000_000) return (val / 1_000_000_000).toFixed(1) + ' tỷ';
        if (val >= 1_000_000)     return (val / 1_000_000).toFixed(1)     + ' tr';
        if (val >= 1_000)         return (val / 1_000).toFixed(0)         + 'k';
        return val;
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

});