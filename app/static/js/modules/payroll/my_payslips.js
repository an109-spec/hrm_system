document.addEventListener('DOMContentLoaded', function () {
    const yearSelect = document.getElementById('filterYear');
    const filterButton = document.getElementById('btnFilter');
    const payrollTableBody = document.getElementById('payrollTableBody');
    const summaryCards = {
        sumNetSalary: document.getElementById('sumNetSalary'),
        sumStatus: document.getElementById('sumStatus'),
        sumPaymentDate: document.getElementById('sumPaymentDate'),
    };

    async function fetchPayslips(year) {
        payrollTableBody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin me-2"></i>Đang tải dữ liệu...</td></tr>`;
        try {
            const response = await PayrollAPI.getMyPayrollHistory(year);
            if (response.ok) {
                renderPayslips(response.data.data.salaries);
                updateSummary(response.data.data.summary);
            } else {
                showError(response.data.swal.text || 'Không thể tải phiếu lương.');
            }
        } catch (error) {
            console.error('Lỗi khi tải phiếu lương:', error);
            showError('Đã xảy ra lỗi. Vui lòng thử lại.');
        }
    }

    function renderPayslips(payslips) {
        payrollTableBody.innerHTML = '';
        if (!payslips || payslips.length === 0) {
            payrollTableBody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">Không tìm thấy phiếu lương cho năm đã chọn.</td></tr>`;
            return;
        }

        payslips.forEach(p => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${p.month}/${p.year}</td>
                <td>${formatCurrency(p.basic_salary)}</td>
                <td>${formatCurrency(p.total_allowance)}</td>
                <td>${formatCurrency(p.overtime_salary)}</td>
                <td>${formatCurrency(p.insurance)}</td>
                <td>${formatCurrency(p.tax)}</td>
                <td>${formatCurrency(p.penalty)}</td>
                <td class="text-success fw-bold">${formatCurrency(p.net_salary)}</td>
                <td><span class="badge bg-${getStatusClass(p.status)}">${p.status_label}</span></td>
                <td>
                    <a href="/payroll/salary-slip/${p.salary_id}" class="btn btn-sm btn-primary">
                        <i class="fas fa-eye"></i> Xem
                    </a>
                </td>
            `;
            payrollTableBody.appendChild(row);
        });
    }

    function updateSummary(summary) {
        if (!summary) {
            summaryCards.sumNetSalary.textContent = '--';
            summaryCards.sumStatus.textContent = '--';
            summaryCards.sumPaymentDate.textContent = '--';
            return;
        }
        summaryCards.sumNetSalary.textContent = formatCurrency(summary.latest_net_salary);
        summaryCards.sumStatus.textContent = summary.latest_status_label || '--';
        summaryCards.sumPaymentDate.textContent = summary.latest_payment_date || '--';
    }

    function init() {
        const currentYear = new Date().getFullYear();
        for (let i = 0; i < 5; i++) {
            const year = currentYear - i;
            const option = new Option(year, year);
            yearSelect.add(option);
        }        
        yearSelect.value = currentYear;
        fetchPayslips(currentYear);

        filterButton.addEventListener('click', () => {
            fetchPayslips(yearSelect.value);
        });
    }

    function formatCurrency(value) {
        if (value === null || value === undefined) return 'N/A';
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value);
    }

    function getStatusClass(status) {
        const statusClasses = {
            DRAFT: 'secondary',
            PENDING: 'warning',
            APPROVED: 'info',
            PAID: 'success',
            REJECTED: 'danger',
        };
        return statusClasses[status] || 'secondary';
    }

    function showError(message) {
        payrollTableBody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-danger">${message}</td></tr>`;
    }

    init();
});
