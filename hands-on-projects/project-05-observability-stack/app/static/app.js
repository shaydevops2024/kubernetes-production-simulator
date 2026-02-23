// ObserveApp — Dashboard JavaScript
// Polls /api/stats every 3 seconds and updates the UI live.

async function fetchStats() {
    try {
        const r = await fetch('/api/stats');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        updateStats(data);
    } catch (e) {
        console.error('Stats fetch failed:', e);
    }
}

function updateStats(data) {
    // Metric cards
    document.getElementById('stat-sessions').textContent = data.active_sessions ?? '—';
    document.getElementById('stat-queue').textContent = data.queue_depth ?? '—';

    const sim = data.simulation || {};

    const errorEl = document.getElementById('stat-error-mode');
    errorEl.textContent = sim.error_mode ? 'ON' : 'OFF';
    errorEl.className = 'stat-value ' + (sim.error_mode ? 'state-on' : 'state-off');

    const slowEl = document.getElementById('stat-slow-mode');
    slowEl.textContent = sim.slow_mode ? 'ON' : 'OFF';
    slowEl.className = 'stat-value ' + (sim.slow_mode ? 'state-on' : 'state-off');

    // Header status badge
    const badge = document.getElementById('status-badge');
    if (sim.error_mode) {
        badge.className = 'status-badge status-degraded';
        badge.textContent = '● Degraded';
    } else if (sim.slow_mode) {
        badge.className = 'status-badge status-slow';
        badge.textContent = '● Slow';
    } else if (sim.high_traffic) {
        badge.className = 'status-badge status-traffic';
        badge.textContent = '● High Traffic';
    } else {
        badge.className = 'status-badge status-healthy';
        badge.textContent = '● Healthy';
    }

    // Button states
    updateButton('btn-traffic', sim.high_traffic);
    updateButton('btn-errors', sim.error_mode);
    updateButton('btn-slowdown', sim.slow_mode);

    // Log stream
    if (data.recent_logs && data.recent_logs.length > 0) {
        renderLogs(data.recent_logs);
    }

    const ts = new Date().toLocaleTimeString();
    document.getElementById('log-updated').textContent = `Updated ${ts}`;
    document.getElementById('header-ts').textContent = ts;
}

function updateButton(id, active) {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.textContent = active ? 'Disable' : 'Enable';
    btn.className = 'toggle-btn' + (active ? ' active' : '');
}

function renderLogs(logs) {
    const container = document.getElementById('log-stream');
    container.innerHTML = logs.map(entry => {
        const level = (entry.level || 'INFO').toUpperCase();
        const ts = entry.timestamp
            ? new Date(entry.timestamp).toLocaleTimeString('en-US', { hour12: false })
            : '';
        const msg = escHtml(entry.message || '');

        const extras = Object.entries(entry)
            .filter(([k]) => !['timestamp', 'level', 'message'].includes(k))
            .map(([k, v]) => `<span class="log-key">${escHtml(k)}=</span><span class="log-val">${escHtml(String(v))}</span>`)
            .join(' ');

        return `<div class="log-line log-${level.toLowerCase()}">
            <span class="log-ts">${ts}</span>
            <span class="log-level log-level-${level.toLowerCase()}">${level}</span>
            <span class="log-msg">${msg}</span>
            ${extras ? `<span class="log-extras">${extras}</span>` : ''}
        </div>`;
    }).join('');
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function toggle(type) {
    try {
        await fetch(`/api/simulate/${type}`, { method: 'POST' });
        await fetchStats();
    } catch (e) {
        console.error('Toggle failed:', e);
    }
}

async function resetAll() {
    try {
        await fetch('/api/simulate/reset', { method: 'POST' });
        await fetchStats();
    } catch (e) {
        console.error('Reset failed:', e);
    }
}

async function generateReport() {
    const btn = document.getElementById('btn-report');
    btn.textContent = 'Running…';
    btn.disabled = true;
    try {
        const r = await fetch('/api/report?report_type=manual', { method: 'POST' });
        const data = await r.json();
        btn.textContent = data.status === 'error' ? '✗ Failed' : '✓ Done';
        setTimeout(() => {
            btn.textContent = 'Run';
            btn.disabled = false;
        }, 2000);
        await fetchStats();
    } catch (e) {
        btn.textContent = '✗ Error';
        setTimeout(() => {
            btn.textContent = 'Run';
            btn.disabled = false;
        }, 2000);
    }
}

// Initial fetch + poll every 3 seconds
fetchStats();
setInterval(fetchStats, 3000);
