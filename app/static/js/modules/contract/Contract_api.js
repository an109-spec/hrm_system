/**
 * contract_api.js
 * Tập trung toàn bộ các lời gọi API của module Contract.
 * Đặt tại: app/static/js/modules/contract/contract_api.js
 *
 * Tất cả hàm đều trả về { success, data, swal } hoặc throw Error
 * để các file JS trang chỉ lo phần render, không lo fetch.
 */

const ContractAPI = (() => {

    // ── Helper nội bộ ──────────────────────────────────────────────────
    async function _fetch(url, options = {}) {
        const defaults = {
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
        };
        const res = await fetch(url, { ...defaults, ...options });

        const contentType = res.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            return res.json();
        } else {
            const text = await res.text();
            throw new Error(`Expected JSON response, but got ${res.status} ${res.statusText} with content: ${text.substring(0, 100)}...`);
        }
    }


    // ── BASE / HR / ADMIN: Danh sách hợp đồng ─────────────────────────

    /**
     * Lấy danh sách HĐ (HR + Admin dùng endpoint /contract/)
     * @param {Object} filters - { search, contract_status, contract_type }
     */
    async function getContracts({ search = '', contract_status = 'all', contract_type = 'all' } = {}) {
        const params = new URLSearchParams({ search, contract_status, contract_type });
        return _fetch(`/contract/api?${params}`);
    }

    /**
     * Lấy chi tiết HĐ (HR + Admin dùng /contract/<id>)
     * @param {number} contractId
     */
    async function getContractDetail(contractId) {
        return _fetch(`/contract/api/${contractId}`);
    }

    /**
     * Lấy danh sách cảnh báo HĐ sắp hết hạn (HR + Admin)
     */
    async function getContractReminders() {
        return _fetch('/contract/api/reminders');
    }

    /**
     * Lấy filter meta (danh mục phòng ban, loại HĐ, trạng thái...) (HR + Admin)
     */
    async function getFilterMeta() {
        return _fetch('/contract/api/meta');
    }

    // ── ADMIN only ─────────────────────────────────────────────────────

    /**
     * Tạo hợp đồng mới (Admin)
     * @param {Object} data - { employee_id, duration, contract_type, basic_salary?, note? }
     */
    async function adminCreateContract(data) {
        return _fetch('/contract/api/admin/contracts', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * Chấm dứt hợp đồng (Admin)
     * @param {number} contractId
     * @param {Object} data - { end_date?, note? }
     */
    async function adminTerminateContract(contractId, data) {
        return _fetch(`/contract/api/admin/contracts/${contractId}/terminate`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    /**
     * Lấy danh sách HĐ theo endpoint Admin
     * @param {Object} filters - { status?, employee_id?, page?, per_page? }
     */
    async function adminGetContracts({ status, employee_id, page = 1, per_page = 20 } = {}) {
        const params = new URLSearchParams({ page, per_page });
        if (status)      params.set('status', status);
        if (employee_id) params.set('employee_id', employee_id);
        return _fetch(`/contract/api/admin/contracts?${params}`);
    }

    // ── HR only ────────────────────────────────────────────────────────

    /**
     * HR gia hạn trực tiếp hợp đồng
     * @param {number} contractId
     * @param {Object} data - { duration? | end_date?, note? }
     */
    async function hrExtendContract(contractId, data) {
        return _fetch(`/contract/api/hr/contracts/${contractId}/extend`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * HR duyệt / từ chối yêu cầu gia hạn từ Manager
     * @param {number} proposalId
     * @param {Object} data - { is_approved: bool, feedback?: string }
     */
    async function hrProcessRenewalRequest(proposalId, data) {
        return _fetch(`/contract/api/hr/contract-proposals/${proposalId}/process`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // ── MANAGER only ───────────────────────────────────────────────────

    /**
     * Lấy danh sách HĐ thuộc quyền Manager
     * @param {Object} filters - { search?, contract_type?, contract_status?, page?, per_page? }
     */
    async function managerGetContracts({ search, contract_type, contract_status, page = 1, per_page = 20 } = {}) {
        const params = new URLSearchParams({ page, per_page });
        if (search)          params.set('search', search);
        if (contract_type)   params.set('contract_type', contract_type);
        if (contract_status) params.set('contract_status', contract_status);
        return _fetch(`/manager/api/contracts?${params}`);
    }

    /**
     * Lấy danh sách HĐ sắp hết hạn (Manager)
     */
    async function managerGetExpiringContracts() {
        return _fetch('/manager/api/contracts/expiring');
    }

    /**
     * Lấy chi tiết HĐ (Manager)
     * @param {number} contractId
     */
    async function managerGetContractDetail(contractId) {
        return _fetch(`/manager/api/contracts/${contractId}`);
    }

    /**
     * Lấy HĐ gần nhất của nhân viên (Manager dùng khi chuẩn bị gia hạn)
     * @param {number} employeeId
     */
    async function managerGetLatestContractForEmployee(employeeId) {
        return _fetch(`/manager/api/employees/${employeeId}/latest-contract`);
    }

    /**
     * Manager gửi yêu cầu gia hạn lên HR
     * @param {number} contractId
     * @param {Object} data - { reason, proposed_duration_months, professional_note? }
     */
    async function managerRequestRenewal(contractId, data) {
        return _fetch(`/manager/api/contracts/${contractId}/request-renewal`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // ── EMPLOYEE only ──────────────────────────────────────────────────

    /**
     * Nhân viên xem chi tiết HĐ của chính mình
     * @param {number} contractId
     */
    async function employeeGetMyContract(contractId) {
        // Employee views their own contract through the base detail page,
        // but the backend decorator will enforce that they can only see their own.
        return _fetch(`/contract/api/${contractId}`);
    }

    // ── Public API ─────────────────────────────────────────────────────
    return {
        // Base / shared
        getContracts,
        getContractDetail,
        getContractReminders,
        getFilterMeta,
        // Admin
        adminCreateContract,
        adminTerminateContract,
        adminGetContracts,
        // HR
        hrExtendContract,
        hrProcessRenewalRequest,
        // Manager
        managerGetContracts,
        managerGetExpiringContracts,
        managerGetContractDetail,
        managerGetLatestContractForEmployee,
        managerRequestRenewal,
        // Employee
        employeeGetMyContract,
    };
})();
