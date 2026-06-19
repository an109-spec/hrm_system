/**
 * create_employee.js
 * Wizard: Step 1 → create shell → Step 2 → assign dept/pos → Step 3
 */

(() => {
    let createdEmployeeId = null;

    /* ── Step navigation ── */
    function goStep(n) {
        [1, 2, 3].forEach(i => {
            document.getElementById(`step${i}`).style.display = (i === n) ? '' : 'none';
        });
        // Update wizard indicators
        [1, 2, 3].forEach(i => {
            const ind  = document.getElementById(`step${i}-indicator`);
            const snum = document.getElementById(`snum${i}`);
            ind.classList.remove('active', 'done');
            if (i < n) {
                ind.classList.add('done');
                snum.innerHTML = '<i class="fa-solid fa-check" style="font-size:.7rem;"></i>';
            } else if (i === n) {
                ind.classList.add('active');
                if (i !== 3) snum.textContent = i;
            } else {
                if (i !== 3) snum.textContent = i;
            }
        });
    }

    /* ── Load metadata ── */
    async function loadMeta() {
        const meta = await Admin.getMeta();
        if (!meta) return;
        Admin.fillSelect(document.getElementById('deptSelect'), meta.departments, 'name', '-- Chọn phòng ban --');
        Admin.fillSelect(document.getElementById('posSelect'),  meta.positions,   'name', '-- Chọn chức danh --');
    }

    /* ── Step 1: Create employee ── */
    document.getElementById('btnStep1').addEventListener('click', async () => {
        const fullName = document.getElementById('fullName').value.trim();
        const dob      = document.getElementById('dob').value;

        if (!fullName) return Admin.toast('warning', 'Vui lòng nhập họ tên');
        if (!dob)      return Admin.toast('warning', 'Vui lòng chọn ngày sinh');

        const payload = {
            full_name:       fullName,
            dob,
            gender:          document.getElementById('gender').value || undefined,
            phone:           document.getElementById('phone').value.trim() || undefined,
            address:         document.getElementById('address').value.trim() || undefined,
            hire_date:       document.getElementById('hireDate').value || undefined,
            employment_type: document.getElementById('employmentType').value,
        };

        const btn = document.getElementById('btnStep1');
        Admin.btnLoading(btn, true);
        const r = await Admin.api('POST', '/admin/api/admin/employees', payload);
        Admin.btnLoading(btn, false);

        if (!r.ok) {
            const s = r.data?.swal;
            Swal.fire({ icon: 'error', title: s?.title || 'Lỗi', text: s?.text || 'Đã xảy ra lỗi' });
            return;
        }

        const emp = r.data?.data;
        createdEmployeeId = emp.id;

        // Populate step 2 info card
        document.getElementById('s2Avatar').textContent = Admin.initials(emp.full_name);
        document.getElementById('s2Name').textContent   = emp.full_name;
        document.getElementById('s2Id').textContent     = emp.id;

        Admin.toast('success', `Đã tạo hồ sơ: ${emp.full_name}`);
        goStep(2);
    });

    /* ── Back to step 1 ── */
    document.getElementById('btnBackStep1').addEventListener('click', () => goStep(1));

    /* ── Step 2: Assign dept & position ── */
    document.getElementById('btnStep2').addEventListener('click', async () => {
        if (!createdEmployeeId) return;

        const dept = document.getElementById('deptSelect').value;
        const pos  = document.getElementById('posSelect').value;

        if (!dept && !pos) return Admin.toast('warning', 'Chọn ít nhất phòng ban hoặc chức danh');

        const payload = {};
        if (dept) payload.department_id = +dept;
        if (pos)  payload.position_id   = +pos;

        const btn = document.getElementById('btnStep2');
        Admin.btnLoading(btn, true);
        const r = await Admin.api('PATCH', `/admin/api/admin/employees/${createdEmployeeId}/work-info`, payload);
        Admin.btnLoading(btn, false);

        if (!r.ok) {
            const s = r.data?.swal;
            Swal.fire({ icon: 'error', title: s?.title || 'Lỗi', text: s?.text || 'Đã xảy ra lỗi' });
            return;
        }

        const emp = r.data?.data;
        document.getElementById('doneTitle').textContent = `${emp.full_name} đã được thêm vào hệ thống!`;
        document.getElementById('doneText').textContent  =
            `Phòng ban: ${emp.department_name || '—'} | Chức danh: ${emp.position_name || '—'}`;

        goStep(3);
    });

    /* ── Reset form ── */
    document.getElementById('btnCreateAnother').addEventListener('click', () => {
        createdEmployeeId = null;
        document.getElementById('fullName').value = '';
        document.getElementById('dob').value      = '';
        document.getElementById('gender').value   = '';
        document.getElementById('phone').value    = '';
        document.getElementById('address').value  = '';
        document.getElementById('hireDate').value = '';
        document.getElementById('employmentType').value = 'probation';
        goStep(1);
    });

    /* ── Init ── */
    loadMeta();
    goStep(1);
})();