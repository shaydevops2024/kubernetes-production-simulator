# YAML Files Explanation - Ansible Basics & Inventory

This guide explains every configuration file in this scenario, breaking down each field and providing context for why and how to write them.

---

## 📋 inventory/hosts.ini

### What is an Inventory File?
The inventory file tells Ansible **which hosts to manage** and **how to connect to them**. It's the foundation of every Ansible project.

### Full File Breakdown:

```ini
[local]
localhost ansible_connection=local
```
**What it is:** A host group named `local` containing one host: `localhost`
- `[local]` - Group header; groups logically organize hosts by role or location
- `localhost` - The host alias (used in Ansible commands and playbooks)
- `ansible_connection=local` - Don't SSH; run commands directly on this machine

**Why use a `local` group?**
- Useful for tasks that run on the Ansible control machine itself
- Testing and development without needing remote hosts
- Gathering local facts or deploying config locally

---

```ini
[webservers]
web1 ansible_host=localhost ansible_port=2221 ansible_user=root ansible_password=root ansible_ssh_common_args='-o StrictHostKeyChecking=no'
web2 ansible_host=localhost ansible_port=2222 ansible_user=root ansible_password=root ansible_ssh_common_args='-o StrictHostKeyChecking=no'
```
**What it is:** Two web server hosts mapped to Docker containers on different ports

- `web1` / `web2` - Logical host aliases used in playbooks (`hosts: webservers`)
- `ansible_host=localhost` - Actual IP/hostname to connect to (the Docker host)
- `ansible_port=2221` - SSH port (Docker containers mapped to different host ports)
- `ansible_user=root` - SSH login user
- `ansible_password=root` - SSH password (use Vault in production!)
- `ansible_ssh_common_args='-o StrictHostKeyChecking=no'` - Skip host key verification (dev only)

**Host variables priority (highest to lowest):**
1. Inventory inline variables (what you see above)
2. `host_vars/<hostname>/` directory
3. `group_vars/<groupname>/` directory
4. `group_vars/all/` directory

**Production alternatives:**
```ini
# SSH key authentication (preferred)
web1 ansible_host=192.168.1.10 ansible_user=ubuntu ansible_private_key_file=~/.ssh/prod_key

# Jump host / bastion
web1 ansible_host=10.0.1.10 ansible_ssh_common_args='-o ProxyJump=bastion.example.com'
```

---

```ini
[databases]
db1 ansible_host=localhost ansible_port=2223 ansible_user=root ansible_password=root ansible_ssh_common_args='-o StrictHostKeyChecking=no'
```
**What it is:** Database server group with one host
- Same structure as webservers but separate group for role separation
- Allows targeting `databases` group independently: `ansible-playbook -i inventory site.yml --limit databases`

---

```ini
[all:vars]
ansible_python_interpreter=/usr/bin/python3
```
**What it is:** Variables applied to ALL hosts in the inventory
- `[all:vars]` - Special group that applies to every host
- `ansible_python_interpreter=/usr/bin/python3` - Tells Ansible which Python to use on remote hosts

**Why specify Python interpreter?**
- Modern systems have both Python 2 and 3
- Ansible defaults may pick the wrong version
- Some modules require Python 3
- Avoids deprecation warnings

**Other common `[all:vars]`:**
```ini
[all:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_pipelining=True    # Faster SSH (fewer connections)
ansible_become=True            # Sudo by default
```

---

## ⚙️ ansible.cfg

### What is ansible.cfg?
The configuration file that controls Ansible's default behavior. Settings here override Ansible's built-in defaults without needing CLI flags.

### Full File Breakdown:

```ini
[defaults]
inventory = inventory/hosts.ini
```
**What it is:** Default inventory file path
- Ansible automatically uses this file unless `-i` flag is passed
- Path is relative to where you run `ansible-playbook`

**Why set this?**
- Avoid typing `-i inventory/hosts.ini` every time
- Enforces consistent inventory location across team

---

```ini
host_key_checking = False
```
**What it is:** Disable SSH host key verification
- `True` (default): Ansible refuses to connect to hosts not in `~/.ssh/known_hosts`
- `False`: Skip the check (connect to any host without verification)

**When to use `False`:**
- Development with Docker containers (IPs change constantly)
- CI/CD pipelines with ephemeral hosts
- Internal networks with controlled access

**Why `True` in production:**
- Prevents MITM (Man-in-the-Middle) attacks
- Ensures you're connecting to the right host
- Security best practice

---

```ini
deprecation_warnings = False
```
**What it is:** Suppress deprecation warning messages
- Older module syntax or features print warnings when this is `True`
- Set to `False` to keep output clean during learning

**When to set `True`:** When upgrading Ansible versions to identify what needs updating

---

### Other Useful ansible.cfg Settings:
```ini
[defaults]
inventory = inventory/hosts.ini
host_key_checking = False
deprecation_warnings = False

# Parallelism: run tasks on 10 hosts simultaneously (default: 5)
forks = 10

# Retry failed hosts (creates a .retry file)
retry_files_enabled = False

# Output formatting
stdout_callback = yaml      # Prettier output (yaml/json/minimal)
callback_whitelist = timer  # Show timing per task

# SSH connection settings
[ssh_connection]
pipelining = True           # Speeds up SSH by reducing connections
ssh_args = -o ControlMaster=auto -o ControlPersist=60s  # Connection reuse

# Privilege escalation
[privilege_escalation]
become = True
become_method = sudo
become_user = root
```

---

## 📁 inventory/group_vars/

### What are group_vars?
Variables files that automatically apply to all hosts in a named group. Instead of cluttering the inventory file, you put variables in separate YAML files.

### Structure:
```
inventory/
├── hosts.ini
├── group_vars/
│   ├── webservers.yml    ← applies to [webservers] group
│   └── all.yml           ← applies to ALL hosts
└── host_vars/
    └── db1.yml           ← applies only to db1
```

### Example group_vars/webservers.yml:
```yaml
http_port: 80
https_port: 443
app_env: production
max_workers: 4
```

**What each variable does:**
- `http_port: 80` - Variable used in templates/tasks: `listen {{ http_port }}`
- `https_port: 443` - Referenced when configuring SSL
- `app_env: production` - Used for conditional logic: `when: app_env == 'production'`
- `max_workers: 4` - Server-side configuration value

**Variable naming conventions:**
- Use `snake_case` (not camelCase)
- Prefix with role/component: `nginx_port`, `db_password`
- Avoid reserved names: `hosts`, `items`, `vars`

---

## 📁 inventory/host_vars/

### What are host_vars?
Variables that apply to a single specific host, overriding group_vars.

### Example host_vars/db1.yml:
```yaml
db_port: 5432
db_name: myapp_db
max_connections: 100
```

**Variable precedence (highest wins):**
```
extra vars (-e flag)          ← HIGHEST
task vars (vars: in task)
block vars
role vars (vars/main.yml)
host facts
host_vars/
group_vars/
group_vars/all
inventory vars
defaults (role defaults/)     ← LOWEST
```

---

## 🔄 How Everything Works Together

### Example Ad-Hoc Commands Using This Structure:

```bash
# Ping all hosts
ansible all -i inventory/hosts.ini -m ping

# Ping only webservers
ansible webservers -m ping

# Run command on databases
ansible databases -m command -a "df -h"

# Get facts from web1 specifically
ansible web1 -m setup

# Dry run a command
ansible webservers -m apt -a "name=nginx state=present" --check
```

### How Ansible Resolves Connections:

```
ansible webservers -m ping
         ↓
Reads ansible.cfg → finds inventory/hosts.ini
         ↓
Finds [webservers] group → web1, web2
         ↓
For web1:
  - Host: localhost
  - Port: 2221
  - User: root
  - Password: root (or SSH key)
  - Python: /usr/bin/python3
         ↓
SSH connection → Copies Python module → Executes → Returns JSON → Ansible parses result
```

---

## 🎯 Best Practices

### 1. Inventory Organization
```ini
# Group by function
[webservers]
web1
web2

[databases]
db1
db2

# Group by environment
[production:children]
webservers
databases

[staging]
staging-web
staging-db

# Common variables
[production:vars]
app_env=production
```

### 2. Never Store Passwords in Inventory
```ini
# BAD - plaintext password
web1 ansible_password=mysecret

# GOOD - Use SSH keys
web1 ansible_private_key_file=~/.ssh/web_key

# GOOD - Use Ansible Vault for passwords
# Store in group_vars/webservers/vault.yml (encrypted)
```

### 3. Use Meaningful Host Aliases
```ini
# BAD - hard to understand
192.168.1.10
192.168.1.11

# GOOD - descriptive aliases
web-prod-01 ansible_host=192.168.1.10
web-prod-02 ansible_host=192.168.1.11
```

### 4. Dynamic Inventory for Cloud
```bash
# Instead of static hosts.ini, use dynamic inventory
ansible-playbook site.yml -i aws_ec2.yml    # AWS
ansible-playbook site.yml -i gcp.yml        # GCP
ansible-playbook site.yml -i azure_rm.yml   # Azure
```

---

## 🔍 Debugging Commands Reference

```bash
# List all hosts in inventory
ansible-inventory --list

# Show inventory in graph format
ansible-inventory --graph

# Show what variables a host has
ansible-inventory --host web1

# Test connectivity to all hosts
ansible all -m ping

# Show what inventory Ansible sees
ansible-inventory -i inventory/hosts.ini --list

# Debug variables on a host
ansible web1 -m debug -a "var=hostvars[inventory_hostname]"

# Check which groups a host belongs to
ansible web1 -m debug -a "var=group_names"
```

---

## 🎓 Key Takeaways

1. **Inventory is the map** - Ansible needs to know which hosts to manage and how to reach them
2. **Groups organize hosts** - Group by role (webservers, databases) or environment (prod, staging)
3. **Variables cascade** - `host_vars` > `group_vars` > `all:vars` (most specific wins)
4. **ansible.cfg sets defaults** - Avoid repeating CLI flags by configuring defaults
5. **Never hardcode secrets** - Use SSH keys or Ansible Vault instead of plaintext passwords
6. **`host_key_checking=False` is dev-only** - Always enable in production
7. **`ansible_connection=local`** - For tasks on the control machine itself

---

*This inventory structure is the foundation of all Ansible automation. A well-organized inventory makes targeting specific hosts, groups, and environments effortless and scalable.*
