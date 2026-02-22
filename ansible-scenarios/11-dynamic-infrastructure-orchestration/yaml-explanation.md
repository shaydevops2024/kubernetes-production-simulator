# YAML Files Explanation - Dynamic Infrastructure Orchestration with Ansible

This guide explains advanced Ansible patterns: dynamic inventory, conditional execution, task output registration, error handling with blocks, and asynchronous tasks.

---

## ⚡ What is Dynamic Infrastructure Orchestration?

Unlike static infrastructure where servers have fixed IPs, dynamic infrastructure creates and destroys servers on-demand. Ansible handles this through:
- **Dynamic inventory** — Discovers hosts at runtime (Docker API, AWS, GCP, etc.)
- **`register`** — Captures task output for use in subsequent tasks
- **`block/rescue/always`** — Structured error handling
- **`async`** — Run long tasks in background without timeout

---

## 📋 dynamic-inventory.py — Docker Dynamic Inventory

### What is Dynamic Inventory?
Instead of a static `hosts.ini`, dynamic inventory runs a script that queries an API and returns hosts in JSON format.

### How Ansible Calls Dynamic Inventory:
```bash
# Ansible calls the script with --list (all hosts)
./dynamic-inventory.py --list

# Or with --host <hostname> (specific host vars)
./dynamic-inventory.py --host container1
```

### Dynamic Inventory Script Pattern:
```python
#!/usr/bin/env python3
import json
import docker

def get_inventory():
    client = docker.from_env()
    inventory = {
        "_meta": {
            "hostvars": {}
        }
    }

    for container in client.containers.list():
        # Group containers by their labels
        group = container.labels.get('ansible_group', 'ungrouped')

        if group not in inventory:
            inventory[group] = {"hosts": [], "vars": {}}

        inventory[group]["hosts"].append(container.name)

        # Per-host variables
        network = list(container.attrs['NetworkSettings']['Networks'].values())[0]
        inventory["_meta"]["hostvars"][container.name] = {
            "ansible_host": network["IPAddress"],
            "ansible_user": "root",
            "container_id": container.short_id,
            "container_image": container.image.tags[0] if container.image.tags else "unknown",
        }

    return inventory

print(json.dumps(get_inventory(), indent=2))
```

**`_meta.hostvars`** — Special key providing per-host variables (avoids separate `--host` calls per host — more efficient)

**Returned JSON structure:**
```json
{
  "_meta": {
    "hostvars": {
      "web1": {"ansible_host": "172.17.0.2", "ansible_user": "root"},
      "db1":  {"ansible_host": "172.17.0.3", "ansible_user": "root"}
    }
  },
  "webservers": {
    "hosts": ["web1", "web2"],
    "vars": {"http_port": 80}
  },
  "databases": {
    "hosts": ["db1"],
    "vars": {}
  },
  "all": {
    "children": ["webservers", "databases"]
  }
}
```

**Using dynamic inventory:**
```bash
# Use executable script as inventory
ansible-playbook site.yml -i dynamic-inventory.py

# Or in ansible.cfg:
# inventory = dynamic-inventory.py
```

---

## 📋 create-infrastructure.yml — Dynamic Container Creation

```yaml
---
- name: Create dynamic Docker infrastructure
  hosts: localhost
  connection: local
  gather_facts: no
  vars:
    containers:
      - name: web1
        image: ubuntu:22.04
        ports: ["8080:80"]
        labels:
          ansible_group: webservers
          environment: staging
      - name: web2
        image: ubuntu:22.04
        ports: ["8081:80"]
        labels:
          ansible_group: webservers
          environment: staging
      - name: db1
        image: ubuntu:22.04
        labels:
          ansible_group: databases
          environment: staging

  tasks:
    - name: Create containers
      community.docker.docker_container:
        name: "{{ item.name }}"
        image: "{{ item.image }}"
        state: started
        restart_policy: unless-stopped
        ports: "{{ item.ports | default([]) }}"
        labels: "{{ item.labels | default({}) }}"
        command: ["/bin/sh", "-c", "while true; do sleep 3600; done"]
      loop: "{{ containers }}"
      register: container_results

    - name: Display created container IPs
      debug:
        msg: "{{ item.container.Name }}: {{ item.container.NetworkSettings.IPAddress }}"
      loop: "{{ container_results.results }}"
      when: item.container is defined

    - name: Wait for SSH to be available on new containers
      wait_for:
        host: "{{ item.container.NetworkSettings.IPAddress }}"
        port: 22
        timeout: 60
        delay: 5
      loop: "{{ container_results.results }}"
      when: item.container is defined

    - name: Refresh dynamic inventory
      meta: refresh_inventory       # Re-run inventory script to see new containers
```

**`connection: local`**
- Run tasks on localhost (not via SSH)
- Used for local operations: Docker API calls, cloud API calls

**`gather_facts: no`**
- Skip automatic fact gathering (`ansible_*` facts)
- Speeds up plays that don't need host facts
- Required when `connection: local` + no remote SSH available yet

**`register: container_results`**
- Captures the output of the loop
- When used with a loop: `container_results.results` is a list, one item per loop iteration
- Access per-item result: `item.container.NetworkSettings.IPAddress`

**`meta: refresh_inventory`**
- Special Ansible meta-task (not a module)
- Re-runs dynamic inventory script to discover newly created hosts
- Allows subsequent plays in the same playbook to target new hosts

---

## 📋 conditional-execution.yml — Fact-Based Conditionals

```yaml
---
- name: Configure infrastructure based on gathered facts
  hosts: all
  become: yes
  tasks:
    - name: Gather system facts
      setup:
        gather_subset:
          - hardware
          - network
          - virtual

    - name: Install packages based on OS family
      package:
        name: "{{ item }}"
        state: present
      loop: "{{ os_packages[ansible_os_family] | default([]) }}"
      vars:
        os_packages:
          Debian: [nginx, curl, htop, python3-pip]
          RedHat: [nginx, curl, htop, python3-pip, policycoreutils]
          Alpine: [nginx, curl]

    - name: Configure based on available memory
      template:
        src: "{{ 'high-memory.conf.j2' if ansible_memtotal_mb >= 8192 else 'low-memory.conf.j2' }}"
        dest: /etc/myapp/app.conf
      when: ansible_memtotal_mb is defined

    - name: Enable swap only on low-memory systems
      command: swapon -a
      when:
        - ansible_memtotal_mb < 2048
        - ansible_swaptotal_mb == 0       # No swap already configured

    - name: Configure worker count based on CPU count
      lineinfile:
        path: /etc/myapp/app.conf
        regexp: '^workers='
        line: "workers={{ [ansible_processor_vcpus * 2, 4] | min }}"
        # Use at most 4 workers, even on 16-core machines
```

**`setup: gather_subset:`**
- By default, `setup` gathers ALL facts (slow: ~0.5s per host)
- `gather_subset:` limits to only what you need (faster)
- Options: `hardware`, `network`, `virtual`, `min`, `all`

**`os_packages[ansible_os_family]`**
- Dictionary lookup using a fact as the key
- `ansible_os_family` = `Debian`, `RedHat`, `Alpine`, etc.
- Returns the list for the current OS, or `[]` if OS not in dict

**Inline conditional in `src:`:**
```yaml
src: "{{ 'high-memory.conf.j2' if ansible_memtotal_mb >= 8192 else 'low-memory.conf.j2' }}"
```
- Selects different templates based on hardware capability

**`[ansible_processor_vcpus * 2, 4] | min`**
- Jinja2 math + `min` filter
- `ansible_processor_vcpus * 2` — Calculate desired workers
- `| min` on a list — Takes the smallest value
- Ensures never more than 4 workers regardless of CPU count

---

## 📋 register-and-use.yml — Task Output Registration

```yaml
---
- name: Advanced task output registration
  hosts: webservers
  become: yes
  tasks:
    - name: Check current app version
      command: /opt/myapp/venv/bin/python -c "import myapp; print(myapp.__version__)"
      register: current_version
      changed_when: false
      failed_when: false          # Don't fail if app isn't installed yet

    - name: Display current version
      debug:
        msg: "Current version: {{ current_version.stdout | default('not installed') }}"

    - name: Download new version
      get_url:
        url: "https://releases.example.com/myapp-{{ new_version }}.tar.gz"
        dest: /tmp/myapp-new.tar.gz
      when:
        - current_version.rc == 0                          # App is installed
        - current_version.stdout != new_version            # Different version
        - new_version is version(current_version.stdout, '>') # New is actually newer

    - name: Get list of running app processes
      command: pgrep -la myapp
      register: running_processes
      changed_when: false
      failed_when: false

    - name: Stop app only if it's running
      service:
        name: myapp
        state: stopped
      when: running_processes.rc == 0   # Only stop if pgrep found processes

    - name: Deploy new version
      unarchive:
        src: /tmp/myapp-new.tar.gz
        dest: /opt/myapp
        remote_src: yes
      when: current_version.stdout != new_version

    - name: Capture deployment result
      command: /opt/myapp/venv/bin/python -m pytest /opt/myapp/tests/smoke_tests.py
      register: smoke_test_result
      failed_when: smoke_test_result.rc != 0

    - name: Write deployment report
      copy:
        content: |
          Deployment Report - {{ ansible_date_time.iso8601 }}
          Host: {{ inventory_hostname }}
          Previous version: {{ current_version.stdout | default('N/A') }}
          New version: {{ new_version }}
          Smoke tests: {{ 'PASSED' if smoke_test_result.rc == 0 else 'FAILED' }}
          Test output:
          {{ smoke_test_result.stdout }}
        dest: /tmp/deployment-report.txt
      delegate_to: localhost
```

**`register` variables contain:**
- `rc` — Return code (0 = success, non-zero = failure)
- `stdout` — Standard output (string)
- `stderr` — Standard error
- `stdout_lines` — stdout as list of lines
- `changed` — Whether the task changed something
- `failed` — Whether the task failed

**`is version(current_version.stdout, '>')`**
- Jinja2 version comparison test
- Compares version strings properly (`1.10 > 1.9` = True)
- Prevents "downgrade" deployments

**`| default('not installed')`**
- Return `'not installed'` if `current_version.stdout` is empty/undefined
- Safe fallback when command fails (`failed_when: false`)

---

## 📋 error-handling-blocks.yml — Structured Error Handling

```yaml
---
- name: Deploy with comprehensive error handling
  hosts: webservers
  serial: 1
  tasks:
    - name: Deploy with rollback capability
      block:
        - name: Validate deployment prerequisites
          assert:
            that:
              - new_version is defined
              - new_version | regex_search('^\d+\.\d+\.\d+$')  # Semver format
            fail_msg: "Invalid version format: {{ new_version }}"

        - name: Create deployment lock
          file:
            path: /tmp/deployment.lock
            state: touch
          register: lock_file

        - name: Deploy application
          include_tasks: deploy-tasks.yml

        - name: Run smoke tests
          uri:
            url: "http://{{ inventory_hostname }}:8080/health"
            status_code: 200
          retries: 5
          delay: 10

      rescue:
        - name: Log deployment failure
          copy:
            content: |
              Deployment FAILED on {{ inventory_hostname }}
              Time: {{ ansible_date_time.iso8601 }}
              Version attempted: {{ new_version | default('unknown') }}
              Error: {{ ansible_failed_result | default({}) | to_yaml }}
            dest: "/var/log/deployment-failures/{{ ansible_date_time.epoch }}.log"
          ignore_errors: yes    # Don't fail the rescue block itself

        - name: Trigger rollback
          include_tasks: rollback-tasks.yml

        - name: Notify team of failure
          uri:
            url: "{{ slack_webhook }}"
            method: POST
            body_format: json
            body:
              text: ":red_circle: Deployment FAILED on {{ inventory_hostname }}"

        - name: Re-raise failure (abort entire play)
          fail:
            msg: "Deployment failed on {{ inventory_hostname }}, rollback complete"

      always:
        - name: Remove deployment lock
          file:
            path: /tmp/deployment.lock
            state: absent
          ignore_errors: yes    # Lock removal must succeed even if everything else failed
```

**`ansible_failed_result`**
- Special variable available in `rescue:` block
- Contains the result object of the task that failed
- Useful for logging: which task failed and why

**`| regex_search('^\\d+\\.\\d+\\.\\d+$')`**
- Jinja2 filter: returns match if found, empty string if not
- Validates version string format (e.g., `1.2.3`)
- Use in `assert: that:` to validate inputs before destructive actions

**`ignore_errors: yes`**
- Continue even if this specific task fails
- Used in cleanup tasks that must run regardless
- Different from `failed_when: false` (which changes what counts as failure)

**`fail:` in rescue block**
- After rollback completes, explicitly fail the play
- Without this, a successful rollback would make the play appear to succeed
- Makes the CI/CD pipeline aware the deployment failed

---

## 📋 async-tasks.yml — Asynchronous Execution

```yaml
---
- name: Run long tasks asynchronously
  hosts: servers
  tasks:
    - name: Start long-running backup (async)
      command: /opt/scripts/full-backup.sh
      async: 3600          # Allow up to 1 hour for this task
      poll: 0              # Don't wait; continue to next task immediately
      register: backup_job

    - name: Run another task while backup runs
      apt:
        name: htop
        state: present

    - name: Check backup status
      async_status:
        jid: "{{ backup_job.ansible_job_id }}"
      register: backup_status
      until: backup_status.finished
      retries: 60           # Check every 30 seconds for up to 30 minutes
      delay: 30

    - name: Run multiple tasks in parallel across hosts (fan-out)
      command: /opt/scripts/process-data.sh --shard={{ item }}
      loop: [1, 2, 3, 4]
      async: 600            # Each shard: up to 10 minutes
      poll: 0
      register: shard_jobs

    - name: Wait for all shards to complete
      async_status:
        jid: "{{ item.ansible_job_id }}"
      loop: "{{ shard_jobs.results }}"
      register: shard_results
      until: shard_results.finished
      retries: 30
      delay: 20
```

**`async: 3600`** — Task is allowed to run for up to 3600 seconds
**`poll: 0`** — Don't poll; return immediately and continue with next task
**`poll: 30`** — Check status every 30 seconds (blocks until done)

**`async_status:`** — Check the status of an async job
- `jid:` — The job ID from the `register` of the async task
- `finished` — True when the job is complete

**When to use async:**
- Tasks that take longer than 2 minutes (SSH timeout protection)
- Tasks you want running in parallel on the same host (loop + async)
- Long-running scripts (backups, data processing, builds)

**`until:` + `retries:` + `delay:`**
- Retry the task until condition is true
- `until: backup_status.finished` — Keep checking until job is done
- `retries: 60` × `delay: 30s` = wait up to 30 minutes

---

## 🔄 Complete Dynamic Infrastructure Flow

```
1. create-infrastructure.yml
   → docker_container: creates web1, web2, db1
   → register: capture IPs
   → meta: refresh_inventory (discover new hosts)
         ↓
2. Dynamic inventory script runs
   → Queries Docker API
   → Returns JSON: {webservers: [web1, web2], databases: [db1]}
         ↓
3. configure-dynamically.yml (targets dynamically discovered hosts)
   → setup: gather facts
   → conditional tasks based on facts
   → register outputs for use in later tasks
   → block/rescue for safe deployment
   → async for long tasks
         ↓
4. destroy-infrastructure.yml
   → Stop and remove containers when done
```

---

## 🎯 Best Practices

### 1. Always Register Results You'll Reuse
```yaml
- command: cat /opt/myapp/VERSION
  register: app_version
  changed_when: false

- debug:
    msg: "Version: {{ app_version.stdout }}"
```

### 2. Use `failed_when: false` for Probe Tasks
```yaml
- command: systemctl is-active myapp
  register: service_status
  failed_when: false    # rc=3 (inactive) shouldn't fail the play
  changed_when: false

- service:
    name: myapp
    state: started
  when: service_status.rc != 0
```

### 3. Async for Any Task >2 Minutes
```yaml
- command: /opt/scripts/long-running.sh
  async: 7200     # 2 hour limit
  poll: 60        # Check every minute (or use poll: 0 + async_status)
```

### 4. Always Clean Up in `always:` Block
```yaml
block:
  - name: Risky operation
    ...
always:
  - name: Remove lock file
    file:
      path: /tmp/operation.lock
      state: absent
    ignore_errors: yes
```

---

## 🔍 Debugging Dynamic Infrastructure

```bash
# Test dynamic inventory output
python3 dynamic-inventory.py --list | jq .

# See what hosts Ansible discovers
ansible-inventory -i dynamic-inventory.py --graph

# Run tasks on dynamically discovered hosts
ansible-playbook site.yml -i dynamic-inventory.py

# Check async job status manually
ansible servers -m async_status -a "jid=<job_id>"

# Debug registered variable
ansible-playbook playbook.yml -e "debug_vars=true" -v

# Step through tasks interactively
ansible-playbook playbook.yml --step
```

---

## 🎓 Key Takeaways

1. **Dynamic inventory** — Scripts query APIs (Docker, AWS, GCP) to return hosts as JSON
2. **`register`** — Capture task output (`rc`, `stdout`, `stderr`) for use in subsequent tasks
3. **`when:`** — Conditional execution based on facts, register results, or variables
4. **`gather_subset:`** — Limit fact collection to what you need (faster)
5. **`block/rescue/always`** — try/catch/finally for Ansible; `always` guarantees cleanup
6. **`ansible_failed_result`** — Available in `rescue:` to log which task failed and why
7. **`async: N, poll: 0`** — Start task in background; use `async_status` to wait later
8. **`meta: refresh_inventory`** — Re-discover hosts after creating new infrastructure
9. **`until: + retries: + delay:`** — Polling pattern to wait for async jobs or slow starts

---

*Dynamic infrastructure orchestration is where Ansible shines brightest — automatically configuring whatever resources exist right now, not what was listed in a static file weeks ago.*
