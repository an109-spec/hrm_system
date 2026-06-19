/**
 * admin.js — Shared utilities for Admin module
 * Depends on: SweetAlert2 (Swal), Bootstrap 5
 */

const Admin = (() => {

    /* ── API helper ─────────────────────────────────────── */
    async function api(method, url, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };
        if (body) opts.body = JSON.stringify(body);

        const res  = await fetch(url, opts);
        const json = await res.json();
        return { ok: res.ok, status: res.status, data: json };
    }

    /* ── SweetAlert2 wrappers ────────────────────────────── */
    function toast(icon, title, timer = 3000) {
        Swal.fire({
            icon, title,
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer,
            timerProgressBar: true,
        });
    }

    function swalResponse(res) {
        const s = res.data?.swal;
        if (!s) return;
        if (res.ok) {
            toast(s.icon || 'success', s.title);
        } else {
            Swal.fire({ icon: s.icon || 'error', title: s.title, text: s.text });
        }
    }

    async function confirm(title, text, confirmText = 'Đồng ý', icon = 'warning') {
        const r = await Swal.fire({
            icon, title, text,
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor:  '#6b7280',
            confirmButtonText:  confirmText,
            cancelButtonText:   'Hủy',
        });
        return r.isConfirmed;
    }

    /* ── Avatar initials ─────────────────────────────────── */
    function initials(name = '') {
        return name.trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();
    }

    /* ── Date helpers ────────────────────────────────────── */
    function fmtDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('vi-VN');
    }

    /* ── Debounce ────────────────────────────────────────── */
    function debounce(fn, ms = 300) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
    }

    /* ── Loading overlay on button ───────────────────────── */
    function btnLoading(btn, loading) {
        if (loading) {
            btn.dataset.origText = btn.innerHTML;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Đang xử lý...';
            btn.disabled = true;
        } else {
            btn.innerHTML = btn.dataset.origText || btn.innerHTML;
            btn.disabled = false;
        }
    }

    /* ── Metadata cache (departments, positions, roles) ──── */
    let _meta = null;
    async function getMeta() {
        if (_meta) return _meta;
        const r = await api('GET', '/admin/api/metadata/filters');
        if (r.ok) _meta = r.data?.data;
        return _meta;
    }

    function fillSelect(sel, items, labelKey = 'name', placeholder = '-- Chọn --') {
        sel.innerHTML = `<option value="">${placeholder}</option>`;
        (items || []).forEach(i => {
            const o = document.createElement('option');
            o.value = i.id;
            o.textContent = i[labelKey];
            sel.appendChild(o);
        });
    }

    return { api, toast, swalResponse, confirm, initials, fmtDate, debounce, btnLoading, getMeta, fillSelect };
})();