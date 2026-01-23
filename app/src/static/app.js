// app/src/static/app.js
// app/src/static/app.js

// Global state
var autoRefreshInterval = null;
var statusMonitorInterval = null;
var clusterStatsInterval = null;
var currentCLISection = null;
var clusterStatsData = null;
var dashboardRefreshInterval = null;
var currentRefreshSeconds = 5; // Default 5 seconds

// Load config and start monitoring on startup
window.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    startStatusMonitoring();
    startClusterStatsMonitoring();
    
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

// Open Play Kubernetes scenarios page
function openPlayKubernetes() {
    window.open('/static/scenarios.html', '_blank');
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
        })
        .catch(function(e) { console.error('Config error:', e); });
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
    var profileHTML = '<div style="text-align: left; padding: 20px; line-height: 1.8;">';
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
    showModal('Developer Profile', profileHTML, true);
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
    } else if (tabName === 'database') {
        refreshDatabaseData();
        fetchDatabaseInfo();
        startAutoRefresh();
        stopStatusMonitoring();
        stopClusterStatsMonitoring();
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
            document.getElementById('metrics-count').textContent = stats.metrics_count || 0;
            
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
        .then(function(users) {
            updateUsersTable(users);
            if (!skipUserDropdown) {
                updateUserDropdown(users);
            }
        })
        .catch(function(e) { console.error('Users error:', e); });
    
    fetch('/api/tasks')
        .then(function(r) { return r.json(); })
        .then(function(tasks) { updateTasksTable(tasks); })
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
    
    fetch('/api/users/create', {
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
        showCLICommandsForUser(result.user);
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
    
    fetch('/api/tasks/create', {
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
        
        showCLICommandsForTask(result.task);
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
    
    fetch('/loadtest/start', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) { 
            showModal('Load Test Started', 'Load test is now running. Pods should start scaling up within 1-2 minutes.<br><br>Monitor with: <code>kubectl get pods -n k8s-multi-demo -w</code>');
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
    
    fetch('/loadtest/stop', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            showModal('Load Test Stopped', 'Load test has been stopped. Pods will scale back down to the minimum after a few minutes.');
        });
}

// Logs functions
function refreshLogs() {
    fetch('/logs')
        .then(function(r) { return r.json(); })
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
                viewer.innerHTML = '<div>No logs available</div>';
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