'use strict';

/* ============================================================
   Configuration
   ============================================================ */
const CONFIG = {
    KONG_URL: 'http://localhost:8888',           // Kong proxy
    ANALYTICS_URL: 'http://localhost:8888/analytics', // Analytics via Kong
};

/* ============================================================
   State
   ============================================================ */
const state = {
    token: null,
    tokenPayload: null,
    tokenInfo: null,
    rateLimitSent: 0,
    rateLimitOk: 0,
    rateLimitBlocked: 0,
    rateLimitRemaining: null,
    currentTab: 'dashboard',
    refreshInterval: null,
};

/* ============================================================
   Protected endpoints (require JWT)
   ============================================================ */
const PROTECTED_PATHS = [
    '/v1/users/me',
    '/v1/orders',
    '/v2/products',
    '/v2/users/me',
    '/auth/validate',
];

/* ============================================================
   Initialisation
   ============================================================ */
function init() {
    updateEndpoint();
    checkHealth();
    loadDashboard();

    // Auto-refresh every 10 seconds
    state.refreshInterval = setInterval(() => {
        checkHealth();
        if (state.currentTab === 'dashboard') {
            loadDashboard();
        }
        if (state.currentTab === 'traffic') {
            loadGatewayConfig();
        }
    }, 10000);
}

/* ============================================================
   Tab switching
   ============================================================ */
function switchTab(tab, el) {
    // Hide all panels
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    // Deactivate all nav items
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    // Show target panel
    const panel = document.getElementById('tab-' + tab);
    if (panel) panel.classList.add('active');

    // Activate nav item
    if (el) el.classList.add('active');

    state.currentTab = tab;

    // Lazy-load tab data
    if (tab === 'dashboard') loadDashboard();
    if (tab === 'traffic')   loadGatewayConfig();
}

/* ============================================================
   Health checks — sidebar status dots
   ============================================================ */
async function checkHealth() {
    // Kong / API service health
    try {
        const res = await fetch(CONFIG.KONG_URL + '/health', { signal: AbortSignal.timeout(4000) });
        if (res.ok) {
            setStatusDot('api', true, 'API Service OK');
            setStatusDot('kong', true, 'Kong Gateway OK');
        } else {
            setStatusDot('api', false, 'API returned ' + res.status);
        }
    } catch (e) {
        setStatusDot('api', false, 'API unreachable');
        setStatusDot('kong', false, 'Kong unreachable');
    }

    // Analytics service health
    try {
        const res = await fetch(CONFIG.ANALYTICS_URL + '/health', { signal: AbortSignal.timeout(4000) });
        if (res.ok) {
            const data = await res.json();
            setStatusDot('kong', data.kong_available, data.kong_available ? 'Kong Gateway OK' : 'Kong unavailable');
        }
    } catch (e) {
        // analytics unreachable — keep existing kong dot
    }
}

function setStatusDot(service, healthy, text) {
    const dot  = document.getElementById(service + '-status-dot');
    const txt  = document.getElementById(service + '-status-text');
    if (!dot || !txt) return;
    dot.className = 'status-dot ' + (healthy ? 'healthy' : 'down');
    txt.textContent = text;
}

/* ============================================================
   Dashboard — load stats + routes + plugins
   ============================================================ */
async function loadDashboard() {
    try {
        const [statsRes, routesRes] = await Promise.all([
            fetch(CONFIG.ANALYTICS_URL + '/stats', { signal: AbortSignal.timeout(5000) }),
            fetch(CONFIG.ANALYTICS_URL + '/routes', { signal: AbortSignal.timeout(5000) }),
        ]);

        if (statsRes.ok) {
            const data = await statsRes.json();
            renderDashboardStats(data);
        }

        if (routesRes.ok) {
            const data = await routesRes.json();
            renderDashboardRoutes(data.routes || []);
        }

        // Also load plugins for the plugins card
        const pluginsRes = await fetch(CONFIG.ANALYTICS_URL + '/plugins', { signal: AbortSignal.timeout(5000) });
        if (pluginsRes.ok) {
            const data = await pluginsRes.json();
            renderDashboardPlugins(data.plugins || []);
        }

    } catch (e) {
        showAnalyticsError();
    }
}

function renderDashboardStats(data) {
    const kong = data.kong || {};
    const api  = data.api_service || {};

    // Stat cards
    setText('stat-services',  kong.services_count  ?? '—');
    setText('stat-routes',    kong.routes_count    ?? '—');
    setText('stat-plugins',   kong.plugins_count   ?? '—');
    setText('stat-consumers', kong.consumers_count ?? '—');

    // Last updated
    if (data.last_updated) {
        const d = new Date(data.last_updated * 1000);
        setText('last-updated', d.toLocaleTimeString());
    }

    // Metrics list
    const list = document.getElementById('metrics-list');
    if (!list) return;

    const errorRate = typeof api.error_rate === 'number' ? (api.error_rate * 100).toFixed(1) + '%' : '0.0%';
    const uptime    = api.uptime_seconds ? formatUptime(api.uptime_seconds) : '—';

    const rows = [
        { key: 'Total Requests',    val: fmtNum(api.total_requests),  cls: '' },
        { key: 'Total Errors',      val: fmtNum(api.total_errors),    cls: api.total_errors > 0 ? 'danger' : 'success' },
        { key: 'Error Rate',        val: errorRate,                    cls: parseFloat(errorRate) > 5 ? 'danger' : 'success' },
        { key: 'Rate Limit Hits',   val: fmtNum(api.rate_limit_hits), cls: api.rate_limit_hits > 0 ? 'warning' : '' },
        { key: 'Auth Failures',     val: fmtNum(api.auth_failures),   cls: api.auth_failures > 0 ? 'danger' : '' },
        { key: 'Uptime',            val: uptime,                       cls: 'success' },
        { key: 'Active Connections',val: fmtNum(kong.connections_active), cls: '' },
        { key: 'Total Proxied',     val: fmtNum(kong.total_requests), cls: '' },
    ];

    list.innerHTML = rows.map(r => `
        <div class="metric-row">
            <span class="metric-key">${r.key}</span>
            <span class="metric-val ${r.cls}">${r.val}</span>
        </div>
    `).join('');
}

function renderDashboardRoutes(routes) {
    const el = document.getElementById('dashboard-routes');
    const count = document.getElementById('routes-count');
    if (!el) return;

    if (count) count.textContent = routes.length;

    if (routes.length === 0) {
        el.innerHTML = '<div class="loading-state">No routes configured</div>';
        return;
    }

    el.innerHTML = '<div style="padding: 0 4px">' + routes.map(r => `
        <div class="route-chip">
            <span class="route-name">${escHtml(r.name || 'unnamed')}</span>
            <span class="route-path">${escHtml((r.paths || []).join(', '))}</span>
        </div>
    `).join('') + '</div>';
}

function renderDashboardPlugins(plugins) {
    const el    = document.getElementById('dashboard-plugins');
    const count = document.getElementById('plugins-count');
    if (!el) return;

    if (count) count.textContent = plugins.length;

    if (plugins.length === 0) {
        el.innerHTML = '<div class="loading-state">No plugins active</div>';
        return;
    }

    el.innerHTML = plugins.map(p => `
        <span class="plugin-badge ${escHtml(p.scope || 'global')}">
            ${escHtml(p.name)}
            <span style="opacity:0.6;font-weight:400">${escHtml(p.scope)}</span>
        </span>
    `).join('');
}

function showAnalyticsError() {
    const placeholders = ['metrics-list', 'dashboard-routes', 'dashboard-plugins'];
    placeholders.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = '<div class="loading-state" style="color:var(--danger)">Analytics service unreachable — is Kong running?</div>';
        }
    });
}

/* ============================================================
   Gateway Config tab — services, routes, plugins, consumers
   ============================================================ */
async function loadGatewayConfig() {
    try {
        const [svcRes, rtRes, plRes, cnRes] = await Promise.all([
            fetch(CONFIG.ANALYTICS_URL + '/services', { signal: AbortSignal.timeout(5000) }),
            fetch(CONFIG.ANALYTICS_URL + '/routes',   { signal: AbortSignal.timeout(5000) }),
            fetch(CONFIG.ANALYTICS_URL + '/plugins',  { signal: AbortSignal.timeout(5000) }),
            fetch(CONFIG.ANALYTICS_URL + '/consumers',{ signal: AbortSignal.timeout(5000) }),
        ]);

        if (svcRes.ok) renderServicesTable((await svcRes.json()).services || []);
        if (rtRes.ok)  renderRoutesTable((await rtRes.json()).routes     || []);
        if (plRes.ok)  renderPluginsCards((await plRes.json()).plugins   || []);
        if (cnRes.ok)  renderConsumersGrid((await cnRes.json()).consumers || []);

    } catch (e) {
        console.warn('Gateway config load failed:', e.message);
    }
}

function renderServicesTable(services) {
    const tbody = document.getElementById('services-tbody');
    const count = document.getElementById('tc-services-count');
    if (!tbody) return;
    if (count) count.textContent = services.length;

    if (services.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--gray-400);padding:20px">No services configured</td></tr>';
        return;
    }

    tbody.innerHTML = services.map(s => `
        <tr>
            <td><strong>${escHtml(s.name)}</strong></td>
            <td class="table-mono">${escHtml(s.host)}</td>
            <td>${escHtml(String(s.port))}</td>
            <td><span class="badge badge-primary">${escHtml(s.protocol)}</span></td>
            <td>${escHtml(String(s.retries))}</td>
        </tr>
    `).join('');
}

function renderRoutesTable(routes) {
    const tbody = document.getElementById('routes-tbody');
    const count = document.getElementById('tc-routes-count');
    if (!tbody) return;
    if (count) count.textContent = routes.length;

    if (routes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--gray-400);padding:20px">No routes configured</td></tr>';
        return;
    }

    tbody.innerHTML = routes.map(r => `
        <tr>
            <td><strong>${escHtml(r.name || '—')}</strong></td>
            <td class="table-mono">${escHtml((r.paths || []).join(', ') || '—')}</td>
            <td>${(r.methods || ['GET']).map(m => `<span class="method-badge ${escHtml(m)}">${escHtml(m)}</span>`).join(' ')}</td>
        </tr>
    `).join('');
}

function renderPluginsCards(plugins) {
    const grid  = document.getElementById('plugins-grid');
    const count = document.getElementById('tc-plugins-count');
    if (!grid) return;
    if (count) count.textContent = plugins.length;

    if (plugins.length === 0) {
        grid.innerHTML = '<div style="color:var(--gray-400);font-size:13px">No plugins configured</div>';
        return;
    }

    const scopeColor = { global: 'badge-primary', route: 'badge-success', service: 'badge-warning' };

    grid.innerHTML = plugins.map(p => `
        <div class="plugin-card">
            <div class="plugin-card-name">${escHtml(p.name)}</div>
            <div class="plugin-card-meta">
                <span class="badge ${scopeColor[p.scope] || 'badge-gray'}">${escHtml(p.scope)}</span>
                <span class="badge ${p.enabled ? 'badge-success' : 'badge-danger'}">${p.enabled ? 'enabled' : 'disabled'}</span>
            </div>
        </div>
    `).join('');
}

function renderConsumersGrid(consumers) {
    const grid  = document.getElementById('consumers-list');
    const count = document.getElementById('tc-consumers-count');
    if (!grid) return;
    if (count) count.textContent = consumers.length;

    if (consumers.length === 0) {
        grid.innerHTML = '<div style="color:var(--gray-400);font-size:13px">No consumers configured</div>';
        return;
    }

    grid.innerHTML = consumers.map(c => {
        const name   = c.username || 'unknown';
        const letter = name[0].toUpperCase();
        const shortId = (c.id || '').slice(0, 8) + '...';
        return `
            <div class="consumer-card">
                <div class="consumer-avatar">${escHtml(letter)}</div>
                <div class="consumer-name">${escHtml(name)}</div>
                <div class="consumer-id">${escHtml(shortId)}</div>
            </div>
        `;
    }).join('');
}

/* ============================================================
   API Explorer
   ============================================================ */
const AUTH_REQUIRED = ['/v1/users/me', '/v1/orders', '/v2/products', '/v2/users/me', '/auth/validate'];

function updateEndpoint() {
    const sel  = document.getElementById('endpoint-select');
    const note = document.getElementById('endpoint-note');
    if (!sel || !note) return;

    const path = sel.value;
    const needsAuth = AUTH_REQUIRED.includes(path);

    if (needsAuth) {
        note.textContent = 'This endpoint requires a valid JWT — enable "Use JWT Token" or login in Auth & JWT tab.';
        note.className = 'form-note auth-required';
    } else {
        note.textContent = 'This endpoint is public — no authentication required.';
        note.className = 'form-note';
    }
}

function toggleAuth() {
    // The checkbox state is read directly in sendRequest(); nothing extra needed here
    updateEndpoint();
}

async function sendRequest() {
    const method   = document.getElementById('http-method').value;
    const endpoint = document.getElementById('endpoint-select').value;
    const useAuth  = document.getElementById('use-auth').checked;

    const headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    };

    if (useAuth && state.token) {
        headers['Authorization'] = 'Bearer ' + state.token;
    }

    const url = CONFIG.KONG_URL + endpoint;

    // Show request headers immediately
    showExplorerResponse();
    document.getElementById('req-headers').textContent = formatHeaders(headers, method, endpoint);
    document.getElementById('resp-body').textContent = 'Sending...';
    document.getElementById('kong-headers').innerHTML = '';
    document.getElementById('resp-status').textContent = '';
    document.getElementById('resp-time').textContent = '';

    const t0 = Date.now();

    try {
        const res = await fetch(url, {
            method,
            headers,
            signal: AbortSignal.timeout(8000),
        });

        const elapsed = Date.now() - t0;
        let body;
        try {
            body = await res.json();
        } catch {
            body = await res.text().catch(() => '(empty)');
        }

        renderExplorerResponse(res, body, elapsed, headers, method, endpoint);

    } catch (err) {
        const elapsed = Date.now() - t0;
        const isTimeout = err.name === 'TimeoutError' || err.name === 'AbortError';
        const msg = isTimeout
            ? 'Request timed out. Is Kong running at ' + CONFIG.KONG_URL + '?'
            : 'Connection failed: ' + err.message + '\n\nMake sure Kong is running:\n  kubectl port-forward svc/kong-proxy 8888:80 -n kong';

        document.getElementById('resp-body').textContent = msg;
        document.getElementById('resp-status').textContent = 'ERR';
        document.getElementById('resp-status').className = 'status-badge err';
        document.getElementById('resp-time').textContent = elapsed + 'ms';
    }
}

function renderExplorerResponse(res, body, elapsed, reqHeaders, method, endpoint) {
    // Status badge
    const statusEl = document.getElementById('resp-status');
    statusEl.textContent = res.status + ' ' + res.statusText;
    statusEl.className = 'status-badge ' + (res.ok ? 'ok' : res.status === 429 ? 'warn' : 'err');

    // Time
    document.getElementById('resp-time').textContent = elapsed + 'ms';

    // Body
    document.getElementById('resp-body').textContent =
        typeof body === 'object' ? JSON.stringify(body, null, 2) : String(body);

    // Kong headers
    const kongHeaderNames = [
        'x-ratelimit-limit-minute',
        'x-ratelimit-remaining-minute',
        'x-ratelimit-limit-second',
        'x-ratelimit-remaining-second',
        'x-kong-upstream-latency',
        'x-kong-proxy-latency',
        'x-request-id',
        'x-consumer-username',
        'x-consumer-id',
        'ratelimit-limit',
        'ratelimit-remaining',
        'ratelimit-reset',
        'retry-after',
    ];

    const kongEl = document.getElementById('kong-headers');
    kongEl.innerHTML = '';

    let found = false;
    kongHeaderNames.forEach(name => {
        const val = res.headers.get(name);
        if (val !== null) {
            found = true;
            const chip = document.createElement('div');
            chip.className = 'kong-header-chip';
            chip.innerHTML = `<span class="hk">${escHtml(name)}</span><span class="hv">: ${escHtml(val)}</span>`;
            kongEl.appendChild(chip);
        }
    });

    if (!found) {
        kongEl.innerHTML = '<span style="color:var(--gray-400);font-size:12px">No Kong headers in response — Kong may not be proxying this request</span>';
    }
}

function showExplorerResponse() {
    const el = document.getElementById('explorer-response');
    if (el) el.style.display = '';
}

function formatHeaders(headers, method, endpoint) {
    const lines = [`${method} ${endpoint} HTTP/1.1`, `Host: ${new URL(CONFIG.KONG_URL).host}`];
    Object.entries(headers).forEach(([k, v]) => {
        if (k === 'Authorization') {
            lines.push(`${k}: Bearer ${v.replace('Bearer ', '').slice(0, 20)}...`);
        } else {
            lines.push(`${k}: ${v}`);
        }
    });
    return lines.join('\n');
}

/* ============================================================
   Rate Limiting
   ============================================================ */
async function spamRequest() {
    const url = CONFIG.KONG_URL + '/v1/products';
    state.rateLimitSent++;
    setText('rl-total', state.rateLimitSent);

    try {
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        const remaining = res.headers.get('x-ratelimit-remaining-minute') ||
                          res.headers.get('ratelimit-remaining');

        if (remaining !== null) {
            state.rateLimitRemaining = parseInt(remaining, 10);
            setText('rl-remaining', remaining);
        }

        if (res.ok) {
            state.rateLimitOk++;
            setText('rl-ok', state.rateLimitOk);
            addRateLog('ok', `200 OK — X-RateLimit-Remaining: ${remaining ?? '?'}`);
        } else if (res.status === 429) {
            state.rateLimitBlocked++;
            setText('rl-blocked', state.rateLimitBlocked);
            addRateLog('limited', '429 Too Many Requests — Rate limit exceeded');
            setText('rl-remaining', '0');
        } else {
            addRateLog('error', `${res.status} ${res.statusText}`);
        }

        // Compute used = limit - remaining (default limit = 10)
        const limit = parseInt(res.headers.get('x-ratelimit-limit-minute') || '10', 10);
        const rem   = state.rateLimitRemaining !== null ? state.rateLimitRemaining : (limit - state.rateLimitOk);
        const used  = Math.max(0, limit - rem);
        updateRateBar(used, limit);

    } catch (e) {
        addRateLog('error', 'Request failed: ' + e.message);
    }
}

async function spamBurst() {
    addRateLog('ok', '--- Starting burst of 15 requests ---');
    for (let i = 0; i < 15; i++) {
        await spamRequest();
        await sleep(100);
    }
    addRateLog('ok', '--- Burst complete ---');
}

function resetRateLimit() {
    state.rateLimitSent = 0;
    state.rateLimitOk = 0;
    state.rateLimitBlocked = 0;
    state.rateLimitRemaining = null;

    setText('rl-total', 0);
    setText('rl-ok', 0);
    setText('rl-blocked', 0);
    setText('rl-remaining', '—');

    updateRateBar(0, 10);

    const log = document.getElementById('rate-log');
    if (log) log.innerHTML = '';
}

function addRateLog(type, message) {
    const log = document.getElementById('rate-log');
    if (!log) return;

    const entry = document.createElement('div');
    entry.className = 'rate-log-entry ' + type;

    const icon = type === 'ok' ? '✓' : type === 'limited' ? '✗' : '!';
    const time = new Date().toLocaleTimeString('en-GB', { hour12: false });
    entry.textContent = `${icon} [${time}] ${message}`;

    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;

    // Keep max 100 entries
    while (log.children.length > 100) {
        log.removeChild(log.firstChild);
    }
}

function updateRateBar(used, limit) {
    const bar   = document.getElementById('rate-bar');
    const label = document.getElementById('rate-bar-label');
    if (!bar) return;

    const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;

    let color = 'var(--success)';
    if (pct >= 80) color = 'var(--danger)';
    else if (pct >= 50) color = 'var(--warning)';

    bar.style.setProperty('--bar-width', pct + '%');
    bar.style.setProperty('--bar-color', color);

    if (label) label.textContent = `${used} / ${limit} requests used`;
}

/* ============================================================
   Auth & JWT
   ============================================================ */
function selectUser(username, plan) {
    const uEl = document.getElementById('login-username');
    const pEl = document.getElementById('login-password');
    if (uEl) uEl.value = username;
    if (pEl) pEl.value = 'demo123';
}

async function doLogin() {
    const username = (document.getElementById('login-username').value || '').trim();
    const password = document.getElementById('login-password').value || '';

    if (!username) {
        showLoginError('Please enter a username');
        return;
    }

    hideLoginError();

    try {
        const res = await fetch(CONFIG.KONG_URL + '/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            signal: AbortSignal.timeout(6000),
        });

        let data;
        try { data = await res.json(); }
        catch { data = {}; }

        if (res.ok && data.access_token) {
            state.token = data.access_token;
            state.tokenInfo = data;
            state.tokenPayload = decodeJWT(data.access_token);

            renderTokenInfo(data);
            renderJWTDecode(data.access_token);
            showToast('Logged in as ' + username, 'success');

            // Auto-enable auth in explorer
            const authCb = document.getElementById('use-auth');
            if (authCb) authCb.checked = true;

        } else {
            const msg = data.detail || data.message || 'Login failed (' + res.status + ')';
            showLoginError(msg);
        }
    } catch (e) {
        const isTimeout = e.name === 'TimeoutError' || e.name === 'AbortError';
        showLoginError(isTimeout
            ? 'Request timed out — is Kong running?'
            : 'Connection failed: ' + e.message);
    }
}

function renderTokenInfo(data) {
    const payload = decodeJWT(data.access_token) || {};

    // Show token panel, hide empty state
    show('token-info');
    hide('token-empty');
    show('logout-btn');

    // Hide login error if any
    hideLoginError();

    setText('token-user',     payload.sub || payload.username || data.username || '—');
    setText('token-plan',     payload.plan || data.plan || '—');
    setText('token-consumer', payload.kong_consumer || data.kong_consumer || '—');

    if (payload.exp) {
        const exp = new Date(payload.exp * 1000);
        setText('token-expires', exp.toLocaleString());
    } else {
        setText('token-expires', '—');
    }

    const tokenEl = document.getElementById('token-value');
    if (tokenEl) tokenEl.textContent = data.access_token;

    // Show protected tests card
    show('protected-tests');
    show('jwt-decode-card');
}

function renderJWTDecode(token) {
    const parts = token.split('.');
    if (parts.length !== 3) return;

    try {
        const header  = JSON.parse(atob(parts[0].replace(/-/g, '+').replace(/_/g, '/')));
        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));

        const headerEl  = document.getElementById('jwt-header');
        const payloadEl = document.getElementById('jwt-payload');

        if (headerEl)  headerEl.textContent  = JSON.stringify(header,  null, 2);
        if (payloadEl) payloadEl.textContent = JSON.stringify(payload, null, 2);

    } catch (e) {
        console.warn('JWT decode error:', e);
    }
}

function decodeJWT(token) {
    if (!token) return null;
    try {
        const parts = token.split('.');
        if (parts.length < 2) return null;
        const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const json = atob(b64);
        return JSON.parse(json);
    } catch {
        return null;
    }
}

function logout() {
    state.token = null;
    state.tokenPayload = null;
    state.tokenInfo = null;

    hide('token-info');
    show('token-empty');
    hide('logout-btn');
    hide('protected-tests');
    hide('jwt-decode-card');
    hide('protected-result');

    const authCb = document.getElementById('use-auth');
    if (authCb) authCb.checked = false;

    const hEl = document.getElementById('jwt-header');
    const pEl = document.getElementById('jwt-payload');
    if (hEl) hEl.textContent = '';
    if (pEl) pEl.textContent = '';

    showToast('Logged out', 'info');
}

function copyToken() {
    if (!state.token) return;
    navigator.clipboard.writeText(state.token).then(() => {
        showToast('Token copied to clipboard', 'success');
    }).catch(() => {
        // Fallback
        const el = document.getElementById('token-value');
        if (el) {
            const range = document.createRange();
            range.selectNode(el);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
            document.execCommand('copy');
            window.getSelection().removeAllRanges();
            showToast('Token copied', 'success');
        }
    });
}

async function testProtected(endpoint) {
    if (!state.token) {
        showToast('Login first to test protected endpoints', 'warning');
        return;
    }

    const el = document.getElementById('protected-result');
    if (el) {
        el.style.display = '';
        el.textContent = 'Loading...';
    }

    try {
        const res = await fetch(CONFIG.KONG_URL + endpoint, {
            headers: {
                'Authorization': 'Bearer ' + state.token,
                'Accept': 'application/json',
            },
            signal: AbortSignal.timeout(6000),
        });

        let body;
        try { body = await res.json(); }
        catch { body = await res.text().catch(() => '(empty)'); }

        const out = {
            status: res.status,
            statusText: res.statusText,
            body: body,
        };

        if (el) {
            el.textContent = JSON.stringify(out, null, 2);
        }

        if (res.ok) {
            showToast(endpoint + ' — ' + res.status + ' OK', 'success');
        } else {
            showToast(endpoint + ' — ' + res.status + ' ' + res.statusText, 'error');
        }

    } catch (e) {
        if (el) el.textContent = 'Request failed: ' + e.message;
        showToast('Request failed: ' + e.message, 'error');
    }
}

function showLoginError(msg) {
    const el = document.getElementById('login-error');
    if (!el) return;
    el.textContent = msg;
    el.style.display = '';
}

function hideLoginError() {
    const el = document.getElementById('login-error');
    if (el) el.style.display = 'none';
}

/* ============================================================
   Toast Notifications
   ============================================================ */
let toastTimer = null;

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    if (toastTimer) {
        clearTimeout(toastTimer);
        toast.classList.remove('show');
    }

    toast.textContent = message;
    toast.className = 'toast ' + type;

    // Force reflow so transition re-triggers
    void toast.offsetWidth;

    toast.classList.add('show');

    toastTimer = setTimeout(() => {
        toast.classList.remove('show');
        toastTimer = null;
    }, 3000);
}

/* ============================================================
   Utility helpers
   ============================================================ */
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function show(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
}

function hide(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatJSON(obj) {
    return JSON.stringify(obj, null, 2);
}

function fmtNum(n) {
    if (n === undefined || n === null) return '—';
    return Number(n).toLocaleString();
}

function formatUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/* ============================================================
   Bootstrap
   ============================================================ */
window.addEventListener('DOMContentLoaded', init);
