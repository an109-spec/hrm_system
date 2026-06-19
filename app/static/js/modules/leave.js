/**
 * leave.js — HRM Leave Management Module
 * Namespace: Leave.*
 * Tổ chức theo từng trang / controller, tất cả đều dùng chung
 * các hàm tiện ích ở Leave.Utils và Leave.Api.
 */

(function (global) {
    "use strict";

    // ─────────────────────────────────────────────────────────────
    // CONSTANTS
    // ─────────────────────────────────────────────────────────────
    const STATUS_CONFIG = {
        pending:              { label: "Chờ duyệt",      cls: "bg-warning text-dark" },
        approved:             { label: "Đã duyệt",       cls: "bg-success" },
        rejected:             { label: "Từ chối",        cls: "bg-danger" },
        cancelled:            { label: "Đã hủy",         cls: "bg-dark" },
        supplement_requested: { label: "Chờ bổ sung",    cls: "bg-secondary" },
        complaint:            { label: "Khiếu nại",      cls: "bg-primary" },
    };

    const CANCELLABLE_STATUSES = ["pending", "pending_hr", "pending_admin", "supplement_requested"];

    // ─────────────────────────────────────────────────────────────
    // UTILS
    // ─────────────────────────────────────────────────────────────
    const Utils = {
        /**
         * Format ISO date string → DD/MM/YYYY
         */
        fmtDate(iso) {
            if (!iso) return "—";
            const [y, m, d] = iso.split("-");
            return `${d}/${m}/${y}`;
        },

        /**
         * Tạo badge HTML dựa trên status key
         */
        statusBadge(status) {
            const cfg = STATUS_CONFIG[status] || { label: status, cls: "bg-light text-dark" };
            return `<span class="badge ${cfg.cls}">${cfg.label}</span>`;
        },

        /**
         * Trả về label chữ của status
         */
        statusLabel(status) {
            return (STATUS_CONFIG[status] || { label: status }).label;
        },

        /**
         * Tính số ngày giữa 2 ISO date string
         */
        daysBetween(from, to) {
            if (!from || !to) return 0;
            const ms = new Date(to) - new Date(from);
            return Math.max(0, Math.floor(ms / 86400000) + 1);
        },

        /**
         * Hiển thị SweetAlert2 toast từ response swal payload
         */
        handleSwal(swal) {
            if (!swal || !global.Swal) return;
            Swal.fire({
                icon: swal.icon,
                title: swal.title,
                text: swal.text || "",
                toast: true,
                position: "top-end",
                showConfirmButton: false,
                timer: 3500,
                timerProgressBar: true,
            });
        },

        /**
         * Cắt chuỗi dài nếu cần
         */
        truncate(str, max = 60) {
            if (!str) return "—";
            return str.length > max ? str.slice(0, max) + "…" : str;
        },

        /**
         * Lấy initials từ full name
         */
        initials(name) {
            if (!name) return "?";
            return name.trim().split(" ").map(w => w[0]).slice(-2).join("").toUpperCase();
        },

        /**
         * Build query string từ object
         */
        toQuery(obj) {
            return Object.entries(obj)
                .filter(([, v]) => v !== undefined && v !== null && v !== "")
                .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
                .join("&");
        },

        /**
         * Disable button trong lúc loading
         */
        setLoading(btn, loading) {
            if (!btn) return;
            if (loading) {
                btn._originalHTML = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...`;
            } else {
                btn.disabled = false;
                btn.innerHTML = btn._originalHTML || "OK";
            }
        },

        /**
         * Parse form thành object
         */
        formToObj(form) {
            const data = {};
            new FormData(form).forEach((v, k) => {
                data[k] = v;
            });
            return data;
        },
    };

    // ─────────────────────────────────────────────────────────────
    // API LAYER
    // ─────────────────────────────────────────────────────────────
    const Api = {
        async _fetch(url, opts = {}) {
            const res = await fetch(url, {
                headers: { "Content-Type": "application/json", ...opts.headers },
                ...opts,
            });
            const json = await res.json().catch(() => ({}));
            return { ok: res.ok, status: res.status, data: json };
        },

        get(url) { return Api._fetch(url, { method: "GET" }); },
        post(url, body) { return Api._fetch(url, { method: "POST", body: JSON.stringify(body) }); },

        // ── Employee endpoints ──
        getMyRequests()       { return Api.get("/leave/my-requests"); },
        getCreateFormData()   { return Api.get("/leave/request/create"); },
        createRequest(body)   { return Api.post("/leave/request/create", body); },
        getDetail(id)         { return Api.get(`/leave/request/${id}`); },
        cancelRequest(id)     { return Api.post(`/leave/request/cancel/${id}`, {}); },

        // ── Manager endpoints ──
        getPendingList()       { return Api.get("/leave/manager/pending"); },
        getMgrDetail(id)       { return Api.get(`/leave/manager/request/${id}`); },
        approve(id)            { return Api.post(`/leave/manager/approve/${id}`, {}); },
        reject(id, reason)     { return Api.post(`/leave/manager/reject/${id}`, { reason }); },
        getLeaveRequests(q)    { return Api.get(`/leave/manager/leaves?${q}`); },
        getLeaveSummary()      { return Api.get("/leave/manager/leaves/summary"); },

        // ── Shared endpoints ──
        getTeamCalendar()      { return Api.get("/leave/team/calendar"); },
        getDeptReport()        { return Api.get("/leave/dept/report"); },
    };

    // ─────────────────────────────────────────────────────────────
    // RENDERERS — dùng chung nhiều trang
    // ─────────────────────────────────────────────────────────────
    const Render = {
        /**
         * Render bảng danh sách đơn của nhân viên
         */
        myRequestRows(list) {
            if (!list || !list.length) {
                return `<tr><td colspan="8" class="text-center py-5 text-muted">
                    <i class="fas fa-inbox fa-2x mb-2 d-block"></i>Chưa có đơn nghỉ phép nào.
                </td></tr>`;
            }
            return list.map(r => `
                <tr>
                    <td><span class="fw-semibold">${r.leave_type_name || r.type || "—"}</span></td>
                    <td>${Utils.fmtDate(r.from_date || r.from)}</td>
                    <td>${Utils.fmtDate(r.to_date || r.to)}</td>
                    <td><span class="badge bg-light text-dark border">${r.days || Utils.daysBetween(r.from_date, r.to_date)} ngày</span></td>
                    <td>${Utils.statusBadge(r.status)}</td>
                    <td class="text-muted small">${r.approver_name || r.approver || "—"}</td>
                    <td class="text-muted small">${Utils.fmtDate(r.created_at)}</td>
                    <td class="text-end">
                        <a href="/leave/request/${r.id}" class="btn btn-sm btn-outline-primary me-1">
                            <i class="fas fa-eye"></i>
                        </a>
                        ${CANCELLABLE_STATUSES.includes(r.status) ? `
                        <button class="btn btn-sm btn-outline-danger btn-cancel-req" data-id="${r.id}">
                            <i class="fas fa-times"></i>
                        </button>` : ""}
                    </td>
                </tr>
            `).join("");
        },

        /**
         * Render danh sách đơn chờ duyệt (Manager pending)
         */
        pendingCards(list) {
            if (!list || !list.length) {
                return `<div class="text-center py-5 text-muted">
                    <i class="fas fa-check-circle fa-2x mb-2 d-block text-success"></i>
                    Không có đơn nào đang chờ duyệt.
                </div>`;
            }
            return `<div class="row g-3">${list.map(r => `
                <div class="col-md-6 col-lg-4">
                    <div class="card border-0 pending-card h-100">
                        <div class="card-body p-4">
                            <div class="d-flex justify-content-between mb-3">
                                <div class="d-flex align-items-center gap-2">
                                    <div class="avatar-circle-sm bg-primary-soft">
                                        <span class="text-primary fw-bold small">${Utils.initials(r.employee_name || r.name)}</span>
                                    </div>
                                    <div>
                                        <div class="fw-semibold">${r.employee_name || r.name || "—"}</div>
                                        <div class="text-muted small">${r.department || "—"}</div>
                                    </div>
                                </div>
                                <span class="badge bg-warning text-dark align-self-start">Chờ duyệt</span>
                            </div>
                            <div class="mb-2">
                                <span class="text-muted small">Loại nghỉ: </span>
                                <span class="fw-semibold small">${r.leave_type_name || r.type || "—"}</span>
                            </div>
                            <div class="mb-2 d-flex gap-3">
                                <div>
                                    <div class="text-muted small">Từ</div>
                                    <div class="fw-semibold">${Utils.fmtDate(r.from_date || r.from)}</div>
                                </div>
                                <div>
                                    <div class="text-muted small">Đến</div>
                                    <div class="fw-semibold">${Utils.fmtDate(r.to_date || r.to)}</div>
                                </div>
                                <div>
                                    <div class="text-muted small">Ngày</div>
                                    <div class="fw-bold text-primary">${r.days || "—"}</div>
                                </div>
                            </div>
                            <p class="text-muted small mb-3 border-top pt-2">${Utils.truncate(r.reason, 80)}</p>
                            <div class="d-flex gap-2">
                                <button class="btn btn-success btn-sm flex-fill btn-quick-approve" data-id="${r.id}">
                                    <i class="fas fa-check me-1"></i>Duyệt
                                </button>
                                <button class="btn btn-outline-danger btn-sm flex-fill btn-quick-reject" data-id="${r.id}">
                                    <i class="fas fa-times me-1"></i>Từ chối
                                </button>
                                <a href="/leave/manager/request/${r.id}" class="btn btn-outline-secondary btn-sm">
                                    <i class="fas fa-eye"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            `).join("")}</div>`;
        },

        /**
         * Render rows cho bảng báo cáo phòng ban
         */
        reportRows(list) {
            if (!list || !list.length) {
                return `<tr><td colspan="11" class="text-center py-5 text-muted">
                    <i class="fas fa-inbox fa-2x mb-2 d-block"></i>Không có dữ liệu.
                </td></tr>`;
            }
            return list.map(r => `
                <tr>
                    <td>
                        <div class="fw-semibold">${r.name || "—"}</div>
                        <div class="text-muted small">${r.employee_code || ""}</div>
                    </td>
                    <td class="text-muted small">${r.department || "—"}</td>
                    <td class="text-muted small">${r.position || "—"}</td>
                    <td>${r.type || "—"}</td>
                    <td class="text-muted small">${Utils.fmtDate(r.from)}</td>
                    <td class="text-muted small">${Utils.fmtDate(r.to)}</td>
                    <td><span class="badge bg-light text-dark border">${r.days} ngày</span></td>
                    <td>
                        ${r.is_paid
                            ? `<span class="badge bg-success-soft text-success">Hưởng lương</span>`
                            : `<span class="badge bg-danger-soft text-danger">Không lương</span>`}
                    </td>
                    <td>${Utils.statusBadge(r.status)}</td>
                    <td>
                        ${r.is_emergency
                            ? `<span class="badge bg-danger"><i class="fas fa-exclamation me-1"></i>Khẩn</span>`
                            : `<span class="text-muted">—</span>`}
                    </td>
                    <td>
                        ${r.attachment
                            ? `<a href="${r.attachment}" target="_blank" class="btn btn-xs btn-outline-primary">
                                <i class="fas fa-paperclip"></i></a>`
                            : `<span class="text-muted small">—</span>`}
                    </td>
                </tr>
            `).join("");
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: MyRequests (my_requests.html)
    // ─────────────────────────────────────────────────────────────
    const MyRequests = {
        _data: [],
        _createModalEl: null,
        _detailModalEl: null,

        async init() {
            this._createModalEl = new bootstrap.Modal(document.getElementById("createLeaveModal"));
            this._detailModalEl = new bootstrap.Modal(document.getElementById("detailLeaveModal"));

            await this._loadList();
            this._bindEvents();
        },

        async _loadList() {
            const tbody = document.getElementById("myRequestsBody");
            const { ok, data } = await Api.getMyRequests();
            if (!ok) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-3">
                    Không thể tải dữ liệu.</td></tr>`;
                return;
            }
            this._data = data.data || [];
            tbody.innerHTML = Render.myRequestRows(this._data);
            this._updateStats(this._data);
        },

        _updateStats(list) {
            const total = 12; // default; API có thể trả về usage data
            const used = list.filter(r => r.status === "approved").reduce((s, r) => s + (r.days || 0), 0);
            const pending = list.filter(r => r.status === "pending").length;
            document.getElementById("statTotal").textContent = total;
            document.getElementById("statUsed").textContent = used;
            document.getElementById("statRemaining").textContent = Math.max(0, total - used);
            document.getElementById("statPending").textContent = pending;
        },

        _bindEvents() {
            // Open create modal
            document.getElementById("btnOpenCreateModal")?.addEventListener("click", () => {
                this._openCreateModal();
            });

            // Cancel buttons (event delegation)
            document.getElementById("myRequestsBody")?.addEventListener("click", async (e) => {
                const btn = e.target.closest(".btn-cancel-req");
                if (btn) {
                    const id = btn.dataset.id;
                    this._cancelRequest(id, btn);
                }
            });
        },

        async _openCreateModal() {
            const modal = document.getElementById("createLeaveModal");
            const body = document.getElementById("createModalBody");
            this._createModalEl.show();

            // Load form data
            const { ok, data } = await Api.getCreateFormData();
            if (!ok) {
                body.innerHTML = `<div class="text-center text-danger py-3">Không thể tải form.</div>`;
                return;
            }

            // Render inline form
            body.innerHTML = RequestForm._buildFormHTML(data.data);
            RequestForm._initFormLogic(body, (result) => {
                this._createModalEl.hide();
                Utils.handleSwal(result.swal);
                this._loadList();
            });
        },

        async _cancelRequest(id, btn) {
            const confirmed = await Swal.fire({
                title: "Hủy đơn?",
                text: "Bạn có chắc muốn hủy đơn nghỉ phép này không?",
                icon: "warning",
                showCancelButton: true,
                confirmButtonColor: "#d33",
                cancelButtonColor: "#6c757d",
                confirmButtonText: "Hủy đơn",
                cancelButtonText: "Không",
            });
            if (!confirmed.isConfirmed) return;

            Utils.setLoading(btn, true);
            const { ok, data } = await Api.cancelRequest(id);
            Utils.setLoading(btn, false);
            Utils.handleSwal(data.swal);
            if (ok) this._loadList();
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: RequestForm (request_form.html + inline modal)
    // ─────────────────────────────────────────────────────────────
    const RequestForm = {
        _leaveTypes: [],
        _onSuccess: null,

        async init() {
            const { ok, data } = await Api.getCreateFormData();
            if (!ok) { this._showError("Không thể tải dữ liệu form."); return; }
            this._leaveTypes = data.data?.leave_types || [];
            this._populateLeaveTypes();
            this._renderBalanceBar(data.data?.balance);
            this._initFormLogic(document, (result) => {
                Utils.handleSwal(result.swal);
                if (result.success) {
                    setTimeout(() => window.location.href = "/leave/my-requests", 1500);
                }
            });
        },

        _buildFormHTML(formData) {
            // Builds a minimal inline version for modal usage
            const types = (formData?.leave_types || [])
                .map(t => `<option value="${t.id}" data-code="${t.code || ""}">${t.name}</option>`)
                .join("");
            return `
                <div class="mb-3">
                    <label class="form-label fw-semibold">Loại nghỉ phép <span class="text-danger">*</span></label>
                    <select class="form-select" id="leaveTypeSelect" name="leave_type_id">
                        <option value="">— Chọn loại nghỉ —</option>${types}
                    </select>
                </div>
                <div class="row g-3 mb-3">
                    <div class="col-6">
                        <label class="form-label fw-semibold">Từ ngày</label>
                        <input type="date" class="form-control" id="fromDate" name="from_date">
                    </div>
                    <div class="col-6">
                        <label class="form-label fw-semibold">Đến ngày</label>
                        <input type="date" class="form-control" id="toDate" name="to_date">
                    </div>
                </div>
                <div class="mb-3">
                    <label class="form-label fw-semibold">Lý do nghỉ <span class="text-danger">*</span></label>
                    <textarea class="form-control" id="reasonInput" name="reason" rows="3" minlength="5"></textarea>
                </div>
                <div class="d-flex justify-content-end gap-2 mt-3 pt-3 border-top">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Hủy</button>
                    <button type="button" class="btn btn-primary" id="btnSubmitLeave">
                        <i class="fas fa-paper-plane me-1"></i>Gửi đơn
                    </button>
                </div>
            `;
        },

        _populateLeaveTypes() {
            const sel = document.getElementById("leaveTypeSelect");
            if (!sel || !this._leaveTypes.length) return;
            this._leaveTypes.forEach(t => {
                const opt = new Option(t.name, t.id);
                opt.dataset.code = t.code || "";
                sel.appendChild(opt);
            });
        },

        _renderBalanceBar(balance) {
            const bar = document.getElementById("balanceBar");
            if (!bar || !balance) return;
            bar.innerHTML = `
                <div class="d-flex gap-4 flex-wrap">
                    <div><span class="text-muted small">Tổng phép năm: </span>
                        <strong>${balance.total_days ?? "—"}</strong> ngày</div>
                    <div><span class="text-muted small">Đã dùng: </span>
                        <strong class="text-danger">${balance.used_days ?? "—"}</strong> ngày</div>
                    <div><span class="text-muted small">Còn lại: </span>
                        <strong class="text-success">${balance.remaining_days ?? "—"}</strong> ngày</div>
                </div>
            `;
        },

        _initFormLogic(root, onSuccess) {
            const typeSelect = root.querySelector("#leaveTypeSelect");
            const fromDate   = root.querySelector("#fromDate");
            const toDate     = root.querySelector("#toDate");
            const subtypeGrp = root.querySelector("#subtypeGroup");
            const relationGrp= root.querySelector("#relationGroup");
            const daysPreview= root.querySelector("#daysPreview");
            const daysCount  = root.querySelector("#daysCount");
            const submitBtn  = root.querySelector("#btnSubmitLeave");

            // Show/hide subtype group
            if (typeSelect && subtypeGrp) {
                typeSelect.addEventListener("change", () => {
                    const code = typeSelect.selectedOptions[0]?.dataset?.code || "";
                    subtypeGrp?.classList.toggle("d-none", code !== "PERSONAL");
                    relationGrp?.classList.add("d-none");
                });
            }

            // Show relation group
            root.querySelector("#subtypeSelect")?.addEventListener("change", (e) => {
                relationGrp?.classList.toggle("d-none", e.target.value !== "FUNERAL");
            });

            // Preview days
            const recalcDays = () => {
                if (!fromDate?.value || !toDate?.value) return;
                const days = Utils.daysBetween(fromDate.value, toDate.value);
                if (daysPreview) daysPreview.classList.remove("d-none");
                if (daysCount) daysCount.textContent = days;
            };
            fromDate?.addEventListener("change", recalcDays);
            toDate?.addEventListener("change", recalcDays);

            // Submit
            submitBtn?.addEventListener("click", async () => {
                const body = {
                    leave_type_id: root.querySelector("[name=leave_type_id]")?.value,
                    from_date:     root.querySelector("[name=from_date]")?.value,
                    to_date:       root.querySelector("[name=to_date]")?.value,
                    reason:        root.querySelector("[name=reason]")?.value?.trim(),
                    subtype:       root.querySelector("[name=subtype]")?.value || null,
                    relation:      root.querySelector("[name=relation]")?.value || null,
                };

                if (!body.leave_type_id || !body.from_date || !body.to_date || !body.reason) {
                    Swal.fire({ icon: "warning", title: "Thiếu thông tin", text: "Vui lòng điền đầy đủ các trường bắt buộc.", toast: true, position: "top-end", showConfirmButton: false, timer: 3000 });
                    return;
                }

                Utils.setLoading(submitBtn, true);
                const { ok, data } = await Api.createRequest(body);
                Utils.setLoading(submitBtn, false);

                if (typeof onSuccess === "function") {
                    onSuccess({ success: ok, swal: data.swal, data });
                } else {
                    Utils.handleSwal(data.swal);
                }
            });
        },

        _showError(msg) {
            document.querySelector(".col-lg-8")?.insertAdjacentHTML(
                "afterbegin",
                `<div class="alert alert-danger">${msg}</div>`
            );
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: RequestDetail (request_detail.html)
    // ─────────────────────────────────────────────────────────────
    const RequestDetail = {
        _leaveId: null,
        _leave: null,
        _cancelModal: null,

        async init(leaveId) {
            this._leaveId = leaveId;
            this._cancelModal = new bootstrap.Modal(document.getElementById("cancelModal"));
            await this._loadDetail();
        },

        async _loadDetail() {
            const { ok, data } = await Api.getDetail(this._leaveId);
            if (!ok) {
                Utils.handleSwal(data.swal);
                return;
            }
            this._leave = data.data;
            this._render(this._leave);
        },

        _render(leave) {
            document.getElementById("detailSkeleton")?.classList.add("d-none");
            document.getElementById("detailContent")?.classList.remove("d-none");

            const setText = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val || "—";
            };

            setText("dLeaveType",  leave.leave_type_name || leave.leave_type?.name);
            setText("dCreatedAt",  "Ngày gửi: " + Utils.fmtDate(leave.created_at));
            setText("dFromDate",   Utils.fmtDate(leave.from_date));
            setText("dToDate",     Utils.fmtDate(leave.to_date));
            setText("dDays",       (leave.days || Utils.daysBetween(leave.from_date, leave.to_date)) + " ngày");
            setText("dIsPaid",     leave.is_paid ? "✅ Hưởng lương" : "❌ Không lương");
            setText("dReason",     leave.reason);
            setText("dApprover",   leave.approver_name || leave.approver?.full_name);
            setText("dSentAt",     Utils.fmtDate(leave.created_at));

            const statusBadge = document.getElementById("dStatusBadge");
            if (statusBadge) statusBadge.outerHTML = Utils.statusBadge(leave.status);

            // Attachment
            if (leave.document_url) {
                document.getElementById("dDocumentRow")?.classList.remove("d-none");
                const link = document.getElementById("dDocumentLink");
                if (link) link.href = leave.document_url;
            }

            // Actions
            const actionsEl = document.getElementById("detailActions");
            if (actionsEl && CANCELLABLE_STATUSES.includes(leave.status)) {
                actionsEl.innerHTML = `
                    <button class="btn btn-outline-danger" id="btnCancelReq">
                        <i class="fas fa-times me-1"></i>Hủy đơn
                    </button>`;
                document.getElementById("btnCancelReq")?.addEventListener("click", () => {
                    this._cancelModal.show();
                });
            }

            document.getElementById("btnConfirmCancel")?.addEventListener("click", async () => {
                this._cancelModal.hide();
                const { ok, data } = await Api.cancelRequest(this._leaveId);
                Utils.handleSwal(data.swal);
                if (ok) setTimeout(() => window.location.href = "/leave/my-requests", 1500);
            });
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: ManagerPending (manager_pending.html)
    // ─────────────────────────────────────────────────────────────
    const ManagerPending = {
        _rejectModal: null,
        _currentId: null,

        async init() {
            this._rejectModal = new bootstrap.Modal(document.getElementById("rejectModal"));
            await this._loadList();
            this._bindRejectConfirm();
        },

        async _loadList() {
            const area = document.getElementById("pendingListArea");
            const { ok, data } = await Api.getPendingList();

            if (!ok) {
                area.innerHTML = `<div class="alert alert-danger">Không thể tải danh sách.</div>`;
                return;
            }

            const list = data.data || [];
            document.getElementById("pendingCountNum").textContent = list.length;
            area.innerHTML = Render.pendingCards(list);

            // Bind quick action buttons
            area.addEventListener("click", async (e) => {
                const approveBtn = e.target.closest(".btn-quick-approve");
                const rejectBtn  = e.target.closest(".btn-quick-reject");

                if (approveBtn) {
                    await this._quickApprove(approveBtn.dataset.id, approveBtn);
                }
                if (rejectBtn) {
                    this._currentId = rejectBtn.dataset.id;
                    document.getElementById("rejectReasonInput").value = "";
                    this._rejectModal.show();
                }
            });
        },

        async _quickApprove(id, btn) {
            const confirmed = await Swal.fire({
                title: "Phê duyệt đơn?",
                icon: "question",
                showCancelButton: true,
                confirmButtonText: "Duyệt",
                cancelButtonText: "Hủy",
                confirmButtonColor: "#198754",
            });
            if (!confirmed.isConfirmed) return;

            Utils.setLoading(btn, true);
            const { ok, data } = await Api.approve(id);
            Utils.handleSwal(data.swal);
            if (ok) await this._loadList();
            else Utils.setLoading(btn, false);
        },

        _bindRejectConfirm() {
            document.getElementById("btnConfirmReject")?.addEventListener("click", async () => {
                const reason = document.getElementById("rejectReasonInput")?.value?.trim();
                if (!reason) {
                    Swal.fire({ icon: "warning", title: "Thiếu lý do", toast: true, position: "top-end", showConfirmButton: false, timer: 2500 });
                    return;
                }
                this._rejectModal.hide();
                const { ok, data } = await Api.reject(this._currentId, reason);
                Utils.handleSwal(data.swal);
                if (ok) await this._loadList();
            });
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: ManagerApproval (manager_approval.html)
    // ─────────────────────────────────────────────────────────────
    const ManagerApproval = {
        _leaveId: null,
        _leave: null,
        _rejectModal: null,

        async init(leaveId) {
            this._leaveId = leaveId;
            this._rejectModal = new bootstrap.Modal(document.getElementById("rejectModal"));
            await this._loadDetail();
            this._bindButtons();
        },

        async _loadDetail() {
            const { ok, data } = await Api.getMgrDetail(this._leaveId);
            if (!ok) { Utils.handleSwal(data.swal); return; }
            this._leave = data.data;
            this._render(this._leave);
        },

        _render(leave) {
            document.getElementById("approvalSkeleton")?.classList.add("d-none");
            document.getElementById("approvalContent")?.classList.remove("d-none");

            const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || "—"; };

            const name = leave.employee_name || leave.employee?.full_name || "—";
            setText("aInitials", Utils.initials(name));
            setText("aName",     name);
            setText("aPosition", leave.position || leave.employee?.position?.job_title);
            setText("aCode",     leave.employee_code || leave.employee?.id);
            setText("aDept",     leave.department || leave.employee?.department?.name);
            setText("aLeaveType", leave.leave_type_name || leave.leave_type?.name);
            setText("aCreatedAt", "Ngày gửi: " + Utils.fmtDate(leave.created_at));
            setText("aFromDate",  Utils.fmtDate(leave.from_date));
            setText("aToDate",    Utils.fmtDate(leave.to_date));
            setText("aDays",      (leave.days || Utils.daysBetween(leave.from_date, leave.to_date)) + "");
            setText("aReason",    leave.reason);

            if (leave.document_url) {
                document.getElementById("aDocumentRow")?.classList.remove("d-none");
                const link = document.getElementById("aDocumentLink");
                if (link) link.href = leave.document_url;
            }

            // Balance info
            const balEl = document.getElementById("aBalanceInfo");
            if (balEl && leave.balance) {
                balEl.innerHTML = `
                    <div class="d-flex flex-column gap-2">
                        <div class="d-flex justify-content-between">
                            <span class="text-muted small">Tổng</span>
                            <strong>${leave.balance.total_days ?? "—"} ngày</strong>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span class="text-muted small">Đã dùng</span>
                            <strong class="text-danger">${leave.balance.used_days ?? "—"} ngày</strong>
                        </div>
                        <div class="d-flex justify-content-between border-top pt-2">
                            <span class="text-muted small">Còn lại</span>
                            <strong class="text-success">${leave.balance.remaining_days ?? "—"} ngày</strong>
                        </div>
                    </div>`;
            }
        },

        _bindButtons() {
            document.getElementById("btnApprove")?.addEventListener("click", async () => {
                const btn = document.getElementById("btnApprove");
                const confirmed = await Swal.fire({
                    title: "Phê duyệt đơn?",
                    icon: "question",
                    showCancelButton: true,
                    confirmButtonText: "Duyệt",
                    cancelButtonText: "Hủy",
                    confirmButtonColor: "#198754",
                });
                if (!confirmed.isConfirmed) return;
                Utils.setLoading(btn, true);
                const { ok, data } = await Api.approve(this._leaveId);
                Utils.handleSwal(data.swal);
                if (ok) setTimeout(() => window.location.href = "/leave/manager/pending", 1500);
                else Utils.setLoading(btn, false);
            });

            document.getElementById("btnReject")?.addEventListener("click", () => {
                document.getElementById("rejectReasonInput").value = "";
                this._rejectModal.show();
            });

            document.getElementById("btnConfirmReject")?.addEventListener("click", async () => {
                const reason = document.getElementById("rejectReasonInput")?.value?.trim();
                if (!reason) {
                    Swal.fire({ icon: "warning", title: "Nhập lý do từ chối", toast: true, position: "top-end", showConfirmButton: false, timer: 2500 });
                    return;
                }
                this._rejectModal.hide();
                const { ok, data } = await Api.reject(this._leaveId, reason);
                Utils.handleSwal(data.swal);
                if (ok) setTimeout(() => window.location.href = "/leave/manager/pending", 1500);
            });
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: Calendar (leave_calendar.html)
    // ─────────────────────────────────────────────────────────────
    const Calendar = {
        _events: [],
        _year: new Date().getFullYear(),
        _month: new Date().getMonth(), // 0-indexed

        async init() {
            await this._loadEvents();
            this._renderMonth();
            this._bindNav();
        },

        async _loadEvents() {
            const { ok, data } = await Api.getTeamCalendar();
            if (ok) this._events = data.data || [];
        },

        _renderMonth() {
            const label = document.getElementById("calMonthLabel");
            const body  = document.getElementById("calBody");
            if (!label || !body) return;

            const monthName = new Date(this._year, this._month).toLocaleDateString("vi-VN", { month: "long", year: "numeric" });
            label.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1);

            const firstDay = new Date(this._year, this._month, 1);
            const daysInMonth = new Date(this._year, this._month + 1, 0).getDate();
            // Week starts Monday; getDay() 0=Sun
            let startOffset = (firstDay.getDay() + 6) % 7;

            let html = "";
            // Empty cells
            for (let i = 0; i < startOffset; i++) {
                html += `<div class="cal-cell cal-empty"></div>`;
            }

            for (let d = 1; d <= daysInMonth; d++) {
                const dateStr = `${this._year}-${String(this._month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
                const dayEvents = this._getEventsForDate(dateStr);
                const isToday = dateStr === new Date().toISOString().slice(0, 10);
                const isWeekend = (startOffset + d - 1) % 7 >= 5;

                html += `<div class="cal-cell${isToday ? " cal-today" : ""}${isWeekend ? " cal-weekend" : ""}" data-date="${dateStr}">
                    <div class="cal-day-num">${d}</div>
                    ${dayEvents.slice(0, 3).map(ev => `
                        <div class="cal-event cal-event-${ev.status}" title="${ev.name}: ${Utils.fmtDate(ev.from_date)} → ${Utils.fmtDate(ev.to_date)}">
                            ${Utils.truncate(ev.employee_name || ev.name, 12)}
                        </div>`).join("")}
                    ${dayEvents.length > 3 ? `<div class="cal-event-more">+${dayEvents.length - 3} nữa</div>` : ""}
                </div>`;
            }
            body.innerHTML = html;

            // Day click
            body.addEventListener("click", (e) => {
                const cell = e.target.closest(".cal-cell[data-date]");
                if (cell) this._showDayDetail(cell.dataset.date);
            });
        },

        _getEventsForDate(dateStr) {
            return this._events.filter(ev => {
                const from = ev.from_date || ev.from;
                const to   = ev.to_date   || ev.to;
                return from && to && from <= dateStr && to >= dateStr;
            });
        },

        _showDayDetail(dateStr) {
            const panel = document.getElementById("dayDetailPanel");
            const label = document.getElementById("selectedDateLabel");
            const list  = document.getElementById("dayEventList");
            if (!panel || !list) return;

            panel.classList.remove("d-none");
            label.textContent = Utils.fmtDate(dateStr);

            const events = this._getEventsForDate(dateStr);
            if (!events.length) {
                list.innerHTML = `<div class="text-muted small">Không có ai nghỉ phép ngày này.</div>`;
                return;
            }
            list.innerHTML = events.map(ev => `
                <div class="d-flex align-items-center gap-2 py-2 border-bottom">
                    <div class="avatar-circle-sm bg-primary-soft">
                        <span class="text-primary fw-bold small">${Utils.initials(ev.employee_name || ev.name)}</span>
                    </div>
                    <div class="flex-grow-1">
                        <div class="fw-semibold small">${ev.employee_name || ev.name || "—"}</div>
                        <div class="text-muted" style="font-size:.75rem">${ev.leave_type_name || ev.type || "—"} · ${Utils.fmtDate(ev.from_date || ev.from)} → ${Utils.fmtDate(ev.to_date || ev.to)}</div>
                    </div>
                    ${Utils.statusBadge(ev.status)}
                </div>
            `).join("");
        },

        _bindNav() {
            document.getElementById("btnPrevMonth")?.addEventListener("click", () => {
                this._month--;
                if (this._month < 0) { this._month = 11; this._year--; }
                this._renderMonth();
            });
            document.getElementById("btnNextMonth")?.addEventListener("click", () => {
                this._month++;
                if (this._month > 11) { this._month = 0; this._year++; }
                this._renderMonth();
            });
            document.getElementById("btnToday")?.addEventListener("click", () => {
                this._year  = new Date().getFullYear();
                this._month = new Date().getMonth();
                this._renderMonth();
            });
        },
    };

    // ─────────────────────────────────────────────────────────────
    // MODULE: DeptReport (department_report.html)
    // ─────────────────────────────────────────────────────────────
    const DeptReport = {
        _data: [],

        async init() {
            await this._loadSummary();
            await this._loadReport();
            this._bindFilter();
        },

        async _loadSummary() {
            const { ok, data } = await Api.getLeaveSummary();
            if (!ok) return;
            const s = data.data;
            const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? "—"; };
            setText("sPending",    s.pending);
            setText("sApproved",   s.approved);
            setText("sRejected",   s.rejected);
            setText("sToday",      s.today);
            setText("sEmergency",  s.emergency);
            setText("sSupplement", s.supplement_requested);
        },

        async _loadReport(filters = {}) {
            const tbody = document.getElementById("reportBody");
            const q = Utils.toQuery(filters);
            const { ok, data } = await Api.getLeaveRequests(q);

            if (!ok) {
                tbody.innerHTML = `<tr><td colspan="11" class="text-center text-danger py-3">Không thể tải dữ liệu.</td></tr>`;
                return;
            }
            this._data = data.data || [];
            tbody.innerHTML = Render.reportRows(this._data);

            const countLabel = document.getElementById("reportCountLabel");
            if (countLabel) countLabel.textContent = `Hiển thị ${this._data.length} đơn`;
        },

        _bindFilter() {
            document.getElementById("reportFilterForm")?.addEventListener("submit", async (e) => {
                e.preventDefault();
                const form = e.target;
                const filters = Utils.formToObj(form);
                if (form.querySelector("#fEmergencyOnly")?.checked) filters.emergency_only = "true";
                await this._loadReport(filters);
            });

            document.getElementById("btnExport")?.addEventListener("click", () => {
                this._exportCSV();
            });
        },

        _exportCSV() {
            if (!this._data.length) return;
            const headers = ["Nhân viên","Phòng ban","Vị trí","Loại nghỉ","Từ","Đến","Số ngày","Hưởng lương","Trạng thái","Khẩn cấp"];
            const rows = this._data.map(r => [
                r.name, r.department, r.position, r.type,
                r.from, r.to, r.days,
                r.is_paid ? "Có" : "Không",
                Utils.statusLabel(r.status),
                r.is_emergency ? "Có" : "Không",
            ]);
            const csv = [headers, ...rows].map(r => r.map(v => `"${(v ?? "").toString().replace(/"/g, '""')}"`).join(",")).join("\n");
            const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `bao_cao_nghi_phep_${new Date().toISOString().slice(0,10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        },
    };

    // ─────────────────────────────────────────────────────────────
    // EXPORT NAMESPACE
    // ─────────────────────────────────────────────────────────────
    global.Leave = {
        Utils,
        Api,
        Render,
        MyRequests,
        RequestForm,
        RequestDetail,
        ManagerPending,
        ManagerApproval,
        Calendar,
        DeptReport,
    };

})(window);