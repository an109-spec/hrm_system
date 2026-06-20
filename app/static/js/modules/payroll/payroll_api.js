
/**
 * PAYROLL API MODULE
 * Tập trung tất cả các lời gọi API liên quan đến Payroll.
 * Sử dụng fetch() với JWT cookie tự động.
 */
const PayrollAPI = (() => {

    const BASE = '/payroll';

    /**
     * Helper gọi API chung
     */
    async function _fetch(url, options = {}) {
        const csrfToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrf_access_token='))
            ?.split('=')[1];

        const defaultHeaders = { 'Content-Type': 'application/json' };
        if (csrfToken) defaultHeaders['X-CSRF-TOKEN'] = csrfToken;

        const response = await fetch(url, {
            credentials: 'include',
            headers: { ...defaultHeaders, ...(options.headers || {}) },
            ...options,
        });
            
        
        if (response.status === 204) {
            return { ok: true, status: 204, data: null };
        }
        
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") === -1) {
            return {
                ok: false,
                status: response.status,
                data: {
                    swal: {
                        icon: 'error',
                        title: 'Lỗi Xác thực',
                        text: 'Phiên đăng nhập có thể đã hết hạn. Trang sẽ không tự tải lại.'
                    }
                }
            };
        }

        const json = await response.json();
        return { ok: response.ok, status: response.status, data: json };
    }

    // ─── EMPLOYEE ENDPOINTS ────────────────────────────────────────────────

    /** GET /payroll/history/me?year=2025 */
    async function getMyPayrollHistory(year, filters = {}) {
        const params = new URLSearchParams({ year, ...filters });
        return _fetch(`${BASE}/history/me?${params}`);
    }

    /** GET /payroll/salary-history/me?year=2025 */
    async function getMySalaryChart(year) {
        return _fetch(`${BASE}/salary-history/me?year=${year}`);
    }

    /** GET /payroll/payslip/<salary_id> */
    async function getPayslipDetail(salaryId) {
        return _fetch(`${BASE}/payslip/${salaryId}`);
    }

    /** GET /payroll/latest/me */
    async function getMyLatestSalary() {
        return _fetch(`${BASE}/latest/me`);
    }

    /** POST /payroll/complaints */
    async function submitComplaint(formData) {
        const csrfToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrf_access_token='))
            ?.split('=')[1];
        const headers = {};
        if (csrfToken) headers['X-CSRF-TOKEN'] = csrfToken;

        const response = await fetch(`${BASE}/complaints`, {
            method: 'POST',
            credentials: 'include',
            headers,
            body: formData, // FormData (multipart)
        });
        const json = await response.json();
        return { ok: response.ok, status: response.status, data: json };
    }

    /** GET /payroll/complaints */
    async function getMyComplaints() {
        return _fetch(`${BASE}/complaints`);
    }

    /** GET /payroll/complaints/<id> */
    async function getComplaintDetail(complaintId) {
        return _fetch(`${BASE}/complaints/${complaintId}`);
    }

    /** PATCH /payroll/complaints/<id>/close */
    async function closeComplaint(complaintId) {
        return _fetch(`${BASE}/complaints/${complaintId}/close`, { method: 'PATCH' });
    }

    /** GET /payroll/reports/monthly?month=5&year=2025 */
    async function getMonthlyReport(month, year) {
        return _fetch(`${BASE}/reports/monthly?month=${month}&year=${year}`);
    }

    // ─── HR ENDPOINTS ──────────────────────────────────────────────────────

    /** POST /payroll/calculate */
    async function calculatePayroll(month, year, departmentId = null) {
        const body = { month, year };
        if (departmentId) body.department_id = departmentId;
        return _fetch(`${BASE}/calculate`, { method: 'POST', body: JSON.stringify(body) });
    }

    /** GET /payroll?month=5&year=2025&... */
    async function getPayrollList(filters = {}) {
        const params = new URLSearchParams(filters);
        return _fetch(`${BASE}?${params}`);
    }

    /** GET /payroll/<salary_id> */
    async function getPayrollDetail(salaryId) {
        return _fetch(`${BASE}/${salaryId}`);
    }

    /** POST /payroll/<salary_id>/submit */
    async function submitPayrollApproval(salaryId) {
        return _fetch(`${BASE}/${salaryId}/submit`, { method: 'POST' });
    }

    /** GET /payroll/complaints (HR) */
    async function getHRComplaints(filters = {}) {
        const params = new URLSearchParams(filters);
        return _fetch(`${BASE}/complaints?${params}`);
    }

    /** POST /payroll/complaints/<id>/resolve */
    async function resolveComplaint(complaintId, action, message, payrollStatus = null) {
        const body = { action, message };
        if (payrollStatus) body.payroll_status = payrollStatus;
        return _fetch(`${BASE}/complaints/${complaintId}/resolve`, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    }

    /** GET /payroll/analytics/total-fund */
    async function getTotalPayrollFund(filters = {}) {
        const params = new URLSearchParams(filters);
        return _fetch(`${BASE}/analytics/total-fund?${params}`);
    }

    /** GET /payroll/all?month=5&year=2025 */
    async function getAllSalaries(month, year, filters = {}) {
        const params = new URLSearchParams({ month, year, ...filters });
        return _fetch(`${BASE}/all?${params}`);
    }

    // ─── MANAGER ENDPOINTS ─────────────────────────────────────────────────

    /** GET /payroll/manager/salaries?month=5&year=2025 */
    async function getManagerPayrollReview(month, year, filters = {}) {
        const params = new URLSearchParams({ month, year, ...filters });
        return _fetch(`${BASE}/manager/salaries?${params}`);
    }

    /** GET /payroll/manager/salaries/<id> */
    async function getManagerPayrollDetail(salaryId) {
        return _fetch(`${BASE}/manager/salaries/${salaryId}`);
    }

    /** PATCH /payroll/manager/salaries/<id>/confirm */
    async function confirmPayroll(salaryId, note = '') {
        return _fetch(`${BASE}/manager/salaries/${salaryId}/confirm`, {
            method: 'PATCH',
            body: JSON.stringify({ note }),
        });
    }

    /** PATCH /payroll/manager/complaints/<id> */
    async function handleManagerComplaint(complaintId, action, note) {
        return _fetch(`${BASE}/manager/complaints/${complaintId}`, {
            method: 'PATCH',
            body: JSON.stringify({ action, note }),
        });
    }

    /** GET /payroll/manager/report?month=5&year=2025 */
    async function getManagerReport(month, year) {
        return _fetch(`${BASE}/manager/report?month=${month}&year=${year}`);
    }

    /** GET /payroll/manager/complaints */
    async function getManagerComplaints(filters = {}) {
        const params = new URLSearchParams(filters);
        return _fetch(`${BASE}/manager/complaints?${params}`);
    }

    // ─── ADMIN ENDPOINTS ───────────────────────────────────────────────────

    /** GET /payroll/admin/policy */
    async function getPolicy() {
        return _fetch(`${BASE}/admin/policy`);
    }

    /** POST /payroll/admin/policy */
    async function updatePolicy(payload) {
        return _fetch(`${BASE}/admin/policy`, {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }

    /** POST /payroll/admin/policy/lock */
    async function setEditLock(locked) {
        return _fetch(`${BASE}/admin/policy/lock`, {
            method: 'POST',
            body: JSON.stringify({ locked }),
        });
    }

    /** POST /payroll/admin/<salary_id>/process */
    async function processPayrollFlow(salaryId, action, note = '') {
        return _fetch(`${BASE}/admin/${salaryId}/process`, {
            method: 'POST',
            body: JSON.stringify({ action, note }),
        });
    }
    async function getDepartments() {
        return _fetch(`/common/departments`);
    }
    // ─── PUBLIC ────────────────────────────────────────────────────────────

    return {
        // Employee
        getMyPayrollHistory,
        getMySalaryChart,
        getPayslipDetail,
        getMyLatestSalary,
        submitComplaint,
        getMyComplaints,
        getComplaintDetail,
        closeComplaint,
        getMonthlyReport,
        // HR
        calculatePayroll,
        getPayrollList,
        getPayrollDetail,
        submitPayrollApproval,
        getHRComplaints,
        resolveComplaint,
        getTotalPayrollFund,
        getAllSalaries,
        // Manager
        getManagerPayrollReview,
        getManagerPayrollDetail,
        confirmPayroll,
        handleManagerComplaint,
        getManagerReport,
        getManagerComplaints,
        // Admin
        getPolicy,
        updatePolicy,
        setEditLock,
        processPayrollFlow,
        getDepartments
    };
})();
