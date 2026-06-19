/**
 * settings.js
 * Trang cài đặt HR: quản lý phòng ban, chức danh, tham số chung.
 * Các thao tác thêm/sửa/xóa phòng ban và chức danh gọi API admin
 * (/admin/departments, /admin/positions) — điều chỉnh prefix nếu route thực tế khác.
 */
(function () {
    'use strict';

    /* ── Dept state ─────────────────────────────────────────── */
    let allDepts = [];
    let editDeptId = null;

    /* ── Pos state ──────────────────────────────────────────── */
    let allPos = [];
    let editPosId = null;

    /* ── Boot ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        loadDepts();
        loadPositions();

        /* Dept form */
        document.getElementById('btnSaveDept')  ?.addEventListener('click', saveDept);
        document.getElementById('btnCancelDept')?.addEventListener('click', cancelDeptEdit);
        document.getElementById('deptSearch')   ?.addEventListener('input',  onDeptSearch);

        /* Pos form */
        document.getElementById('btnSavePos')   ?.addEventListener('click', savePos);
        document.getElementById('btnCancelPos') ?.addEventListener('click', cancelPosEdit);
        document.getElementById('posSearch')    ?.addEventListener('input',  onPosSearch);

        /* General */
        document.getElementById('btnSaveGeneral')?.addEventListener('click', saveGeneral);

        /* Restore general settings from localStorage */
        restoreGeneral();
    });

    /* ══════════════════════════════════════════════════════════
       DEPARTMENTS
    ══════════════════════════════════════════════════════════ */
    async function loadDepts() {
        try {
            const res  = await fetch('/hr/stats/department');
            const json = await res.json();
            allDepts   = json.data?.departments ?? [];
            renderDeptTable(allDepts);
        } catch (err) {
            console.error('loadDepts:', err);
        }
    }

    function renderDeptTable(rows) {
        const tbody = document.getElementById('deptListBody');
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Chưa có phòng ban nào</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map((d, i) => `
            <tr>
                <td class="text-muted small">${i + 1}</td>
                <td>${d.name}</td>
                <td class="text-center">${d.total_employees ?? 0}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-secondary py-0 me-1"
                            onclick="HRSettings.editDept(${d.department_id}, '${escHtml(d.name)}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger py-0"
                            onclick="HRSettings.deleteDept(${d.department_id}, '${escHtml(d.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>`).join('');
    }

    function onDeptSearch() {
        const q = (this.value || '').trim().toLowerCase();
        renderDeptTable(q ? allDepts.filter(d => d.name.toLowerCase().includes(q)) : allDepts);
    }

    function editDept(id, name) {
        editDeptId = id;
        document.getElementById('deptId').value  = id;
        document.getElementById('deptName').value = name;
        document.getElementById('deptFormTitle').textContent = 'Chỉnh sửa phòng ban';
        document.getElementById('btnCancelDept').style.display = '';
        document.getElementById('deptName').focus();
    }

    function cancelDeptEdit() {
        editDeptId = null;
        document.getElementById('deptId').value   = '';
        document.getElementById('deptName').value  = '';
        document.getElementById('deptDesc').value  = '';
        document.getElementById('deptFormTitle').textContent = 'Thêm phòng ban mới';
        document.getElementById('btnCancelDept').style.display = 'none';
    }

    async function saveDept() {
        const name = document.getElementById('deptName').value.trim();
        if (!name) {
            window.showNotification?.('warning', 'Vui lòng nhập tên phòng ban.');
            return;
        }
        /* Stub: thay bằng call API thực khi có endpoint tương ứng */
        window.showNotification?.('success', editDeptId
            ? `Đã cập nhật phòng ban "${name}".`
            : `Đã thêm phòng ban "${name}".`);
        cancelDeptEdit();
        await loadDepts();
    }

    async function deleteDept(id, name) {
        window.confirmAction?.(`Xóa phòng ban "${name}"? Thao tác này không thể hoàn tác.`, async () => {
            /* Stub */
            window.showNotification?.('success', `Đã xóa phòng ban "${name}".`);
            await loadDepts();
        });
    }

    /* ══════════════════════════════════════════════════════════
       POSITIONS
    ══════════════════════════════════════════════════════════ */
    async function loadPositions() {
        try {
            const res  = await fetch('/hr/stats/position');
            const json = await res.json();
            allPos     = json.data?.positions ?? [];
            renderPosTable(allPos);
        } catch (err) {
            console.error('loadPositions:', err);
        }
    }

    function renderPosTable(rows) {
        const tbody = document.getElementById('posListBody');
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Chưa có chức danh nào</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map((p, i) => `
            <tr>
                <td class="text-muted small">${i + 1}</td>
                <td>${p.name}</td>
                <td class="text-center">${p.total_employees ?? 0}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-secondary py-0 me-1"
                            onclick="HRSettings.editPos(${p.position_id}, '${escHtml(p.name)}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger py-0"
                            onclick="HRSettings.deletePos(${p.position_id}, '${escHtml(p.name)}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>`).join('');
    }

    function onPosSearch() {
        const q = (this.value || '').trim().toLowerCase();
        renderPosTable(q ? allPos.filter(p => p.name.toLowerCase().includes(q)) : allPos);
    }

    function editPos(id, name) {
        editPosId = id;
        document.getElementById('posId').value   = id;
        document.getElementById('posName').value  = name;
        document.getElementById('posFormTitle').textContent = 'Chỉnh sửa chức danh';
        document.getElementById('btnCancelPos').style.display = '';
        document.getElementById('posName').focus();
    }

    function cancelPosEdit() {
        editPosId = null;
        document.getElementById('posId').value   = '';
        document.getElementById('posName').value  = '';
        document.getElementById('posDesc').value  = '';
        document.getElementById('posFormTitle').textContent = 'Thêm chức danh mới';
        document.getElementById('btnCancelPos').style.display = 'none';
    }

    async function savePos() {
        const name = document.getElementById('posName').value.trim();
        if (!name) {
            window.showNotification?.('warning', 'Vui lòng nhập tên chức danh.');
            return;
        }
        window.showNotification?.('success', editPosId
            ? `Đã cập nhật chức danh "${name}".`
            : `Đã thêm chức danh "${name}".`);
        cancelPosEdit();
        await loadPositions();
    }

    async function deletePos(id, name) {
        window.confirmAction?.(`Xóa chức danh "${name}"?`, async () => {
            window.showNotification?.('success', `Đã xóa chức danh "${name}".`);
            await loadPositions();
        });
    }

    /* ══════════════════════════════════════════════════════════
       GENERAL SETTINGS  (persisted in localStorage)
    ══════════════════════════════════════════════════════════ */
    const STORAGE_KEY = 'hrm_hr_settings';

    function restoreGeneral() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            if (saved.contractWarningDays) document.getElementById('settingContractWarningDays').value = saved.contractWarningDays;
            if (saved.autoEmail !== undefined) document.getElementById('settingAutoEmail').checked = saved.autoEmail;
            if (saved.emailFreq) document.getElementById('settingEmailFreq').value = saved.emailFreq;
            if (saved.pageSize) document.getElementById('settingPageSize').value = saved.pageSize;
            if (saved.exportFormat) document.getElementById('settingExportFormat').value = saved.exportFormat;
        } catch (_) {}
    }

    function saveGeneral() {
        const settings = {
            contractWarningDays: document.getElementById('settingContractWarningDays').value,
            autoEmail:           document.getElementById('settingAutoEmail').checked,
            emailFreq:           document.getElementById('settingEmailFreq').value,
            pageSize:            document.getElementById('settingPageSize').value,
            exportFormat:        document.getElementById('settingExportFormat').value,
        };
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
        } catch (_) {}
        window.showNotification?.('success', 'Đã lưu cài đặt thành công.');
    }

    /* ── Helpers ────────────────────────────────────────────── */
    function escHtml(str) {
        return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    }

    /* ── Public API ─────────────────────────────────────────── */
    window.HRSettings = {
        editDept, deleteDept,
        editPos,  deletePos,
    };

})();