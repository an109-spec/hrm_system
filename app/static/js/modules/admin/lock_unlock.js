/**
 * lock_unlock.js
 * Quản lý khóa / mở khóa tài khoản nhân viên
 */

"use strict";

(function () {
    /* ── State ──────────────────────────────────────────────── */
    let allUsers    = [];
    let targetUserId = null;

    /* ── Bootstrap modal refs ───────────────────────────────── */
    const modalLock   = new bootstrap.Modal(document.getElementById("modalLock"));
    const modalUnlock = new bootstrap.Modal(document.getElementById("modalUnlock"));
    const modalReset  = new bootstrap.Modal(document.getElementById("modalReset"));

    /* ── Init ───────────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", () => {
        loadUsers();
        bindEvents();
    });

    /* ── API helpers ────────────────────────────────────────── */
    async function apiFetch(url, options = {}) {
        const res = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return res.json();
    }

    /* ── Load users list ────────────────────────────────────── */
    async function loadUsers() {
        try {
            // Giả định endpoint tổng hợp; điều chỉnh nếu BE có route riêng
            const data = await apiFetch("/api/roles");
            // Nạp metadata role vào dropdown filter
            if (data?.data?.items) {
                const sel = document.getElementById("filterRole");
                data.data.items.forEach(r => {
                    const opt = document.createElement("option");
                    opt.value = r.name;
                    opt.textContent = r.name;
                    sel.appendChild(opt);
                });
            }
        } catch (_) { /* silent */ }

        // TODO: gọi endpoint GET /api/admin/users khi BE có sẵn
        // Tạm dùng dữ liệu mock để render UI
        allUsers = getMockUsers();
        renderTable(allUsers);
        updateStats(allUsers);
    }

    /* ── Render table ───────────────────────────────────────── */
    function renderTable(users) {
        const tbody = document.getElementById("usersTableBody");

        if (!users.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="table-empty-state">
                        <div><i class="bi bi-people"></i></div>
                        <div>Không tìm thấy tài khoản nào</div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = users.map((u, idx) => `
            <tr>
                <td class="text-muted">${idx + 1}</td>
                <td>
                    <div class="fw-medium">${escHtml(u.employee_name || "–")}</div>
                    <div class="text-muted" style="font-size:.8rem">${escHtml(u.email)}</div>
                </td>
                <td>
                    <div>${escHtml(u.username)}</div>
                    <div class="text-muted" style="font-size:.75rem">ID: ${u.user_id}</div>
                </td>
                <td>
                    <span class="badge bg-light text-dark border">${escHtml(u.role || "–")}</span>
                </td>
                <td>${u.is_active
                        ? '<span class="badge-active"><i class="bi bi-check-circle-fill"></i>Hoạt động</span>'
                        : '<span class="badge-locked"><i class="bi bi-lock-fill"></i>Đã khóa</span>'}
                </td>
                <td class="text-muted" style="font-size:.8rem">
                    ${u.lock_reason ? escHtml(u.lock_reason) : "–"}
                </td>
                <td class="text-center">
                    <div class="d-flex justify-content-center gap-1">
                        ${u.is_active
                            ? `<button class="btn-action btn-action--danger" title="Khóa tài khoản"
                                       onclick="openLock(${u.user_id}, '${escHtml(u.employee_name || u.username)}')">
                                   <i class="bi bi-lock"></i>
                               </button>`
                            : `<button class="btn-action btn-action--success" title="Mở khóa"
                                       onclick="openUnlock(${u.user_id}, '${escHtml(u.employee_name || u.username)}')">
                                   <i class="bi bi-unlock"></i>
                               </button>`
                        }
                        <button class="btn-action btn-action--warning" title="Đặt lại mật khẩu"
                                onclick="openReset(${u.user_id}, '${escHtml(u.employee_name || u.username)}')">
                            <i class="bi bi-key"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    /* ── Update stats ────────────────────────────────────────── */
    function updateStats(users) {
        document.getElementById("statTotal").textContent   = users.length;
        document.getElementById("statActive").textContent  = users.filter(u => u.is_active).length;
        document.getElementById("statLocked").textContent  = users.filter(u => !u.is_active).length;
        document.getElementById("statPending").textContent = users.filter(u => !u.employee_id).length;
    }

    /* ── Filter logic ────────────────────────────────────────── */
    function applyFilter() {
        const search  = document.getElementById("searchInput").value.toLowerCase();
        const status  = document.getElementById("filterStatus").value;
        const role    = document.getElementById("filterRole").value;

        const filtered = allUsers.filter(u => {
            const matchSearch = !search ||
                (u.employee_name || "").toLowerCase().includes(search) ||
                (u.email || "").toLowerCase().includes(search) ||
                (u.username || "").toLowerCase().includes(search);

            const matchStatus = !status ||
                (status === "active" && u.is_active) ||
                (status === "locked" && !u.is_active);

            const matchRole = !role || u.role === role;

            return matchSearch && matchStatus && matchRole;
        });

        renderTable(filtered);
    }

    /* ── Public: open modals (called from inline onclick) ───── */
    window.openLock = function (userId, name) {
        targetUserId = userId;
        document.getElementById("lockUserName").textContent = name;
        document.getElementById("lockReason").value = "";
        modalLock.show();
    };

    window.openUnlock = function (userId, name) {
        targetUserId = userId;
        document.getElementById("unlockUserName").textContent = name;
        modalUnlock.show();
    };

    window.openReset = function (userId, name) {
        targetUserId = userId;
        document.getElementById("resetUserName").textContent = name;
        document.getElementById("newPassword").value = "";
        modalReset.show();
    };

    /* ── Confirm lock ─────────────────────────────────────────── */
    async function confirmLock() {
        const reason = document.getElementById("lockReason").value.trim() || "Khóa bởi Admin";
        const btn = document.getElementById("btnConfirmLock");

        btn.disabled = true;
        try {
            const data = await apiFetch(`/api/admin/users/${targetUserId}/lock`, {
                method: "POST",
                body: JSON.stringify({ reason }),
            });

            modalLock.hide();
            handleResponse(data, "Khóa tài khoản thành công", () => {
                const user = allUsers.find(u => u.user_id === targetUserId);
                if (user) { user.is_active = false; user.lock_reason = reason; }
                renderTable(allUsers);
                updateStats(allUsers);
            });
        } catch (e) {
            showError("Lỗi kết nối. Vui lòng thử lại.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Confirm unlock ─────────────────────────────────────── */
    async function confirmUnlock() {
        const btn = document.getElementById("btnConfirmUnlock");
        btn.disabled = true;
        try {
            const data = await apiFetch(`/api/admin/users/${targetUserId}/unlock`, { method: "POST" });

            modalUnlock.hide();
            handleResponse(data, "Mở khóa thành công", () => {
                const user = allUsers.find(u => u.user_id === targetUserId);
                if (user) { user.is_active = true; user.lock_reason = null; }
                renderTable(allUsers);
                updateStats(allUsers);
            });
        } catch (e) {
            showError("Lỗi kết nối. Vui lòng thử lại.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Confirm reset password ──────────────────────────────── */
    async function confirmReset() {
        const pwd = document.getElementById("newPassword").value;
        if (pwd.length < 8) {
            showError("Mật khẩu phải có ít nhất 8 ký tự.");
            return;
        }

        const btn = document.getElementById("btnConfirmReset");
        btn.disabled = true;
        try {
            const data = await apiFetch(`/api/admin/users/${targetUserId}/reset-password`, {
                method: "POST",
                body: JSON.stringify({ new_password: pwd }),
            });

            modalReset.hide();
            handleResponse(data, "Đặt lại mật khẩu thành công");
        } catch (e) {
            showError("Lỗi kết nối. Vui lòng thử lại.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Response handler ────────────────────────────────────── */
    function handleResponse(data, defaultMsg, onSuccess) {
        const swal = data?.swal || {};
        if (data?.success !== false) {
            Swal.fire({
                icon: swal.icon || "success",
                title: swal.title || defaultMsg,
                text: swal.text || "",
                timer: 2500,
                showConfirmButton: false,
            });
            if (typeof onSuccess === "function") onSuccess();
        } else {
            showError(swal.text || "Đã xảy ra lỗi.");
        }
    }

    function showError(msg) {
        Swal.fire({ icon: "error", title: "Lỗi", text: msg });
    }

    /* ── Bind events ─────────────────────────────────────────── */
    function bindEvents() {
        document.getElementById("btnFilter").addEventListener("click", applyFilter);
        document.getElementById("btnClearFilter").addEventListener("click", () => {
            document.getElementById("searchInput").value = "";
            document.getElementById("filterStatus").value = "";
            document.getElementById("filterRole").value = "";
            renderTable(allUsers);
        });

        document.getElementById("btnRefresh").addEventListener("click", loadUsers);

        document.getElementById("btnConfirmLock").addEventListener("click", confirmLock);
        document.getElementById("btnConfirmUnlock").addEventListener("click", confirmUnlock);
        document.getElementById("btnConfirmReset").addEventListener("click", confirmReset);

        // Live search
        document.getElementById("searchInput").addEventListener("input", applyFilter);

        // Toggle password visibility
        document.getElementById("togglePwd").addEventListener("click", () => {
            const input = document.getElementById("newPassword");
            const icon  = document.querySelector("#togglePwd i");
            if (input.type === "password") {
                input.type = "text";
                icon.className = "bi bi-eye-slash";
            } else {
                input.type = "password";
                icon.className = "bi bi-eye";
            }
        });
    }

    /* ── Util ────────────────────────────────────────────────── */
    function escHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    /* ── Mock data (xóa khi BE có endpoint thật) ─────────────── */
    function getMockUsers() {
        return [
            { user_id: 1, username: "admin",    email: "admin@hrm.vn",    employee_name: "Nguyễn Văn Admin",  role: "ADMIN",    is_active: true,  lock_reason: null,                employee_id: 1 },
            { user_id: 2, username: "hr01",      email: "hr01@hrm.vn",     employee_name: "Trần Thị HR",       role: "HR",       is_active: true,  lock_reason: null,                employee_id: 2 },
            { user_id: 3, username: "manager01", email: "mgr@hrm.vn",      employee_name: "Lê Minh Manager",   role: "MANAGER",  is_active: false, lock_reason: "Vi phạm nội quy", employee_id: 3 },
            { user_id: 4, username: "emp001",    email: "emp001@hrm.vn",   employee_name: "Phạm Văn Nam",      role: "EMPLOYEE", is_active: true,  lock_reason: null,                employee_id: 4 },
            { user_id: 5, username: "emp002",    email: "emp002@hrm.vn",   employee_name: "Nguyễn Thị Mai",    role: "EMPLOYEE", is_active: false, lock_reason: "Nghỉ việc",       employee_id: 5 },
        ];
    }
})();