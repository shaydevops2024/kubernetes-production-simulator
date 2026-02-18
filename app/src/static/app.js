// app/src/static/app.js
// app/src/static/app.js

// Global state
var autoRefreshInterval = null;
var statusMonitorInterval = null;
var clusterStatsInterval = null;
var toolsStatusInterval = null;
var currentCLISection = null;
var clusterStatsData = null;
var dashboardRefreshInterval = null;
var currentRefreshSeconds = 5; // Default 5 seconds

// Load config and start monitoring on startup
window.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    startStatusMonitoring();
    startClusterStatsMonitoring();
    startToolsStatusMonitoring();
    
    var taskSubmit = document.getElementById('create-task-form').querySelector('button[type="submit"]');
    if (taskSubmit) {
        taskSubmit.disabled = true;
        taskSubmit.textContent = 'Loading users...';
    }
    
    setTimeout(function() {
        var btn = document.getElementById('create-task-form').querySelector('button[type="submit"]');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Create Task';
        }
    }, 2000);
});

window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
    
    // Stop dashboard refresh if active
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
    stopStatusMonitoring();
    stopClusterStatsMonitoring();
    stopToolsStatusMonitoring();
});

// Modal functions
function showModal(title, message, hideCloseButton) {
    var overlay = document.getElementById('modal-overlay');
    var titleEl = document.getElementById('modal-title');
    var bodyEl = document.getElementById('modal-body');
    var closeBtn = overlay.querySelector('.modal-close');
    var footer = document.getElementById('modal-footer');
    
    titleEl.textContent = title;
    bodyEl.innerHTML = message;
    
    // Hide or show close button and footer based on parameter
    if (hideCloseButton) {
        if (closeBtn) closeBtn.style.display = 'none';
        if (footer) footer.style.display = 'none';
    } else {
        if (closeBtn) closeBtn.style.display = 'block';
        if (footer) footer.style.display = 'block';
    }
    
    overlay.classList.add('active');
}

function closeModal() {
    var overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('active');
}

// Close modal on overlay click
document.getElementById('modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Close sidebar with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeTestingSidebar();
    }
});

// Open Play Kubernetes scenarios page
function openPlayKubernetes() {
    window.open('/static/scenarios.html', '_blank');
}

// Open Play ArgoCD scenarios page
function openPlayArgoCD() {
    window.open('/static/argocd-scenarios.html', '_blank');
}

// Open Play Helm scenarios page
function openPlayHelm() {
    window.open('/static/helm-scenarios.html', '_blank');
}

// Open Play GitLab CI scenarios page
function openPlayGitlabCI() {
    window.open('/static/gitlab-ci-scenarios.html', '_blank');
}

// Open Play Jenkins scenarios page
function openPlayJenkins() {
    window.open('/static/jenkins-scenarios.html', '_blank');
}

// Open Play Terraform scenarios page
function openPlayTerraform() {
    window.open('/static/terraform-scenarios.html', '_blank');
}

// Open Play Ansible scenarios page
function openPlayAnsible() {
    window.open('/static/ansible-scenarios.html', '_blank');
}

// Open Hands-On Projects page
function openHandsOnProjects() {
    window.open('/static/hands-on-projects.html', '_blank');
}

// Open ArgoCD with automatic fallback
function openArgoCD() {
    // Ask backend which ArgoCD URL to use
    fetch('/api/argocd/url')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.url) {
                window.open(data.url, '_blank');
            } else {
                // Default fallback
                window.open('http://k8s-multi-demo.argocd:30800/', '_blank');
            }
        })
        .catch(function(error) {
            console.log('Error getting ArgoCD URL, using default:', error);
            // On error, default to argocd URL
            window.open('http://k8s-multi-demo.argocd:30800/', '_blank');
        });
}

// Load app configuration
function loadConfig() {
    fetch('/api/config')
        .then(function(r) { return r.json(); })
        .then(function(config) {
            document.getElementById('app-env').textContent = config.app_env;
            document.getElementById('app-name').textContent = config.app_name;

            var badge = document.getElementById('secret-badge');
            if (config.secret_configured) {
                badge.className = 'badge badge-success';
                badge.textContent = '✓ Yes';
            } else {
                badge.className = 'badge badge-warning';
                badge.textContent = '⚠ No';
            }

            var configmapBadge = document.getElementById('configmap-badge');
            if (config.configmap_configured) {
                configmapBadge.className = 'badge badge-success';
                configmapBadge.textContent = '✓ Yes';
            } else {
                configmapBadge.className = 'badge badge-warning';
                configmapBadge.textContent = '⚠ No';
            }
        })
        .catch(function(e) { console.error('Config error:', e); });
}

// Fetch deployment tools status (Helm & ArgoCD) - queries real cluster data
function fetchToolsStatus() {
    refreshHelmStatus();
    refreshArgoCDStatus();
}

// Refresh Helm status (installed, version, release count)
function refreshHelmStatus() {
    var installedEl = document.getElementById('helm-installed');
    var versionEl = document.getElementById('helm-version');
    var releasesEl = document.getElementById('helm-releases');

    fetch('/api/tools/helm')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (installedEl) {
                if (data.installed) {
                    installedEl.className = 'badge badge-success';
                    installedEl.textContent = '✓ Yes';
                } else {
                    installedEl.className = 'badge badge-grey';
                    installedEl.textContent = '✗ No';
                }
            }

            if (versionEl) {
                versionEl.textContent = data.version || '-';
            }

            if (releasesEl) {
                releasesEl.textContent = data.release_count;
                if (data.release_count > 0) {
                    releasesEl.style.cursor = 'pointer';
                    releasesEl.onclick = function() {
                        refreshHelmReleases();
                        toggleHelmReleasesList();
                    };
                } else {
                    releasesEl.style.cursor = 'default';
                    releasesEl.onclick = null;
                }
            }
        })
        .catch(function(err) {
            console.error('Helm status error:', err);
            if (installedEl) {
                installedEl.className = 'badge badge-grey';
                installedEl.textContent = 'Error';
            }
        });
}

// Refresh ArgoCD status (installed, version, app count)
function refreshArgoCDStatus() {
    var installedEl = document.getElementById('argocd-installed');
    var versionEl = document.getElementById('argocd-version');
    var appsEl = document.getElementById('argocd-app-count');

    fetch('/api/tools/argocd')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (installedEl) {
                if (data.installed) {
                    installedEl.className = 'badge badge-success';
                    installedEl.textContent = '✓ Yes';
                } else {
                    installedEl.className = 'badge badge-grey';
                    installedEl.textContent = '✗ No';
                }
            }

            if (versionEl) {
                versionEl.textContent = data.version || '-';
            }

            if (appsEl) {
                appsEl.textContent = data.app_count;
                if (data.app_count > 0) {
                    appsEl.style.cursor = 'pointer';
                    appsEl.onclick = function() {
                        refreshArgoCDApps();
                        toggleArgoCDAppsList();
                    };
                } else {
                    appsEl.style.cursor = 'default';
                    appsEl.onclick = null;
                }
            }
        })
        .catch(function(err) {
            console.error('ArgoCD status error:', err);
            if (installedEl) {
                installedEl.className = 'badge badge-grey';
                installedEl.textContent = 'Error';
            }
        });
}

// Refresh Helm releases (dynamic)
function refreshHelmReleases() {
    var releasesEl = document.getElementById('helm-releases');
    var listEl = document.getElementById('helm-releases-list');

    if (releasesEl) releasesEl.textContent = '...';

    fetch('/api/tools/helm/releases')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (releasesEl) {
                if (data.release_count > 0) {
                    releasesEl.textContent = data.release_count + ' release(s)';
                    releasesEl.style.cursor = 'pointer';
                    releasesEl.onclick = function() { toggleHelmReleasesList(); };
                } else {
                    releasesEl.textContent = 'None';
                    releasesEl.style.cursor = 'default';
                    releasesEl.onclick = null;
                }
            }

            // Build the list
            if (listEl && data.releases && data.releases.length > 0) {
                var html = '';
                data.releases.forEach(function(release) {
                    var statusClass = release.status === 'deployed' ? 'badge-success' : 'badge-warning';
                    html += '<div class="tool-list-item">';
                    html += '<span class="name">' + release.name + '</span>';
                    html += '<span class="details">' + release.namespace + ' - ' + release.chart + '</span>';
                    html += '<span class="badge ' + statusClass + '">' + release.status + '</span>';
                    html += '</div>';
                });
                listEl.innerHTML = html;
            } else if (listEl) {
                listEl.innerHTML = '';
                listEl.style.display = 'none';
            }
        })
        .catch(function(err) {
            console.error('Helm releases error:', err);
            if (releasesEl) releasesEl.textContent = 'Error';
        });
}

// Toggle Helm releases list visibility
function toggleHelmReleasesList() {
    var listEl = document.getElementById('helm-releases-list');
    if (listEl && listEl.innerHTML) {
        listEl.style.display = listEl.style.display === 'none' ? 'block' : 'none';
    }
}

// Refresh ArgoCD apps (dynamic)
function refreshArgoCDApps() {
    var appsEl = document.getElementById('argocd-app-count');
    var listEl = document.getElementById('argocd-apps-list');

    if (appsEl) appsEl.textContent = '...';

    fetch('/api/tools/argocd/apps')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (appsEl) {
                if (data.app_count > 0) {
                    appsEl.textContent = data.app_count + ' app(s)';
                    appsEl.style.cursor = 'pointer';
                    appsEl.onclick = function() { toggleArgoCDAppsList(); };
                } else {
                    appsEl.textContent = 'None';
                    appsEl.style.cursor = 'default';
                    appsEl.onclick = null;
                }
            }

            // Build the list
            if (listEl && data.applications && data.applications.length > 0) {
                var html = '';
                data.applications.forEach(function(app) {
                    var healthClass = app.health === 'Healthy' ? 'badge-success' :
                                      app.health === 'Progressing' ? 'badge-warning' : 'badge-danger';
                    var syncClass = app.sync === 'Synced' ? 'badge-success' : 'badge-warning';
                    html += '<div class="tool-list-item">';
                    html += '<span class="name">' + app.name + '</span>';
                    html += '<span class="badge ' + healthClass + '">' + app.health + '</span>';
                    html += '<span class="badge ' + syncClass + '">' + app.sync + '</span>';
                    html += '</div>';
                });
                listEl.innerHTML = html;
            } else if (listEl) {
                listEl.innerHTML = '';
                listEl.style.display = 'none';
            }
        })
        .catch(function(err) {
            console.error('ArgoCD apps error:', err);
            if (appsEl) appsEl.textContent = 'Error';
        });
}

// Toggle ArgoCD apps list visibility
function toggleArgoCDAppsList() {
    var listEl = document.getElementById('argocd-apps-list');
    if (listEl && listEl.innerHTML) {
        listEl.style.display = listEl.style.display === 'none' ? 'block' : 'none';
    }
}

// Cluster stats monitoring
function startClusterStatsMonitoring() {
    if (clusterStatsInterval) clearInterval(clusterStatsInterval);
    updateClusterStats();
    clusterStatsInterval = setInterval(updateClusterStats, 3000);
}

function stopClusterStatsMonitoring() {
    if (clusterStatsInterval) {
        clearInterval(clusterStatsInterval);
        clusterStatsInterval = null;
    }
}

// Tools status monitoring (Helm & ArgoCD)
function startToolsStatusMonitoring() {
    if (toolsStatusInterval) clearInterval(toolsStatusInterval);
    fetchToolsStatus();
    toolsStatusInterval = setInterval(fetchToolsStatus, 3000);
}

function stopToolsStatusMonitoring() {
    if (toolsStatusInterval) {
        clearInterval(toolsStatusInterval);
        toolsStatusInterval = null;
    }
}

// Dashboard auto-refresh control
function changeRefreshInterval() {
    var select = document.getElementById("refresh-interval");
    var value = select.value;
    
    // Stop existing interval
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
    
    if (value === "off") {
        currentRefreshSeconds = 0;
        return;
    }
    
    currentRefreshSeconds = parseInt(value);
    
    // Start new interval
    dashboardRefreshInterval = setInterval(function() {
        updateClusterStats();
        updateStatusBadges();
        fetchToolsStatus();
    }, currentRefreshSeconds * 1000);
}

// Initialize refresh on dashboard tab activation
function initDashboardRefresh() {
    var select = document.getElementById("refresh-interval");
    if (select) {
        // Set default to 5 seconds
        select.value = "5";
        changeRefreshInterval();
    }
}


function updateClusterStats() {
    var dashboardTab = document.getElementById('dashboard-tab');
    if (!dashboardTab || !dashboardTab.classList.contains('active')) {
        return;
    }
    
    fetch('/api/cluster/stats')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            clusterStatsData = data;
            
            // Update Deployments (two-column display)
            var deploymentsCount = document.getElementById('cluster-deployments-count');
            var deploymentsReady = document.getElementById('cluster-deployments-ready');
            if (deploymentsCount) {
                deploymentsCount.textContent = data.deployments.count;
            }
            if (deploymentsReady && data.deployments.details.length > 0) {
                var mainDeployment = data.deployments.details[0];
                // Show just the replica count (e.g., "5/5") without extra text
                deploymentsReady.textContent = mainDeployment.ready;
            }
            
            // Update Pods
            var podsCount = document.getElementById('cluster-pods-count');
            var podsReady = document.getElementById('cluster-pods-ready');
            if (podsCount) {
                podsCount.textContent = data.pods.count;
            }
            if (podsReady && data.pods.details.length > 0) {
                var readyPods = data.pods.details.filter(function(p) { 
                    return p.status === 'Running'; 
                }).length;
                podsReady.textContent = readyPods + ' running';
            }
            
            // Update Nodes
            var nodesCount = document.getElementById('cluster-nodes-count');
            var nodesStatus = document.getElementById('cluster-nodes-status');
            if (nodesCount) {
                nodesCount.textContent = data.nodes.count;
            }
            if (nodesStatus && data.nodes.details.length > 0) {
                var readyNodes = data.nodes.details.filter(function(n) { 
                    return n.status === 'Ready'; 
                }).length;
                nodesStatus.textContent = readyNodes + ' ready';
            }
        })
        .catch(function(e) {
            console.error('Cluster stats error:', e);
        });
}

function showClusterDetails(type) {
    if (!clusterStatsData) {
        showModal('Loading...', 'Cluster data is loading, please try again.');
        return;
    }
    
    var title = '';
    var content = '<pre style="text-align: left; font-family: monospace; font-size: 12px;">';
    
    if (type === 'deployments') {
        title = 'Deployments';
        content += 'NAME                READY    UP-TO-DATE   AVAILABLE   AGE\n';
        content += '─────────────────────────────────────────────────────────────\n';
        var deployments = clusterStatsData.deployments.details;
        if (deployments && deployments.length > 0) {
            for (var i = 0; i < deployments.length; i++) {
                var d = deployments[i];
                var name = (d.name || '').padEnd(20, ' ');
                var ready = (d.ready || '').padEnd(9, ' ');
                var upToDate = (String(d.up_to_date) || '0').padEnd(13, ' ');
                var available = (String(d.available) || '0').padEnd(12, ' ');
                content += name + ready + upToDate + available + d.age + '\n';
            }
        } else {
            content += 'No deployments found\n';
        }
    } else if (type === 'pods') {
        title = 'Pods';
        content += 'NAME                                        READY    STATUS      RESTARTS   AGE\n';
        content += '───────────────────────────────────────────────────────────────────────────────\n';
        var pods = clusterStatsData.pods.details;
        if (pods && pods.length > 0) {
            for (var i = 0; i < pods.length; i++) {
                var pod = pods[i];
                var name = (pod.name || '').padEnd(44, ' ');
                var ready = (pod.ready || '').padEnd(9, ' ');
                var status = (pod.status || '').padEnd(12, ' ');
                var restarts = (String(pod.restarts) || '0').padEnd(11, ' ');
                content += name + ready + status + restarts + pod.age + '\n';
            }
        } else {
            content += 'No pods found\n';
        }
    } else if (type === 'nodes') {
        title = 'Cluster Nodes';
        content += 'NAME                                STATUS    ROLES            AGE     VERSION\n';
        content += '────────────────────────────────────────────────────────────────────────────────\n';
        var nodes = clusterStatsData.nodes.details;
        if (nodes && nodes.length > 0) {
            for (var i = 0; i < nodes.length; i++) {
                var node = nodes[i];
                var name = (node.name || '').padEnd(36, ' ');
                var status = (node.status || '').padEnd(10, ' ');
                var roles = (node.roles || '<none>').padEnd(17, ' ');
                var age = (node.age || '').padEnd(8, ' ');
                content += name + status + roles + age + node.version + '\n';
            }
        } else {
            content += 'No nodes found\n';
        }
    }
    
    content += '</pre>';
    showModal(title, content);
}

// Developer profile popup
function showDeveloperProfile() {
    var profileHTML = '<div style="text-align: left; padding: 20px; line-height: 1.8; background: #FFF7ED; border-radius: 8px;">';
    profileHTML += '<h3 style="margin-top: 0; color: #2c3e50;">Author: Shay Guedj</h3>';
    profileHTML += '<p style="margin: 15px 0; color: #555; font-size: 14px;">';
    profileHTML += 'DevOps Engineer with 3+ years of hands-on experience architecting and managing cloud-native infrastructures on AWS. ';
    profileHTML += 'Proven expertise in Kubernetes orchestration, microservices deployment, and Infrastructure as Code using Terraform and Ansible. ';
    profileHTML += 'Skilled in implementing GitOps workflows, optimizing CI/CD pipelines with Jenkins, and driving cost efficiency through cloud resource optimization. ';
    profileHTML += 'Strong background in monitoring solutions with Grafana, Prometheus, and CloudWatch, combined with advanced Linux/Windows server administration and Python/Bash scripting for automation.';
    profileHTML += '</p>';
    profileHTML += '<div style="margin-top: 25px; display: flex; gap: 10px; justify-content: center;">';
    profileHTML += '<button class="btn btn-primary" onclick="window.open(\'https://github.com/shaydevops2024/kubernetes-production-simulator\', \'_blank\'); closeModal();" style="padding: 10px 20px;">🚀 Visit My GitHub</button>';
    profileHTML += '<button class="btn btn-secondary" onclick="closeModal()" style="padding: 10px 20px;">Close</button>';
    profileHTML += '</div>';
    profileHTML += '</div>';

    // Pass true to hide the X button and OK button
    showModal('My DevOps Profile', profileHTML, true);
}

// Status monitoring
function startStatusMonitoring() {
    if (statusMonitorInterval) clearInterval(statusMonitorInterval);
    updateStatusBadges();
    statusMonitorInterval = setInterval(updateStatusBadges, 3000);
}

function stopStatusMonitoring() {
    if (statusMonitorInterval) {
        clearInterval(statusMonitorInterval);
        statusMonitorInterval = null;
    }
}

function updateStatusBadges() {
    var dashboardTab = document.getElementById('dashboard-tab');
    if (!dashboardTab || !dashboardTab.classList.contains('active')) {
        return;
    }
    
    fetch('/health')
        .then(function(r) {
            var healthBadge = document.getElementById('health-badge');
            if (r.ok) {
                healthBadge.className = 'badge badge-success';
                healthBadge.textContent = '✓ Healthy';
            } else {
                healthBadge.className = 'badge badge-danger';
                healthBadge.textContent = '✗ Unhealthy';
            }
            return r.json();
        })
        .catch(function(e) {
            var healthBadge = document.getElementById('health-badge');
            healthBadge.className = 'badge badge-danger';
            healthBadge.textContent = '✗ Error';
        });
    
    fetch('/ready')
        .then(function(r) {
            var readyBadge = document.getElementById('ready-badge');
            if (r.ok) {
                readyBadge.className = 'badge badge-success';
                readyBadge.textContent = '✓ Ready';
            } else {
                readyBadge.className = 'badge badge-warning';
                readyBadge.textContent = '⏸ Not Ready';
            }
            return r.json();
        })
        .catch(function(e) {
            var readyBadge = document.getElementById('ready-badge');
            readyBadge.className = 'badge badge-danger';
            readyBadge.textContent = '✗ Error';
        });
}

// CLI Commands toggle (only one visible at a time)
function showCLICommands(commandsHTML, title) {
    var container = document.getElementById('cli-commands-container');
    var titleEl = document.getElementById('cli-commands-title');
    var listEl = document.getElementById('cli-commands-list');
    
    if (currentCLISection === title && container.style.display === 'block') {
        container.style.display = 'none';
        currentCLISection = null;
        return;
    }
    
    titleEl.textContent = title;
    listEl.innerHTML = commandsHTML;
    container.style.display = 'block';
    currentCLISection = title;
    
    setTimeout(function() {
        container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

// Tab switching
function switchTab(tabName) {
    var tabs = document.querySelectorAll('.nav-item');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].classList.remove('active');
    }
    event.target.classList.add('active');
    
    var contents = document.querySelectorAll('.tab-content');
    for (var j = 0; j < contents.length; j++) {
        contents[j].classList.remove('active');
    }
    document.getElementById(tabName + '-tab').classList.add('active');
    
    stopAutoRefresh();
    
    // Stop dashboard refresh if active
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
    
    var cliContainer = document.getElementById('cli-commands-container');
    if (cliContainer) {
        cliContainer.style.display = 'none';
        currentCLISection = null;
    }
    
    if (tabName === 'dashboard') {
        initDashboardRefresh();
        startStatusMonitoring();
        startClusterStatsMonitoring();
        startToolsStatusMonitoring();
    } else if (tabName === 'database') {
        refreshDatabaseData();
        fetchDatabaseInfo();
        startAutoRefresh();
        stopStatusMonitoring();
        stopClusterStatsMonitoring();
        stopToolsStatusMonitoring();
    } else if (tabName === 'logs') {
        refreshLogs();
        stopStatusMonitoring();
        stopClusterStatsMonitoring();
    } else {
        stopStatusMonitoring();
        stopClusterStatsMonitoring();
    }
}

// Auto-refresh control
function startAutoRefresh() {
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    autoRefreshInterval = setInterval(function() {
        var dbTab = document.getElementById('database-tab');
        if (dbTab && dbTab.classList.contains('active')) {
            refreshDatabaseData();
        }
    }, 5000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Dashboard button functions
function makeUnhealthy() {
    var commands = '<div class="cli-command"><code>kubectl get pods -n k8s-multi-demo -w</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl describe pod -n k8s-multi-demo -l app=k8s-demo-app | grep -A 10 "Liveness"</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl logs -n k8s-multi-demo -l app=k8s-demo-app --tail=50</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl get events -n k8s-multi-demo --field-selector involvedObject.kind=Pod</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    
    showCLICommands(commands, '💔 Monitor Pod Health & Restart');
    
    fetch('/simulate/crash', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('Pod Health Simulated', '✓ Pod is now unhealthy<br><br>Kubernetes will detect the failed health check and automatically restart the pod in ~30 seconds.<br><br>Use the CLI commands below to monitor the restart process.');
            setTimeout(updateStatusBadges, 500);
        })
        .catch(function(e) {
            showModal('Error', 'Failed to make pod unhealthy: ' + e.message);
        });
}

function simulateNotReady() {
    var commands = '<div class="cli-command"><code>kubectl get endpoints -n k8s-multi-demo k8s-demo-service</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl describe pod -n k8s-multi-demo -l app=k8s-demo-app | grep -A 10 "Readiness"</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>curl http://localhost:30080/ready</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl get service -n k8s-multi-demo k8s-demo-service</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    
    showCLICommands(commands, '⏸️ Monitor Service Routing');
    
    fetch('/simulate/notready', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('Readiness Simulated', '✓ Pod is now not ready<br><br>Kubernetes will stop routing traffic to this pod. The pod will be removed from service endpoints.<br><br>Use the CLI commands below to verify traffic routing.');
            setTimeout(updateStatusBadges, 500);
        })
        .catch(function(e) {
            showModal('Error', 'Failed to simulate not ready: ' + e.message);
        });
}

function resetApp() {
    var commands = '<div class="cli-command"><code>curl http://localhost:30080/health</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>curl http://localhost:30080/ready</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl get pods -n k8s-multi-demo -l app=k8s-demo-app</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    
    showCLICommands(commands, '🔄 Verify Reset');
    
    fetch('/reset', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('App Reset', '✓ Application reset to healthy state<br><br>Both health and readiness probes are now passing.<br><br>Use the CLI commands below to verify the status.');
            setTimeout(updateStatusBadges, 500);
        })
        .catch(function(e) {
            showModal('Error', 'Failed to reset app: ' + e.message);
        });
}

function showMonitoringCommands() {
    var commands = '<div class="cli-command"><code>kubectl get pods -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl top pods -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl get hpa -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl describe pod -n k8s-multi-demo -l app=k8s-demo-app</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>kubectl get events -n k8s-multi-demo --sort-by=.metadata.creationTimestamp</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';

    showCLICommands(commands, '📊 General Monitoring Commands');
}

// Open testing actions sidebar
function openTestingSidebar() {
    var sidebar = document.getElementById('testing-sidebar');
    var overlay = document.getElementById('sidebar-overlay');

    if (sidebar) sidebar.classList.add('active');
    if (overlay) overlay.classList.add('active');

    // Prevent body scroll when sidebar is open
    document.body.style.overflow = 'hidden';
}

// Close testing actions sidebar
function closeTestingSidebar() {
    var sidebar = document.getElementById('testing-sidebar');
    var overlay = document.getElementById('sidebar-overlay');

    if (sidebar) sidebar.classList.remove('active');
    if (overlay) overlay.classList.remove('active');

    // Restore body scroll
    document.body.style.overflow = '';
}

// Show Helm CLI commands
function showHelmCommands() {
    var commands = '<div class="cli-command"><code>helm list -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>helm history k8s-demo -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>helm get values k8s-demo -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';
    commands += '<div class="cli-command"><code>helm status k8s-demo -n k8s-multi-demo</code><button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button></div>';

    showCLICommands(commands, '⎈ Helm Commands');
}

// Copy command functionality
function copyCommand(button) {
    var cliCommand = button.parentElement;
    var code = cliCommand.querySelector('code');
    if (!code) return;
    
    var text = code.textContent;
    
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function() {
            var originalText = button.textContent;
            button.textContent = '✓ Copied';
            button.style.background = '#16A34A';
            setTimeout(function() {
                button.textContent = originalText;
                button.style.background = '';
            }, 2000);
        }).catch(function(e) {
            showModal('Copy Failed', 'Failed to copy: ' + e.message);
        });
    } else {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            var originalText = button.textContent;
            button.textContent = '✓ Copied';
            button.style.background = '#16A34A';
            setTimeout(function() {
                button.textContent = originalText;
                button.style.background = '';
            }, 2000);
        } catch (e) {
            showModal('Copy Failed', 'Failed to copy: ' + e.message);
        }
        document.body.removeChild(textarea);
    }
}

// Database functions
function refreshDatabaseData(skipUserDropdown) {
    fetch('/api/db/stats')
        .then(function(r) { return r.json(); })
        .then(function(stats) {
            document.getElementById('db-url').textContent = stats.database_url || 'Unknown';
            document.getElementById('users-count').textContent = stats.users_count || 0;
            document.getElementById('active-users-count').textContent = stats.active_users_count || 0;
            document.getElementById('tasks-count').textContent = stats.tasks_count || 0;
            document.getElementById('pending-tasks-count').textContent = stats.pending_tasks_count || 0;
            
            var badge = document.getElementById('db-status-badge');
            if (stats.connected) {
                badge.className = 'badge badge-success';
                badge.textContent = '🟢 Connected';
            } else {
                badge.className = 'badge badge-danger';
                badge.textContent = '🔴 Disconnected';
            }
        })
        .catch(function(e) { console.error('Stats error:', e); });
    
    fetch('/api/users')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            updateUsersTable(data.users || []);
            if (!skipUserDropdown) {
                updateUserDropdown(data.users || []);
            }
        })
        .catch(function(e) { console.error('Users error:', e); });

    fetch('/api/tasks')
        .then(function(r) { return r.json(); })
        .then(function(data) { updateTasksTable(data.tasks || []); })
        .catch(function(e) { console.error('Tasks error:', e); });
    
    // Fetch database configuration info
    fetchDatabaseInfo();
}


// Fetch database StatefulSet info (secrets and configmaps)
function fetchDatabaseInfo() {
    fetch("/api/db/info")
        .then(function(r) { return r.json(); })
        .then(function(info) {
            var secretInfo = document.getElementById("db-secret-info");
            var configmapInfo = document.getElementById("db-configmap-info");
            
            if (secretInfo) {
                if (info.uses_secret && info.secret_name) {
                    secretInfo.innerHTML = "<span class=\"badge badge-success\">✓ Yes</span> - " + escapeHtml(info.secret_name);
                } else if (info.uses_secret) {
                    secretInfo.innerHTML = "<span class=\"badge badge-success\">✓ Yes</span>";
                } else {
                    secretInfo.innerHTML = "<span class=\"badge badge-grey\">✗ No</span>";
                }
            }
            
            if (configmapInfo) {
                if (info.uses_configmap && info.configmap_name) {
                    configmapInfo.innerHTML = "<span class=\"badge badge-success\">✓ Yes</span> - " + escapeHtml(info.configmap_name);
                } else if (info.uses_configmap) {
                    configmapInfo.innerHTML = "<span class=\"badge badge-success\">✓ Yes</span>";
                } else {
                    configmapInfo.innerHTML = "<span class=\"badge badge-grey\">✗ No</span>";
                }
            }
        })
        .catch(function(e) { 
            console.error("Database info error:", e);
            var secretInfo = document.getElementById("db-secret-info");
            var configmapInfo = document.getElementById("db-configmap-info");
            if (secretInfo) secretInfo.textContent = "Error loading info";
            if (configmapInfo) configmapInfo.textContent = "Error loading info";
        });
}

function updateUsersTable(users) {
    var tbody = document.getElementById('users-tbody');
    if (!tbody) return;
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No users found</td></tr>';
        return;
    }
    
    var html = '';
    for (var i = 0; i < users.length; i++) {
        var u = users[i];
        html += '<tr>';
        html += '<td><strong>' + escapeHtml(u.username) + '</strong></td>';
        html += '<td>' + escapeHtml(u.email) + '</td>';
        html += '<td>' + escapeHtml(u.full_name || 'N/A') + '</td>';
        html += '<td><span class="badge badge-primary">' + u.tasks_count + '</span></td>';
        html += '<td><span class="badge ' + (u.is_active ? 'badge-success' : 'badge-danger') + '">';
        html += u.is_active ? '✅ Active' : '❌ Inactive';
        html += '</span></td>';
        html += '<td>' + formatDate(u.created_at) + '</td>';
        html += '</tr>';
    }
    tbody.innerHTML = html;
}

function updateTasksTable(tasks) {
    var tbody = document.getElementById('tasks-tbody');
    if (!tbody) return;
    if (!tasks || tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No tasks found</td></tr>';
        return;
    }
    
    var html = '';
    for (var i = 0; i < tasks.length; i++) {
        var t = tasks[i];
        var badgeClass = 'badge-warning';
        var icon = '⏳';
        if (t.status === 'completed') {
            badgeClass = 'badge-success';
            icon = '✅';
        } else if (t.status === 'in_progress') {
            badgeClass = 'badge-primary';
            icon = '🔄';
        }
        
        html += '<tr>';
        html += '<td><strong>' + escapeHtml(t.title) + '</strong></td>';
        html += '<td>' + escapeHtml(t.username || 'Unknown') + '</td>';
        html += '<td><span class="badge ' + badgeClass + '">' + icon + ' ' + t.status + '</span></td>';
        html += '<td><span class="badge badge-grey">Priority ' + t.priority + '</span></td>';
        html += '<td>' + formatDate(t.created_at) + '</td>';
        html += '</tr>';
    }
    tbody.innerHTML = html;
}

function updateUserDropdown(users) {
    var select = document.getElementById('task-user-id');
    if (!select) return;
    
    var currentValue = select.value;
    var submitBtn = document.getElementById('create-task-form').querySelector('button[type="submit"]');
    
    if (!users || users.length === 0) {
        select.innerHTML = '<option value="">No users - create one first</option>';
        select.disabled = true;
        if (submitBtn) submitBtn.disabled = true;
    } else {
        select.disabled = false;
        if (submitBtn) submitBtn.disabled = false;
        
        var html = '';
        for (var i = 0; i < users.length; i++) {
            html += '<option value="' + users[i].id + '"';
            if (users[i].id === currentValue) {
                html += ' selected';
            } else if (i === 0 && !currentValue) {
                html += ' selected';
            }
            html += '>' + escapeHtml(users[i].username) + ' (' + escapeHtml(users[i].email) + ')</option>';
        }
        select.innerHTML = html;
    }
}

// Form submission handlers
document.getElementById('create-user-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    var data = {
        username: document.getElementById('user-username').value,
        email: document.getElementById('user-email').value,
        full_name: document.getElementById('user-fullname').value
    };
    
    fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(function(r) {
        if (r.ok) return r.json();
        return r.json().then(function(e) { throw new Error(e.detail); });
    })
    .then(function(result) {
        var msg = document.getElementById('user-success');
        msg.textContent = '✅ User "' + data.username + '" created successfully!';
        msg.classList.add('show');
        setTimeout(function() { msg.classList.remove('show'); }, 5000);

        document.getElementById('create-user-form').reset();
        showCLICommandsForUser(result);
        refreshDatabaseData();
        
        setTimeout(function() {
            var usersSection = document.getElementById('users-section');
            if (usersSection) {
                usersSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 500);
    })
    .catch(function(e) { showModal('Error', 'Failed to create user: ' + e.message); });
});

document.getElementById('create-task-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    var data = {
        user_id: document.getElementById('task-user-id').value,
        title: document.getElementById('task-title').value,
        description: document.getElementById('task-description').value,
        status: document.getElementById('task-status').value,
        priority: parseInt(document.getElementById('task-priority').value)
    };
    
    fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(function(r) {
        if (r.ok) return r.json();
        return r.json().then(function(e) { throw new Error(e.detail); });
    })
    .then(function(result) {
        var msg = document.getElementById('task-success');
        msg.textContent = '✅ Task "' + data.title + '" created successfully!';
        msg.classList.add('show');
        setTimeout(function() { msg.classList.remove('show'); }, 5000);

        document.getElementById('create-task-form').reset();
        document.getElementById('task-user-id').value = data.user_id;

        showCLICommandsForTask(result);
        refreshDatabaseData(true);
        
        setTimeout(function() {
            var tasksSection = document.getElementById('tasks-section');
            if (tasksSection) {
                tasksSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 500);
    })
    .catch(function(e) { showModal('Error', 'Failed to create task: ' + e.message); });
});

function showCLICommandsForUser(user) {
    var section = document.getElementById('cli-section');
    var list = document.getElementById('cli-commands-db-list');
    if (!section || !list) return;
    
    var username = user.username.replace(/'/g, "''");
    var html = '<div style="margin-bottom: 15px;">';
    html += '<div style="color: var(--text-secondary); margin-bottom: 5px;">View user in database:</div>';
    html += '<div class="cli-command">';
    html += '<code>kubectl exec -n k8s-multi-demo $(kubectl get pods -n k8s-multi-demo -l app=postgres -o jsonpath=\'{.items[0].metadata.name}\') -- psql -U k8s_demo_user -d k8s_demo_db -c "SELECT * FROM users WHERE username=\'' + escapeHtml(username) + '\';"</code>';
    html += '<button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button>';
    html += '</div></div>';
    
    list.innerHTML = html;
    section.style.display = 'block';
}

function showCLICommandsForTask(task) {
    var section = document.getElementById('cli-section');
    var list = document.getElementById('cli-commands-db-list');
    if (!section || !list) return;
    
    var title = task.title.replace(/'/g, "''");
    var html = '<div style="margin-bottom: 15px;">';
    html += '<div style="color: var(--text-secondary); margin-bottom: 5px;">View task in database:</div>';
    html += '<div class="cli-command">';
    html += '<code>kubectl exec -n k8s-multi-demo $(kubectl get pods -n k8s-multi-demo -l app=postgres -o jsonpath=\'{.items[0].metadata.name}\') -- psql -U k8s_demo_user -d k8s_demo_db -c "SELECT title, status FROM tasks WHERE title=\'' + escapeHtml(title) + '\';"</code>';
    html += '<button class="copy-btn" onclick="copyCommand(this)">📋 Copy</button>';
    html += '</div></div>';
    
    list.innerHTML = html;
    section.style.display = 'block';
}

function exportDatabaseStats() {
    fetch('/api/db/stats')
        .then(function(r) { return r.json(); })
        .then(function(stats) {
            var blob = new Blob([JSON.stringify(stats, null, 2)], { type: 'application/json' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'db-stats-' + new Date().toISOString() + '.json';
            a.click();
        });
}

// Load test functions
function startLoadTest() {
    var startBtn = document.getElementById('start-load-btn');
    var stopBtn = document.getElementById('stop-load-btn');
    var statusBadge = document.getElementById('load-status');
    
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;
    if (statusBadge) {
        statusBadge.className = 'badge badge-warning';
        statusBadge.textContent = '⚡ Running';
    }
    
    fetch('/api/load-test/start', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('Load Test Started', 'Load test is now running. Pods should start scaling up within 1-2 minutes.<br><br>Monitor with: <code>kubectl get pods -n k8s-multi-demo -w</code>');
        })
        .catch(function(e) {
            showModal('Error', 'Failed to start load test: ' + e.message);
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
        });
}

function stopLoadTest() {
    var startBtn = document.getElementById('start-load-btn');
    var stopBtn = document.getElementById('stop-load-btn');
    var statusBadge = document.getElementById('load-status');
    
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
    if (statusBadge) {
        statusBadge.className = 'badge badge-grey';
        statusBadge.textContent = 'Not Running';
    }
    
    fetch('/api/load-test/stop', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('Load Test Stopped', 'Load test has been stopped. Pods will scale back down to the minimum after a few minutes.');
        });
}

// Logs functions
function refreshLogs() {
    fetch('/api/logs')
        .then(function(r) {
            if (!r.ok) throw new Error('Failed to fetch logs');
            return r.json();
        })
        .then(function(data) {
            var viewer = document.getElementById('log-viewer');
            if (!viewer) return;

            if (data.logs && data.logs.length > 0) {
                var html = '';
                for (var i = 0; i < data.logs.length; i++) {
                    var log = data.logs[i];
                    html += '<div class="log-entry ' + log.level + '">';
                    html += '[' + log.timestamp + '] ' + log.level + ': ' + escapeHtml(log.message);
                    html += '</div>';
                }
                viewer.innerHTML = html;
                viewer.scrollTop = viewer.scrollHeight;
            } else {
                viewer.innerHTML = '<div class="info-message">No logs available yet. Logs will appear here as the application runs.</div>';
            }
        })
        .catch(function(e) {
            console.error('Error fetching logs:', e);
            var viewer = document.getElementById('log-viewer');
            if (viewer) {
                viewer.innerHTML = '<div class="error-message">Failed to load logs: ' + escapeHtml(e.message) + '</div>';
            }
        });
}

function clearLogs() {
    var viewer = document.getElementById('log-viewer');
    if (viewer) {
        viewer.innerHTML = '<div>Logs cleared</div>';
    }
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        return new Date(dateString).toLocaleString();
    } catch(e) {
        return dateString;
    }
}

// ==================== GUIDED TOUR ====================

var tourCurrentStep = 0;
var tourSteps = [
    {
        element: '#tour-sidebar-nav',
        title: 'Navigation Menu',
        content: 'Navigate between Dashboard and interactive learning scenarios for Kubernetes, ArgoCD, Helm, Terraform, Ansible, and more. Each section opens hands-on practice environments.',
        position: 'right'
    },
    {
        element: '#tour-cluster-stats',
        title: 'Cluster Overview',
        content: 'Monitor your Kubernetes cluster in real-time. Click any stat box to see detailed information about deployments, pods, and nodes.',
        position: 'bottom'
    },
    {
        element: '#tour-app-info',
        title: 'Application Status',
        content: 'Track your application\'s health and readiness status from Kubernetes probes. This reflects real-time data from your cluster.',
        position: 'bottom'
    },
    {
        element: '#tour-testing-btn',
        title: 'Testing Actions',
        content: 'Simulate real-world scenarios like pod failures, health check issues, and load testing. Observe how Kubernetes self-heals automatically.',
        position: 'left'
    },
    {
        element: '#tour-prerequisites-btn',
        title: 'Prerequisites',
        content: 'Check which DevOps tools are installed on your machine (kubectl, helm, docker, etc.) and install missing tools with a single command.',
        position: 'left'
    },
    {
        element: '#tour-deployment-tools',
        title: 'Deployment Tools',
        content: 'Monitor Helm releases and ArgoCD applications in your cluster. Access CLI commands and open the ArgoCD UI to manage GitOps deployments.',
        position: 'top'
    },
    {
        element: '#tour-hands-on-projects',
        title: 'Hands-On Projects',
        content: 'Complete real-world DevOps projects combining multiple tools and technologies. Perfect for portfolio building and interview preparation!',
        position: 'right'
    },
    {
        element: '#tour-developer-info',
        title: 'How was it created',
        content: 'Built by a DevOps Engineer to help others learn through practical scenarios. Click "Click Me" to learn more and access the GitHub repository.',
        position: 'right'
    }
];

// Check if user has seen the tour
function checkTourStatus() {
    var hasSeenTour = localStorage.getItem('devops-simulator-tour-seen');
    if (!hasSeenTour) {
        setTimeout(function() {
            showTourWelcome();
        }, 1000);
    }
}

// Show welcome modal
function showTourWelcome() {
    var modal = document.getElementById('tour-welcome-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

// Hide welcome modal
function hideTourWelcome() {
    var modal = document.getElementById('tour-welcome-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Start the tour
function startTour() {
    hideTourWelcome();
    tourCurrentStep = 0;
    showTourStep(tourCurrentStep);

    var overlay = document.getElementById('tour-overlay');
    if (overlay) {
        overlay.classList.add('active');
    }
}

// Skip the tour
function skipTour() {
    var dontShow = document.getElementById('tour-dont-show');
    if (dontShow && dontShow.checked) {
        localStorage.setItem('devops-simulator-tour-seen', 'true');
    }
    hideTourWelcome();
}

// End the tour
function endTour() {
    localStorage.setItem('devops-simulator-tour-seen', 'true');

    var overlay = document.getElementById('tour-overlay');
    var tooltip = document.getElementById('tour-tooltip');

    if (overlay) overlay.classList.remove('active');
    if (tooltip) tooltip.classList.remove('active');

    // Remove highlight from current element
    var highlighted = document.querySelector('.tour-highlight');
    if (highlighted) {
        highlighted.classList.remove('tour-highlight');
    }
}

// Show a specific tour step
function showTourStep(stepIndex) {
    var step = tourSteps[stepIndex];
    if (!step) return;

    // Remove previous highlight
    var prevHighlighted = document.querySelector('.tour-highlight');
    if (prevHighlighted) {
        prevHighlighted.classList.remove('tour-highlight');
    }

    // Find and highlight the element
    var element = document.querySelector(step.element);
    if (!element) {
        // Skip to next step if element not found
        if (stepIndex < tourSteps.length - 1) {
            nextTourStep();
        } else {
            endTour();
        }
        return;
    }

    element.classList.add('tour-highlight');

    // Scroll element into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Update tooltip content
    var titleEl = document.getElementById('tour-title');
    var contentEl = document.getElementById('tour-content');
    var counterEl = document.getElementById('tour-step-counter');
    var prevBtn = document.getElementById('tour-prev-btn');
    var nextBtn = document.getElementById('tour-next-btn');

    if (titleEl) titleEl.textContent = step.title;
    if (contentEl) contentEl.textContent = step.content;
    if (counterEl) counterEl.textContent = (stepIndex + 1) + '/' + tourSteps.length;

    // Update navigation buttons
    if (prevBtn) {
        prevBtn.style.display = stepIndex === 0 ? 'none' : 'inline-block';
    }
    if (nextBtn) {
        nextBtn.textContent = stepIndex === tourSteps.length - 1 ? 'Finish' : 'Next';
    }

    // Update progress dots
    updateTourProgress(stepIndex);

    // Position the tooltip
    setTimeout(function() {
        positionTooltip(element, step.position);
    }, 300);
}

// Position tooltip relative to element
function positionTooltip(element, position) {
    var tooltip = document.getElementById('tour-tooltip');
    if (!tooltip || !element) return;

    var rect = element.getBoundingClientRect();
    var tooltipRect = tooltip.getBoundingClientRect();
    var padding = 15;

    // Remove all arrow classes
    tooltip.classList.remove('arrow-top', 'arrow-bottom', 'arrow-left', 'arrow-right');

    var top, left;

    switch (position) {
        case 'right':
            top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
            left = rect.right + padding;
            tooltip.classList.add('arrow-left');
            break;
        case 'left':
            top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
            left = rect.left - tooltipRect.width - padding;
            tooltip.classList.add('arrow-right');
            break;
        case 'bottom':
            top = rect.bottom + padding;
            left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            tooltip.classList.add('arrow-top');
            break;
        case 'top':
            top = rect.top - tooltipRect.height - padding;
            left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            tooltip.classList.add('arrow-bottom');
            break;
        default:
            top = rect.bottom + padding;
            left = rect.left;
            tooltip.classList.add('arrow-top');
    }

    // Keep tooltip within viewport
    var viewportWidth = window.innerWidth;
    var viewportHeight = window.innerHeight;

    if (left < 10) left = 10;
    if (left + tooltipRect.width > viewportWidth - 10) {
        left = viewportWidth - tooltipRect.width - 10;
    }
    if (top < 10) top = 10;
    if (top + tooltipRect.height > viewportHeight - 10) {
        top = viewportHeight - tooltipRect.height - 10;
    }

    tooltip.style.top = top + 'px';
    tooltip.style.left = left + 'px';
    tooltip.classList.add('active');
}

// Update progress dots
function updateTourProgress(currentIndex) {
    var progressContainer = document.getElementById('tour-progress');
    if (!progressContainer) return;

    var html = '';
    for (var i = 0; i < tourSteps.length; i++) {
        var className = 'tour-progress-dot';
        if (i < currentIndex) className += ' completed';
        if (i === currentIndex) className += ' active';
        html += '<div class="' + className + '"></div>';
    }
    progressContainer.innerHTML = html;
}

// Next step
function nextTourStep() {
    if (tourCurrentStep < tourSteps.length - 1) {
        tourCurrentStep++;
        showTourStep(tourCurrentStep);
    } else {
        endTour();
    }
}

// Previous step
function prevTourStep() {
    if (tourCurrentStep > 0) {
        tourCurrentStep--;
        showTourStep(tourCurrentStep);
    }
}

// Initialize tour check on page load
window.addEventListener('DOMContentLoaded', function() {
    setTimeout(checkTourStatus, 1000);
});

// ============================================
// PREREQUISITES MODAL
// ============================================

var currentPrereqStep = 1;
var currentSessionId = null;
var prerequisitesData = null;

function openPrerequisitesModal() {
    currentPrereqStep = 1;
    showPrereqStep(1);
    var modal = document.getElementById('prerequisites-modal');
    modal.classList.add('active');
}

function closePrerequisitesModal() {
    var modal = document.getElementById('prerequisites-modal');
    modal.classList.remove('active');
    currentPrereqStep = 1;
    currentSessionId = null;
}

function showPrereqStep(stepNum) {
    var steps = document.querySelectorAll('.prereq-step');
    steps.forEach(function(step, idx) {
        step.classList.remove('active');
        if (idx + 1 === stepNum) {
            step.classList.add('active');
        }
    });
    currentPrereqStep = stepNum;
}

function copyCheckerCommand() {
    var code = document.getElementById('checker-command');
    var textToCopy = code.textContent.trim();

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(function() {
            // Change button text temporarily
            var btn = event.target;
            var originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = '#16A34A';
            setTimeout(function() {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        }).catch(function(err) {
            showModal('Error', 'Failed to copy: ' + err, false);
        });
    } else {
        // Fallback for older browsers
        var textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            var btn = event.target;
            var originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = '#16A34A';
            setTimeout(function() {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (err) {
            showModal('Error', 'Failed to copy: ' + err, false);
        }
        document.body.removeChild(textArea);
    }
}

function refreshPrereqStatus(retryCount) {
    retryCount = retryCount || 0;
    var maxRetries = 5;
    var retryDelay = 500; // ms

    // Poll for latest session report
    fetch('/api/prerequisites/status/latest')
        .then(function(r) {
            if (!r.ok) {
                throw new Error('NOT_FOUND');
            }
            return r.json();
        })
        .then(function(data) {
            currentSessionId = data.session_id || 'latest';
            prerequisitesData = data;
            displayPrereqResults(data);
            showPrereqStep(2);
        })
        .catch(function(e) {
            // Retry if report not found yet and retries remaining
            if (e.message === 'NOT_FOUND' && retryCount < maxRetries) {
                setTimeout(function() {
                    refreshPrereqStatus(retryCount + 1);
                }, retryDelay);
            } else {
                // Close prerequisites modal first, then show error
                closePrerequisitesModal();
                setTimeout(function() {
                    var message = retryCount >= maxRetries
                        ? 'No report found after multiple attempts. Please run the checker command and try again.'
                        : 'Error loading prerequisites status. Please try again.';
                    showModal('Error', message, false);
                }, 300);
            }
        });
}

function displayPrereqResults(data) {
    var tools = data.tools;
    var installedCount = 0;
    var missingCount = 0;
    var listHtml = '';

    // Sort tools: installed first, then missing
    var toolEntries = Object.entries(tools).sort(function(a, b) {
        if (a[1].installed === b[1].installed) return 0;
        return a[1].installed ? -1 : 1;
    });

    toolEntries.forEach(function(entry) {
        var toolId = entry[0];
        var tool = entry[1];
        var installed = tool.installed;

        if (installed) installedCount++;
        else missingCount++;

        var itemClass = installed ? 'prereq-item installed' : 'prereq-item';
        var statusClass = installed ? 'prereq-status installed' : 'prereq-status missing';
        var statusText = installed ? '✓ Installed' : '✗ Missing';
        var versionText = installed ? tool.version : 'Not available';
        var locationText = tool.location || '';
        var locationBadge = locationText === 'local' ? '<span class="location-badge local">📍 local</span>' : '';
        var checkboxDisabled = installed ? 'disabled' : '';

        listHtml += '<div class="' + itemClass + '">';
        listHtml += '  <input type="checkbox" class="prereq-checkbox" ';
        listHtml += '    data-tool-id="' + toolId + '" ';
        listHtml += '    onchange="updateDownloadButton()" ';
        listHtml += checkboxDisabled + '>';
        listHtml += '  <div class="prereq-info">';
        listHtml += '    <div class="prereq-name">' + toolId + ' ' + locationBadge + '</div>';
        listHtml += '    <div class="prereq-version">' + versionText + '</div>';
        listHtml += '  </div>';
        listHtml += '  <div class="' + statusClass + '">' + statusText + '</div>';
        listHtml += '</div>';
    });

    document.getElementById('prereq-installed-count').textContent = installedCount + ' Installed';
    document.getElementById('prereq-missing-count').textContent = missingCount + ' Missing';
    document.getElementById('prerequisites-list').innerHTML = listHtml;

    // Auto-check missing tools
    updateDownloadButton();
}

function updateDownloadButton() {
    var checkboxes = document.querySelectorAll('.prereq-checkbox:checked:not([disabled])');
    var downloadBtn = document.getElementById('download-installer-btn');
    var installBtn = document.getElementById('install-now-btn');

    if (checkboxes.length > 0) {
        var toolText = checkboxes.length + ' tool' + (checkboxes.length > 1 ? 's' : '');
        downloadBtn.disabled = false;
        downloadBtn.textContent = '📥 Download Installer (' + toolText + ')';
        installBtn.disabled = false;
        installBtn.textContent = '🚀 Install Now (' + toolText + ')';
    } else {
        downloadBtn.disabled = true;
        downloadBtn.textContent = '📥 Download Installer';
        installBtn.disabled = true;
        installBtn.textContent = '🚀 Install Now';
    }
}

function installNow() {
    var checkboxes = document.querySelectorAll('.prereq-checkbox:checked:not([disabled])');
    var selectedTools = [];

    checkboxes.forEach(function(cb) {
        selectedTools.push(cb.dataset.toolId);
    });

    if (selectedTools.length === 0) {
        showModal('Error', 'Please select at least one tool to install.', false);
        return;
    }

    // Build the install command with selected tools
    var toolsParam = selectedTools.join(',');
    var installCmd = 'curl -s http://localhost:30080/api/prerequisites/installer.sh?tools=' + toolsParam + ' | bash';

    // Update the command in Step 3
    document.getElementById('install-command').textContent = installCmd;

    // Show step 3
    showPrereqStep(3);
}

function copyInstallCommand() {
    var code = document.getElementById('install-command');
    var textToCopy = code.textContent.trim();

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(function() {
            var btn = event.target;
            var originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = '#16A34A';
            setTimeout(function() {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        }).catch(function(err) {
            showModal('Error', 'Failed to copy: ' + err, false);
        });
    } else {
        var textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            var btn = event.target;
            var originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            btn.style.background = '#16A34A';
            setTimeout(function() {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (err) {
            showModal('Error', 'Failed to copy: ' + err, false);
        }
        document.body.removeChild(textArea);
    }
}

function downloadInstaller() {
    var checkboxes = document.querySelectorAll('.prereq-checkbox:checked:not([disabled])');
    var selectedTools = [];

    checkboxes.forEach(function(cb) {
        selectedTools.push(cb.dataset.toolId);
    });

    if (selectedTools.length === 0) {
        showModal('Error', 'Please select at least one tool to install.', false);
        return;
    }

    // Download installer script
    var url = '/api/prerequisites/installer.sh?tools=' + selectedTools.join(',');
    window.location.href = url;

    // Show step 4 (download instructions)
    setTimeout(function() {
        showPrereqStep(4);
    }, 500);
}

function backToStep1() {
    showPrereqStep(1);
}

function backToStep2() {
    showPrereqStep(2);
}