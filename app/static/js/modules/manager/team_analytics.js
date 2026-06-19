/**
 * team_analytics.js — Manager Team Analytics
 * Talks to: GET /manager/attendance/dashboard?month=&year=
 */

const Analytics = (() => {
    /* ── chart refs ─────────────────────────────────────────── */
    let barChart    = null;
    let donutChart  = null;

    /* ── palette ────────────────────────────────────────────── */
    const COLORS = {
        on_time: '#2563eb',
        late:    '#d97706',
        absent:  '#dc2626',
        leave:   '#0891b2',
    };

    const LABELS = {
        on_time: 'Đúng giờ',
        late:    'Đi muộn',
        absent:  'Vắng',
        leave:   'Nghỉ phép',
    };

    /* ── helpers ────────────────────────────────────────────── */
    const api = url => fetch(url, { credentials: 'same-origin' }).then(r => r.json());

    function getControls() {
        return {
            month: parseInt(document.getElementById('ctrl-month').value),
            year:  parseInt(document.getElementById('ctrl-year').value),
        };
    }

    function setKpi(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value ?? '—';
    }

    /* ── init selects to current month/year ─────────────────── */
    function initSelects() {
        const now = new Date();
        const monthEl = document.getElementById('ctrl-month');
        const yearEl  = document.getElementById('ctrl-year');
        if (monthEl) monthEl.value = now.getMonth() + 1;
        if (yearEl)  yearEl.value  = now.getFullYear();
    }

    /* ── build bar chart ────────────────────────────────────── */
    function buildBarChart(rows) {
        const labels   = rows.map(r => r.full_name.split(' ').pop()); // last name
        const datasets = ['on_time', 'late', 'absent', 'leave'].map(key => ({
            label:           LABELS[key],
            data:            rows.map(r => r.stats[key] || 0),
            backgroundColor: COLORS[key] + 'cc',
            borderColor:     COLORS[key],
            borderWidth:     1,
            borderRadius:    4,
        }));

        const ctx = document.getElementById('chart-attendance-bar');
        if (!ctx) return;

        if (barChart) { barChart.destroy(); }

        barChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 11 }, boxWidth: 12, padding: 14 },
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} ngày`,
                        },
                    },
                },
                scales: {
                    x: {
                        stacked: false,
                        grid: { display: false },
                        ticks: { font: { size: 11 } },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, font: { size: 11 } },
                        grid: { color: '#f1f5f9' },
                    },
                },
            },
        });
    }

    /* ── build donut chart ───────────────────────────────────── */
    function buildDonut(totals) {
        const keys  = Object.keys(totals);
        const data  = keys.map(k => totals[k]);
        const bgCol = keys.map(k => COLORS[k] || '#94a3b8');
        const total = data.reduce((a, b) => a + b, 0);

        const ctx = document.getElementById('chart-donut');
        if (!ctx) return;

        if (donutChart) { donutChart.destroy(); }

        donutChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: keys.map(k => LABELS[k]),
                datasets: [{ data, backgroundColor: bgCol, borderWidth: 2, borderColor: '#fff' }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${ctx.parsed} ngày (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });

        /* legend below donut */
        const legendEl = document.getElementById('donut-legend');
        if (legendEl) {
            legendEl.innerHTML = keys.map(k => {
                const pct = total > 0 ? ((totals[k] / total) * 100).toFixed(1) : 0;
                return `
                    <div class="d-flex align-items-center gap-1">
                        <span style="width:10px;height:10px;border-radius:50%;background:${COLORS[k]};display:inline-block;"></span>
                        <span style="color:var(--mgr-muted);">${LABELS[k]}</span>
                        <strong style="color:var(--mgr-text);">${pct}%</strong>
                    </div>`;
            }).join('');
        }
    }

    /* ── ranking table ───────────────────────────────────────── */
    function buildRanking(rows) {
        const sorted = [...rows].sort((a, b) => (b.stats.on_time || 0) - (a.stats.on_time || 0));
        const tbody  = document.getElementById('ranking-tbody');
        if (!tbody) return;

        if (!sorted.length) {
            tbody.innerHTML = `<tr><td colspan="7">
                <div class="mgr-empty">
                    <div class="mgr-empty-icon"><i class="bi bi-bar-chart"></i></div>
                    <div class="mgr-empty-title">Chưa có dữ liệu</div>
                </div></td></tr>`;
            return;
        }

        const maxOnTime = Math.max(...sorted.map(r => r.stats.on_time || 0), 1);

        tbody.innerHTML = sorted.map((r, i) => {
            const s    = r.stats;
            const tot  = (s.on_time || 0) + (s.late || 0) + (s.absent || 0) + (s.leave || 0);
            const pct  = tot > 0 ? Math.round(((s.on_time || 0) / tot) * 100) : 0;
            const rank = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i+1}`;
            const initials = (r.full_name || '?').split(' ').slice(-2).map(w => w[0]).join('').toUpperCase();

            return `
                <tr>
                    <td class="text-center fw-bold" style="font-size:.95rem;">${rank}</td>
                    <td>
                        <div class="emp-cell">
                            <div class="emp-avatar">${initials}</div>
                            <div>
                                <div class="emp-name">${r.full_name}</div>
                                <div class="emp-code">ID ${r.employee_id}</div>
                            </div>
                        </div>
                    </td>
                    <td class="text-center">
                        <span class="mgr-badge primary">${s.on_time || 0}</span>
                    </td>
                    <td class="text-center">
                        <span class="mgr-badge warning">${s.late || 0}</span>
                    </td>
                    <td class="text-center">
                        <span class="mgr-badge danger">${s.absent || 0}</span>
                    </td>
                    <td class="text-center">
                        <span class="mgr-badge info">${s.leave || 0}</span>
                    </td>
                    <td>
                        <div style="font-size:.75rem; color:var(--mgr-muted); margin-bottom:3px;">${pct}% đúng giờ</div>
                        <div class="mgr-progress-bar">
                            <div class="mgr-progress-fill"
                                style="width:${pct}%;background:var(--mgr-primary);"></div>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    /* ── compute totals ──────────────────────────────────────── */
    function computeTotals(rows) {
        const totals = { on_time: 0, late: 0, absent: 0, leave: 0 };
        rows.forEach(r => {
            Object.keys(totals).forEach(k => {
                totals[k] += r.stats[k] || 0;
            });
        });
        return totals;
    }

    /* ── main load ───────────────────────────────────────────── */
    async function load() {
        const { month, year } = getControls();

        // Update period label
        const lbl = document.getElementById('chart-period-label');
        if (lbl) lbl.textContent = `Tháng ${month}/${year}`;

        // Reset KPIs
        ['kpi-ontime','kpi-late','kpi-absent','kpi-leave'].forEach(id => setKpi(id, '…'));

        const tbody = document.getElementById('ranking-tbody');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7"><div class="text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary"></div>
                <span class="ms-2 text-muted">Đang tải…</span>
            </div></td></tr>`;
        }

        try {
            const res = await api(`/manager/attendance/dashboard?month=${month}&year=${year}`);
            if (!res.success) throw new Error(res.swal?.text || 'Lỗi API');

            const rows   = res.data || [];
            const totals = computeTotals(rows);

            setKpi('kpi-ontime', totals.on_time);
            setKpi('kpi-late',   totals.late);
            setKpi('kpi-absent', totals.absent);
            setKpi('kpi-leave',  totals.leave);

            buildBarChart(rows);
            buildDonut(totals);
            buildRanking(rows);

        } catch (err) {
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="7">
                    <div class="mgr-empty">
                        <div class="mgr-empty-icon text-danger"><i class="bi bi-x-circle"></i></div>
                        <div class="mgr-empty-title">Không tải được dữ liệu</div>
                        <div class="mgr-empty-text">${err.message}</div>
                    </div></td></tr>`;
            }
        }
    }

    /* ── init ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        initSelects();
        load();
    });

    return { load };
})();