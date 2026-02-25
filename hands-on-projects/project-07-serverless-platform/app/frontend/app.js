/* ── Config ──────────────────────────────────────────────────────────────────── */
// In Docker Compose / K8s, the nginx proxy forwards /api/* → function-service
// Locally (without nginx), you can override with ?api=http://localhost:8001
const params = new URLSearchParams(location.search);
const API = params.get('api') || '/api';

let invocationHistory = [];
let scalingStats = { total: 0, success: 0, latencies: [] };
let cronInterval = null;
const CRON_CITIES = ['Tel Aviv', 'New York', 'London', 'Tokyo', 'Sydney', 'Berlin', 'São Paulo'];
let cronCityIdx = 0;

// Function metadata for hints / examples
const FN_EXAMPLES = {
    'hello-world':    { hint: 'Try: {"name": "DevOps Engineer"}', payload: { name: 'DevOps Engineer' } },
    'fibonacci':      { hint: 'Try n between 1 and 40. Higher n = more CPU.', payload: { n: 35 } },
    'text-processor': { hint: 'Paste any text you want analyzed.', payload: { text: 'Kubernetes is an amazing platform for running containerized workloads at scale in production environments.' } },
    'image-info':     { hint: 'Provide any image URL (mock analysis, no real fetch).', payload: { url: 'https://example.com/photo.jpg' } },
    'weather-report': { hint: 'Try any city name.', payload: { city: 'Tel Aviv' } },
};

/* ── Tab switching ───────────────────────────────────────────────────────────── */
function switchTab(name, el) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    if (el) el.classList.add('active');
}

/* ── Health checks ───────────────────────────────────────────────────────────── */
async function checkHealth() {
    // Service health
    try {
        const r = await fetch(API + '/health', { signal: AbortSignal.timeout(3000) });
        const dot = document.getElementById('svc-dot');
        const txt = document.getElementById('svc-text');
        if (r.ok) {
            dot.className = 'status-dot ok';
            txt.textContent = 'Function Service: OK';
        } else {
            dot.className = 'status-dot err';
            txt.textContent = 'Function Service: error';
        }
    } catch {
        document.getElementById('svc-dot').className = 'status-dot err';
        document.getElementById('svc-text').textContent = 'Function Service: offline';
    }

    // Runner health (indirect — invoke a cheap function)
    try {
        const r = await fetch(API + '/functions/hello-world/invoke', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload: { name: 'health-check' } }),
            signal: AbortSignal.timeout(5000),
        });
        const dot = document.getElementById('runner-dot');
        const txt = document.getElementById('runner-text');
        if (r.ok) {
            dot.className = 'status-dot ok';
            txt.textContent = 'Function Runner: OK';
        } else {
            dot.className = 'status-dot err';
            txt.textContent = 'Function Runner: error';
        }
    } catch {
        document.getElementById('runner-dot').className = 'status-dot err';
        document.getElementById('runner-text').textContent = 'Function Runner: offline';
    }
}

/* ── Dashboard ───────────────────────────────────────────────────────────────── */
async function loadDashboard() {
    try {
        const [fnRes, statsRes] = await Promise.all([
            fetch(API + '/functions'),
            fetch(API + '/stats'),
        ]);
        const { functions } = await fnRes.json();
        const stats = await statsRes.json();

        // Stat cards
        document.getElementById('stat-functions').textContent = functions.length;
        document.getElementById('stat-invocations').textContent = stats.total_invocations;

        const invFns = stats.functions.filter(f => f.invocations > 0);
        const avgLat = invFns.length
            ? Math.round(invFns.reduce((s, f) => s + f.avg_latency_ms, 0) / invFns.length)
            : '—';
        document.getElementById('stat-avg-latency').textContent = avgLat;

        document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();

        // Function list
        const list = document.getElementById('function-list');
        list.innerHTML = functions.map(f => `
            <div class="fn-row">
                <div style="display:flex;align-items:center;gap:8px">
                    <div class="fn-status"></div>
                    <span class="fn-name">${f.name}</span>
                </div>
                <span class="fn-trigger">${f.trigger}</span>
                <span style="font-size:12px;color:var(--gray-400)">${f.memory}</span>
            </div>
        `).join('');

        // Invocation stats bars
        const maxInv = Math.max(1, ...stats.functions.map(f => f.invocations));
        const statEl = document.getElementById('invocation-stats');
        statEl.innerHTML = stats.functions.map(f => `
            <div class="inv-row">
                <span style="font-size:12px;font-weight:600;color:var(--primary);font-family:monospace;min-width:130px">${f.name}</span>
                <div class="inv-bar-wrap">
                    <div class="inv-bar" style="width:${Math.round(f.invocations / maxInv * 100)}%"></div>
                </div>
                <span class="inv-count">${f.invocations}</span>
            </div>
        `).join('');

    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

/* ── Marketplace ─────────────────────────────────────────────────────────────── */
async function loadMarketplace() {
    const grid = document.getElementById('marketplace-grid');
    try {
        const r = await fetch(API + '/functions');
        const { functions } = await r.json();

        grid.innerHTML = functions.map(f => `
            <div class="fn-card" onclick="goInvoke('${f.name}')">
                <div class="fn-card-banner"></div>
                <div class="fn-card-body">
                    <div class="fn-card-top">
                        <span class="fn-card-name">${f.name}</span>
                        <span style="font-size:11px;background:var(--success-light);color:var(--success);padding:2px 8px;border-radius:99px;font-weight:600">Ready</span>
                    </div>
                    <div class="fn-card-desc">${f.description}</div>
                    <div class="fn-card-meta">
                        <span class="meta-tag primary">${f.trigger}</span>
                        <span class="meta-tag">${f.runtime}</span>
                        <span class="meta-tag">${f.memory}</span>
                        <span class="meta-tag">timeout: ${f.timeout_s}s</span>
                    </div>
                </div>
                <div class="fn-card-footer">
                    <span style="font-size:12px;color:var(--gray-500)">${f.invocations} invocations</span>
                    <button class="btn btn-primary btn-sm">Invoke &#9654;</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        grid.innerHTML = '<div class="loading-state" style="color:var(--danger)">Failed to load functions. Is the function-service running?</div>';
    }
}

function goInvoke(name) {
    document.getElementById('invoke-fn-select').value = name;
    onFunctionSelect();
    switchTab('invoke', document.querySelector('[data-tab="invoke"]'));
}

/* ── Invoke ──────────────────────────────────────────────────────────────────── */
function onFunctionSelect() {
    const name = document.getElementById('invoke-fn-select').value;
    const ex = FN_EXAMPLES[name];
    if (ex) {
        document.getElementById('invoke-hint').innerHTML = ex.hint;
    }
}

function loadExamplePayload() {
    const name = document.getElementById('invoke-fn-select').value;
    const ex = FN_EXAMPLES[name];
    if (ex) {
        document.getElementById('invoke-payload').value = JSON.stringify(ex.payload, null, 2);
    }
}

async function invokeFunction() {
    const name = document.getElementById('invoke-fn-select').value;
    const rawPayload = document.getElementById('invoke-payload').value.trim();

    let payload = {};
    if (rawPayload) {
        try {
            payload = JSON.parse(rawPayload);
        } catch {
            toast('Invalid JSON payload');
            return;
        }
    }

    const resultEl = document.getElementById('invoke-result');
    const bodyEl = document.getElementById('result-body');
    resultEl.style.display = 'none';
    bodyEl.textContent = 'Running...';

    const t0 = performance.now();
    try {
        const r = await fetch(`${API}/functions/${name}/invoke`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload }),
        });

        const data = await r.json();
        const elapsed = Math.round(performance.now() - t0);

        resultEl.style.display = 'block';
        document.getElementById('result-fn-name').textContent = name;
        document.getElementById('result-latency').textContent = `${data.latency_ms || elapsed} ms`;
        document.getElementById('result-count').textContent = `Invocation #${data.invocations_total || '?'}`;
        bodyEl.textContent = JSON.stringify(data.result?.output || data, null, 2);

        // Add to history
        invocationHistory.unshift({ name, latency: data.latency_ms || elapsed, time: new Date() });
        if (invocationHistory.length > 20) invocationHistory.pop();
        renderHistory();
        toast(`${name} executed in ${data.latency_ms || elapsed} ms`);

    } catch (e) {
        resultEl.style.display = 'block';
        bodyEl.textContent = 'Error: ' + e.message;
        toast('Invocation failed', true);
    }
}

function renderHistory() {
    const el = document.getElementById('invoke-history');
    if (!invocationHistory.length) return;
    el.innerHTML = invocationHistory.map(h => `
        <div class="history-row">
            <span class="history-fn">${h.name}</span>
            <span class="history-latency">${h.latency} ms</span>
            <span class="history-time">${h.time.toLocaleTimeString()}</span>
        </div>
    `).join('');
}

/* ── Scaling Demo ────────────────────────────────────────────────────────────── */
function resetScaling() {
    scalingStats = { total: 0, success: 0, latencies: [] };
    updateScalingUI();
    document.getElementById('scale-log').innerHTML = '';
}

function updateScalingUI() {
    document.getElementById('sc-total').textContent = scalingStats.total;
    document.getElementById('sc-success').textContent = scalingStats.success;
    const lats = scalingStats.latencies;
    document.getElementById('sc-min').textContent = lats.length ? Math.min(...lats) : '—';
    document.getElementById('sc-avg').textContent = lats.length ? Math.round(lats.reduce((a, b) => a + b, 0) / lats.length) : '—';
    document.getElementById('sc-max').textContent = lats.length ? Math.max(...lats) : '—';
}

async function scaleRunOne() {
    await runScalingRequest();
}

async function scaleRunBurst(n) {
    const promises = Array.from({ length: n }, () => runScalingRequest());
    await Promise.allSettled(promises);
}

async function runScalingRequest() {
    const t0 = performance.now();
    scalingStats.total++;
    try {
        const r = await fetch(`${API}/functions/fibonacci/invoke`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload: { n: 35 } }),
        });
        const data = await r.json();
        const elapsed = Math.round(performance.now() - t0);
        scalingStats.success++;
        scalingStats.latencies.push(elapsed);
        appendScaleLog('fibonacci', elapsed, true, data.result?.output?.result);
    } catch (e) {
        appendScaleLog('fibonacci', Math.round(performance.now() - t0), false, null);
    }
    updateScalingUI();
}

function appendScaleLog(fn, ms, ok, result) {
    const log = document.getElementById('scale-log');
    const timeStr = new Date().toLocaleTimeString();
    const resultStr = result !== null && result !== undefined ? ` → fib(35)=${result}` : '';
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-fn">${fn}</span>
        <span class="${ok ? 'log-ok' : 'log-err'}">${ok ? '✓' : '✗'}</span>
        <span style="color:var(--gray-500)">${resultStr}</span>
        <span class="log-ms">${ms} ms</span>
    `;
    log.prepend(entry);
    // Keep last 50 entries
    while (log.children.length > 50) log.removeChild(log.lastChild);
}

/* ── Cron simulation ─────────────────────────────────────────────────────────── */
async function simulateCron() {
    const city = CRON_CITIES[cronCityIdx % CRON_CITIES.length];
    cronCityIdx++;

    const log = document.getElementById('cron-log');
    const timeStr = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${timeStr}</span><span class="log-fn">weather-report</span><span style="color:var(--gray-400)">city=${city}</span><span class="log-ms">running...</span>`;
    log.prepend(entry);

    try {
        const t0 = performance.now();
        const r = await fetch(`${API}/functions/weather-report/invoke`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payload: { city } }),
        });
        const data = await r.json();
        const elapsed = Math.round(performance.now() - t0);
        const weather = data.result?.output;
        const summary = weather ? `${weather.temperature_c}°C, ${weather.condition}` : 'ok';
        entry.querySelector('.log-ms').textContent = `${elapsed} ms → ${summary}`;
        entry.querySelector('.log-ms').insertAdjacentHTML('beforebegin', '<span class="log-ok">✓ </span>');
    } catch (e) {
        entry.querySelector('.log-ms').textContent = 'failed';
        entry.insertAdjacentHTML('beforeend', '<span class="log-err">✗ error</span>');
    }
}

function startAutoCron() {
    if (cronInterval) return;
    document.getElementById('auto-cron-btn').style.display = 'none';
    document.getElementById('stop-cron-btn').style.display = '';
    simulateCron();
    cronInterval = setInterval(simulateCron, 5000);
}

function stopAutoCron() {
    clearInterval(cronInterval);
    cronInterval = null;
    document.getElementById('auto-cron-btn').style.display = '';
    document.getElementById('stop-cron-btn').style.display = 'none';
}

/* ── Toast ───────────────────────────────────────────────────────────────────── */
let toastTimer;
function toast(msg, isError = false) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.style.background = isError ? 'var(--danger)' : 'var(--gray-900)';
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3000);
}

/* ── Init ────────────────────────────────────────────────────────────────────── */
async function init() {
    await checkHealth();
    await loadDashboard();
    await loadMarketplace();
    onFunctionSelect();

    // Auto-refresh dashboard every 10s
    setInterval(async () => {
        await checkHealth();
        if (document.getElementById('tab-dashboard').classList.contains('active')) {
            await loadDashboard();
        }
    }, 10000);
}

document.addEventListener('DOMContentLoaded', init);
