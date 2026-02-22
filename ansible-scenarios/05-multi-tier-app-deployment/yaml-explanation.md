# YAML Files Explanation - Multi-Tier Application Deployment

This guide explains the role-based structure and each playbook file in detail, breaking down every field and providing context for why and how to write them.

---

## 🎭 site.yml — The Master Playbook

### What is site.yml?
The top-level playbook that orchestrates the entire deployment across all tiers. It references roles instead of defining tasks inline.

### Full File Breakdown:

```yaml
---
- name: Deploy database tier
  hosts: database
  become: yes
  tags: database
  roles:
    - database
```

**`- name: Deploy database tier`**
- Each `- name:` block is a separate **play**
- site.yml has 3 plays: one per tier
- Plays run in order: database → backend → frontend

**`hosts: database`**
- Targets the `database` group from inventory
- Only hosts in this group run this play
- Tier separation: database tasks only run on database hosts

**`become: yes`**
- Apply privilege escalation to all tasks in this play
- Can also be set per-role or per-task for granular control

**`tags: database`**
- Allows targeting just this play: `ansible-playbook site.yml --tags database`
- **Why tags?**
  - Deploy only one tier: `--tags frontend`
  - Skip a tier: `--skip-tags database`
  - Speed up development: only redeploy the tier you changed

**`roles:`**
- List of roles to apply to the hosts in this play
- Each role is a directory with a defined structure
- Roles encapsulate all logic (tasks, templates, handlers, vars) for one component

---

```yaml
- name: Deploy backend tier
  hosts: backend
  become: yes
  tags: backend
  roles:
    - backend
```

**Why separate play for backend (not combined with database)?**
- Different hosts: backend servers ≠ database servers
- Different privileges: may need different `become_user`
- Independent failure domains: database failure doesn't stop backend play from running on its hosts
- Cleaner separation of concerns

---

```yaml
- name: Deploy frontend tier
  hosts: frontend
  become: yes
  tags: frontend
  roles:
    - frontend
```

**Play ordering — why database first?**
- Backend needs database to exist (connection strings, schema)
- Frontend needs backend to exist (API endpoints, health checks)
- Ansible processes plays sequentially, so order matters

---

## 📁 roles/ — The Role Structure

### What is an Ansible Role?
A standardized directory structure that bundles related tasks, templates, variables, and handlers for one component. Roles make playbooks reusable and organized.

### Standard Role Directory Layout:
```
roles/
├── database/
│   ├── tasks/
│   │   └── main.yml       ← Entry point (required)
│   ├── templates/
│   │   └── pg_hba.conf.j2
│   ├── handlers/
│   │   └── main.yml       ← Handlers (restart services)
│   ├── vars/
│   │   └── main.yml       ← Role variables (high priority)
│   ├── defaults/
│   │   └── main.yml       ← Default variables (lowest priority)
│   └── meta/
│       └── main.yml       ← Role metadata, dependencies
├── backend/
│   ├── tasks/
│   │   └── main.yml
│   ├── templates/
│   │   └── app.conf.j2
│   ├── handlers/
│   │   └── main.yml
│   ├── vars/
│   │   └── main.yml
│   └── meta/
│       └── main.yml
└── frontend/
    └── ...
```

**Key rule:** Only `tasks/main.yml` is required. All other directories are optional.

---

## 🗄️ roles/database/tasks/main.yml

### Database Role Task Flow:

```yaml
---
- name: Install PostgreSQL
  apt:
    name:
      - postgresql
      - postgresql-client
      - python3-psycopg2    # Required for Ansible PostgreSQL modules
    state: present
    update_cache: yes

- name: Ensure PostgreSQL is running
  service:
    name: postgresql
    state: started
    enabled: yes

- name: Create application database
  community.postgresql.postgresql_db:
    name: "{{ db_name }}"
    encoding: UTF-8
    lc_collate: en_US.UTF-8
    lc_ctype: en_US.UTF-8
    state: present
  become_user: postgres    # PostgreSQL commands run as postgres user

- name: Create application database user
  community.postgresql.postgresql_user:
    name: "{{ db_user }}"
    password: "{{ db_password }}"   # Should come from Vault
    db: "{{ db_name }}"
    priv: "ALL"
    state: present
  become_user: postgres

- name: Deploy pg_hba.conf
  template:
    src: pg_hba.conf.j2
    dest: /etc/postgresql/14/main/pg_hba.conf
    owner: postgres
    group: postgres
    mode: '0640'
  notify: restart postgresql
```

**`python3-psycopg2`**
- Python library required for Ansible's PostgreSQL modules
- Must be installed on the remote host, not the control machine

**`become_user: postgres`**
- Run specific tasks as the `postgres` OS user
- PostgreSQL requires its commands run as the `postgres` user
- Different from `become: yes` (which escalates to root)

**`community.postgresql.postgresql_db:`**
- Ansible collection module (requires `community.general` or `community.postgresql`)
- Creates databases without manual `psql` commands
- Idempotent: won't recreate existing database

**`notify: restart postgresql`**
- Triggers handler if pg_hba.conf changes
- PostgreSQL needs restart (not just reload) for auth changes

---

## 🐍 roles/backend/tasks/main.yml

### Backend Role Task Flow:

```yaml
---
- name: Install Python and dependencies
  apt:
    name:
      - python3
      - python3-pip
      - python3-venv
    state: present

- name: Create application directory
  file:
    path: /opt/myapp
    state: directory
    owner: www-data
    group: www-data
    mode: '0755'

- name: Deploy application code
  copy:
    src: app/
    dest: /opt/myapp/
    owner: www-data
    group: www-data

- name: Install Python requirements
  pip:
    requirements: /opt/myapp/requirements.txt
    virtualenv: /opt/myapp/venv
    virtualenv_command: python3 -m venv

- name: Deploy application configuration
  template:
    src: app.conf.j2
    dest: /opt/myapp/config.py
    owner: www-data
    mode: '0640'
  notify: restart backend

- name: Deploy systemd service file
  template:
    src: myapp.service.j2
    dest: /etc/systemd/system/myapp.service
    mode: '0644'
  notify:
    - reload systemd
    - restart backend

- name: Start and enable backend service
  service:
    name: myapp
    state: started
    enabled: yes
```

**`pip:` module**
- Installs Python packages from pip
- `virtualenv:` creates/uses a virtual environment (isolated Python environment)
- `virtualenv_command:` specifies how to create the venv

**Multiple `notify:` handlers**
- Notify multiple handlers when a task changes
- Handlers run in the order they're defined, not the order they're notified

**`copy:` with `src: app/`**
- Copies entire directory from control machine to remote
- Trailing `/` copies directory *contents* (not the directory itself)

---

## 🌐 roles/frontend/tasks/main.yml

### Frontend Role Task Flow:

```yaml
---
- name: Install nginx
  apt:
    name: nginx
    state: present

- name: Remove default nginx site
  file:
    path: /etc/nginx/sites-enabled/default
    state: absent
  notify: reload nginx

- name: Deploy nginx virtual host config
  template:
    src: vhost.conf.j2
    dest: /etc/nginx/sites-available/myapp
    mode: '0644'
  notify: reload nginx

- name: Enable site
  file:
    src: /etc/nginx/sites-available/myapp
    dest: /etc/nginx/sites-enabled/myapp
    state: link            # Creates symlink
  notify: reload nginx

- name: Deploy static files
  copy:
    src: static/
    dest: /var/www/html/
    owner: www-data
    group: www-data

- name: Ensure nginx is started
  service:
    name: nginx
    state: started
    enabled: yes
```

**`state: absent` (file module)**
- Removes the file if it exists
- Used here to remove nginx's default site that would conflict

**`state: link` (file module)**
- Creates a symbolic link
- `src:` = the actual file, `dest:` = the symlink path
- Standard nginx pattern: config in `sites-available/`, enabled via symlink in `sites-enabled/`

---

## 📋 roles/*/handlers/main.yml

### Handlers — Triggered Service Management:

```yaml
---
# database handlers
- name: restart postgresql
  service:
    name: postgresql
    state: restarted

# backend handlers
- name: reload systemd
  systemd:
    daemon_reload: yes

- name: restart backend
  service:
    name: myapp
    state: restarted

# frontend handlers
- name: reload nginx
  service:
    name: nginx
    state: reloaded
```

**Why `reloaded` for nginx but `restarted` for backend?**
- `nginx -s reload` — nginx supports graceful config reload (no downtime)
- Most web apps need full restart to pick up config changes (no downtime-free reload)

**Handler execution rules:**
1. Handlers run **after all tasks complete** (end of play)
2. Each handler runs **only once** regardless of how many times it's notified
3. Handlers run in the **order defined**, not the order notified
4. Only run if the **notifying task reported `changed`**

---

## 🔧 roles/*/vars/main.yml vs defaults/main.yml

### Variable Priority Difference:

```yaml
# roles/database/defaults/main.yml (LOWEST priority)
db_port: 5432
db_name: myapp
db_user: myapp_user
db_pool_size: 10

# roles/database/vars/main.yml (HIGH priority — overrides group_vars)
postgresql_version: "14"
postgresql_data_dir: "/var/lib/postgresql/14/main"
```

**`defaults/main.yml`** — Lowest priority variables
- Meant to be overridden by users of the role
- Good for sensible defaults: `db_port: 5432`
- **Use for:** Values that users commonly want to customize

**`vars/main.yml`** — High priority variables
- Overrides group_vars and host_vars (but not extra vars)
- Meant for role-internal constants
- **Use for:** Internal values users shouldn't normally change

**Priority (high → low):**
```
extra vars (-e)      ← Highest
task vars
host_vars/
group_vars/
play vars
role vars/main.yml
role defaults/main.yml  ← Lowest
```

---

## 🗂️ roles/*/meta/main.yml

### Role Dependencies:

```yaml
---
galaxy_info:
  role_name: database
  author: your-team
  description: Deploys PostgreSQL database
  min_ansible_version: "2.9"

dependencies:
  - role: common          # Always install common role first
  - role: firewall
    vars:
      firewall_allowed_ports:
        - 5432
```

**`dependencies:`**
- Roles that must run before this role
- Ansible automatically runs dependency roles first
- **Prevents:** Database role failing because OS tuning (common role) wasn't applied

**`common` role pattern:**
- A role run on all hosts for baseline setup
- Installs monitoring agents, sets NTP, configures logging, etc.
- Referenced as a dependency by all other roles

---

## 🔄 How Multi-Tier Deployment Works

### Complete Deployment Flow:

```
ansible-playbook site.yml
         ↓
PLAY 1: Deploy database tier
  → hosts: database (db1)
  → Role: database
    ├── Install PostgreSQL
    ├── Create database + user
    └── Deploy pg_hba.conf → handler: restart postgresql
         ↓
PLAY 2: Deploy backend tier
  → hosts: backend (app1, app2)
  → Role: backend
    ├── Install Python + pip
    ├── Deploy app code
    ├── Install requirements
    ├── Deploy config (uses db_host from vars) → handler: restart backend
    └── Create systemd service → handler: reload systemd
         ↓
PLAY 3: Deploy frontend tier
  → hosts: frontend (web1, web2)
  → Role: frontend
    ├── Install nginx
    ├── Deploy vhost config → handler: reload nginx
    ├── Enable site (symlink)
    └── Deploy static files
```

### Selective Deployment with Tags:

```bash
# Deploy only frontend
ansible-playbook site.yml --tags frontend

# Deploy all except database (for quick code updates)
ansible-playbook site.yml --skip-tags database

# List all available tags without running
ansible-playbook site.yml --list-tags

# Deploy to specific host only
ansible-playbook site.yml --limit web1
```

---

## 🎯 Best Practices

### 1. Keep Roles Focused and Reusable
```
# GOOD - One role, one responsibility
roles/
├── postgresql/    ← Only DB setup
├── flask/         ← Only Flask app setup
└── nginx/         ← Only nginx config

# BAD - Monolithic role
roles/
└── everything/    ← DB + App + nginx all mixed
```

### 2. Use Role Defaults for Customizable Values
```yaml
# defaults/main.yml - Safe to override
db_port: 5432
db_max_connections: 100

# vars/main.yml - Internal constants
postgresql_config_dir: /etc/postgresql/14/main
```

### 3. Always Notify Handlers, Don't Always Restart
```yaml
# GOOD - Only restart if config changed
- template:
    src: app.conf.j2
    dest: /etc/myapp/config.yml
  notify: restart app

# BAD - Restarts every run (causes downtime unnecessarily)
- service:
    name: myapp
    state: restarted
```

### 4. Use Tags for Selective Deployment
```yaml
- name: Deploy database tier
  tags:
    - database
    - db          # Multiple tags per play/task
```

### 5. Validate Before Deploying
```yaml
- name: Validate nginx config
  command: nginx -t -c /etc/nginx/nginx.conf
  changed_when: false   # This is a check, not a change

- name: Deploy nginx config
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: reload nginx
```

---

## 🔍 Debugging Commands

```bash
# Run in check mode (dry run - no changes)
ansible-playbook site.yml --check

# Show what would change (diff mode)
ansible-playbook site.yml --diff

# List all tasks without running them
ansible-playbook site.yml --list-tasks

# Run only specific tags
ansible-playbook site.yml --tags database

# Verbose output
ansible-playbook site.yml -v    # Basic
ansible-playbook site.yml -vvv  # Full debug

# Step through tasks one by one
ansible-playbook site.yml --step

# Check role syntax
ansible-playbook site.yml --syntax-check
```

---

## 🎓 Key Takeaways

1. **Roles = organized, reusable task bundles** — one role per component
2. **`site.yml` orchestrates plays** — database → backend → frontend order matters
3. **Tags enable selective deployment** — `--tags frontend` redeploys only frontend
4. **`defaults/` vs `vars/`** — defaults are meant to be overridden; vars are internal
5. **Handlers are efficient** — run once after all tasks, only if something changed
6. **`become_user: postgres`** — switch to specific user for certain tasks (not just root)
7. **Role `meta/` for dependencies** — declare that backend requires database role to run first
8. **`--check` + `--diff`** — validate what would happen before making changes

---

*Multi-tier application deployment with Ansible roles is the industry standard for managing complex application stacks. Well-structured roles are reusable across projects and form the foundation of scalable infrastructure automation.*
