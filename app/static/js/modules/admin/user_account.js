/**
 * user_account.js
 * Handles: pending list, create account modal, role change, lock/unlock
 */

(() => {
    /* ── State ── */
    let pendingList = [];
    let activeList  = [];
    let targetEmpId = null;
    let targetUserId = null;

    /* ── Modals ── */
    const createModal = new bootstrap.Modal(document.getElementById('createAccountModal'));
    const roleModal   = new bootstrap.Modal(document.getElementById('roleModal'));

    /* ── Tab switching ── */
    document.querySelectorAll('[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tab = btn.dataset.tab;
            document.getElementById('tab-pending').style.display = tab === 'pending' ? '' : 'none';
            document.getElementById('tab-active').style.display  = tab === 'active'  ? '' : 'none';
            if (tab === 'active' && activeList.length === 0) loadActiveUsers();
        });
    });

    /* ══ PENDING TAB ══════════════════════════════════════════ */
    async function loadPending() {
        const r = await Admin.api('GET', '/admin/api/admin/employees/pending');
        if (!r.ok) {
            document.getElementById('pendingBody').innerHTML =
                `<tr><td colspan="5" class="admin-empty"><i class="fa-solid fa-circle-exclamation"></i><p>Không tải được dữ liệu.</p></td></tr>`;
            return;
        }
        pendingList = r.data?.data?.items || [];
        document.getElementById('pendingCount').textContent = pendingList.length;
        renderPending();
    }

    function renderPending() {
        const tbody = document.getElementById('pendingBody');
        if (!pendingList.length) {
            tbody.innerHTML = `<tr><td colspan="5">
                <div class="admin-empty">
                    <i class="fa-solid fa-circle-check"></i>
                    <p>Không có nhân viên nào đang chờ tạo tài khoản.</p>
                </div></td></tr>`;
            return;
        }
        tbody.innerHTML = pendingList.map(e => `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="avatar-circle">${Admin.initials(e.full_name)}</div>
                        <div>
                            <div class="fw-semibold" style="font-size:.875rem;">${e.full_name}</div>
                            <div style="font-size:.75rem;color:var(--admin-muted);">ID: ${e.id}</div>
                        </div>
                    </div>
                </td>
                <td>${e.department_name || '—'}</td>
                <td>${e.position_name   || '—'}</td>
                <td>${Admin.fmtDate(e.hire_date)}</td>
                <td style="text-align:right;">
                    <button class="btn-admin-primary" style="font-size:.78rem;padding:.35rem .8rem;"
                            onclick="openCreateAccount(${e.id}, '${e.full_name.replace(/'/g,"\\'")}', '${e.department_name||''}', '${e.position_name||''}')">
                        <i class="fa-solid fa-user-plus"></i> Cấp tài khoản
                    </button>
                </td>
            </tr>
        `).join('');
    }

    /* ── Create Account Modal ── */
    window.openCreateAccount = async function(empId, name, dept, pos) {
        targetEmpId = empId;
        document.getElementById('caAvatar').textContent = Admin.initials(name);
        document.getElementById('caName').textContent   = name;
        document.getElementById('caDept').textContent   = dept || '—';
        document.getElementById('caPos').textContent    = pos  || '—';
        document.getElementById('caUsername').value = '';
        document.getElementById('caEmail').value    = '';
        document.getElementById('caPassword').value = '';
        document.getElementById('caStrengthBar').className = 'password-strength-fill strength-0';
        document.getElementById('caStrengthLabel').textContent = '';

        // Load roles
        const r = await Admin.api('GET', '/admin/api/roles');
        const roles = r.data?.data?.items || [];
        const sel = document.getElementById('caRoleId');
        sel.innerHTML = '<option value="">-- Chọn vai trò --</option>';
        roles.forEach(role => {
            const o = document.createElement('option');
            o.value = role.id;
            o.textContent = role.name;
            if (role.name === 'EMPLOYEE') o.selected = true;
            sel.appendChild(o);
        });

        createModal.show();
    };

    // Password strength
    document.getElementById('caPassword').addEventListener('input', function() {
        const val = this.value;
        let score = 0;
        if (val.length >= 8)  score++;
        if (/[A-Z]/.test(val)) score++;
        if (/[0-9]/.test(val)) score++;
        if (/[^A-Za-z0-9]/.test(val)) score++;
        const bar = document.getElementById('caStrengthBar');
        const lbl = document.getElementById('caStrengthLabel');
        bar.className = `password-strength-fill strength-${score}`;
        const labels = ['', 'Yếu', 'Trung bình', 'Khá mạnh', 'Mạnh'];
        lbl.textContent = score ? `Mức độ: ${labels[score]}` : '';
    });

    // Toggle password visibility
    document.getElementById('btnToggleCaPass').addEventListener('click', () => {
        const inp = document.getElementById('caPassword');
        const ico = document.querySelector('#btnToggleCaPass i');
        if (inp.type === 'password') { inp.type = 'text'; ico.classList.replace('fa-eye','fa-eye-slash'); }
        else { inp.type = 'password'; ico.classList.replace('fa-eye-slash','fa-eye'); }
    });

    document.getElementById('btnCreateAccount').addEventListener('click', async () => {
        if (!targetEmpId) return;
        const username = document.getElementById('caUsername').value.trim();
        const email    = document.getElementById('caEmail').value.trim();
        const password = document.getElementById('caPassword').value;
        const role_id  = document.getElementById('caRoleId').value;

        if (!username || !email || !password || !role_id)
            return Admin.toast('warning', 'Vui lòng điền đầy đủ thông tin');
        if (password.length < 8)
            return Admin.toast('warning', 'Mật khẩu tối thiểu 8 ký tự');

        const btn = document.getElementById('btnCreateAccount');
        Admin.btnLoading(btn, true);
        const r = await Admin.api('POST', `/admin/api/employees/${targetEmpId}/account`,
            { username, email, password, role_id: +role_id });
        Admin.btnLoading(btn, false);

        Admin.swalResponse(r);
        if (r.ok) {
            createModal.hide();
            await loadPending();
        }
    });

    /* ══ ACTIVE USERS TAB ═════════════════════════════════════ */
    async function loadActiveUsers() {
        document.getElementById('activeBody').innerHTML =
            `<tr><td colspan="5" class="admin-loading">
             <span class="spinner-border spinner-border-sm me-2"></span>Đang tải...</td></tr>`;

        const r = await Admin.api('GET', '/admin/api/employees');
        activeList = r.data?.data?.items || [];

        // Load roles for filter
        const meta = await Admin.getMeta();
        if (meta) {
            Admin.fillSelect(document.getElementById('roleFilter'), meta.roles, 'name', 'Tất cả vai trò');
        }

        renderActive(activeList);
    }

    const searchInput  = document.getElementById('userSearch');
    const roleFilterEl = document.getElementById('roleFilter');

    searchInput.addEventListener('input', Admin.debounce(filterActive));
    roleFilterEl.addEventListener('change', filterActive);

    function filterActive() {
        const q    = searchInput.value.toLowerCase();
        const role = roleFilterEl.value;
        renderActive(activeList.filter(u =>
            (!q || (u.full_name||'').toLowerCase().includes(q)) &&
            (!role || u.role === role)
        ));
    }

    function renderActive(list) {
        const tbody = document.getElementById('activeBody');
        if (!list.length) {
            tbody.innerHTML = `<tr><td colspan="5"><div class="admin-empty">
                <i class="fa-solid fa-users-slash"></i><p>Không tìm thấy tài khoản nào.</p>
            </div></td></tr>`;
            return;
        }
        tbody.innerHTML = list.map(u => `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="avatar-circle">${Admin.initials(u.full_name || u.username || '?')}</div>
                        <div>
                            <div class="fw-semibold" style="font-size:.875rem;">${u.full_name || u.username}</div>
                            <div style="font-size:.75rem;color:var(--admin-muted);">
                                ${u.department_name || ''} ${u.position_name ? '/ '+u.position_name : ''}
                            </div>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="font-size:.875rem;">${u.username || '—'}</div>
                    <div style="font-size:.75rem;color:var(--admin-muted);">${u.email || '—'}</div>
                </td>
                <td><span class="role-badge role-${u.role}">${u.role || '—'}</span></td>
                <td>
                    ${u.is_active
                        ? '<span class="badge-status badge-active">Hoạt động</span>'
                        : '<span class="badge-status badge-locked">Đã khóa</span>'}
                </td>
                <td style="text-align:right;">
                    <button class="btn-icon primary me-1" title="Đổi vai trò"
                            onclick="openRoleModal(${u.user_id}, '${(u.username||'').replace(/'/g,"\\'")}', '${u.role||''}')">
                        <i class="fa-solid fa-shield-halved"></i>
                    </button>
                    ${u.is_active
                        ? `<button class="btn-icon danger" title="Khóa tài khoản"
                                onclick="lockUser(${u.user_id}, '${(u.username||'').replace(/'/g,"\\'")}')">
                            <i class="fa-solid fa-lock"></i>
                           </button>`
                        : `<button class="btn-icon success" title="Mở khóa"
                                onclick="unlockUser(${u.user_id}, '${(u.username||'').replace(/'/g,"\\'")}')">
                            <i class="fa-solid fa-lock-open"></i>
                           </button>`}
                </td>
            </tr>
        `).join('');
    }

    /* ── Role modal ── */
    window.openRoleModal = function(userId, username, currentRole) {
        targetUserId = userId;
        document.getElementById('roleTargetName').textContent = username;
        document.getElementById('roleSelect').value = currentRole || 'EMPLOYEE';
        roleModal.show();
    };

    document.getElementById('btnRoleSave').addEventListener('click', async () => {
        if (!targetUserId) return;
        const role_name = document.getElementById('roleSelect').value;
        const btn = document.getElementById('btnRoleSave');
        Admin.btnLoading(btn, true);
        const r = await Admin.api('PATCH', `/admin/api/users/${targetUserId}/role`, { role_name });
        Admin.btnLoading(btn, false);
        Admin.swalResponse(r);
        if (r.ok) {
            roleModal.hide();
            activeList = [];
            await loadActiveUsers();
        }
    });

    /* ── Lock / Unlock ── */
    window.lockUser = async function(userId, username) {
        const ok = await Admin.confirm(
            `Khóa tài khoản "${username}"?`,
            'Người dùng sẽ không thể đăng nhập cho đến khi được mở khóa.',
            'Khóa tài khoản'
        );
        if (!ok) return;
        const r = await Admin.api('POST', `/admin/api/admin/users/${userId}/lock`,
            { reason: 'Khóa bởi Admin' });
        Admin.swalResponse(r);
        if (r.ok) { activeList = []; await loadActiveUsers(); }
    };

    window.unlockUser = async function(userId, username) {
        const ok = await Admin.confirm(
            `Mở khóa tài khoản "${username}"?`,
            'Người dùng sẽ có thể đăng nhập trở lại.',
            'Mở khóa', 'question'
        );
        if (!ok) return;
        const r = await Admin.api('POST', `/admin/api/admin/users/${userId}/unlock`);
        Admin.swalResponse(r);
        if (r.ok) { activeList = []; await loadActiveUsers(); }
    };

    /* ── Init ── */
    loadPending();
})();