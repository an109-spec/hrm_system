/**
 * metadata.js
 * Quản lý phòng ban, chức danh và vai trò hệ thống
 */

"use strict";

(function () {
    /* ── State ───────────────────────────────────────────────── */
    let allDepts     = [];
    let allPositions = [];
    let allRoles     = [];

    const modalDept = new bootstrap.Modal(document.getElementById("modalDept"));
    const modalPos  = new bootstrap.Modal(document.getElementById("modalPos"));

    /* ── Init ────────────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", () => {
        initTabs();
        loadMetadata();
        bindEvents();
    });

    /* ── API fetch helper ────────────────────────────────────── */
    async function apiFetch(url, options = {}) {
        const res = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return res.json();
    }

    /* ── Load all metadata ───────────────────────────────────── */
    async function loadMetadata() {
        try {
            const data = await apiFetch("/api/metadata/filters");
            if (data?.data) {
                allDepts     = data.data.departments || [];
                allPositions = data.data.positions || [];
                allRoles     = data.data.roles || [];

                document.getElementById("deptCount").textContent = allDepts.length;
                document.getElementById("posCount").textContent  = allPositions.length;
                document.getElementById("roleCount").textContent = allRoles.length;

                renderDepts(allDepts);
                renderPositions(allPositions);
                renderRoles(allRoles);
            }
        } catch (_) {
            // Fallback mock
            allDepts     = getMockDepts();
            allPositions = getMockPositions();
            allRoles     = getMockRoles();

            document.getElementById("deptCount").textContent = allDepts.length;
            document.getElementById("posCount").textContent  = allPositions.length;
            document.getElementById("roleCount").textContent = allRoles.length;

            renderDepts(allDepts);
            renderPositions(allPositions);
            renderRoles(allRoles);
        }
    }

    /* ── Render: Departments ─────────────────────────────────── */
    function renderDepts(items) {
        const tbody = document.getElementById("deptTableBody");
        if (!items.length) {
            tbody.innerHTML = emptyRow(6, "Không có phòng ban nào");
            return;
        }

        tbody.innerHTML = items.map((d, i) => `
            <tr>
                <td class="text-muted">${i + 1}</td>
                <td class="fw-medium">${escHtml(d.name)}</td>
                <td>${d.manager_name ? escHtml(d.manager_name) : '<span class="text-muted">Chưa gán</span>'}</td>
                <td class="text-muted" style="font-size:.85rem">
                    ${d.description ? escHtml(d.description) : "–"}
                </td>
                <td>${statusBadge(d.status)}</td>
                <td class="text-center">
                    <button class="btn-action" title="Sửa tên"
                            onclick="openEditDept(${d.id}, '${escHtml(d.name)}', '${escHtml(d.description || '')}', ${d.manager_id || 'null'})">
                        <i class="bi bi-pencil"></i>
                    </button>
                </td>
            </tr>
        `).join("");
    }

    /* ── Render: Positions ───────────────────────────────────── */
    function renderPositions(items) {
        const tbody = document.getElementById("posTableBody");
        if (!items.length) {
            tbody.innerHTML = emptyRow(5, "Không có chức danh nào");
            return;
        }

        tbody.innerHTML = items.map((p, i) => `
            <tr>
                <td class="text-muted">${i + 1}</td>
                <td class="fw-medium">${escHtml(p.name || p.job_title)}</td>
                <td class="text-muted" style="font-size:.85rem">
                    ${p.requirements ? escHtml(p.requirements) : "–"}
                </td>
                <td>${statusBadge(p.status === "active" || p.status === true)}</td>
                <td class="text-center">
                    <button class="btn-action" title="Sửa tên"
                            onclick="openEditPos(${p.id}, '${escHtml(p.name || p.job_title)}', '${escHtml(p.requirements || '')}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                </td>
            </tr>
        `).join("");
    }

    /* ── Render: Roles ───────────────────────────────────────── */
    function renderRoles(roles) {
        const grid = document.getElementById("rolesGrid");
        const rolesMeta = {
            ADMIN:    { icon: "bi-shield-fill-check", cls: "role-icon--admin",    desc: "Toàn quyền quản trị hệ thống" },
            HR:       { icon: "bi-person-lines-fill",  cls: "role-icon--hr",       desc: "Quản lý nhân sự, hợp đồng, phép" },
            MANAGER:  { icon: "bi-diagram-3-fill",     cls: "role-icon--manager",  desc: "Quản lý nhóm và duyệt yêu cầu" },
            EMPLOYEE: { icon: "bi-person-fill",        cls: "role-icon--employee", desc: "Xem thông tin và gửi yêu cầu" },
        };

        if (!roles.length) {
            grid.innerHTML = '<div class="col-12 text-center text-muted py-4">Không có vai trò nào.</div>';
            return;
        }

        grid.innerHTML = roles.map(r => {
            const meta = rolesMeta[r.name] || { icon: "bi-circle", cls: "role-icon--default", desc: "Vai trò tùy chỉnh" };
            return `
                <div class="col-6 col-md-3">
                    <div class="role-card">
                        <div class="role-icon ${meta.cls}">
                            <i class="bi ${meta.icon}"></i>
                        </div>
                        <div class="role-name">${escHtml(r.name)}</div>
                        <div class="role-desc">${meta.desc}</div>
                    </div>
                </div>`;
        }).join("");
    }

    /* ── Tab system ─────────────────────────────────────────── */
    function initTabs() {
        document.querySelectorAll("#metadataTabs .nav-link").forEach(link => {
            link.addEventListener("click", e => {
                e.preventDefault();
                const tab = link.dataset.tab;

                document.querySelectorAll("#metadataTabs .nav-link").forEach(l => l.classList.remove("active"));
                link.classList.add("active");

                document.querySelectorAll(".tab-pane-custom").forEach(p => p.classList.add("d-none"));
                document.getElementById("tab-" + tab)?.classList.remove("d-none");
            });
        });
    }

    /* ── Dept modal ─────────────────────────────────────────── */
    window.openEditDept = function (id, name, desc, managerId) {
        document.getElementById("deptModalTitle").textContent = "Sửa phòng ban";
        document.getElementById("deptId").value        = id;
        document.getElementById("deptName").value      = name;
        document.getElementById("deptDesc").value      = desc;
        document.getElementById("deptManagerId").value = managerId ?? "";
        modalDept.show();
    };

    function openAddDept() {
        document.getElementById("deptModalTitle").textContent = "Thêm phòng ban";
        document.getElementById("deptId").value        = "";
        document.getElementById("deptName").value      = "";
        document.getElementById("deptDesc").value      = "";
        document.getElementById("deptManagerId").value = "";
        modalDept.show();
    }

    async function saveDept() {
        const id   = document.getElementById("deptId").value;
        const name = document.getElementById("deptName").value.trim();
        const desc = document.getElementById("deptDesc").value.trim();
        const mgrId = document.getElementById("deptManagerId").value;

        if (!name) { showError("Vui lòng nhập tên phòng ban."); return; }

        const btn = document.getElementById("btnSaveDept");
        btn.disabled = true;

        try {
            let data;
            if (id) {
                data = await apiFetch(`/api/departments/${id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ name }),
                });
            } else {
                data = await apiFetch("/api/departments", {
                    method: "POST",
                    body: JSON.stringify({ name, description: desc, manager_id: mgrId ? +mgrId : null }),
                });
            }
            modalDept.hide();
            handleResponse(data, id ? "Cập nhật thành công" : "Thêm phòng ban thành công", loadMetadata);
        } catch (_) {
            showError("Lỗi kết nối.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Position modal ─────────────────────────────────────── */
    window.openEditPos = function (id, title, requirements) {
        document.getElementById("posModalTitle").textContent = "Sửa chức danh";
        document.getElementById("posId").value           = id;
        document.getElementById("posTitle").value        = title;
        document.getElementById("posRequirements").value = requirements;
        modalPos.show();
    };

    function openAddPos() {
        document.getElementById("posModalTitle").textContent = "Thêm chức danh";
        document.getElementById("posId").value           = "";
        document.getElementById("posTitle").value        = "";
        document.getElementById("posRequirements").value = "";
        modalPos.show();
    }

    async function savePos() {
        const id    = document.getElementById("posId").value;
        const title = document.getElementById("posTitle").value.trim();
        const req   = document.getElementById("posRequirements").value.trim();

        if (!title) { showError("Vui lòng nhập tên chức danh."); return; }

        const btn = document.getElementById("btnSavePos");
        btn.disabled = true;

        try {
            let data;
            if (id) {
                data = await apiFetch(`/api/positions/${id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ job_title: title }),
                });
            } else {
                data = await apiFetch("/api/positions", {
                    method: "POST",
                    body: JSON.stringify({ job_title: title, requirements: req }),
                });
            }
            modalPos.hide();
            handleResponse(data, id ? "Cập nhật thành công" : "Thêm chức danh thành công", loadMetadata);
        } catch (_) {
            showError("Lỗi kết nối.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Assign role ─────────────────────────────────────────── */
    async function assignRole() {
        const userId   = document.getElementById("assignUserId").value;
        const roleName = document.getElementById("assignRoleName").value;

        if (!userId || !roleName) {
            showError("Vui lòng nhập User ID và chọn vai trò.");
            return;
        }

        const btn = document.getElementById("btnAssignRole");
        btn.disabled = true;
        try {
            const data = await apiFetch(`/api/users/${userId}/role`, {
                method: "PATCH",
                body: JSON.stringify({ role_name: roleName }),
            });
            handleResponse(data, "Gán vai trò thành công");
        } catch (_) {
            showError("Lỗi kết nối.");
        } finally {
            btn.disabled = false;
        }
    }

    /* ── Filter logic ────────────────────────────────────────── */
    function filterDepts() {
        const q      = document.getElementById("deptSearch").value.toLowerCase();
        const status = document.getElementById("deptStatusFilter").value;
        renderDepts(allDepts.filter(d => {
            const matchQ = !q || d.name.toLowerCase().includes(q);
            const matchS = !status ||
                (status === "active" && d.status) ||
                (status === "inactive" && !d.status);
            return matchQ && matchS;
        }));
    }

    function filterPos() {
        const q      = document.getElementById("posSearch").value.toLowerCase();
        const status = document.getElementById("posStatusFilter").value;
        renderPositions(allPositions.filter(p => {
            const title = (p.name || p.job_title || "").toLowerCase();
            const matchQ = !q || title.includes(q);
            const matchS = !status ||
                (status === "active"   && (p.status === "active" || p.status === true)) ||
                (status === "inactive" && (p.status === "inactive" || p.status === false));
            return matchQ && matchS;
        }));
    }

    /* ── Bind events ─────────────────────────────────────────── */
    function bindEvents() {
        document.getElementById("btnAddDept").addEventListener("click", openAddDept);
        document.getElementById("btnSaveDept").addEventListener("click", saveDept);

        document.getElementById("btnAddPos").addEventListener("click", openAddPos);
        document.getElementById("btnSavePos").addEventListener("click", savePos);

        document.getElementById("btnAssignRole").addEventListener("click", assignRole);

        document.getElementById("deptSearch").addEventListener("input", filterDepts);
        document.getElementById("deptStatusFilter").addEventListener("change", filterDepts);

        document.getElementById("posSearch").addEventListener("input", filterPos);
        document.getElementById("posStatusFilter").addEventListener("change", filterPos);
    }

    /* ── Helpers ─────────────────────────────────────────────── */
    function statusBadge(isActive) {
        return isActive
            ? '<span class="badge-active">Hoạt động</span>'
            : '<span class="badge-locked">Ngừng</span>';
    }

    function emptyRow(cols, msg) {
        return `<tr><td colspan="${cols}" class="table-empty-state">
                    <div><i class="bi bi-inbox"></i></div><div>${msg}</div>
                </td></tr>`;
    }

    function handleResponse(data, defaultMsg, onSuccess) {
        const swal = data?.swal || {};
        if (data?.success !== false) {
            Swal.fire({ icon: swal.icon || "success", title: swal.title || defaultMsg,
                        text: swal.text || "", timer: 2000, showConfirmButton: false });
            if (typeof onSuccess === "function") onSuccess();
        } else {
            showError(swal.text || "Đã xảy ra lỗi.");
        }
    }

    function showError(msg) {
        Swal.fire({ icon: "error", title: "Lỗi", text: msg });
    }

    function escHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    /* ── Mock data ───────────────────────────────────────────── */
    function getMockDepts() {
        return [
            { id: 1, name: "Phòng Kỹ thuật",   manager_id: 3, manager_name: "Lê Minh Manager", description: "R&D và phát triển sản phẩm", status: true },
            { id: 2, name: "Phòng Nhân sự",     manager_id: 2, manager_name: "Trần Thị HR",     description: "Quản lý nhân sự toàn công ty", status: true },
            { id: 3, name: "Phòng Kế toán",     manager_id: null, manager_name: null,           description: "Tài chính và kế toán", status: true },
            { id: 4, name: "Phòng Kinh doanh",  manager_id: null, manager_name: null,           description: null, status: false },
        ];
    }

    function getMockPositions() {
        return [
            { id: 1, name: "Lập trình viên",    requirements: "3+ năm kinh nghiệm", status: "active" },
            { id: 2, name: "Kế toán viên",       requirements: "Tốt nghiệp Kế toán", status: "active" },
            { id: 3, name: "Trưởng phòng",       requirements: "5+ năm kinh nghiệm quản lý", status: "active" },
            { id: 4, name: "Thực tập sinh",      requirements: "Đang học hoặc mới tốt nghiệp", status: "inactive" },
        ];
    }

    function getMockRoles() {
        return [
            { id: 1, name: "ADMIN" },
            { id: 2, name: "HR" },
            { id: 3, name: "MANAGER" },
            { id: 4, name: "EMPLOYEE" },
        ];
    }
})();