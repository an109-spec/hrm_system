/**
 * reset_password.js
 * Trang reset mật khẩu cho Admin.
 *
 * Phụ thuộc: Admin (admin.js), SweetAlert2, Bootstrap 5
 *
 * Luồng:
 *   1. Load danh sách nhân viên có tài khoản (GET /api/employees)
 *   2. Admin click chọn → hiện form reset bên phải
 *   3. Nhập + xác nhận mật khẩu → POST /api/admin/users/<id>/reset-password
 *   4. Hiện màn hình thành công, cho phép reset tiếp
 */

(() => {
    /* ─── State ──────────────────────────────────────────── */
    let allUsers     = [];   // danh sách đã load
    let selectedUser = null; // { user_id, employee_name, email, role, is_active }

    /* ─── DOM refs ───────────────────────────────────────── */
    const searchInput   = document.getElementById('userSearchInput');
    const userListWrap  = document.getElementById('userListWrap');

    const placeholder   = document.getElementById('resetPlaceholder');
    const formPanel     = document.getElementById('resetForm');
    const successPanel  = document.getElementById('resetSuccess');

    const rfAvatar      = document.getElementById('rfAvatar');
    const rfName        = document.getElementById('rfName');
    const rfEmail       = document.getElementById('rfEmail');
    const rfRole        = document.getElementById('rfRole');
    const rfStatus      = document.getElementById('rfStatus');
    const lockedBanner  = document.getElementById('lockedBanner');

    const newPassInput    = document.getElementById('newPassword');
    const confirmPassInput= document.getElementById('confirmPassword');
    const strengthBar     = document.getElementById('strengthBar');
    const strengthLabel   = document.getElementById('strengthLabel');
    const matchMsg        = document.getElementById('matchMsg');

    const btnToggleNew    = document.getElementById('btnToggleNew');
    const btnToggleConfirm= document.getElementById('btnToggleConfirm');
    const btnDoReset      = document.getElementById('btnDoReset');
    const btnCancel       = document.getElementById('btnCancelReset');
    const btnResetAnother = document.getElementById('btnResetAnother');
    const successMsg      = document.getElementById('successMsg');

    /* ─── Load user list ─────────────────────────────────── */
    async function loadUsers() {
        userListWrap.innerHTML = `<div class="admin-loading">
            <span class="spinner-border spinner-border-sm me-2"></span>Đang tải...</div>`;

        const r = await Admin.api('GET', '/admin/api/employees');
        if (!r.ok) {
            userListWrap.innerHTML = `<div class="admin-empty">
                <i class="fa-solid fa-circle-exclamation"></i>
                <p>Không tải được danh sách tài khoản.</p></div>`;
            return;
        }

        // Lọc chỉ những employee ĐÃ có tài khoản (user_id != null)
        allUsers = (r.data?.data?.items || []).filter(e => e.user_id);
        renderUserList(allUsers);
    }

    function renderUserList(list) {
        if (!list.length) {
            userListWrap.innerHTML = `<div class="admin-empty" style="padding:2rem;">
                <i class="fa-solid fa-users-slash"></i>
                <p>Không tìm thấy tài khoản nào.</p></div>`;
            return;
        }

        userListWrap.innerHTML = list.map(u => `
            <div class="user-list-item ${selectedUser?.user_id === u.user_id ? 'selected' : ''}"
                 data-id="${u.user_id}"
                 onclick="selectUser(${u.user_id})">
                <div class="avatar-circle" style="width:36px;height:36px;font-size:.8rem;flex-shrink:0;">
                    ${Admin.initials(u.full_name || '?')}
                </div>
                <div style="min-width:0;">
                    <div class="fw-semibold text-truncate" style="font-size:.85rem;">
                        ${u.full_name || '—'}
                    </div>
                    <div class="text-truncate" style="font-size:.73rem;color:var(--admin-muted);">
                        ${u.department_name || ''} ${u.position_name ? '· '+u.position_name : ''}
                    </div>
                </div>
                ${u.is_active === false
                    ? '<span class="badge-status badge-locked ms-auto" style="font-size:.65rem;">Khóa</span>'
                    : ''}
            </div>
        `).join('');
    }

    /* ─── Select user → show form ────────────────────────── */
    window.selectUser = function(userId) {
        const u = allUsers.find(x => x.user_id === userId);
        if (!u) return;
        selectedUser = u;

        // Highlight selected item
        document.querySelectorAll('.user-list-item').forEach(el => {
            el.classList.toggle('selected', +el.dataset.id === userId);
        });

        // Populate info card
        rfAvatar.textContent = Admin.initials(u.full_name || '?');
        rfName.textContent   = u.full_name || u.username || '—';
        rfEmail.textContent  = u.email || '—';
        rfRole.innerHTML     = u.role
            ? `<span class="role-badge role-${u.role}">${u.role}</span>` : '';
        rfStatus.innerHTML   = u.is_active === false
            ? '<span class="badge-status badge-locked">Đang khóa</span>'
            : '<span class="badge-status badge-active">Hoạt động</span>';

        // Locked banner
        lockedBanner.classList.toggle('d-none', u.is_active !== false);

        // Clear fields
        newPassInput.value     = '';
        confirmPassInput.value = '';
        strengthBar.className  = 'password-strength-fill strength-0';
        strengthLabel.textContent = '';
        matchMsg.classList.add('d-none');
        matchMsg.textContent = '';

        // Show form
        placeholder.style.display  = 'none';
        successPanel.style.display = 'none';
        formPanel.style.display    = '';
    };

    /* ─── Password strength ──────────────────────────────── */
    newPassInput.addEventListener('input', () => {
        const val = newPassInput.value;
        let score = 0;
        if (val.length >= 8)           score++;
        if (/[A-Z]/.test(val))         score++;
        if (/[0-9]/.test(val))         score++;
        if (/[^A-Za-z0-9]/.test(val))  score++;

        strengthBar.className = `password-strength-fill strength-${score}`;
        const labels = ['', 'Yếu — cần cải thiện', 'Trung bình', 'Khá mạnh', 'Mạnh'];
        strengthLabel.textContent = score ? `Độ mạnh: ${labels[score]}` : '';

        checkMatch();
    });

    /* ─── Password match check ───────────────────────────── */
    confirmPassInput.addEventListener('input', checkMatch);

    function checkMatch() {
        const p1 = newPassInput.value;
        const p2 = confirmPassInput.value;
        if (!p2) { matchMsg.classList.add('d-none'); return; }

        matchMsg.classList.remove('d-none');
        if (p1 === p2) {
            matchMsg.textContent = '✓ Mật khẩu khớp';
            matchMsg.style.color = 'var(--admin-success)';
        } else {
            matchMsg.textContent = '✗ Mật khẩu chưa khớp';
            matchMsg.style.color = 'var(--admin-danger)';
        }
    }

    /* ─── Toggle password visibility ────────────────────── */
    function toggleVis(input, btn) {
        const ico = btn.querySelector('i');
        if (input.type === 'password') {
            input.type = 'text';
            ico.classList.replace('fa-eye', 'fa-eye-slash');
        } else {
            input.type = 'password';
            ico.classList.replace('fa-eye-slash', 'fa-eye');
        }
    }
    btnToggleNew.addEventListener('click',     () => toggleVis(newPassInput,     btnToggleNew));
    btnToggleConfirm.addEventListener('click', () => toggleVis(confirmPassInput, btnToggleConfirm));

    /* ─── Do reset ───────────────────────────────────────── */
    btnDoReset.addEventListener('click', async () => {
        if (!selectedUser) return;

        const newPass     = newPassInput.value;
        const confirmPass = confirmPassInput.value;

        // Validate
        if (!newPass) {
            return Admin.toast('warning', 'Vui lòng nhập mật khẩu mới');
        }
        if (newPass.length < 8) {
            return Admin.toast('warning', 'Mật khẩu phải có ít nhất 8 ký tự');
        }
        if (newPass !== confirmPass) {
            return Admin.toast('error', 'Mật khẩu xác nhận không khớp');
        }

        // Confirm dialog
        const confirmed = await Admin.confirm(
            `Reset mật khẩu cho "${selectedUser.full_name || selectedUser.username}"?`,
            selectedUser.is_active === false
                ? 'Thao tác này sẽ đặt lại mật khẩu và đồng thời mở khóa tài khoản.'
                : 'Mật khẩu hiện tại sẽ bị thay thế ngay lập tức.',
            'Xác nhận reset',
            'warning'
        );
        if (!confirmed) return;

        Admin.btnLoading(btnDoReset, true);
        const r = await Admin.api(
            'POST',
            `/admin/api/admin/users/${selectedUser.user_id}/reset-password`,
            { new_password: newPass }
        );
        Admin.btnLoading(btnDoReset, false);

        if (!r.ok) {
            const s = r.data?.swal;
            Swal.fire({
                icon:  s?.icon  || 'error',
                title: s?.title || 'Lỗi',
                text:  s?.text  || 'Không thể reset mật khẩu.',
            });
            return;
        }

        // Show success state
        const name = selectedUser.full_name || selectedUser.username;
        successMsg.textContent =
            `Mật khẩu của "${name}" đã được đặt lại thành công.` +
            (selectedUser.is_active === false ? ' Tài khoản cũng đã được mở khóa.' : '');

        formPanel.style.display    = 'none';
        successPanel.style.display = '';

        // Update local state (account is now active after reset)
        const idx = allUsers.findIndex(u => u.user_id === selectedUser.user_id);
        if (idx !== -1) allUsers[idx].is_active = true;
        renderUserList(filterList(searchInput.value));

        selectedUser = null;
    });

    /* ─── Cancel / Reset another ────────────────────────── */
    btnCancel.addEventListener('click', () => {
        formPanel.style.display   = 'none';
        placeholder.style.display = '';
        selectedUser = null;
        document.querySelectorAll('.user-list-item').forEach(el => el.classList.remove('selected'));
    });

    btnResetAnother.addEventListener('click', () => {
        successPanel.style.display = 'none';
        placeholder.style.display  = '';
        document.querySelectorAll('.user-list-item').forEach(el => el.classList.remove('selected'));
    });

    /* ─── Search filter ──────────────────────────────────── */
    searchInput.addEventListener('input', Admin.debounce(() => {
        renderUserList(filterList(searchInput.value));
    }));

    function filterList(q) {
        if (!q) return allUsers;
        const lower = q.toLowerCase();
        return allUsers.filter(u =>
            (u.full_name     || '').toLowerCase().includes(lower) ||
            (u.email         || '').toLowerCase().includes(lower) ||
            (u.department_name || '').toLowerCase().includes(lower) ||
            (u.username      || '').toLowerCase().includes(lower)
        );
    }

    /* ─── Init ───────────────────────────────────────────── */
    loadUsers();
})();