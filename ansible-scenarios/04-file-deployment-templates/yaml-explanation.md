# YAML Files Explanation - File Deployment and Jinja2 Templates

This guide explains each playbook and template file in detail, breaking down every field and providing context for why and how to write them.

---

## 🌐 deploy-nginx-config.yml

### What is this Playbook?
Deploys a dynamically generated nginx configuration file from a Jinja2 template.

### Full File Breakdown:

```yaml
---
- name: Deploy nginx configuration from template
  hosts: webservers
  become: yes
  tasks:
    - name: Deploy nginx.conf
      template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: '0644'
        backup: yes
```

**`template:` module**
- Renders a Jinja2 template (`.j2` file) using Ansible variables and facts
- Uploads the rendered result to the remote host
- **Key difference from `copy:`** — `template` processes Jinja2 syntax; `copy` sends the file as-is

**`src: templates/nginx.conf.j2`**
- Path to the Jinja2 template on the **control machine** (where you run ansible-playbook)
- Relative to the playbook file
- **Convention:** Keep templates in a `templates/` subdirectory

**`dest: /etc/nginx/nginx.conf`**
- Destination path on the **remote host**
- Must be writable by the become user (root in this case)

**`owner: root`** + **`group: root`**
- Sets file ownership after deployment
- Always set explicitly to avoid owning by the SSH user

**`mode: '0644'`**
- File permissions: owner read/write, group read, others read
- **Always quote octal:** `'0644'` not `0644`
- **Common modes:**
  - `'0644'` — Config files (readable by all, writable by owner)
  - `'0600'` — Secret files (readable only by owner)
  - `'0755'` — Executable scripts
  - `'0700'` — Private directories

**`backup: yes`**
- Creates a backup of the existing file before overwriting
- Format: `/etc/nginx/nginx.conf.20240115.143022.12345`
- **Why?** Safe rollback if new config is broken
- **Production tip:** Use `backup: yes` for critical config files

---

## 🏗️ templates/nginx.conf.j2

### What is a Jinja2 Template?
A text file with placeholders (`{{ variable }}`) and logic (`{% if %}`, `{% for %}`) that Ansible replaces with actual values from variables and facts.

### Full Template Breakdown:

```jinja2
user www-data;
worker_processes {{ nginx_worker_processes }};
```

**`{{ nginx_worker_processes }}`**
- Jinja2 variable substitution
- Replaced with the value of `nginx_worker_processes` from Ansible variables
- Sources (priority order):
  1. Extra vars (`-e nginx_worker_processes=4`)
  2. Host vars, group vars
  3. Playbook `vars:`
  4. Ansible facts (`ansible_processor_vcpus` for CPU count)

**Common pattern — auto-detect CPU count:**
```jinja2
worker_processes {{ ansible_processor_vcpus }};
```
`ansible_processor_vcpus` is an Ansible **fact** — automatically discovered from the host.

---

```jinja2
    listen {{ nginx_port }};
    server_name {{ server_name }};
    client_max_body_size {{ max_upload_size }};
```

- `{{ nginx_port }}` → e.g., `80` or `443`
- `{{ server_name }}` → e.g., `example.com` or `_` (catch-all)
- `{{ max_upload_size }}` → e.g., `10m`, `100m`

**Why use variables instead of hardcoding?**
- Same template for dev (port 8080), staging (port 80), production (port 443)
- Different server names per environment
- One template, many configurations

---

```jinja2
    {% if app_env == 'production' %}
    # Production-specific settings
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    {% endif %}
```

**`{% if %} ... {% endif %}`**
- Jinja2 conditional block
- Content only rendered when condition is `True`
- `app_env` comes from group_vars or inventory vars

**Why use conditionals in templates?**
- One template handles multiple environments
- Security headers only in production (not confusing in dev)
- Debug settings only in dev

**Other Jinja2 conditionals:**
```jinja2
{% if ssl_enabled | bool %}
    listen 443 ssl;
    ssl_certificate {{ ssl_cert_path }};
    ssl_certificate_key {{ ssl_key_path }};
{% else %}
    listen 80;
{% endif %}
```

---

```jinja2
    # Backend upstreams
    {% for backend in backend_servers %}
    # Upstream: {{ backend }}
    {% endfor %}
```

**`{% for %} ... {% endfor %}`**
- Jinja2 loop — iterates over a list
- `backend_servers` is a list variable, e.g.:
```yaml
backend_servers:
  - app1.internal:8080
  - app2.internal:8080
  - app3.internal:8080
```

**Practical upstream example:**
```jinja2
upstream backend_pool {
    {% for server in backend_servers %}
    server {{ server }} weight=1;
    {% endfor %}
}
```
→ Renders to:
```nginx
upstream backend_pool {
    server app1.internal:8080 weight=1;
    server app2.internal:8080 weight=1;
    server app3.internal:8080 weight=1;
}
```

---

## 📄 deploy-app-config.yml

### App Config Deployment with Loops

```yaml
---
- name: Deploy application configuration files
  hosts: webservers
  become: yes
  tasks:
    - name: Create config directory
      file:
        path: /etc/myapp
        state: directory
        owner: www-data
        mode: '0755'

    - name: Deploy config from template
      template:
        src: templates/app-config.yml.j2
        dest: /etc/myapp/config.yml
        owner: www-data
        group: www-data
        mode: '0640'
      notify: reload application
```

**`notify: reload application`**
- Triggers a handler named "reload application" if the task changes
- Handler runs **once** at the end of the play, even if notified multiple times
- More efficient than always restarting: only restarts if config actually changed

---

## 🔁 deploy-with-loops.yml

### Deploying Multiple Files with a Loop

```yaml
---
- name: Deploy multiple config files
  hosts: webservers
  become: yes
  vars:
    config_files:
      - src: templates/app.conf.j2
        dest: /etc/myapp/app.conf
        mode: '0644'
      - src: templates/db.conf.j2
        dest: /etc/myapp/db.conf
        mode: '0600'
  tasks:
    - name: Deploy config files
      template:
        src: "{{ item.src }}"
        dest: "{{ item.dest }}"
        mode: "{{ item.mode }}"
        owner: www-data
      loop: "{{ config_files }}"
      loop_control:
        label: "{{ item.dest }}"    # Cleaner output (shows dest, not full dict)
```

**`loop:`**
- Iterates the task over each item in the list
- `item` refers to the current element
- **More readable than:** One task per file

**`loop_control: label:`**
- Customizes what's shown in task output for each iteration
- Without it: shows the entire dict (cluttered)
- With it: shows just the meaningful part (file path)

---

## 🔀 deploy-conditional.yml

### Conditional Deployment Based on Facts

```yaml
---
- name: Deploy OS-specific configurations
  hosts: webservers
  become: yes
  tasks:
    - name: Deploy Ubuntu-specific config
      template:
        src: templates/ubuntu.conf.j2
        dest: /etc/myapp/platform.conf
      when: ansible_distribution == "Ubuntu"

    - name: Deploy Debian-specific config
      template:
        src: templates/debian.conf.j2
        dest: /etc/myapp/platform.conf
      when: ansible_distribution == "Debian"

    - name: Deploy config only for production
      template:
        src: templates/prod.conf.j2
        dest: /etc/myapp/prod.conf
      when:
        - app_env == "production"
        - ansible_memtotal_mb >= 4096    # At least 4GB RAM
```

**`when:` (single condition)**
- Task runs only if the condition is truthy
- Uses Ansible facts (`ansible_distribution`) or variables (`app_env`)

**`when:` (list = AND logic)**
- All conditions must be true for the task to run
- `ansible_memtotal_mb >= 4096` — fact-based condition (server has 4GB+ RAM)

**Common `when` patterns:**
```yaml
when: ansible_os_family == "Debian"          # Debian/Ubuntu
when: ansible_os_family == "RedHat"          # RHEL/CentOS
when: "'webservers' in group_names"          # Host is in webservers group
when: my_var is defined                       # Variable exists
when: my_var is not defined                   # Variable doesn't exist
when: my_var | bool                           # Variable is truthy
when: inventory_hostname == 'web1'           # Specific host only
```

---

## 📑 templates/app-config.yml.j2

### Application Config Template Pattern:

```jinja2
# Application Configuration
# Generated by Ansible on {{ ansible_date_time.date }}
# DO NOT EDIT MANUALLY

database:
  host: {{ db_host }}
  port: {{ db_port | default(5432) }}
  name: {{ db_name }}
  pool_size: {{ db_pool_size | default(10) }}

server:
  host: 0.0.0.0
  port: {{ app_port }}
  workers: {{ ansible_processor_vcpus * 2 }}   {# auto-scale workers to CPU count #}
  debug: {{ (app_env == 'development') | lower }}

logging:
  level: {{ 'DEBUG' if app_env == 'development' else 'INFO' }}
  file: /var/log/{{ app_name }}/app.log
```

**`{{ ansible_date_time.date }}`** — Ansible fact for current date
**`{{ value | default(5432) }}`** — Jinja2 filter: use `5432` if `db_port` not defined
**`{{ ansible_processor_vcpus * 2 }}`** — Math in templates
**`{# comment #}`** — Jinja2 comment (not in rendered output)
**`{{ (app_env == 'development') | lower }}`** — Inline conditional with filter

---

## 🔄 How Templates and Playbooks Work Together

### Complete Flow:

```
group_vars/webservers.yml          host_vars/web1.yml
(nginx_port: 80,                   (server_name: web1.example.com)
 app_env: production,
 backend_servers: [...])
         ↓
ansible-playbook deploy-nginx-config.yml
         ↓
Ansible gathers facts (ansible_processor_vcpus, etc.)
         ↓
Template engine merges: template + variables + facts
         ↓
Rendered nginx.conf (all {{ }} replaced with values)
         ↓
File uploaded to /etc/nginx/nginx.conf on remote host
         ↓
Handler notified → nginx reload (if file changed)
```

---

## 🎯 Best Practices

### 1. Use `validate` for Critical Config Files
```yaml
- template:
    src: templates/nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: reload nginx

handlers:
  - name: reload nginx
    command: nginx -t        # Validate first!
    register: nginx_test
    failed_when: nginx_test.rc != 0

  - name: reload nginx service
    service:
      name: nginx
      state: reloaded
    when: nginx_test.rc == 0
```

### 2. Provide Defaults in Templates
```jinja2
{# BAD - fails if variable undefined #}
workers {{ num_workers }};

{# GOOD - safe default #}
workers {{ num_workers | default(4) }};
```

### 3. Add Generated-by Comment to Templates
```jinja2
# ============================================================
# This file is managed by Ansible
# DO NOT EDIT MANUALLY - changes will be overwritten
# Template: templates/nginx.conf.j2
# Last deployed: {{ ansible_date_time.iso8601 }}
# ============================================================
```

### 4. Use `backup: yes` for Important Configs
```yaml
- template:
    src: templates/sshd_config.j2
    dest: /etc/ssh/sshd_config
    backup: yes        # Creates timestamped backup before overwriting
    validate: /usr/sbin/sshd -t -f %s   # Validate SSH config before applying
```

### 5. Separate Variables by Environment
```
group_vars/
├── all.yml           ← Shared defaults
├── webservers.yml    ← Web-specific vars
├── production/
│   └── vars.yml      ← Production overrides
└── staging/
    └── vars.yml      ← Staging overrides
```

---

## 🔍 Debugging Templates

```bash
# Test template rendering without deploying
ansible webservers -m template -a "src=templates/nginx.conf.j2 dest=/tmp/test-nginx.conf" --check --diff

# Show what the rendered template will look like
ansible-playbook deploy-nginx-config.yml --diff

# Check what variables are available
ansible webservers -m debug -a "var=vars"

# Check specific variable value
ansible webservers -m debug -a "var=nginx_port"

# Check ansible facts
ansible webservers -m setup -a "filter=ansible_processor*"
ansible webservers -m setup -a "filter=ansible_distribution*"

# Debug template with verbose output
ansible-playbook deploy-nginx-config.yml -vv
```

---

## 🎓 Key Takeaways

1. **`template` vs `copy`** — Use `template` when the file has `{{ variables }}`; use `copy` for static files
2. **`backup: yes`** — Always back up before overwriting critical config files
3. **`mode: '0644'`** — Always quote octal permissions to avoid YAML integer parsing issues
4. **`notify` + handlers** — Restart/reload services only when config actually changes (efficient)
5. **`when:` conditions** — Target specific hosts, environments, or OS families without separate playbooks
6. **`loop:` + dict items** — Deploy multiple files efficiently instead of repeating tasks
7. **Jinja2 `default()` filter** — Provide fallbacks for optional variables to prevent template failures
8. **`ansible_*` facts** — Auto-discovered host info (CPU count, OS, memory) usable directly in templates

---

*Jinja2 templates are the heart of Ansible's configuration management power. Master templates and you can manage configuration for hundreds of servers from a single source of truth.*
