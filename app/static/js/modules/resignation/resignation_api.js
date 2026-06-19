/**
 * resignation_api.js
 * Lớp giao tiếp API cho module Nghỉ việc.
 * Tất cả hàm trả về Promise<Response JSON>.
 */

const ResignationAPI = (() => {
    const BASE = '/resignation';

    async function _request(method, url, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(url, opts);
        const data = await res.json();
        return { ok: res.ok, status: res.status, data };
    }

    return {
        /** Nhân viên gửi đơn tự nguyện */
        submit(payload) {
            return _request('POST', `${BASE}/submit`, payload);
        },

        /** Manager đề xuất nghỉ cho nhân viên */
        propose(payload) {
            return _request('POST', `${BASE}/propose`, payload);
        },

        /** Manager duyệt / từ chối */
        managerReview(id, action, note) {
            return _request('PATCH', `${BASE}/${id}/manager-review`, { action, note });
        },

        /** HR xử lý offboarding checklist */
        hrProcess(id, action, payload) {
            return _request('PATCH', `${BASE}/${id}/hr-process`, { action, ...payload });
        },

        /** Admin phê duyệt cuối */
        adminFinalize(id, action, note) {
            return _request('PATCH', `${BASE}/${id}/admin-finalize`, { action, note });
        },

        /** Danh sách đơn (phân quyền server-side) */
        list(params = {}) {
            const qs = new URLSearchParams(params).toString();
            return _request('GET', `${BASE}/?${qs}`);
        },

        /** Chi tiết một đơn */
        get(id) {
            return _request('GET', `${BASE}/${id}`);
        },
    };
})();