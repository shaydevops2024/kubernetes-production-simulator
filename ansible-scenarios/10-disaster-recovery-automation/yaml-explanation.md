# YAML Files Explanation - Disaster Recovery Automation with Ansible

This guide explains the playbook patterns for automated backups, restore procedures, backup validation, and disaster recovery runbooks.

---

## 💾 What is Disaster Recovery Automation?

Disaster Recovery (DR) automation ensures you can recover from data loss, server failure, or corruption quickly and reliably. Ansible automates the backup/restore cycle, turning a manual emergency procedure into a tested, repeatable process.

**Key DR concepts:**
- **RPO (Recovery Point Objective)** — Maximum acceptable data loss (e.g., "last 1 hour of data")
- **RTO (Recovery Time Objective)** — Maximum acceptable downtime (e.g., "back up within 30 minutes")
- **Backup rotation** — Keep N backups, delete old ones (storage management)
- **Restore testing** — Regularly verify backups are actually restorable

---

## 📋 backup-database.yml — Automated PostgreSQL Backups

### Full File Breakdown:

```yaml
---
- name: Automated database backup
  hosts: databases
  become: yes
  vars:
    backup_dir: /var/backups/postgresql
    backup_retention_days: 30
    db_name: "{{ vault_db_name }}"
    backup_timestamp: "{{ ansible_date_time.date }}_{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}"

  tasks:
    - name: Ensure backup directory exists
      file:
        path: "{{ backup_dir }}"
        state: directory
        owner: postgres
        group: postgres
        mode: '0750'

    - name: Run pg_dump to create backup
      command: >
        pg_dump
        --format=custom
        --compress=9
        --file={{ backup_dir }}/{{ db_name }}_{{ backup_timestamp }}.dump
        {{ db_name }}
      become_user: postgres
      register: backup_result
      failed_when: backup_result.rc != 0

    - name: Verify backup file was created
      stat:
        path: "{{ backup_dir }}/{{ db_name }}_{{ backup_timestamp }}.dump"
      register: backup_file

    - name: Assert backup is not empty
      assert:
        that:
          - backup_file.stat.exists
          - backup_file.stat.size > 0
        fail_msg: "Backup file is missing or empty!"

    - name: Set backup file permissions
      file:
        path: "{{ backup_dir }}/{{ db_name }}_{{ backup_timestamp }}.dump"
        owner: postgres
        group: postgres
        mode: '0640'

    - name: Remove backups older than {{ backup_retention_days }} days
      find:
        paths: "{{ backup_dir }}"
        patterns: "*.dump"
        age: "{{ backup_retention_days }}d"
        age_stamp: mtime
      register: old_backups

    - name: Delete old backup files
      file:
        path: "{{ item.path }}"
        state: absent
      loop: "{{ old_backups.files }}"

    - name: Record backup metadata
      copy:
        content: |
          backup_timestamp: {{ backup_timestamp }}
          database: {{ db_name }}
          file: {{ db_name }}_{{ backup_timestamp }}.dump
          size: {{ backup_file.stat.size }}
          host: {{ inventory_hostname }}
          ansible_run: {{ ansible_date_time.iso8601 }}
        dest: "{{ backup_dir }}/latest-backup.yml"
```

**`ansible_date_time.date`** — Ansible fact: current date (`2024-01-15`)
**`ansible_date_time.hour`** — Current hour (`14`)
**`ansible_date_time.minute`** — Current minute (`30`)

Combined: `backup_timestamp: "2024-01-15_1430"` → Sortable, unique backup names

**`command: >` (folded scalar)**
- The `>` means: fold newlines into spaces
- Allows splitting long commands across multiple lines for readability
- Rendered as a single line: `pg_dump --format=custom --compress=9 --file=...`

**`--format=custom`** — Binary format (faster, compressed, allows selective restore)
**`--compress=9`** — Maximum compression (gzip level 9)

**`stat:` module**
- Gets file information on remote host (size, permissions, timestamps, etc.)
- Returns `stat` dict with: `exists`, `size`, `mode`, `owner`, `mtime`, etc.

**`find:` + `age:` + `age_stamp: mtime`**
- Find files older than N days based on modification time
- `age: "30d"` — Files older than 30 days
- Returns list of matching files in `register`

---

## 📋 backup-to-git.yml — Configuration Backup to Git

```yaml
---
- name: Backup configurations to Git
  hosts: all_servers
  become: yes
  vars:
    backup_repo: /opt/config-backup
    git_repo_url: "{{ vault_git_backup_repo }}"
    config_paths:
      - /etc/nginx
      - /etc/prometheus
      - /etc/postgresql
      - /etc/ssh/sshd_config
      - /etc/crontab

  tasks:
    - name: Clone or update backup repository
      git:
        repo: "{{ git_repo_url }}"
        dest: "{{ backup_repo }}"
        update: yes
        force: yes
      delegate_to: localhost    # Git operations on control machine

    - name: Create host directory in backup repo
      file:
        path: "{{ backup_repo }}/{{ inventory_hostname }}"
        state: directory
      delegate_to: localhost

    - name: Fetch configuration files from remote host
      fetch:
        src: "{{ item }}"
        dest: "{{ backup_repo }}/{{ inventory_hostname }}/"
        flat: no                # Preserve directory structure
        fail_on_missing: no     # Don't fail if file doesn't exist
      loop: "{{ config_paths }}"

    - name: Commit changes to Git
      shell: |
        cd {{ backup_repo }}
        git config user.email "ansible@example.com"
        git config user.name "Ansible Automation"
        git add -A
        git diff --cached --quiet || git commit -m "Auto-backup {{ inventory_hostname }} - {{ ansible_date_time.iso8601 }}"
      delegate_to: localhost
      register: git_commit
      changed_when: "'nothing to commit' not in git_commit.stdout"

    - name: Push backup to remote repository
      command: git push origin main
      args:
        chdir: "{{ backup_repo }}"
      delegate_to: localhost
      when: git_commit.changed
```

**`fetch:` module**
- Copies files FROM remote host TO control machine
- Opposite of `copy:` (which goes control → remote)
- `flat: no` — Preserves the full path structure in destination

**`flat: no`** vs `flat: yes`:
```
flat: no  → dest/inventory_hostname/etc/nginx/nginx.conf
flat: yes → dest/nginx.conf (filename only, loses path info)
```

**`delegate_to: localhost`** for Git operations
- All `git` commands run on the control machine (where the repo is cloned)
- Remote file paths still refer to the current remote host being iterated

**`changed_when:` for shell/command**
- `shell:` is never idempotent by default (always reports `changed`)
- `changed_when: "'nothing to commit' not in git_commit.stdout"` — Only `changed` if we actually committed
- Prevents false `changed` reports

---

## 📋 restore-database.yml — Restore Procedures

```yaml
---
- name: Restore database from backup
  hosts: databases
  become: yes
  vars:
    restore_backup: ""            # Must be provided: --extra-vars "restore_backup=mydb_2024-01-15.dump"
    backup_dir: /var/backups/postgresql

  pre_tasks:
    - name: Validate restore_backup is specified
      fail:
        msg: "You must specify the backup file: -e restore_backup=<filename>"
      when: restore_backup == ""

    - name: Check backup file exists
      stat:
        path: "{{ backup_dir }}/{{ restore_backup }}"
      register: backup_stat

    - name: Fail if backup file not found
      fail:
        msg: "Backup file not found: {{ backup_dir }}/{{ restore_backup }}"
      when: not backup_stat.stat.exists

    - name: Confirm restore (interactive prompt)
      pause:
        prompt: |
          WARNING: This will DROP and recreate database '{{ db_name }}'!
          Backup file: {{ restore_backup }}
          Type 'yes' to proceed, anything else to cancel
      register: confirm_restore

    - name: Abort if not confirmed
      fail:
        msg: "Restore cancelled by user"
      when: confirm_restore.user_input != 'yes'

  tasks:
    - name: Stop application before restore
      service:
        name: myapp
        state: stopped
      delegate_to: "{{ groups['webservers'] | first }}"

    - name: Drop existing database
      community.postgresql.postgresql_db:
        name: "{{ db_name }}"
        state: absent
      become_user: postgres

    - name: Create fresh database
      community.postgresql.postgresql_db:
        name: "{{ db_name }}"
        encoding: UTF-8
        state: present
      become_user: postgres

    - name: Restore from backup
      command: >
        pg_restore
        --no-owner
        --no-acl
        --jobs=4
        --dbname={{ db_name }}
        {{ backup_dir }}/{{ restore_backup }}
      become_user: postgres
      register: restore_result

    - name: Verify row counts after restore
      community.postgresql.postgresql_query:
        db: "{{ db_name }}"
        query: "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC"
      become_user: postgres
      register: table_counts

    - name: Display restored table row counts
      debug:
        var: table_counts.query_results

  post_tasks:
    - name: Start application after restore
      service:
        name: myapp
        state: started
      delegate_to: "{{ groups['webservers'] | first }}"
```

**`pause:` module**
- Pauses execution and waits for user input
- `prompt:` shows a message and waits for the user to type something
- `register: confirm_restore` captures what the user typed
- **Use for:** Destructive operations that need human confirmation

**`when: confirm_restore.user_input != 'yes'`**
- Only fails (aborts) if the user didn't type exactly `'yes'`
- Safety gate for destructive operations

**`--jobs=4`** (pg_restore)
- Restores using 4 parallel workers (faster for large databases)

**`--no-owner`** + **`--no-acl`**
- Doesn't try to set original ownership or access control
- Useful when restoring to a different database user

---

## 📋 test-backup-restore.yml — Backup Validation

```yaml
---
- name: Validate backup integrity with restore cycle
  hosts: databases
  become: yes
  vars:
    test_db: "restore_test_{{ ansible_date_time.epoch }}"
    backup_dir: /var/backups/postgresql

  tasks:
    - name: Find latest backup
      find:
        paths: "{{ backup_dir }}"
        patterns: "*.dump"
        age_stamp: mtime
      register: backup_files

    - name: Set latest backup path
      set_fact:
        latest_backup: "{{ (backup_files.files | sort(attribute='mtime') | last).path }}"

    - name: Create test database for restore validation
      community.postgresql.postgresql_db:
        name: "{{ test_db }}"
        state: present
      become_user: postgres

    - name: Restore backup to test database
      command: >
        pg_restore
        --no-owner
        --no-acl
        --dbname={{ test_db }}
        {{ latest_backup }}
      become_user: postgres
      register: restore_test
      failed_when: restore_test.rc != 0

    - name: Verify test restore has data
      community.postgresql.postgresql_query:
        db: "{{ test_db }}"
        query: "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public'"
      become_user: postgres
      register: table_count_result

    - name: Assert restored data is valid
      assert:
        that:
          - table_count_result.query_results[0].table_count | int > 0
        fail_msg: "Backup restore validation FAILED - no tables found"
        success_msg: "Backup restore validation PASSED - {{ table_count_result.query_results[0].table_count }} tables restored"

  always:
    - name: Drop test database (cleanup)
      community.postgresql.postgresql_db:
        name: "{{ test_db }}"
        state: absent
      become_user: postgres
```

**`sort(attribute='mtime') | last`** — Jinja2 filter chain
- `sort(attribute='mtime')` — Sort file list by modification time
- `| last` — Get the last (most recent) item
- Combined: get the most recently modified backup file

**`ansible_date_time.epoch`** — Unix timestamp (seconds since 1970)
- Used to create a unique test database name per run
- `restore_test_1705363200` — Unique, sortable

**`always:` block**
- Cleanup always runs, even if validation fails
- Ensures the test database is always dropped (no orphaned test databases)

---

## ⏱️ backup-rotation.yml — Retention Policy

```yaml
---
- name: Apply backup retention policy
  hosts: databases
  become: yes
  vars:
    backup_dir: /var/backups/postgresql
    retention:
      daily: 7        # Keep 7 daily backups
      weekly: 4       # Keep 4 weekly backups
      monthly: 12     # Keep 12 monthly backups

  tasks:
    - name: Find all backup files
      find:
        paths: "{{ backup_dir }}"
        patterns: "*.dump"
      register: all_backups

    - name: Sort backups by date and apply retention
      set_fact:
        sorted_backups: "{{ all_backups.files | sort(attribute='mtime', reverse=True) }}"

    - name: Delete backups beyond retention limit
      file:
        path: "{{ item.path }}"
        state: absent
      loop: "{{ sorted_backups[retention.daily:] }}"   # Keep first N, delete rest
      when: sorted_backups | length > retention.daily
```

**`sort(attribute='mtime', reverse=True)`** — Sort newest-first
**`sorted_backups[retention.daily:]`** — Python-style list slicing
- `[7:]` means: everything from index 7 onwards (skip first 7)
- Combined: sorted_backups[7:] = all backups except the 7 most recent = backups to delete

---

## 🔄 DR Automation Flow

```
Scheduled (cron/CI):
  backup-database.yml runs every 6 hours
         ↓
  pg_dump → compressed backup file
         ↓
  Verify backup not empty (assert)
         ↓
  Rotate old backups (find + delete)
         ↓
  backup-to-git.yml runs daily
         ↓
  fetch configs from all servers
         ↓
  git commit + push to remote repo

Weekly:
  test-backup-restore.yml
         ↓
  Find latest backup
         ↓
  Restore to test DB
         ↓
  Validate table counts
         ↓
  Drop test DB (always block)
         ↓
  Alert if validation fails

Disaster event:
  restore-database.yml
         ↓
  pause: confirm with user
         ↓
  Stop app → drop DB → restore → verify
         ↓
  Start app
```

---

## 🎯 Best Practices

### 1. Always Verify Backups After Creating
```yaml
- stat:
    path: "{{ backup_file }}"
  register: stat
- assert:
    that:
      - stat.stat.exists
      - stat.stat.size > 1024    # At least 1KB
```

### 2. Test Restores Regularly
```yaml
# Run restore validation weekly
- name: Validate backup
  include_tasks: test-backup-restore.yml
  when: ansible_date_time.weekday == "6"   # Sundays
```

### 3. Require Confirmation for Destructive Operations
```yaml
- pause:
    prompt: "Type 'yes' to restore (DESTROYS current data)"
  register: confirm
- fail:
    msg: "Cancelled"
  when: confirm.user_input != 'yes'
```

### 4. Always Cleanup in `always:` Block
```yaml
block:
  - name: Test restore
    ...
always:
  - name: Drop test database
    ...
```

### 5. Use Timestamps in Backup Names
```yaml
backup_name: "db_{{ ansible_date_time.date }}_{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}.dump"
# Result: db_2024-01-15_1430.dump
```

---

## 🔍 Debugging Commands

```bash
# Run backup manually
ansible-playbook backup-database.yml -e "db_name=myapp" --vault-pass-file .vault-pass

# Restore specific backup
ansible-playbook restore-database.yml -e "restore_backup=myapp_2024-01-15_1430.dump"

# Test latest backup integrity
ansible-playbook test-backup-restore.yml

# List available backups
ansible databases -m find -a "paths=/var/backups/postgresql patterns=*.dump" --become

# Check backup file size
ansible databases -m stat -a "path=/var/backups/postgresql/latest.dump" --become

# Dry run backup (check mode)
ansible-playbook backup-database.yml --check
```

---

## 🎓 Key Takeaways

1. **`ansible_date_time`** — Built-in fact for timestamps; use for unique backup filenames
2. **`stat:` + `assert:`** — Verify backup was actually created and has content
3. **`find: age:`** — Find old files for rotation; combine with `file: state: absent` to delete
4. **`fetch:`** — Copies files FROM remote TO control machine (opposite of `copy`)
5. **`pause: prompt:`** — Human confirmation gate for destructive operations like restores
6. **`always:` block** — Cleanup (drop test DB) always runs, even if restore validation fails
7. **`sort | last`** — Jinja2 filter chain to get the most recent backup file
8. **`changed_when:`** — Make `shell`/`command` tasks idempotent with custom change detection
9. **Test regularly** — A backup you've never tested restoring is not a real backup

---

*Disaster recovery automation turns a stressful, error-prone manual process into a calm, repeatable procedure. By automating and regularly testing your backups, you can recover from any disaster confidently.*
