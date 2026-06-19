/**
 * admin.js
 * ========
 * Module JS dành cho trang quản trị nhân viên (HR / Admin).
 * Xử lý: Employee CRUD, profile lookup, avatar upload, dependent management
 * từ góc nhìn HR/Admin (employee_id-based API).
 *
 * Phụ thuộc: SweetAlert2 (đã khai báo trong base.html hoặc main.js)
 */

(function () {
  "use strict";

  // ══════════════════════════════════════════════════════════════════════
  // 1. API ENDPOINTS
  // ══════════════════════════════════════════════════════════════════════

  const API = {
    profile:    (empId) => `/personnel/profile/${empId}`,
    profileEdit:(empId) => `/personnel/profile/${empId}`,
    avatar:     (empId) => `/personnel/profile/${empId}/avatar`,
    dependents: (empId) => `/personnel/profile/${empId}/dependents`,
    dependent:  (empId, depId) => `/personnel/profile/${empId}/dependents/${depId}`,
    history:    (empId) => `/personnel/profile/${empId}/history`,
  };

  // ══════════════════════════════════════════════════════════════════════
  // 2. SHARED HELPERS
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Generic fetch wrapper that:
   * - handles JSON serialisation
   * - auto-shows SweetAlert on API-level errors
   * @returns {Promise<{ok: boolean, data: any}>}
   */
  async function apiFetch(url, { method = "GET", body = null, form = null } = {}) {
    const opts = { method, headers: {} };

    if (form) {
      opts.body = form; // FormData (file upload)
    } else if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }

    try {
      const res  = await fetch(url, opts);
      const data = await res.json();
      return { ok: !!data.success, data };
    } catch (err) {
      console.error("[admin.js] fetch error:", err);
      return { ok: false, data: null };
    }
  }

  function swalFromResponse(data, fallbackTitle = "Thông báo") {
    if (!data) {
      Swal.fire("Lỗi", "Không thể kết nối đến máy chủ.", "error");
      return;
    }
    Swal.fire({
      icon:               data.swal?.icon  || "info",
      title:              data.swal?.title || fallbackTitle,
      text:               data.swal?.text  || "",
      timer:              data.success ? 2000 : undefined,
      showConfirmButton:  !data.success,
    });
  }

  // ══════════════════════════════════════════════════════════════════════
  // 3. EMPLOYEE PROFILE (HR / ADMIN VIEW)
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Tải và render hồ sơ nhân viên vào container chỉ định.
   * @param {number}      employeeId
   * @param {HTMLElement} container  - element sẽ nhận HTML
   */
  async function loadEmployeeProfile(employeeId, container) {
    container.innerHTML = '<div class="text-center py-4"><span class="spinner-border spinner-border-sm"></span> Đang tải...</div>';
    const { ok, data } = await apiFetch(API.profile(employeeId));
    if (!ok || !data?.data) {
      container.innerHTML = '<p class="text-danger text-center py-4">Không thể tải hồ sơ nhân viên.</p>';
      return;
    }
    const p = data.data;
    const b = p.basic, j = p.job, s = p.system;

    container.innerHTML = `
      <div class="row g-3">
        <div class="col-md-3 text-center">
          <img src="${b.avatar || '/static/img/default_avatar.png'}"
               class="rounded-circle border shadow-sm"
               style="width:90px;height:90px;object-fit:cover"
               onerror="this.src='/static/img/default_avatar.png'">
          <div class="fw-bold mt-2">${b.full_name}</div>
          <small class="text-muted">${j.position || '—'}</small>
        </div>
        <div class="col-md-9">
          <div class="row g-2 small">
            <div class="col-6"><span class="text-muted">Giới tính:</span> ${b.gender?.label || '—'}</div>
            <div class="col-6"><span class="text-muted">Ngày sinh:</span> ${b.dob || '—'}</div>
            <div class="col-6"><span class="text-muted">Điện thoại:</span> ${b.phone || '—'}</div>
            <div class="col-6"><span class="text-muted">Email:</span> ${b.email || '—'}</div>
            <div class="col-6"><span class="text-muted">Phòng ban:</span> ${j.department || '—'}</div>
            <div class="col-6"><span class="text-muted">Trực thuộc:</span> ${j.manager || '—'}</div>
            <div class="col-6"><span class="text-muted">Loại hình:</span> ${j.employment_type?.label || '—'}</div>
            <div class="col-6"><span class="text-muted">Trạng thái:</span> ${j.working_status?.label || '—'}</div>
            <div class="col-6"><span class="text-muted">Ngày vào:</span> ${j.hire_date || '—'}</div>
            <div class="col-6"><span class="text-muted">Username:</span> <code>${s.username || '—'}</code></div>
          </div>
        </div>
      </div>`;
  }

  // ══════════════════════════════════════════════════════════════════════
  // 4. UPDATE EMPLOYEE PROFILE (HR / ADMIN)
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Gửi payload cập nhật hồ sơ theo employee_id (HR/Admin).
   * @param {number} employeeId
   * @param {object} payload    - {full_name, gender, dob, phone, address, ...}
   * @param {Function} [onSuccess]
   */
  async function updateEmployeeProfile(employeeId, payload, onSuccess) {
    const { ok, data } = await apiFetch(API.profileEdit(employeeId), { method: "PUT", body: payload });
    swalFromResponse(data, "Cập nhật hồ sơ");
    if (ok && typeof onSuccess === "function") onSuccess(data);
  }

  // ══════════════════════════════════════════════════════════════════════
  // 5. AVATAR UPLOAD (HR / ADMIN)
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Upload avatar cho nhân viên theo employee_id.
   * @param {number}   employeeId
   * @param {File}     file
   * @param {Function} [onSuccess]  - callback nhận { avatar: url }
   */
  async function uploadEmployeeAvatar(employeeId, file, onSuccess) {
    const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
    if (!file || !ALLOWED.includes(file.type)) {
      return Swal.fire("Định dạng không hỗ trợ", "Chỉ chấp nhận JPG, PNG, WEBP.", "warning");
    }
    if (file.size > 5 * 1024 * 1024) {
      return Swal.fire("Tệp quá lớn", "Vui lòng chọn tệp nhỏ hơn 5 MB.", "warning");
    }

    const fd = new FormData();
    fd.append("avatar", file);

    const { ok, data } = await apiFetch(API.avatar(employeeId), { method: "POST", form: fd });
    swalFromResponse(data, "Cập nhật ảnh đại diện");
    if (ok && typeof onSuccess === "function") onSuccess(data?.data);
  }

  // ══════════════════════════════════════════════════════════════════════
  // 6. DEPENDENTS (HR / ADMIN)
  // ══════════════════════════════════════════════════════════════════════

  /** Lấy danh sách người phụ thuộc của nhân viên */
  async function listDependents(employeeId) {
    const { data } = await apiFetch(API.dependents(employeeId));
    return data?.data || null;
  }

  /** Tạo người phụ thuộc mới cho nhân viên */
  async function createDependent(employeeId, payload, onSuccess) {
    const { ok, data } = await apiFetch(API.dependents(employeeId), { method: "POST", body: payload });
    swalFromResponse(data, "Thêm người phụ thuộc");
    if (ok && typeof onSuccess === "function") onSuccess(data?.data);
    return ok;
  }

  /** Cập nhật thông tin người phụ thuộc */
  async function updateDependent(employeeId, dependentId, payload, onSuccess) {
    const { ok, data } = await apiFetch(API.dependent(employeeId, dependentId), { method: "PUT", body: payload });
    swalFromResponse(data, "Cập nhật người phụ thuộc");
    if (ok && typeof onSuccess === "function") onSuccess(data?.data);
    return ok;
  }

  /** Xóa người phụ thuộc (sau khi xác nhận) */
  async function deleteDependent(employeeId, dependentId, depName, onSuccess) {
    const confirm = await Swal.fire({
      title:             "Bạn có chắc chắn?",
      text:              `Xóa người phụ thuộc "${depName}" khỏi hồ sơ nhân viên?`,
      icon:              "warning",
      showCancelButton:  true,
      confirmButtonColor:"#d33",
      cancelButtonColor: "#3085d6",
      confirmButtonText: "Đồng ý xóa",
      cancelButtonText:  "Hủy",
    });
    if (!confirm.isConfirmed) return false;

    const { ok, data } = await apiFetch(API.dependent(employeeId, dependentId), { method: "DELETE" });
    swalFromResponse(data, "Xóa người phụ thuộc");
    if (ok && typeof onSuccess === "function") onSuccess();
    return ok;
  }

  // ══════════════════════════════════════════════════════════════════════
  // 7. HISTORY
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Lấy lịch sử hoạt động của nhân viên (HR/Admin view).
   * @returns {Array} mảng log items
   */
  async function loadEmployeeHistory(employeeId) {
    const { data } = await apiFetch(API.history(employeeId));
    return data?.data || [];
  }

  // ══════════════════════════════════════════════════════════════════════
  // 8. EMPLOYEE LIST TABLE HELPERS
  // ══════════════════════════════════════════════════════════════════════

  const WS_LABEL = {
    active:             "Đang làm",
    probation:          "Thử việc",
    on_leave:           "Đang nghỉ phép",
    pending_resignation:"Chờ nghỉ việc",
    resigned:           "Đã nghỉ việc",
    inactive:           "Không hoạt động",
    terminated:         "Đã chấm dứt",
    retired:            "Đã về hưu",
  };

  const ET_LABEL = {
    permanent: "Chính thức",
    probation: "Thử việc",
    intern:    "Thực tập sinh",
    contract:  "Hợp đồng",
  };

  /** Xây dựng badge HTML trạng thái làm việc */
  function workingStatusBadge(ws) {
    const colorMap = {
      active: "success", probation: "warning", on_leave: "info",
      resigned: "danger", terminated: "danger", inactive: "secondary",
      pending_resignation: "warning", retired: "secondary",
    };
    const color = colorMap[ws] || "secondary";
    return `<span class="badge bg-${color}-subtle text-${color} rounded-pill px-2 py-1" style="font-size:.72rem">
              ${WS_LABEL[ws] || ws}
            </span>`;
  }

  /**
   * Render danh sách nhân viên vào <tbody>.
   * @param {Array}       employees
   * @param {HTMLElement} tbody
   * @param {object}      opts  - { showActions, onView, onEdit }
   */
  function renderEmployeeTable(employees, tbody, opts = {}) {
    if (!employees.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-5">
        <i class="fas fa-search me-1"></i>Không tìm thấy nhân viên nào.
      </td></tr>`;
      return;
    }

    tbody.innerHTML = employees.map((e, i) => {
      const avatar = e.avatar || "/static/img/default_avatar.png";
      const actions = opts.showActions !== false ? `
        <td class="text-end">
          <button class="btn btn-outline-primary btn-sm me-1" title="Xem hồ sơ"
                  onclick="window.__adminJS.viewEmployee(${e.id})">
            <i class="fas fa-eye"></i>
          </button>
          <button class="btn btn-outline-secondary btn-sm"  title="Chỉnh sửa"
                  onclick="window.__adminJS.editEmployee(${e.id})">
            <i class="fas fa-pen"></i>
          </button>
        </td>` : "<td></td>";

      return `
        <tr>
          <td class="text-muted small ps-3">${i + 1}</td>
          <td>
            <div class="d-flex align-items-center gap-2">
              <img src="${avatar}" alt="${e.full_name}"
                   style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid #e2e8f0"
                   onerror="this.src='/static/img/default_avatar.png'">
              <div>
                <div class="fw-semibold" style="font-size:.87rem;color:#1e293b">${e.full_name}</div>
                <div style="font-size:.75rem;color:#94a3b8">${e.email || '—'}</div>
              </div>
            </div>
          </td>
          <td style="font-size:.85rem">${e.department || '—'}</td>
          <td style="font-size:.85rem">${e.position   || '—'}</td>
          <td>${workingStatusBadge(e.working_status)}</td>
          <td style="font-size:.82rem;color:#64748b">${ET_LABEL[e.employment_type] || e.employment_type || '—'}</td>
          <td style="font-size:.82rem;color:#64748b">${e.hire_date || '—'}</td>
          ${actions}
        </tr>`;
    }).join('');
  }

  // ══════════════════════════════════════════════════════════════════════
  // 9. CONVENIENT ACTION SHORTCUTS (attached to window.__adminJS)
  //    Called by inline onclick in renderEmployeeTable
  // ══════════════════════════════════════════════════════════════════════

  function viewEmployee(empId) {
    window.location.href = `/personnel/profile/${empId}`;
  }

  function editEmployee(empId) {
    window.location.href = `/personnel/profile/${empId}/edit`;
  }

  // ══════════════════════════════════════════════════════════════════════
  // 10. CSV EXPORT
  // ══════════════════════════════════════════════════════════════════════

  /**
   * Xuất danh sách nhân viên ra file CSV (UTF-8 BOM cho Excel).
   * @param {Array}  employees
   * @param {string} filename
   */
  function exportEmployeesCSV(employees, filename = "nhan_vien") {
    if (!employees.length) {
      Swal.fire("Không có dữ liệu", "Không có nhân viên nào để xuất.", "info");
      return;
    }
    const header = ["ID", "Họ tên", "Email", "Điện thoại", "Phòng ban", "Chức danh", "Trạng thái", "Loại hình", "Ngày vào"];
    const rows   = employees.map(e => [
      e.id,
      `"${e.full_name}"`,
      e.email          || "",
      e.phone          || "",
      e.department     || "",
      e.position       || "",
      WS_LABEL[e.working_status]       || e.working_status       || "",
      ET_LABEL[e.employment_type]       || e.employment_type       || "",
      e.hire_date      || "",
    ]);

    const csv  = [header, ...rows].map(r => r.join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ══════════════════════════════════════════════════════════════════════
  // 11. PUBLIC API (exposed to global scope)
  // ══════════════════════════════════════════════════════════════════════

  window.__adminJS = {
    // Profile
    loadEmployeeProfile,
    updateEmployeeProfile,
    // Avatar
    uploadEmployeeAvatar,
    // Dependents
    listDependents,
    createDependent,
    updateDependent,
    deleteDependent,
    // History
    loadEmployeeHistory,
    // Table utils
    renderEmployeeTable,
    workingStatusBadge,
    exportEmployeesCSV,
    // Navigation shortcuts
    viewEmployee,
    editEmployee,
    // Constants
    WS_LABEL,
    ET_LABEL,
  };

  console.log("[admin.js] Module loaded ✓");
})();