# YAML Files Explanation - Monitoring Stack Deployment with Ansible

This guide explains the playbook patterns for deploying Prometheus, Node Exporter, Grafana, and alerting rules using Ansible.

---

## 📊 What is the Monitoring Stack?

A complete observability stack using open-source tools:
- **Prometheus** — Metrics collection and storage (time-series database)
- **Node Exporter** — System metrics agent (CPU, memory, disk, network)
- **Grafana** — Dashboards and visualization
- **Alertmanager** — Alert routing and notification

```
[Servers with Node Exporter]
        ↓ (scrapes metrics every 15s)
   [Prometheus]
        ↓ (reads metrics)
    [Grafana]  ←→  [Alertmanager] → Email/Slack/PagerDuty
```

---

## 📋 deploy-prometheus.yml — Prometheus Server

### Full File Breakdown:

```yaml
---
- name: Deploy Prometheus monitoring server
  hosts: monitoring
  become: yes
  vars:
    prometheus_version: "2.45.0"
    prometheus_port: 9090
    prometheus_data_dir: /var/lib/prometheus
    prometheus_config_dir: /etc/prometheus
    scrape_interval: 15s
    evaluation_interval: 15s

  tasks:
    - name: Create prometheus user (service account)
      user:
        name: prometheus
        shell: /usr/sbin/nologin
        system: yes
        create_home: no
        state: present

    - name: Create prometheus directories
      file:
        path: "{{ item }}"
        state: directory
        owner: prometheus
        group: prometheus
        mode: '0755'
      loop:
        - "{{ prometheus_config_dir }}"
        - "{{ prometheus_data_dir }}"
        - "{{ prometheus_config_dir }}/rules"

    - name: Download Prometheus
      get_url:
        url: "https://github.com/prometheus/prometheus/releases/download/v{{ prometheus_version }}/prometheus-{{ prometheus_version }}.linux-amd64.tar.gz"
        dest: /tmp/prometheus.tar.gz
        checksum: "sha256:abc123..."    # Always verify downloads!

    - name: Extract Prometheus
      unarchive:
        src: /tmp/prometheus.tar.gz
        dest: /tmp/
        remote_src: yes

    - name: Install Prometheus binaries
      copy:
        src: "/tmp/prometheus-{{ prometheus_version }}.linux-amd64/{{ item }}"
        dest: "/usr/local/bin/{{ item }}"
        remote_src: yes
        owner: root
        mode: '0755'
      loop:
        - prometheus
        - promtool

    - name: Deploy Prometheus configuration
      template:
        src: templates/prometheus.yml.j2
        dest: "{{ prometheus_config_dir }}/prometheus.yml"
        owner: prometheus
        mode: '0644'
      notify: restart prometheus

    - name: Deploy alert rules
      template:
        src: templates/alert-rules.yml.j2
        dest: "{{ prometheus_config_dir }}/rules/alert-rules.yml"
        owner: prometheus
        mode: '0644'
      notify: restart prometheus

    - name: Deploy Prometheus systemd service
      template:
        src: templates/prometheus.service.j2
        dest: /etc/systemd/system/prometheus.service
        mode: '0644'
      notify:
        - reload systemd
        - restart prometheus

    - name: Start and enable Prometheus
      service:
        name: prometheus
        state: started
        enabled: yes

  handlers:
    - name: reload systemd
      systemd:
        daemon_reload: yes

    - name: restart prometheus
      service:
        name: prometheus
        state: restarted
```

**`get_url:` module**
- Downloads files from URLs
- `checksum: "sha256:..."` — Verifies download integrity (CRITICAL for security)
- Idempotent: skips download if file already exists with correct checksum

**`unarchive:` module**
- Extracts tar.gz, zip, etc. archives
- `remote_src: yes` — Archive is on remote host (not control machine)
- Handles permissions automatically

**`system: yes`** (user module)
- Creates a system user (UID < 1000, no login, no home)
- Used for service accounts that don't need interactive login

---

## 📋 templates/prometheus.yml.j2 — Prometheus Configuration

```yaml
# /etc/prometheus/prometheus.yml
global:
  scrape_interval: {{ scrape_interval }}         # How often to collect metrics
  evaluation_interval: {{ evaluation_interval }} # How often to evaluate alert rules
  external_labels:
    cluster: {{ cluster_name | default('default') }}
    environment: {{ app_env }}

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - "{{ alertmanager_host }}:9093"

# Rules files
rule_files:
  - "{{ prometheus_config_dir }}/rules/*.yml"

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:{{ prometheus_port }}']

  # Node Exporter on all monitored servers
  - job_name: 'node_exporter'
    static_configs:
      - targets:
{% for host in groups['all_servers'] %}
          - "{{ hostvars[host]['ansible_host'] | default(host) }}:9100"
{% endfor %}
        labels:
          environment: {{ app_env }}

  # Application metrics
  - job_name: 'myapp'
    metrics_path: /metrics
    scrape_interval: 30s    # Override global for this job
    static_configs:
      - targets:
{% for host in groups['webservers'] %}
          - "{{ hostvars[host]['ansible_host'] | default(host) }}:8080"
{% endfor %}
```

**`scrape_interval: 15s`** — Prometheus pulls metrics every 15 seconds
**`evaluation_interval: 15s`** — Alert rules evaluated every 15 seconds

**`groups['all_servers']`** — Ansible inventory group access in Jinja2
**`hostvars[host]['ansible_host']`** — Get a variable from another host's vars

**Jinja2 loop generating scrape targets:**
```jinja2
{% for host in groups['webservers'] %}
    - "{{ hostvars[host]['ansible_host'] }}:8080"
{% endfor %}
```
→ Renders to:
```yaml
    - "10.0.1.10:8080"
    - "10.0.1.11:8080"
    - "10.0.1.12:8080"
```

---

## 📋 templates/alert-rules.yml.j2 — Alerting Rules

```yaml
groups:
  - name: system_alerts
    interval: 30s    # Evaluate this group every 30s (overrides global)
    rules:
      # Alert if any instance is down
      - alert: InstanceDown
        expr: up == 0
        for: 5m            # Must be true for 5 minutes before firing
        labels:
          severity: critical
          team: infrastructure
        annotations:
          summary: "Instance {{ "{{ $labels.instance }}" }} is down"
          description: "{{ "{{ $labels.instance }}" }} of job {{ "{{ $labels.job }}" }} has been down for more than 5 minutes."
          runbook: "https://wiki.example.com/runbook/instance-down"

      # Alert on high CPU usage
      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > {{ cpu_alert_threshold | default(85) }}
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ "{{ $labels.instance }}" }}"
          description: "CPU usage is {{ "{{ $value | humanize }}" }}% (threshold: {{ cpu_alert_threshold | default(85) }}%)"

      # Alert on low disk space
      - alert: LowDiskSpace
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < {{ disk_alert_threshold | default(20) }}
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space on {{ "{{ $labels.instance }}" }}"
          description: "Disk is {{ "{{ $value | humanize }}" }}% full"

      # Alert on high memory usage
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > {{ memory_alert_threshold | default(90) }}
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage on {{ "{{ $labels.instance }}" }}"
```

**`for: 5m`** — Alert fires only if condition is true for 5 continuous minutes
- Prevents alert storms from brief spikes
- `for: 0m` would fire immediately

**Alert labels** — Used for routing (Alertmanager uses labels to decide who to notify)
- `severity: critical` → PagerDuty on-call
- `severity: warning` → Slack notification
- `team: infrastructure` → Route to infra team

**`{{ "{{ $labels.instance }}" }}`** — Prometheus template variable inside Jinja2
- Outer `{{ }}` = Jinja2 variable (Ansible)
- Inner `{{ $labels.instance }}` = Prometheus template (evaluated by Prometheus at alert time)
- Jinja2 escaping required to prevent Ansible from processing the inner `{{ }}`

---

## 📋 deploy-node-exporter.yml — System Metrics Agent

```yaml
---
- name: Deploy Node Exporter on all servers
  hosts: all_servers         # Deploy to every server being monitored
  become: yes
  vars:
    node_exporter_version: "1.6.1"
    node_exporter_port: 9100

  tasks:
    - name: Create node_exporter user
      user:
        name: node_exporter
        shell: /usr/sbin/nologin
        system: yes
        create_home: no

    - name: Download Node Exporter
      get_url:
        url: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/node_exporter-{{ node_exporter_version }}.linux-amd64.tar.gz"
        dest: /tmp/node_exporter.tar.gz

    - name: Extract and install Node Exporter
      unarchive:
        src: /tmp/node_exporter.tar.gz
        dest: /tmp/
        remote_src: yes

    - name: Copy binary to /usr/local/bin
      copy:
        src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-amd64/node_exporter"
        dest: /usr/local/bin/node_exporter
        remote_src: yes
        owner: root
        mode: '0755'

    - name: Deploy Node Exporter systemd service
      copy:
        content: |
          [Unit]
          Description=Node Exporter
          After=network.target

          [Service]
          User=node_exporter
          Group=node_exporter
          Type=simple
          ExecStart=/usr/local/bin/node_exporter \
            --collector.systemd \
            --collector.processes \
            --web.listen-address=0.0.0.0:{{ node_exporter_port }}

          [Install]
          WantedBy=multi-user.target
        dest: /etc/systemd/system/node_exporter.service
        mode: '0644'
      notify:
        - reload systemd
        - restart node_exporter
```

**Inline systemd service file with `copy: content:`**
- Use `content:` to write a string directly to a file (no template file needed)
- Good for simple service files that don't need variable substitution
- Multi-line strings use YAML block scalar `|` (literal block)

**Node Exporter collectors:**
- `--collector.systemd` — Exposes systemd service states as metrics
- `--collector.processes` — Exposes process stats
- `--web.listen-address` — Port for Prometheus to scrape

---

## 📋 deploy-grafana.yml — Dashboard and Visualization

```yaml
---
- name: Deploy Grafana
  hosts: monitoring
  become: yes
  vars:
    grafana_port: 3000
    grafana_admin_password: "{{ vault_grafana_password }}"

  tasks:
    - name: Add Grafana apt repository
      apt_repository:
        repo: "deb https://packages.grafana.com/oss/deb stable main"
        state: present
        filename: grafana

    - name: Add Grafana GPG key
      apt_key:
        url: https://packages.grafana.com/gpg.key
        state: present

    - name: Install Grafana
      apt:
        name: grafana
        state: present
        update_cache: yes

    - name: Configure Grafana
      template:
        src: templates/grafana.ini.j2
        dest: /etc/grafana/grafana.ini
        mode: '0640'
        owner: root
        group: grafana
      notify: restart grafana

    - name: Start and enable Grafana
      service:
        name: grafana-server
        state: started
        enabled: yes

    - name: Wait for Grafana to start
      wait_for:
        port: "{{ grafana_port }}"
        timeout: 60

    - name: Add Prometheus datasource
      community.grafana.grafana_datasource:
        grafana_url: "http://localhost:{{ grafana_port }}"
        grafana_user: admin
        grafana_password: "{{ vault_grafana_password }}"
        name: Prometheus
        ds_type: prometheus
        ds_url: "http://localhost:{{ prometheus_port }}"
        is_default: yes
        state: present

    - name: Import Node Exporter dashboard
      community.grafana.grafana_dashboard:
        grafana_url: "http://localhost:{{ grafana_port }}"
        grafana_user: admin
        grafana_password: "{{ vault_grafana_password }}"
        dashboard_id: 1860    # Official Node Exporter Full dashboard ID from grafana.com
        overwrite: yes
        state: present
```

**`community.grafana.grafana_datasource:`**
- Configures Grafana datasources via API (no manual UI clicks)
- `is_default: yes` — Sets this as the default datasource for new panels

**`community.grafana.grafana_dashboard:`**
- Imports dashboards from Grafana.com by ID
- `dashboard_id: 1860` — The popular "Node Exporter Full" community dashboard
- `overwrite: yes` — Update if dashboard already imported

**`wait_for: port:`** — Wait until Grafana's HTTP port is accepting connections before making API calls

---

## 🔄 How the Monitoring Stack Deploys

```
ansible-playbook monitoring-site.yml
         ↓
Play 1: Deploy Node Exporter on ALL servers
  → Creates prometheus user
  → Installs binary → systemd service
  → Starts on port 9100
         ↓
Play 2: Deploy Prometheus on monitoring server
  → Downloads Prometheus
  → Generates prometheus.yml with all host IPs
  → Generates alert rules from template
  → Starts on port 9090
  → Begins scraping node_exporter:9100 on all servers
         ↓
Play 3: Deploy Grafana on monitoring server
  → Installs via apt
  → Configures grafana.ini
  → Waits for Grafana to start
  → Adds Prometheus datasource via API
  → Imports dashboards via API
         ↓
Complete: Metrics flowing → Grafana showing dashboards
```

---

## 🎯 Best Practices

### 1. Always Verify Downloads
```yaml
- get_url:
    url: "https://..."
    dest: /tmp/prometheus.tar.gz
    checksum: "sha256:actual_hash_here"  # Prevents supply chain attacks
```

### 2. Use Service Accounts for Daemons
```yaml
- user:
    name: prometheus
    shell: /usr/sbin/nologin   # Can't log in interactively
    system: yes                # System user, low UID
    create_home: no            # No /home/prometheus
```

### 3. Template Scrape Configs from Inventory
```jinja2
{% for host in groups['webservers'] %}
  - "{{ hostvars[host]['ansible_host'] }}:9100"
{% endfor %}
```

### 4. Use Vault for Grafana Admin Password
```yaml
grafana_admin_password: "{{ vault_grafana_password }}"  # From Ansible Vault
```

### 5. Tag Tasks for Selective Redeployment
```yaml
tags:
  - monitoring
  - prometheus    # --tags prometheus
  - grafana       # --tags grafana
  - node_exporter # --tags node_exporter
```

---

## 🔍 Debugging Commands

```bash
# Check Prometheus targets are up
curl http://prometheus-host:9090/api/v1/targets | jq '.data.activeTargets[].health'

# Check Node Exporter is running on servers
ansible all_servers -m uri -a "url=http://localhost:9100/metrics return_content=no"

# Verify Prometheus config syntax
promtool check config /etc/prometheus/prometheus.yml

# Verify alert rules syntax
promtool check rules /etc/prometheus/rules/*.yml

# Check Grafana is up
ansible monitoring -m uri -a "url=http://localhost:3000/api/health"

# Restart monitoring stack
ansible-playbook monitoring-site.yml --tags restart
```

---

## 🎓 Key Takeaways

1. **`get_url` + `checksum`** — Always verify downloaded binaries (supply chain security)
2. **`unarchive: remote_src: yes`** — Extract archives that are already on the remote host
3. **Jinja2 loops over inventory groups** — Dynamically generate Prometheus scrape configs from inventory
4. **Escaping `{{ }}` in alert templates** — Use `{{ "{{ $labels.instance }}" }}` to pass Prometheus templates through Jinja2
5. **`wait_for: port:`** — Wait for services to start before making API calls
6. **`community.grafana.*` modules** — Configure Grafana programmatically (datasources, dashboards)
7. **Service user accounts** — Always run daemons as dedicated low-privilege users
8. **`for: 5m` in alert rules** — Prevents alert storms from brief metric spikes

---

*Deploying a monitoring stack with Ansible gives you full observability from day one. Every server is automatically added to monitoring as it's provisioned — no manual Prometheus/Grafana configuration needed.*
