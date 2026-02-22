# YAML Files Explanation - User and Permission Management

This guide explains each playbook file in detail, breaking down every field and providing context for why and how to write them.

---

## 👥 create-users.yml

### What is this Playbook?
Creates Linux groups and users with specific UIDs, shells, and home directories.

### Full File Breakdown:

```yaml
---
- name: Create users and groups
  hosts: servers
  become: yes
  tasks:
    - name: Create developers group
      group:
        name: developers
        gid: 3000
        state: present
```

**`group:` module**
- Manages Linux groups (`/etc/group`)
- Creates, modifies, or removes groups

**`name: developers`**
- Group name as it appears in `/etc/group`
- Used in `user` module to assign group membership

**`gid: 3000`**
- Group ID (GID) — unique numeric identifier for the group
- If omitted, system auto-assigns next available GID
- **Why pin GID?** Consistency across servers — same GID on all nodes ensures file permission consistency when sharing files via NFS
- **Convention:** UIDs/GIDs 1000-1999 for system users, 2000+ for application users

**`state: present`**
- Create group if it doesn't exist (idempotent)
- `absent` would delete the group

---

```yaml
    - name: Create devuser
      user:
        name: devuser
        uid: 2001
        group: developers
        shell: /bin/bash
        create_home: yes
        state: present
```

**`user:` module**
- Manages Linux user accounts (`/etc/passwd`, `/etc/shadow`)
- Handles home directory, shell, group membership, SSH keys

**`name: devuser`**
- Username for the account
- Used in `sudo`, SSH, and file ownership

**`uid: 2001`**
- User ID — numeric identifier
- **Why pin UID?** Same reason as GID — consistency across servers for file ownership

**`group: developers`**
- Primary group for the user
- Must exist before creating the user (task order matters!)
- Affects default file permissions for files the user creates

**`shell: /bin/bash`**
- Login shell for the user
- **Options:**
  - `/bin/bash` - Full interactive shell (most users)
  - `/bin/sh` - POSIX shell, minimal
  - `/usr/sbin/nologin` - Prevents interactive login (service accounts)
  - `/bin/false` - Strict no-login (even more restrictive)

**`create_home: yes`**
- Create `/home/devuser/` directory
- Copies skeleton files from `/etc/skel/` (.bashrc, .profile)
- Set to `no` for service accounts that don't need a home directory

**`state: present`**
- Ensure user exists
- Does NOT modify existing user (use `state: present` + other params to update)
- `absent` removes the user

---

```yaml
    - name: Create appuser
      user:
        name: appuser
        uid: 2003
        shell: /bin/bash
        create_home: yes
        state: present
```

**Notice:** `appuser` has no `group:` set
- User gets a private group created automatically (same name as user)
- This is the Linux default when no primary group specified
- Use when user doesn't belong to a shared group

---

## 🔑 deploy-ssh-keys.yml

### What is this Playbook?
Deploys SSH public keys for users, enabling passwordless authentication.

### Full File Breakdown:

```yaml
---
- name: Deploy SSH keys for passwordless authentication
  hosts: servers
  become: yes
  tasks:
    - name: Add SSH key for devuser
      authorized_key:
        user: devuser
        key: "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDemokey123 devuser@example.com"
        state: present
```

**`authorized_key:` module**
- Manages `~/.ssh/authorized_keys` file
- Adds or removes SSH public keys for a user

**`user: devuser`**
- The Linux user whose `~/.ssh/authorized_keys` to modify
- Ansible resolves to `/home/devuser/.ssh/authorized_keys`

**`key: "ssh-rsa AAAA..."`**
- The SSH public key content (from `~/.ssh/id_rsa.pub` or similar)
- **In production:** Read from a file or variable, never hardcode:
```yaml
key: "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"
# or
key: "{{ lookup('file', '/path/to/devuser_key.pub') }}"
```

**`state: present`**
- Add the key if not present (idempotent — won't duplicate)
- `absent` removes the specific key

**Security implications:**
- The key grants SSH access without password
- Only deploy keys you trust and control
- Rotate keys regularly

**Multiple keys for one user:**
```yaml
- name: Add multiple SSH keys for devuser
  authorized_key:
    user: devuser
    key: "{{ item }}"
    state: present
  loop:
    - "ssh-rsa AAAA...key1 laptop"
    - "ssh-rsa AAAA...key2 workstation"
    - "ssh-rsa AAAA...key3 ci-system"
```

---

## 📝 configure-sudo.yml

### What is this Playbook?
Configures sudo access for specific users (referenced by the scenario).

### Sudo Configuration Pattern:

```yaml
---
- name: Configure sudo access
  hosts: servers
  become: yes
  tasks:
    - name: Allow developers group to use sudo
      community.general.sudoers:
        name: developers-sudo
        group: developers
        commands: ALL
        state: present

    - name: Allow dbadmin passwordless sudo for pg commands only
      community.general.sudoers:
        name: dbadmin-pg
        user: dbadmin
        commands:
          - /usr/bin/pg_dump
          - /usr/bin/pg_restore
          - /usr/bin/psql
        nopassword: yes
        state: present
```

**`community.general.sudoers:` module**
- Manages `/etc/sudoers.d/` files safely
- Validates syntax before writing (prevents lockouts)

**`name:` (sudoers)**
- Filename in `/etc/sudoers.d/` — keep it descriptive
- `developers-sudo` → `/etc/sudoers.d/developers-sudo`

**`group: developers`**
- Apply rule to the entire group
- Equivalent to `%developers ALL=(ALL) ALL` in sudoers

**`commands: ALL`**
- Allow all commands (full sudo access)
- **Restrict for security:** `commands: /usr/bin/systemctl, /usr/bin/journalctl`

**`nopassword: yes`**
- No password prompt required (NOPASSWD in sudoers)
- **Use case:** Automation/service accounts, CI/CD
- **Avoid:** For human interactive users (security risk)

**Using `lineinfile` as alternative:**
```yaml
- name: Add sudo rule for devuser
  lineinfile:
    path: /etc/sudoers
    line: "devuser ALL=(ALL) NOPASSWD: /usr/bin/systemctl"
    validate: /usr/sbin/visudo -cf %s    # Validate before writing!
    state: present
```

---

## 🖥️ deploy-bashrc.yml

### What is this Playbook?
Deploys custom shell configuration to users.

### Shell Configuration Pattern:

```yaml
---
- name: Deploy custom .bashrc for devuser
  hosts: servers
  become: yes
  tasks:
    - name: Deploy .bashrc from template
      template:
        src: templates/devuser_bashrc.j2
        dest: /home/devuser/.bashrc
        owner: devuser
        group: developers
        mode: '0644'

    - name: Ensure .ssh directory exists
      file:
        path: /home/devuser/.ssh
        state: directory
        owner: devuser
        group: devuser
        mode: '0700'           # SSH requires strict permissions
```

**`template:` module**
- Renders Jinja2 template → deploys to remote
- Variables in the template are replaced with actual values

**`file:` module**
- Creates directories and manages file/directory properties
- `state: directory` creates the path if it doesn't exist

**`mode: '0700'`**
- Octal file permissions (owner: rwx, group: ---, others: ---)
- SSH is picky: `~/.ssh` must be `0700`, `authorized_keys` must be `0600`
- Always quote octal modes: `'0700'` not `0700` (YAML parses unquoted as integer)

**`owner: devuser`** + **`group: devuser`**
- Ensure the user owns their own files
- Important when `become: yes` (tasks run as root by default)

---

## 🔄 How User Management Works End-to-End

### Execution Order Matters!

```
1. Create groups first  (group module)
         ↓
2. Create users         (user module — primary group must exist)
         ↓
3. Create .ssh dir      (file module — user must exist)
         ↓
4. Deploy SSH keys      (authorized_key — .ssh dir must exist)
         ↓
5. Configure sudo       (sudoers module)
         ↓
6. Deploy shell configs (template module)
```

### Example Combined Playbook:

```yaml
---
- name: Complete user setup
  hosts: servers
  become: yes
  tasks:
    # Step 1: Groups
    - name: Create groups
      group:
        name: "{{ item.name }}"
        gid: "{{ item.gid }}"
        state: present
      loop:
        - { name: developers, gid: 3000 }
        - { name: dbadmins, gid: 3001 }

    # Step 2: Users
    - name: Create users
      user:
        name: "{{ item.name }}"
        uid: "{{ item.uid }}"
        group: "{{ item.group }}"
        shell: /bin/bash
        create_home: yes
        state: present
      loop:
        - { name: devuser, uid: 2001, group: developers }
        - { name: dbadmin, uid: 2002, group: dbadmins }

    # Step 3: SSH directories
    - name: Create .ssh directories
      file:
        path: "/home/{{ item }}/.ssh"
        state: directory
        owner: "{{ item }}"
        group: "{{ item }}"
        mode: '0700'
      loop:
        - devuser
        - dbadmin

    # Step 4: SSH keys
    - name: Deploy SSH keys
      authorized_key:
        user: "{{ item.user }}"
        key: "{{ lookup('file', item.keyfile) }}"
        state: present
      loop:
        - { user: devuser, keyfile: keys/devuser.pub }
        - { user: dbadmin, keyfile: keys/dbadmin.pub }
```

---

## 🎯 Best Practices

### 1. Always Pin UIDs and GIDs
```yaml
# GOOD - Consistent across servers (critical for NFS/shared storage)
user:
  name: appuser
  uid: 2001

# RISKY - Different servers may assign different UIDs
user:
  name: appuser
  # No uid specified
```

### 2. Use Variables for User Definitions
```yaml
# In group_vars/all.yml:
users:
  - name: devuser
    uid: 2001
    group: developers
    shell: /bin/bash
    ssh_key: "{{ lookup('file', 'keys/devuser.pub') }}"

# In playbook:
- user:
    name: "{{ item.name }}"
    uid: "{{ item.uid }}"
  loop: "{{ users }}"
```

### 3. Service Accounts Should Use `/usr/sbin/nologin`
```yaml
# Service account - can't login interactively
- user:
    name: nginx
    shell: /usr/sbin/nologin
    create_home: no
    system: yes      # Lower UID range, no home dir by default
```

### 4. Use `validate` When Editing sudoers
```yaml
# ALWAYS validate sudoers changes to prevent lockouts
- lineinfile:
    path: /etc/sudoers
    line: "devuser ALL=(ALL) ALL"
    validate: /usr/sbin/visudo -cf %s   # If this fails, file is NOT written
```

### 5. Remove Users Completely When Offboarding
```yaml
- name: Remove departed employee
  user:
    name: exemployee
    state: absent
    remove: yes      # Also removes home directory and mail spool
    force: yes       # Remove even if user is logged in
```

---

## 🔍 Debugging Commands

```bash
# Check if user exists on remote hosts
ansible servers -m command -a "id devuser"

# List all users with UID >= 1000 (human users)
ansible servers -m command -a "awk -F: '$3>=1000' /etc/passwd"

# Verify SSH key is deployed
ansible servers -m command -a "cat /home/devuser/.ssh/authorized_keys"

# Check sudo access
ansible servers -m command -a "sudo -l -U devuser"

# Verify group membership
ansible servers -m command -a "groups devuser"

# Test SSH key authentication
ssh -i ~/.ssh/id_rsa devuser@server1 "echo 'SSH key works'"

# Debug user facts
ansible servers -m user -a "name=devuser state=present" --check
```

---

## 🎓 Key Takeaways

1. **`group` before `user`** — primary group must exist before creating user
2. **Pin UIDs/GIDs** — critical for consistency across multiple servers, especially with shared storage
3. **`authorized_key`** manages SSH keys idempotently — safe to run multiple times
4. **`mode: '0700'`** for `.ssh/`, `mode: '0600'` for `authorized_keys` — SSH enforces strict permissions
5. **`/usr/sbin/nologin`** for service accounts — prevents interactive login while allowing process execution
6. **Always `validate` sudoers changes** — a syntax error can lock you out of sudo
7. **`become: yes` is required** — user/group management needs root privileges

---

*User and permission management is foundational to Linux security. Automating it with Ansible ensures consistency, auditability, and repeatability across your entire infrastructure.*
