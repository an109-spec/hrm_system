/**
 * system_settings.js
 * Quản lý cài đặt hệ thống HRM
 */

"use strict";

(function () {
    /* ── Config key → field ID map ───────────────────────────── */
    const FIELD_MAP = {
        // General
        system_name:        "cfgSystemName",
        admin_email:        "cfgAdminEmail",
        timezone:           "cfgTimezone",
        language:           "cfgLanguage",
        date_format:        "cfgDateFormat",
        // Security
        max_login_fail:     "cfgMaxLoginFail",
        lock_duration:      "cfgLockDuration",
        session_expiry:     "cfgSessionExpiry",
        min_password_len:   "cfgMinPasswordLen",
        require_special:    "cfgSpecialChar",
        csrf_protect:       "cfgCsrfProtect",
        multi_device:       "cfgMultiDevice",
        // HR
        annual_leave:       "cfgAnnualLeave",
        sick_leave:         "cfgSickLeave",
        probation_days:     "cfgProbationDays",
        contract_warn_days: "cfgContractWarnDays",
        auto_leave:         "cfgAutoLeave",
        carryover_leave:    "cfgCarryoverLeave",
        // Payroll
        payroll_day:        "cfgPayrollDay",
        min_wage:           "cfgMinWage",
        personal_deduct:    "cfgPersonalDeduct",
        dependant_deduct:   "cfgDependantDeduct",
        social_insurance:   "cfgSocialInsurance",
        // Attendance
        work_start:         "cfgWorkStart",
        work_end:           "cfgWorkEnd",
        break_time:         "cfgBreakTime",
        ot_rate:            "cfgOTRate",
        allow_late:         "cfgAllowLate",
        qr_only:            "cfgQrOnly",
        // Notification
        notif_contract:     "cfgNotifContract",
        notif_leave:        "cfgNotifLeave",
        notif_payroll:      "cfgNotifPayroll",
        notif_lock:         "cfgNotifLock",
        mail_from:          "cfgMailFrom",
        // Maintenance
        maintenance_mode:   "cfgMaintenance",
    };

    /* ── Track dirty state ───────────────────────────────────── */
    let isDirty = false;

    /* ── Init ────────────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", () => {
        initNav();
        loadSettings();
        bindEvents();
        updateSysInfo();
    });

    /* ── Navigation ──────────────────────────────────────────── */
    function initNav() {
        document.querySelectorAll(".settings-nav-item").forEach(item => {
            item.addEventListener("click", e => {
                e.preventDefault();
                const section = item.dataset.section;

                document.querySelectorAll(".settings-nav-item").forEach(i => i.classList.remove("active"));
                item.classList.add("active");

                document.querySelectorAll(".settings-section").forEach(s => s.classList.add("d-none"));
                document.getElementById("section-" + section)?.classList.remove("d-none");

                // Scroll to top of content on mobile
                document.querySelector(".content-wrapper")?.scrollTo({ top: 0, behavior: "smooth" });
            });
        });
    }

    /* ── Load settings from API / localStorage fallback ──────── */
    async function loadSettings() {
        // TODO: Replace with real API when available
        // const data = await apiFetch("/api/admin/settings");
        const stored = getStoredSettings();
        applySettings(stored);
    }

    function applySettings(cfg) {
        if (!cfg) return;
        Object.entries(FIELD_MAP).forEach(([key, fieldId]) => {
            const el = document.getElementById(fieldId);
            if (!el || !(key in cfg)) return;

            if (el.type === "checkbox") {
                el.checked = Boolean(cfg[key]);
            } else {
                el.value = cfg[key] ?? "";
            }
        });
    }

    function collectSettings() {
        const cfg = {};
        Object.entries(FIELD_MAP).forEach(([key, fieldId]) => {
            const el = document.getElementById(fieldId);
            if (!el) return;
            cfg[key] = el.type === "checkbox" ? el.checked : el.value;
        });
        return cfg;
    }

    /* ── localStorage helpers ─────────────────────────────────── */
    function getStoredSettings() {
        try {
            return JSON.parse(sessionStorage.getItem("hrm_settings") || "null");
        } catch (_) { return null; }
    }

    function storeSettings(cfg) {
        try { sessionStorage.setItem("hrm_settings", JSON.stringify(cfg)); } catch (_) {}
    }

    /* ── Save all ─────────────────────────────────────────────── */
    async function saveAll() {
        const cfg = collectSettings();
        const btn = document.getElementById("btnSaveAll");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Đang lưu…';

        try {
            // TODO: await apiFetch("/api/admin/settings", { method: "PUT", body: JSON.stringify(cfg) });
            await delay(800); // simulate network
            storeSettings(cfg);
            isDirty = false;

            Swal.fire({
                icon: "success",
                title: "Đã lưu cài đặt",
                text: "Các thay đổi sẽ có hiệu lực sau khi tải lại trang.",
                timer: 2500,
                showConfirmButton: false,
            });
        } catch (e) {
            Swal.fire({ icon: "error", title: "Lưu thất bại", text: String(e) });
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-floppy me-1"></i>Lưu tất cả thay đổi';
        }
    }

    /* ── Maintenance actions ─────────────────────────────────── */
    function clearCache() {
        Swal.fire({
            icon: "question",
            title: "Xóa cache hệ thống?",
            text: "Hệ thống sẽ tải lại cấu hình mới nhất từ database.",
            showCancelButton: true,
            confirmButtonText: "Xóa cache",
            cancelButtonText: "Hủy",
        }).then(async res => {
            if (!res.isConfirmed) return;
            // TODO: await apiFetch("/api/admin/cache", { method: "DELETE" });
            await delay(600);
            Swal.fire({ icon: "success", title: "Cache đã được xóa", timer: 1800, showConfirmButton: false });
        });
    }

    function exportLog() {
        Swal.fire({
            icon: "info",
            title: "Xuất log hệ thống",
            text: "Đang chuẩn bị file log 30 ngày gần nhất…",
            timer: 1500,
            showConfirmButton: false,
        }).then(() => {
            // TODO: window.open("/api/admin/logs/export");
            window.showNotification("info", "Tính năng xuất log đang được phát triển.");
        });
    }

    function resetAllSettings() {
        Swal.fire({
            icon: "warning",
            title: "Đặt lại toàn bộ cài đặt?",
            text: "Tất cả cấu hình sẽ trở về mặc định. Thao tác này không thể hoàn tác!",
            showCancelButton: true,
            confirmButtonColor: "#dc2626",
            confirmButtonText: "Đặt lại",
            cancelButtonText: "Hủy",
        }).then(async res => {
            if (!res.isConfirmed) return;
            sessionStorage.removeItem("hrm_settings");
            applySettings(getDefaultSettings());
            Swal.fire({ icon: "success", title: "Đã đặt lại cài đặt", timer: 1800, showConfirmButton: false });
        });
    }

    /* ── System info ─────────────────────────────────────────── */
    function updateSysInfo() {
        const now = new Date();
        document.getElementById("sysLastUpdate").textContent =
            now.toLocaleDateString("vi-VN") + " " + now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
        document.getElementById("sysDb").textContent = "PostgreSQL";
    }

    /* ── Dirty tracking ──────────────────────────────────────── */
    function markDirty() { isDirty = true; }

    /* ── Bind all events ─────────────────────────────────────── */
    function bindEvents() {
        document.getElementById("btnSaveAll").addEventListener("click", saveAll);
        document.getElementById("btnClearCache").addEventListener("click", clearCache);
        document.getElementById("btnExportLog").addEventListener("click", exportLog);
        document.getElementById("btnResetAll").addEventListener("click", resetAllSettings);

        // Dirty tracking
        Object.values(FIELD_MAP).forEach(fieldId => {
            const el = document.getElementById(fieldId);
            if (!el) return;
            el.addEventListener("change", markDirty);
            if (el.tagName === "INPUT" && el.type !== "checkbox") {
                el.addEventListener("input", markDirty);
            }
        });

        // Warn before unload
        window.addEventListener("beforeunload", e => {
            if (isDirty) { e.preventDefault(); e.returnValue = ""; }
        });
    }

    /* ── Defaults ─────────────────────────────────────────────── */
    function getDefaultSettings() {
        return {
            system_name: "HRM System", admin_email: "", timezone: "Asia/Ho_Chi_Minh",
            language: "vi", date_format: "DD/MM/YYYY",
            max_login_fail: 5, lock_duration: 30, session_expiry: 24, min_password_len: 8,
            require_special: true, csrf_protect: true, multi_device: false,
            annual_leave: 12, sick_leave: 5, probation_days: 60, contract_warn_days: 30,
            auto_leave: true, carryover_leave: false,
            payroll_day: 25, min_wage: 4960000, personal_deduct: 11000000, dependant_deduct: 4400000,
            social_insurance: true,
            work_start: "08:00", work_end: "17:30", break_time: 60, ot_rate: 1.5,
            allow_late: true, qr_only: false,
            notif_contract: true, notif_leave: true, notif_payroll: true, notif_lock: true,
            mail_from: "",
            maintenance_mode: false,
        };
    }

    /* ── Utils ────────────────────────────────────────────────── */
    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function apiFetch(url, options = {}) {
        const res = await fetch(url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return res.json();
    }
})();