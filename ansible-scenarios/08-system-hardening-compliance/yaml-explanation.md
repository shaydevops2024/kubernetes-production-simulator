# YAML Files Explanation - System Hardening and Security Compliance

This guide explains the playbook patterns for SSH hardening, firewall configuration, service management, and security compliance automation.

---

## 🔒 What is System Hardening?

System hardening reduces the attack surface by disabling unnecessary services, enforcing strong authentication, applying firewall rules, and configuring intrusion detection. Ansible makes this repeatable and auditable across all servers.

---

## 🔑 harden-ssh.yml — SSH Security Configuration

### Full File Breakdown:

```yaml
---
- name: Harden SSH configuration
  hosts: servers
  become: yes
  tasks:
    - name: Backup original sshd_config
      copy:
        src: /etc/ssh/sshd_config
        dest: /etc/ssh/sshd_config.bak
        remote_src: yes      # Copy is on remote host (not control machine)
        backup: yes

    - name: Configure secure SSH settings
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
        state: present
        validate: /usr/sbin/sshd -t -f %s   # Validate before writing!
      loop:
        - { regexp: '^#?PermitRootLogin', line: 'PermitRootLogin no' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?X11Forwarding', line: 'X11Forwarding no' }
        - { regexp: '^#?MaxAuthTries', line: 'MaxAuthTries 3' }
        - { regexp: '^#?Protocol', line: 'Protocol 2' }
        - { regexp: '^#?ClientAliveInterval', line: 'ClientAliveInterval 300' }
        - { regexp: '^#?ClientAliveCountMax', line: 'ClientAliveCountMax 2' }
        - { regexp: '^#?AllowTcpForwarding', line: 'AllowTcpForwarding no' }
        - { regexp: '^#?LogLevel', line: 'LogLevel VERBOSE' }
      notify: restart sshd
```

**`lineinfile:` module**
- Ensures a specific line is present (or absent) in a file
- Uses regex to find existing lines and replace them

**`regexp: '^#?PermitRootLogin'`**
- Matches the line whether it's commented (`#PermitRootLogin`) or not (`PermitRootLogin`)
- `^` — Start of line
- `#?` — Zero or one `#` character (matches both commented and uncommented)

**`line: 'PermitRootLogin no'`**
- Replaces the matched line with this exact string
- If no match found, appends to end of file

**`validate: /usr/sbin/sshd -t -f %s`**
- **CRITICAL** — Validates SSH config syntax before writing
- `%s` is replaced with a temp file path before the real file is modified
- If validation fails → file is NOT written → no lockout risk
- **Always use validate for SSH config!**

**Key SSH hardening settings:**
| Setting | Value | Why |
|---|---|---|
| `PermitRootLogin no` | no | Never log in as root directly |
| `PasswordAuthentication no` | no | Keys only, no brute-force risk |
| `X11Forwarding no` | no | Disable GUI forwarding (attack vector) |
| `MaxAuthTries 3` | 3 | Limit login attempts |
| `Protocol 2` | 2 | SSHv1 is insecure, use only v2 |
| `ClientAliveInterval 300` | 300 | Disconnect idle sessions after 5 min |
| `AllowTcpForwarding no` | no | Disable SSH tunneling (if not needed) |
| `LogLevel VERBOSE` | VERBOSE | Log all authentication attempts |

**`remote_src: yes`** (copy module)
- Source file is on the remote host, not the control machine
- Used for: making remote-to-remote copies (backup existing file before modifying)

---

## 🔥 configure-firewall.yml — UFW Firewall Rules

### Full File Breakdown:

```yaml
---
- name: Configure UFW firewall
  hosts: servers
  become: yes
  tasks:
    - name: Install UFW
      apt:
        name: ufw
        state: present

    - name: Set UFW default policies
      ufw:
        direction: "{{ item.direction }}"
        policy: "{{ item.policy }}"
      loop:
        - { direction: incoming, policy: deny }   # Block all inbound by default
        - { direction: outgoing, policy: allow }  # Allow all outbound

    - name: Allow SSH (before enabling UFW!)
      ufw:
        rule: allow
        port: "22"
        proto: tcp
        comment: "SSH access"

    - name: Allow HTTP and HTTPS
      ufw:
        rule: allow
        port: "{{ item }}"
        proto: tcp
      loop:
        - "80"
        - "443"

    - name: Allow specific IP range for internal services
      ufw:
        rule: allow
        src: "10.0.0.0/8"
        dest: any
        port: "8080"
        proto: tcp
        comment: "Internal app access"

    - name: Rate limit SSH (brute force protection)
      ufw:
        rule: limit
        port: "22"
        proto: tcp

    - name: Enable UFW
      ufw:
        state: enabled
        logging: 'on'

  handlers:
    - name: reload ufw
      ufw:
        state: reloaded
```

**`ufw:` module — UFW (Uncomplicated Firewall)**

**Default policies:**
- `incoming: deny` — Block all inbound traffic unless explicitly allowed
- `outgoing: allow` — Allow all outbound traffic (servers initiate outbound connections)

**CRITICAL — Allow SSH before enabling UFW:**
- If you enable UFW without allowing SSH first → locked out!
- Ansible task order matters: SSH rule → then enable UFW

**`rule: limit` for SSH**
- UFW rate-limiting: blocks source IP after 6 connections within 30 seconds
- Built-in brute-force protection
- Better than nothing, but use fail2ban for comprehensive protection

**`src: "10.0.0.0/8"`**
- Restrict access to specific CIDR ranges
- Internal-only services: only accept from private IP ranges
- Reduces external attack surface

**`logging: 'on'`**
- Log blocked connection attempts to `/var/log/ufw.log`
- Essential for intrusion detection and incident response

---

## 🛡️ configure-fail2ban.yml — Intrusion Detection

### Full File Breakdown:

```yaml
---
- name: Configure fail2ban intrusion detection
  hosts: servers
  become: yes
  tasks:
    - name: Install fail2ban
      apt:
        name: fail2ban
        state: present

    - name: Deploy fail2ban jail configuration
      template:
        src: templates/jail.local.j2
        dest: /etc/fail2ban/jail.local
        mode: '0644'
      notify: restart fail2ban

    - name: Start and enable fail2ban
      service:
        name: fail2ban
        state: started
        enabled: yes

  handlers:
    - name: restart fail2ban
      service:
        name: fail2ban
        state: restarted
```

### templates/jail.local.j2 — fail2ban Configuration Template:

```jinja2
[DEFAULT]
# Ban time and retry settings
bantime = {{ fail2ban_bantime | default('1h') }}
findtime = {{ fail2ban_findtime | default('10m') }}
maxretry = {{ fail2ban_maxretry | default(5) }}

# Backend for log monitoring
backend = systemd

# Email notifications (optional)
{% if fail2ban_email_enabled | default(false) %}
destemail = {{ fail2ban_email }}
sender = fail2ban@{{ ansible_hostname }}
action = %(action_mwl)s   # Ban + email with whois + log lines
{% else %}
action = %(action_)s      # Ban only (no email)
{% endif %}

[sshd]
enabled = true
port = 22
filter = sshd
maxretry = {{ fail2ban_ssh_maxretry | default(3) }}
bantime = {{ fail2ban_ssh_bantime | default('24h') }}
```

**`bantime = 1h`** — IP is banned for 1 hour after threshold reached
**`findtime = 10m`** — Count failures within a 10-minute window
**`maxretry = 5`** — Ban after 5 failures in the findtime window
**`[sshd]` jail** — Monitor `/var/log/auth.log` for SSH failures specifically

---

## 🔧 disable-services.yml — Attack Surface Reduction

```yaml
---
- name: Disable unnecessary services
  hosts: servers
  become: yes
  vars:
    services_to_disable:
      - avahi-daemon      # mDNS/DNS-SD service (usually unnecessary)
      - cups              # Printing service
      - bluetooth         # Bluetooth
      - postfix           # Mail server (unless needed)
      - rpcbind           # NFS/RPC (unless using NFS)
      - telnet            # Plaintext remote access (NEVER use)
      - ftp               # Plaintext file transfer (NEVER use)

  tasks:
    - name: Disable unnecessary services
      service:
        name: "{{ item }}"
        state: stopped
        enabled: no
      loop: "{{ services_to_disable }}"
      failed_when: false    # Don't fail if service doesn't exist on this host

    - name: Remove telnet and ftp packages
      apt:
        name:
          - telnet
          - ftp
          - rsh-client
        state: absent
        purge: yes           # Remove config files too (not just binaries)
```

**`state: stopped` + `enabled: no`**
- `stopped` — Stop the service immediately
- `enabled: no` — Prevent it from starting on reboot
- Both together ensure the service never runs

**`failed_when: false`**
- Don't fail if the service doesn't exist on this host
- Some servers won't have `bluetooth` or `cups` installed
- Allows the loop to continue even if one service is missing

**`purge: yes`** (apt module)
- Removes configuration files in addition to the package
- `state: absent` without purge leaves `/etc/` files behind
- `purge: yes` is a clean uninstall

---

## 📁 configure-permissions.yml — File Permission Hardening

```yaml
---
- name: Harden file permissions
  hosts: servers
  become: yes
  tasks:
    - name: Set critical file permissions
      file:
        path: "{{ item.path }}"
        mode: "{{ item.mode }}"
        owner: "{{ item.owner | default('root') }}"
        group: "{{ item.group | default('root') }}"
      loop:
        - { path: /etc/passwd,    mode: '0644' }   # User database (readable, not writable)
        - { path: /etc/shadow,    mode: '0640' }   # Password hashes (root + shadow group only)
        - { path: /etc/gshadow,   mode: '0640' }   # Group passwords
        - { path: /etc/group,     mode: '0644' }   # Group database
        - { path: /etc/sudoers,   mode: '0440' }   # Sudo config (read-only)
        - { path: /etc/crontab,   mode: '0600' }   # Root crontab
        - { path: /boot,          mode: '0700' }   # Bootloader files

    - name: Find world-writable files (security audit)
      find:
        paths: /etc
        file_type: file
        mode: '0002'          # Match if others-writable bit is set
      register: world_writable_files

    - name: Report world-writable files
      debug:
        msg: "World-writable file found: {{ item.path }}"
      loop: "{{ world_writable_files.files }}"
      when: world_writable_files.files | length > 0

    - name: Fix world-writable files
      file:
        path: "{{ item.path }}"
        mode: "o-w"           # Remove world-write bit (symbolic mode)
      loop: "{{ world_writable_files.files }}"
```

**`find:` module**
- Searches for files matching criteria on remote hosts
- `mode: '0002'` — Find files where the world-write bit is set
- Returns a list of matching files in `register`

**`mode: "o-w"`** (symbolic mode)
- Remove the world-write permission bit
- `o` = others, `-` = remove, `w` = write
- Safer than setting absolute mode (preserves other existing permissions)

---

## ✅ compliance-check.yml — Validation and Reporting

```yaml
---
- name: Run security compliance checks
  hosts: servers
  become: yes
  tasks:
    - name: Check PermitRootLogin is disabled
      command: grep -E "^PermitRootLogin\s+no" /etc/ssh/sshd_config
      register: root_login_check
      changed_when: false       # This is a read-only check
      failed_when: root_login_check.rc != 0

    - name: Check PasswordAuthentication is disabled
      command: grep -E "^PasswordAuthentication\s+no" /etc/ssh/sshd_config
      register: password_auth_check
      changed_when: false
      failed_when: password_auth_check.rc != 0

    - name: Check UFW is enabled
      command: ufw status
      register: ufw_status
      changed_when: false
      failed_when: "'Status: active' not in ufw_status.stdout"

    - name: Check fail2ban is running
      service_facts:

    - name: Assert fail2ban is active
      assert:
        that:
          - "'fail2ban.service' in ansible_facts.services"
          - "ansible_facts.services['fail2ban.service'].state == 'running'"
        fail_msg: "fail2ban is NOT running on {{ inventory_hostname }}"
        success_msg: "fail2ban is running on {{ inventory_hostname }}"

    - name: Generate compliance report
      template:
        src: templates/compliance-report.j2
        dest: "/tmp/compliance-{{ inventory_hostname }}-{{ ansible_date_time.date }}.txt"
      delegate_to: localhost
```

**`changed_when: false`**
- Mark the task as `ok` (not `changed`) even if it runs a command
- Commands are not idempotent by default — this tells Ansible "this is just a check"
- **Use for:** Any task that only reads/checks state, never modifies it

**`failed_when:`**
- Custom failure condition
- `failed_when: root_login_check.rc != 0` — fail if grep returns non-zero exit code
- More expressive than relying on module's default failure

**`assert:` module**
- Validates that conditions are true
- `that:` — List of conditions (all must be true)
- `fail_msg:` — Clear error if assertion fails
- `success_msg:` — Optional success message

---

## 🔄 How Hardening Playbooks Chain Together

```yaml
---
# site-hardening.yml — Master hardening playbook
- import_playbook: disable-services.yml        # Remove attack vectors first
- import_playbook: configure-firewall.yml      # Lock down network
- import_playbook: harden-ssh.yml              # Secure remote access
- import_playbook: configure-fail2ban.yml      # Add intrusion detection
- import_playbook: configure-permissions.yml   # Fix file permissions
- import_playbook: compliance-check.yml        # Validate everything applied
```

**`import_playbook:`**
- Includes an entire playbook file
- Runs sequentially, in order
- **vs `include_playbook:`** — `import` is static (parsed at start), `include` is dynamic (parsed at runtime)

---

## 🎯 Best Practices

### 1. Always Validate SSH Config Before Applying
```yaml
- lineinfile:
    path: /etc/ssh/sshd_config
    line: "PermitRootLogin no"
    validate: /usr/sbin/sshd -t -f %s   # ALWAYS validate!
```

### 2. Allow SSH Before Enabling Firewall
```yaml
tasks:
  - name: Allow SSH first
    ufw:
      rule: allow
      port: "22"

  - name: Enable UFW (AFTER SSH allowed)
    ufw:
      state: enabled
```

### 3. Use `changed_when: false` for Audit Tasks
```yaml
- command: grep "PermitRootLogin no" /etc/ssh/sshd_config
  changed_when: false    # It's a check, not a change
  register: result
  failed_when: result.rc != 0
```

### 4. Tag Hardening Tasks for Selective Runs
```yaml
- name: Harden SSH
  lineinfile:
    ...
  tags:
    - hardening
    - ssh
    - security
```

### 5. Generate Compliance Reports
```yaml
- template:
    src: compliance-report.j2
    dest: "reports/{{ inventory_hostname }}-{{ ansible_date_time.date }}.txt"
  delegate_to: localhost    # Save report locally
```

---

## 🔍 Debugging Security Configurations

```bash
# Test SSH config validity
ssh -T -o StrictHostKeyChecking=no user@server "sudo sshd -t"

# Check UFW status
ansible servers -m command -a "ufw status verbose" --become

# Check fail2ban status
ansible servers -m command -a "fail2ban-client status" --become

# Run compliance checks only
ansible-playbook site-hardening.yml --tags compliance

# Check file permissions
ansible servers -m stat -a "path=/etc/ssh/sshd_config"

# Dry run before applying
ansible-playbook harden-ssh.yml --check --diff

# Test on one server first
ansible-playbook site-hardening.yml --limit web1
```

---

## 🎓 Key Takeaways

1. **`validate:` for SSH** — Always validate `sshd_config` before writing; syntax errors = lockout
2. **`lineinfile` with `regexp`** — Safely replace existing settings (commented or not)
3. **Allow SSH before enabling UFW** — Task order is critical; wrong order = lockout
4. **`changed_when: false`** — Audit/check tasks shouldn't report as `changed`
5. **`assert:` module** — Express compliance requirements as readable assertions
6. **`find:` + loop** — Discover and fix world-writable files automatically
7. **`failed_when: false`** — Skip tasks for services that don't exist on all hosts
8. **`purge: yes`** — Complete package removal including config files
9. **`import_playbook:`** — Chain multiple hardening playbooks into a master playbook

---

*System hardening with Ansible turns manual, error-prone security steps into repeatable, auditable automation. Every server in your fleet can be identically hardened with a single command.*
