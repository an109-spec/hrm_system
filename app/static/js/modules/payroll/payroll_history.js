document.addEventListener('DOMContentLoaded', () => {

    // ─── State ────────────────────────────────────────────────────────────
    let currentYear = new Date().getFullYear();
    let allItems    = [];
    let incomeChart = null;

    // ─── DOM refs (Đã sửa khớp 100% với HTML) ─────────────────────────────
    const yearSelect      = document.getElementById('filterYear');
    const statusFilter    = document.getElementById('filterStatus');
    const applyBtn        = document.getElementById('btnFilter');
    const tableBody       = document.getElementById('payrollTableBody');

    // Summary Cards
    const sumNetSalary    = document.getElementById('sumNetSalary');
    const sumStatus       = document.getElementById('sumStatus');
    const sumPaymentDate  = document.getElementById('sumPaymentDate');
    const sumDependents   = document.getElementById('sumDependents');

    // Chart
    const chartCanvas     = document.getElementById('salaryChart');

    // ─── Init ─────────────────────────────────────────────────────────────
    // Tự động set select filter năm thành năm hiện tại
    if (yearSelect && !yearSelect.value) {
        yearSelect.value = currentYear.toString();
    }
    loadHistory();

    // ─── Events ───────────────────────────────────────────────────────────
    applyBtn?.addEventListener('click', loadHistory);

    // ─── Functions ────────────────────────────────────────────────────────
    async function loadHistory() {
        currentYear = parseInt(yearSelect?.value) || new Date().getFullYear();

        const filters = {};
        if (statusFilter?.value) filters.status = statusFilter.value;

        _setLoading(true);

        try {
            const res = await PayrollAPI.getMyPayrollHistory(currentYear, filters);

            if (!res.ok) {
                showNotification('error', res.data?.swal?.text || 'Không thể tải dữ liệu lịch sử lương.');
                _setLoading(false);
                return;
            }

            const payload = res.data?.data || {};
            allItems = payload.items || [];

            _renderSummary(payload.summary || {});
            _renderTable(allItems);
            _renderChart(allItems);

        } catch (err) {
            console.error('loadHistory error:', err);
            showNotification('error', 'Lỗi kết nối máy chủ.');
        } finally {
            _setLoading(false);
        }
    }

    function _setLoading(state) {
        if (tableBody) {
            tableBody.style.opacity = state ? '0.4' : '1';
            if (state) {
                tableBody.innerHTML = `<tr><td colspan="11" class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin me-2"></i>Đang tải dữ liệu...</td></tr>`;
            }
        }
    }

    function _renderSummary(summary) {
        if (sumNetSalary)   sumNetSalary.textContent   = _fmt(summary.net_salary);
        if (sumStatus)      sumStatus.textContent      = summary.status || '--';
        if (sumPaymentDate) sumPaymentDate.textContent = summary.payment_date || '--';
        if (sumDependents)  sumDependents.textContent  = summary.dependents_count || '--'; 
    }

    function _renderTable(items) {
        if (!tableBody) return;

        if (!items.length) {
            tableBody.innerHTML = `<tr><td colspan="11" class="text-center py-4 text-muted">Không có dữ liệu.</td></tr>`;
            return;
        }

        tableBody.innerHTML = items.map(item => `
            <tr>
                <td class="fw-semibold">Tháng ${String(item.month).padStart(2,'0')}/${item.year}</td>
                <td>${_fmt(item.basic_salary)}</td>
                <td class="text-success">+${_fmt(item.allowance)}</td>
                <td class="text-info">+${_fmt(item.overtime)}</td>
                <td class="text-warning">-${_fmt(item.insurance)}</td>
                <td class="text-danger">-${_fmt(item.tax)}</td>
                <td class="text-danger">-${_fmt(item.deduction)}</td>
                <td class="fw-bold text-success">${_fmt(item.net_salary)}</td>
                <td>${_statusBadge(item.status, item.status_label)}</td>
                <td>
                    ${item.has_complaint
                        ? `<span class="badge bg-warning text-dark">${item.complaint_status_label || 'Có'}</span>`
                        : `<span class="text-muted small">--</span>`
                    }
                </td>
                <td>
                    <a href="/payroll/payslip/${item.id}" class="btn btn-sm btn-outline-primary">
                        <i class="fas fa-file-invoice-dollar me-1"></i>Xem
                    </a>
                </td>
            </tr>
        `).join('');
    }

    function _renderChart(items) {
        if (!chartCanvas || !window.Chart) return;

        // Backend thường trả mảng giảm dần (tháng mới nhất đầu tiên). Chart cần lật lại mảng.
        const reversedItems = [...items].reverse();

        const labels     = reversedItems.map(i => `T${String(i.month).padStart(2,'0')}`);
        const netData    = reversedItems.map(i => i.net_salary);
        const grossData  = reversedItems.map(i => i.basic_salary);

        if (incomeChart) incomeChart.destroy();

        incomeChart = new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Thực lĩnh',
                        data: netData,
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderRadius: 6,
                        order: 1,
                    },
                    {
                        label: 'Lương cơ bản',
                        data: grossData,
                        type: 'line',
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16,185,129,0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        order: 0,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.dataset.label}: ${_fmt(ctx.raw)}`
                        }
                    }
                },
                scales: {
                    y: { ticks: { callback: val => _fmtShort(val) } }
                }
            }
        });
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    function _fmt(val) {
        if (val == null) return '--';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
    }

    function _fmtShort(val) {
        if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + 'tr';
        if (val >= 1_000)     return (val / 1_000).toFixed(0) + 'k';
        return val;
    }

    function _statusBadge(status, label) {
        const map = {
            draft:    'secondary',
            pending:  'warning text-dark',
            approved: 'info',
            locked:   'primary',
            paid:     'success',
            rejected: 'danger',
        };
        const color = map[status] || 'secondary';
        return `<span class="badge bg-${color}">${label || status}</span>`;
    }

});