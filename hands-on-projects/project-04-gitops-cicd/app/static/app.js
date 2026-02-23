// ── API base URL ──────────────────────────────────────────────
// Works for local dev (same origin) and when proxied via nginx
const API_BASE = '';

// ── State ─────────────────────────────────────────────────────
let versionInfo = null;

// ── Boot ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadVersionInfo();
  await loadProjects();
  setupInfoPanel();
});

// ── Version Info ──────────────────────────────────────────────
async function loadVersionInfo() {
  try {
    const res = await fetch(`${API_BASE}/api/version`);
    if (!res.ok) throw new Error('Failed to fetch version');
    versionInfo = await res.json();
    renderVersionInfo(versionInfo);
  } catch (err) {
    console.error('Version fetch error:', err);
    renderVersionFallback();
  }
}

function renderVersionInfo(info) {
  const { version, environment, build_date, git_commit, replica_id } = info;

  // Banner
  const banner = document.getElementById('bannerText');
  if (banner) {
    banner.textContent = `You are viewing ${version.toUpperCase()} · deployed to ${environment} · built ${build_date} · commit ${git_commit.slice(0, 7)}`;
  }

  // Header badge
  const badge = document.getElementById('versionValue');
  if (badge) badge.textContent = version.toUpperCase();

  // Footer
  const fv = document.getElementById('footerVersion');
  if (fv) fv.textContent = version.toUpperCase();

  const fc = document.getElementById('footerCommit');
  if (fc) fc.textContent = git_commit.slice(0, 7);

  const fr = document.getElementById('footerReplica');
  if (fr) fr.textContent = `pod: ${replica_id}`;

  // Info panel fields
  const fields = {
    infoVersion: version,
    infoEnv:     environment,
    infoBuild:   build_date,
    infoCommit:  git_commit,
    infoReplica: replica_id,
  };
  for (const [id, val] of Object.entries(fields)) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  // Stat card
  const statEnv = document.getElementById('statEnv');
  if (statEnv) statEnv.textContent = environment;

  // Update CSS accent color per version (so v2 is visually distinct)
  applyVersionTheme(version);
}

function renderVersionFallback() {
  const banner = document.getElementById('bannerText');
  if (banner) banner.textContent = 'Version info unavailable';
}

// ── Version-specific theme ────────────────────────────────────
// When you deploy v2, change the accent here (CI can inject this).
// During a canary you'll see blue (v1) and green (v2) on page refresh.
function applyVersionTheme(version) {
  const root = document.documentElement;
  if (version === 'v2') {
    root.style.setProperty('--accent',      '#22c55e');
    root.style.setProperty('--accent-glow', 'rgba(34, 197, 94, 0.12)');
    root.style.setProperty('--accent-text', '#86efac');
  }
  // v1 keeps the default blue from CSS
}

// ── Projects ──────────────────────────────────────────────────
async function loadProjects() {
  try {
    const res = await fetch(`${API_BASE}/api/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    const data = await res.json();
    renderProjects(data);
  } catch (err) {
    console.error('Projects fetch error:', err);
    document.getElementById('projectsGrid').innerHTML =
      '<div class="loading">Failed to load projects — is the API running?</div>';
  }
}

function renderProjects(data) {
  const grid = document.getElementById('projectsGrid');
  if (!grid) return;

  // Stats
  const total    = document.getElementById('statTotal');
  const available = document.getElementById('statAvailable');
  const coming   = document.getElementById('statComing');
  if (total)    total.textContent    = data.total;
  if (available) available.textContent = data.available;
  if (coming)   coming.textContent   = data.total - data.available;

  // Cards
  grid.innerHTML = data.projects.map(p => renderCard(p)).join('');
}

function renderCard(project) {
  const isAvailable = project.status === 'available';
  const paddedId = String(project.id).padStart(2, '0');

  const topicsHtml = project.topics
    .map(t => `<span class="topic-tag">${t}</span>`)
    .join('');

  const footerHtml = isAvailable
    ? `<a class="card-link" href="https://github.com/shaydevops2024/kubernetes-production-simulator/tree/main/hands-on-projects/${project.folder}" target="_blank" rel="noopener">
         Open Project →
       </a>`
    : `<span class="card-coming-label">🔜 Coming Soon</span>`;

  return `
    <div class="project-card ${isAvailable ? 'available' : 'coming-soon'}">
      <span class="card-number">#${paddedId}</span>
      <div class="card-status ${isAvailable ? 'available' : 'coming-soon'}">
        ${isAvailable ? '✓ Available' : '⏳ Coming Soon'}
      </div>
      <div class="card-title">${project.title}</div>
      <div class="card-topics">${topicsHtml}</div>
      <div class="card-footer">${footerHtml}</div>
    </div>
  `;
}

// ── Deployment Info Panel ─────────────────────────────────────
function setupInfoPanel() {
  const toggle = document.getElementById('infoToggle');
  const panel  = document.getElementById('infoPanel');
  const close  = document.getElementById('infoClose');

  if (!toggle || !panel || !close) return;

  toggle.addEventListener('click', () => panel.classList.toggle('open'));
  close.addEventListener('click',  () => panel.classList.remove('open'));

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target) && e.target !== toggle) {
      panel.classList.remove('open');
    }
  });
}
