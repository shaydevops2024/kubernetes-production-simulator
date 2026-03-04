'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let allTeams = [];
let selectedTemplateId = null;

// ─── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    allTeams = await apiFetch('/api/teams');
    populateTeamFilter(allTeams);
    await loadPage('dashboard');
});

// ─── Navigation ───────────────────────────────────────────────────────────────
function navigate(page, el) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    if (el) el.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.getElementById('page-title').textContent = pageTitle(page);
    currentPage = page;
    loadPage(page);
}

function pageTitle(p) {
    return { dashboard: 'Dashboard', teams: 'Teams', namespaces: 'Namespaces',
             services: 'Services', pipelines: 'Pipelines', catalog: 'Service Catalog', costs: 'Costs' }[p] || p;
}

async function loadPage(page) {
    if (page === 'dashboard') await loadDashboard();
    else if (page === 'teams') await loadTeams();
    else if (page === 'namespaces') await loadNamespaces();
    else if (page === 'services') await loadServices();
    else if (page === 'pipelines') await loadPipelines();
    else if (page === 'catalog') await loadCatalog();
    else if (page === 'costs') await loadCosts();
}

// ─── API helper ───────────────────────────────────────────────────────────────
async function apiFetch(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`API error ${r.status}`);
    return r.json();
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
    const [dash, pipes, svcs] = await Promise.all([
        apiFetch('/api/dashboard'),
        apiFetch('/api/pipelines'),
        apiFetch('/api/services'),
    ]);

    document.getElementById('dashboard-stats').innerHTML = `
        <div class="stat-card">
            <div class="stat-label">Services Running</div>
            <div class="stat-value stat-green">${dash.services_running}</div>
            <div class="stat-sub">${dash.services_degraded > 0 ? `<span class="stat-yellow">${dash.services_degraded} degraded</span>` : 'All healthy'}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Active Teams</div>
            <div class="stat-value stat-purple">${dash.teams}</div>
            <div class="stat-sub">${dash.namespaces} namespaces</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Pods</div>
            <div class="stat-value">${dash.total_pods}</div>
            <div class="stat-sub">${dash.pipelines_running} pipelines active</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Month Cost (est.)</div>
            <div class="stat-value stat-purple">$${dash.monthly_cost.toFixed(0)}</div>
            <div class="stat-sub">${dash.pipelines_failed > 0 ? `<span class="stat-red">${dash.pipelines_failed} pipeline${dash.pipelines_failed > 1 ? 's' : ''} failed</span>` : 'No failures'}</div>
        </div>
    `;

    const pipeHtml = pipes.slice(0, 5).map(p => `
        <div class="pipeline-row">
            <div>
                <div class="pipeline-name">${p.name}</div>
                <div class="pipeline-meta">${p.repo} · ${p.branch} · ${p.triggered_by}</div>
            </div>
            <div class="pipeline-right">
                ${chipStatus(p.status)}
                <div class="pipeline-duration">${p.duration}</div>
            </div>
        </div>
    `).join('');
    document.getElementById('dashboard-pipelines').innerHTML = pipeHtml;

    const svcHtml = svcs.slice(0, 6).map(s => `
        <div class="service-row">
            <div>
                <div class="service-name">${s.name}</div>
                <div class="service-meta"><span>${s.namespace}</span></div>
            </div>
            <div class="service-right">
                <span class="replicas-badge">${s.ready}/${s.replicas} pods</span>
                ${chipStatus(s.status)}
            </div>
        </div>
    `).join('');
    document.getElementById('dashboard-services').innerHTML = svcHtml;
}

// ─── Teams ────────────────────────────────────────────────────────────────────
async function loadTeams() {
    const teams = await apiFetch('/api/teams');
    document.getElementById('teams-list').innerHTML = teams.map(t => `
        <div class="team-card" style="--team-color:${t.color}">
            <div class="team-name">${t.name}</div>
            <div class="team-desc">${t.description}</div>
            <div class="team-meta">
                <div><strong>${t.members}</strong> Members</div>
                <div><strong>${t.namespace}</strong> Namespace</div>
            </div>
            <div style="margin-top:12px; font-size:11px; color:var(--text-muted)">Lead: ${t.lead}</div>
        </div>
    `).join('');
}

// ─── Namespaces ───────────────────────────────────────────────────────────────
async function loadNamespaces() {
    const nsList = await apiFetch('/api/namespaces');
    document.getElementById('ns-tbody').innerHTML = nsList.map(n => {
        const cpuPct = Math.round((parseFloat(n.cpu_used) / parseFloat(n.cpu_limit)) * 100);
        const memUsedGi = parseFloat(n.memory_used);
        const memLimitGi = parseFloat(n.memory_limit);
        const memPct = Math.round((memUsedGi / memLimitGi) * 100);
        return `
        <tr>
            <td><strong>${n.name}</strong></td>
            <td>${n.team}</td>
            <td>
                <div style="font-size:12px;color:var(--text-muted)">${n.cpu_used} / ${n.cpu_limit} cores</div>
                <div class="progress-bar" style="width:120px">
                    <div class="progress-fill ${cpuPct > 80 ? 'danger' : cpuPct > 60 ? 'warn' : ''}" style="width:${cpuPct}%"></div>
                </div>
            </td>
            <td>
                <div style="font-size:12px;color:var(--text-muted)">${n.memory_used} / ${n.memory_limit}</div>
                <div class="progress-bar" style="width:120px">
                    <div class="progress-fill ${memPct > 80 ? 'danger' : memPct > 60 ? 'warn' : ''}" style="width:${memPct}%"></div>
                </div>
            </td>
            <td>${n.pod_count} / ${n.pod_limit}</td>
            <td><span class="chip chip-green">● ${n.status}</span></td>
        </tr>`;
    }).join('');
}

// ─── Services ─────────────────────────────────────────────────────────────────
async function loadServices() {
    const teamFilter = document.getElementById('svc-team-filter')?.value || '';
    const url = teamFilter ? `/api/services?team_id=${teamFilter}` : '/api/services';
    const svcs = await apiFetch(url);
    document.getElementById('services-list').innerHTML = svcs.map(s => `
        <div class="service-row">
            <div style="flex:1">
                <div style="display:flex;align-items:center;gap:8px">
                    <div class="service-name">${s.name}</div>
                    <span class="tag-type">${s.type}</span>
                </div>
                <div class="service-meta">
                    <span>ns: ${s.namespace}</span>
                    <span>cpu: ${s.cpu}</span>
                    <span>mem: ${s.memory}</span>
                    ${s.ingress ? `<a class="ingress-link" href="#">⬡ ${s.ingress}</a>` : ''}
                </div>
            </div>
            <div class="service-right">
                <span class="replicas-badge">${s.ready}/${s.replicas} pods</span>
                ${chipStatus(s.status)}
                <span style="font-size:11px;color:var(--text-muted)">up ${s.uptime}</span>
            </div>
        </div>
    `).join('');
}

function populateTeamFilter(teams) {
    const sel = document.getElementById('svc-team-filter');
    if (!sel) return;
    teams.forEach(t => {
        const o = document.createElement('option');
        o.value = t.id;
        o.textContent = t.name;
        sel.appendChild(o);
    });
}

// ─── Pipelines ────────────────────────────────────────────────────────────────
async function loadPipelines() {
    const pipes = await apiFetch('/api/pipelines');
    document.getElementById('pipelines-list').innerHTML = pipes.map(p => `
        <div class="pipeline-row" style="flex-wrap:wrap">
            <div style="flex:1;min-width:180px">
                <div class="pipeline-name">${p.name}</div>
                <div class="pipeline-meta">${p.repo} · branch: <strong>${p.branch}</strong></div>
                <div class="pipeline-meta" style="margin-top:2px;font-style:italic">"${p.commit_msg}"</div>
            </div>
            <div style="display:flex;align-items:center;gap:16px;flex-shrink:0">
                <div style="text-align:center">
                    <div style="font-size:11px;color:var(--text-muted)">Stage</div>
                    <div style="font-weight:600;font-size:13px">${p.stage}</div>
                </div>
                <div style="text-align:center">
                    <div style="font-size:11px;color:var(--text-muted)">By</div>
                    <div style="font-weight:600;font-size:13px">${p.triggered_by}</div>
                </div>
                <div style="text-align:right">
                    ${chipStatus(p.status)}
                    <div class="pipeline-duration">${p.duration}</div>
                </div>
            </div>
        </div>
    `).join('');
}

// ─── Service Catalog ──────────────────────────────────────────────────────────
async function loadCatalog() {
    const catalog = await apiFetch('/api/catalog');
    const ICONS = { api: '🔌', worker: '⚙️', frontend: '🖥️', grpc: '🚀', database: '🗄️' };
    document.getElementById('catalog-list').innerHTML = catalog.map(c => `
        <div class="catalog-card">
            <div class="catalog-icon">${ICONS[c.icon] || '📦'}</div>
            <div class="catalog-name">${c.name}</div>
            <div class="catalog-desc">${c.description}</div>
            <div class="catalog-tags">${c.tags.map(t => `<span class="catalog-tag">${t}</span>`).join('')}</div>
            <button class="btn-primary" style="margin-top:8px" onclick="openDeployModal('${c.id}', '${c.name}')">
                Deploy →
            </button>
        </div>
    `).join('');
}

// ─── Costs ────────────────────────────────────────────────────────────────────
async function loadCosts() {
    const costs = await apiFetch('/api/costs');
    document.getElementById('costs-period').textContent = costs.period + ' — Cost Breakdown';
    document.getElementById('costs-total').textContent = '$' + costs.total_month.toFixed(2) + ' total';
    const maxCost = Math.max(...costs.teams.map(t => t.month_cost));
    document.getElementById('costs-teams').innerHTML = costs.teams.map(t => {
        const pct = Math.round((t.month_cost / maxCost) * 100);
        const trendClass = t.trend_direction === 'up' ? 'trend-up' : 'trend-down';
        return `
        <div class="cost-row">
            <div class="cost-team-name">${t.name}</div>
            <div class="cost-bar-wrap">
                <div style="font-size:11px;color:var(--text-muted);margin-bottom:3px">CPU: $${t.cpu_cost} · Mem: $${t.memory_cost}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${pct}%"></div>
                </div>
            </div>
            <div class="cost-amount">$${t.month_cost.toFixed(2)}</div>
            <div class="cost-trend ${trendClass}">${t.trend}</div>
        </div>`;
    }).join('');
}

// ─── Deploy Modal ─────────────────────────────────────────────────────────────
function openDeployModal(templateId, templateName) {
    selectedTemplateId = templateId;
    document.getElementById('modal-template-name').textContent = `Deploy: ${templateName}`;
    document.getElementById('deploy-template-id').value = templateId;
    const sel = document.getElementById('deploy-team');
    sel.innerHTML = '<option value="">Select team…</option>';
    allTeams.forEach(t => {
        const o = document.createElement('option');
        o.value = t.id;
        o.textContent = t.name;
        sel.appendChild(o);
    });
    document.getElementById('deploy-modal').style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

async function submitDeploy(e) {
    e.preventDefault();
    const body = {
        service_name: document.getElementById('deploy-name').value,
        team_id: document.getElementById('deploy-team').value,
        template_id: document.getElementById('deploy-template-id').value,
        image_tag: document.getElementById('deploy-tag').value,
        replicas: parseInt(document.getElementById('deploy-replicas').value),
    };
    const result = await apiFetch('/api/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    closeModal('deploy-modal');
    toast('Pipeline triggered! ' + result.message, 5000);
}

// ─── Namespace Modal ──────────────────────────────────────────────────────────
function showNsModal() {
    document.getElementById('ns-modal').style.display = 'flex';
}

async function submitNsRequest(e) {
    e.preventDefault();
    const body = {
        team_name: document.getElementById('ns-team-name').value,
        lead_email: document.getElementById('ns-lead-email').value,
        description: document.getElementById('ns-description').value,
        cpu_limit: document.getElementById('ns-cpu').value,
        memory_limit: document.getElementById('ns-memory').value,
    };
    const result = await apiFetch('/api/namespaces/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    closeModal('ns-modal');
    toast(result.message, 5000);
}

// ─── Chip helpers ─────────────────────────────────────────────────────────────
function chipStatus(status) {
    const map = {
        Running: ['chip-green', '●'],
        success: ['chip-green', '✓'],
        Degraded: ['chip-yellow', '⚠'],
        failed: ['chip-red', '✕'],
        running: ['chip-blue', '▶'],
        queued: ['chip-gray', '…'],
    };
    const [cls, icon] = map[status] || ['chip-gray', '?'];
    return `<span class="chip ${cls}">${icon} ${status}</span>`;
}

// ─── Toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, duration = 3500) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), duration);
}
