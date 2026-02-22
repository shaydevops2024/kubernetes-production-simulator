# YAML Files Explanation - Package Management with Ansible

This guide explains each playbook file in detail, breaking down every field and providing context for why and how to write them.

---

## 📦 install-packages.yml

### What is this Playbook?
A playbook that installs multiple packages on Debian/Ubuntu hosts using the `apt` module.

### Full File Breakdown:

```yaml
---
- name: Install and manage packages
  hosts: pkg_servers
  become: yes
```

**`---`**
- YAML document start marker
- Optional but conventional in Ansible playbooks
- Signals to parsers that a YAML document begins

**`- name: Install and manage packages`**
- Human-readable description of the play
- Shown in output: `PLAY [Install and manage packages]`
- Use descriptive names — they are your documentation

**`hosts: pkg_servers`**
- Which inventory group to target
- Must match a group in your inventory file
- **Options:**
  - `hosts: all` - Every host in inventory
  - `hosts: webservers:databases` - Multiple groups (union)
  - `hosts: webservers:!databases` - Exclude a group
  - `hosts: web1` - A single specific host

**`become: yes`**
- Run tasks with elevated privileges (sudo)
- Required for package installation (apt needs root)
- **Options:**
  - `become: yes` - Escalate privileges
  - `become_user: postgres` - Become a specific user (not just root)
  - `become_method: sudo` - How to escalate (sudo, su, pbrun, etc.)

---

```yaml
  tasks:
    - name: Update apt cache
      apt:
        update_cache: yes
        cache_valid_time: 3600
```

**`tasks:`**
- List of actions to perform in order
- Each task calls one Ansible module

**`- name: Update apt cache`**
- Task description (shown in output per-host)
- **Best practice:** Name every task, even simple ones

**`apt:`**
- Ansible module for managing apt packages (Debian/Ubuntu)
- **Alternative modules:**
  - `yum` / `dnf` - RHEL/CentOS/Fedora
  - `package` - Distribution-agnostic (auto-detects)
  - `zypper` - SUSE
  - `homebrew` - macOS

**`update_cache: yes`**
- Runs `apt-get update` before installing
- Ensures package lists are fresh
- Without this, you might install outdated versions

**`cache_valid_time: 3600`**
- Only update cache if it's older than 3600 seconds (1 hour)
- Prevents unnecessary updates on every playbook run
- **Performance tip:** Saves 5-15 seconds per run when cache is fresh

---

```yaml
    - name: Install nginx, curl, and htop
      apt:
        name:
          - nginx
          - curl
          - htop
        state: present
```

**`name:` (list format)**
- Install multiple packages in a single task
- More efficient than separate tasks per package
- Single apt transaction = faster and atomic

**`state: present`**
- Ensure packages are installed
- **State options:**
  - `present` - Install if not installed (idempotent)
  - `latest` - Install and upgrade to latest version
  - `absent` - Uninstall the package
  - `build-dep` - Install build dependencies
  - `fixed` - Attempt to fix broken packages

**Why `present` not `latest`?**
- `present` is idempotent: if nginx 1.18 is installed, it stays at 1.18
- `latest` would upgrade nginx 1.18 → 1.22 on every run
- **Production best practice:** Use `present` for stability, explicit version pinning when needed

**Version pinning:**
```yaml
- name: Install specific nginx version
  apt:
    name: nginx=1.18.0-0ubuntu1
    state: present
```

---

## 🔧 manage-service.yml

### What is this Playbook?
Ensures a service is running and configured to start on boot.

### Full File Breakdown:

```yaml
---
- name: Manage nginx service
  hosts: pkg_servers
  become: yes
  tasks:
    - name: Ensure nginx is started and enabled
      service:
        name: nginx
        state: started
        enabled: yes
```

**`service:`**
- Manages system services (systemd, SysV, upstart)
- Works across different init systems automatically

**`name: nginx`**
- The service name as systemd/init knows it
- Same name used in `systemctl status nginx`

**`state: started`**
- Ensure the service is running right now
- **State options:**
  - `started` - Start if not running (idempotent)
  - `stopped` - Stop if running
  - `restarted` - Always restart (not idempotent!)
  - `reloaded` - Send SIGHUP to reload config (gentler than restart)

**`enabled: yes`**
- Configure service to start automatically at boot
- Runs `systemctl enable nginx`
- **Options:**
  - `yes` - Enable (start on boot)
  - `no` - Disable (don't start on boot)

**Why separate `state` and `enabled`?**
- A service can be started-but-not-enabled (won't survive reboot)
- A service can be enabled-but-not-started (not running now)
- Setting both ensures correct state immediately **and** after reboot

---

## 🔄 How Playbooks and Modules Work Together

### Playbook Execution Flow:

```
ansible-playbook install-packages.yml
         ↓
Parse YAML → Validate syntax
         ↓
Load inventory → Find pkg_servers hosts
         ↓
Connect to each host via SSH
         ↓
For each task:
  1. Compile module code (Python)
  2. Copy to remote host
  3. Execute module
  4. Collect result (JSON)
  5. Report: ok / changed / failed / skipped
```

### Idempotency - The Key Principle:

Running a playbook multiple times should produce the same result:

```bash
# First run: installs nginx (CHANGED)
# Second run: nginx already installed (OK - no change)
# Third run: still OK
ansible-playbook install-packages.yml
```

**`ok`** = Task ran, no change needed
**`changed`** = Task ran, made a change
**`failed`** = Task encountered an error
**`skipped`** = Task was skipped (condition not met)

---

## 🧩 Advanced Package Management Patterns

### Installing from Custom Repository:
```yaml
- name: Add nginx official repository
  apt_repository:
    repo: deb http://nginx.org/packages/ubuntu focal nginx
    state: present
    filename: nginx-official

- name: Add nginx signing key
  apt_key:
    url: https://nginx.org/keys/nginx_signing.key
    state: present

- name: Install nginx from official repo
  apt:
    name: nginx
    state: present
    update_cache: yes
```

### Installing from .deb File:
```yaml
- name: Download package
  get_url:
    url: https://example.com/app_1.0.deb
    dest: /tmp/app.deb

- name: Install local deb package
  apt:
    deb: /tmp/app.deb
    state: present
```

### Using Handlers for Service Restart:
```yaml
- name: Install and configure nginx
  hosts: webservers
  become: yes
  tasks:
    - name: Install nginx
      apt:
        name: nginx
        state: present
      notify: restart nginx          # Only trigger if this task changes

    - name: Deploy nginx config
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
      notify: restart nginx          # Trigger if config changes

  handlers:
    - name: restart nginx            # Only runs if notified, and only once
      service:
        name: nginx
        state: restarted
```

**Why handlers?**
- Prevents unnecessary restarts (only restarts if config changed)
- Runs once at the end even if notified multiple times
- More efficient than `state: restarted` in a task

### Cross-Distribution Package Management:
```yaml
- name: Install web server (any distro)
  package:                           # Distribution-agnostic module
    name: "{{ web_server_package }}" # Variable set per distro
    state: present

# In group_vars/ubuntu.yml:
# web_server_package: nginx

# In group_vars/centos.yml:
# web_server_package: httpd
```

---

## 🔍 Debugging Package Issues

```bash
# Check if package is installed on remote host
ansible pkg_servers -m apt -a "name=nginx state=present" --check

# List installed packages
ansible pkg_servers -m command -a "dpkg -l nginx"

# Check service status
ansible pkg_servers -m service_facts

# View service status in output
ansible pkg_servers -m debug -a "var=ansible_facts.services['nginx.service']"

# Gather all facts about hosts
ansible pkg_servers -m setup

# Run with verbose output (shows module args and returns)
ansible-playbook install-packages.yml -v
ansible-playbook install-packages.yml -vvv   # Maximum verbosity
```

---

## 🎯 Best Practices

### 1. Always Update Cache Before Installing
```yaml
- apt:
    name: nginx
    state: present
    update_cache: yes              # Refresh package lists
    cache_valid_time: 86400        # But only if older than 24 hours
```

### 2. Use `present` for Stability
```yaml
# GOOD - Stable, predictable
state: present

# RISKY in production - May unexpectedly upgrade
state: latest
```

### 3. Install Multiple Packages in One Task
```yaml
# GOOD - One apt transaction, faster
- apt:
    name:
      - nginx
      - curl
      - htop
    state: present

# BAD - Three separate transactions, slower
- apt:
    name: nginx
    state: present
- apt:
    name: curl
    state: present
- apt:
    name: htop
    state: present
```

### 4. Always Pair Install with Service Management
```yaml
tasks:
  - name: Install nginx
    apt:
      name: nginx
      state: present

  - name: Start and enable nginx
    service:
      name: nginx
      state: started
      enabled: yes
```

### 5. Use Variables for Package Lists
```yaml
# In vars or group_vars:
packages:
  - nginx
  - curl
  - htop
  - vim

# In playbook:
- apt:
    name: "{{ packages }}"
    state: present
```

---

## 🎓 Key Takeaways

1. **`apt` module** manages packages declaratively — you define the desired state, not the steps
2. **`state: present`** is idempotent — safe to run multiple times
3. **`update_cache: yes` with `cache_valid_time`** balances freshness with performance
4. **`service` module** controls both current state (`started`) and boot behavior (`enabled`)
5. **Handlers** trigger service restarts only when configuration actually changes
6. **`become: yes`** is required for package installation — apt needs root privileges
7. **Install multiple packages in one task** — more efficient than one task per package

---

*Package management is the foundation of infrastructure automation. Mastering `apt`, `yum`, and `service` modules gives you the power to configure entire server fleets consistently and repeatably.*
