/**
 * company_analytics.js
 * Trang phân tích tổng quan công ty cho HR/Admin.
 * Gọi 3 API: /hr/summary, /hr/stats/department, /hr/stats/position
 */
(function () {
    'use strict';

    /* ── Palette ────────────────────────────────────────────── */
    const COLORS = [
        '#4f46e5','#0ea5e9','#16a34a','#d97706',
        '#dc2626','#7c3aed','#0891b2','#059669',
        '#ea580c','#9333ea'
    ];

    let deptChart = null;
    let posChart  = null;

    /* ── Boot ───────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        loadSummary();
        loadDeptStats();
        loadPosStats();

        document.getElementById('btnExportAnalytics')
            ?.addEventListener('click', exportAnalytics);

        document.getElementById('deptTableSearch')
            ?.addEventListener('input', onDeptSearch);
    });

    /* ── 1. Summary KPIs ────────────────────────────────────── */
    async function loadSummary() {
        try {
            const res  = await fetch('/hr/summary');
            const json = await res.json();
            if (!json.swal || json.swal.icon !== 'success') throw new Error(json.swal?.text);

            const d = json.data;
            animateCount('kpiTotal',     d.total_employees    ?? 0);
            animateCount('kpiActive',    d.active_employees   ?? 0);
            animateCount('kpiProbation', d.probation_employees?? 0);
            animateCount('kpiExpiring',  d.expiring_contracts ?? 0);
        } catch (err) {
            console.error('loadSummary:', err);
        }
    }

    /* ── 2. Department stats ────────────────────────────────── */
    let allDeptRows = [];

    async function loadDeptStats() {
        try {
            const res  = await fetch('/hr/stats/department');
            const json = await res.json();
            if (!json.swal || json.swal.icon !== 'success') throw new Error(json.swal?.text);

            const depts = json.data?.departments ?? [];
            document.getElementById('deptTotalBadge').textContent =
                `${depts.length} phòng ban`;

            allDeptRows = depts;
            renderDeptChart(depts);
            renderDeptTable(depts);
        } catch (err) {
            console.error('loadDeptStats:', err);
        }
    }

    function renderDeptChart(depts) {
        const ctx = document.getElementById('deptChart');
        if (!ctx) return;

        const labels = depts.map(d => d.name);
        const values = depts.map(d => d.total_employees);

        if (deptChart) deptChart.destroy();

        deptChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: COLORS.slice(0, labels.length),
                    borderRadius: 6,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.y} nhân viên`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 },
                        grid: { color: '#f1f5f9' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });

        /* Custom legend */
        const legendEl = document.getElementById('deptLegend');
        if (legendEl) {
            legendEl.innerHTML = depts.map((d, i) => `
                <span class="hr-legend-item">
                    <span class="hr-legend-dot" style="background:${COLORS[i % COLORS.length]}"></span>
                    ${d.name}
                </span>`).join('');
        }
    }

    function renderDeptTable(depts) {
        const tbody  = document.getElementById('deptTableBody');
        const total  = depts.reduce((s, d) => s + (d.total_employees ?? 0), 0);

        if (!depts.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Không có dữ liệu</td></tr>';
            return;
        }

        tbody.innerHTML = depts.map((d, i) => {
            const pct = total ? Math.round((d.total_employees / total) * 100) : 0;
            return `
            <tr>
                <td class="text-muted small">${i + 1}</td>
                <td>${d.name}</td>
                <td class="text-center fw-semibold">${d.total_employees}</td>
                <td>
                    <div class="hr-dept-bar-wrap">
                        <div class="hr-dept-bar"
                             style="width:${Math.max(pct, 2)}%; background:${COLORS[i % COLORS.length]}">
                        </div>
                        <span class="hr-dept-bar-label">${pct}%</span>
                    </div>
                </td>
            </tr>`;
        }).join('');
    }

    function onDeptSearch() {
        const q     = (this.value || '').trim().toLowerCase();
        const rows  = q ? allDeptRows.filter(d => d.name.toLowerCase().includes(q)) : allDeptRows;
        renderDeptTable(rows);
    }

    /* ── 3. Position stats ──────────────────────────────────── */
    async function loadPosStats() {
        try {
            const res  = await fetch('/hr/stats/position');
            const json = await res.json();
            if (!json.swal || json.swal.icon !== 'success') throw new Error(json.swal?.text);

            const positions = json.data?.positions ?? [];
            document.getElementById('posTotalBadge').textContent =
                `${positions.length} chức danh`;

            renderPosChart(positions);
        } catch (err) {
            console.error('loadPosStats:', err);
        }
    }

    function renderPosChart(positions) {
        const ctx = document.getElementById('posChart');
        if (!ctx) return;

        const labels = positions.map(p => p.name);
        const values = positions.map(p => p.total_employees);

        if (posChart) posChart.destroy();

        posChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: COLORS.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12,
                            padding: 12,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.parsed} nhân viên`
                        }
                    }
                }
            }
        });
    }

    /* ── Export (stub) ──────────────────────────────────────── */
    function exportAnalytics() {
        window.showNotification?.('info', 'Chức năng xuất báo cáo đang được phát triển.');
    }

    /* ── Helpers ────────────────────────────────────────────── */
    function animateCount(id, target) {
        const el    = document.getElementById(id);
        if (!el) return;
        const step  = Math.ceil(target / 30);
        let   cur   = 0;
        const timer = setInterval(() => {
            cur = Math.min(cur + step, target);
            el.textContent = cur.toLocaleString('vi-VN');
            if (cur >= target) clearInterval(timer);
        }, 30);
    }

})();