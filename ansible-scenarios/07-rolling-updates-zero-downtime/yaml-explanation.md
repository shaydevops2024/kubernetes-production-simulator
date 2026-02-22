# YAML Files Explanation - Rolling Updates and Zero Downtime Deployments

This guide explains the playbook patterns for rolling updates, serial execution, health checks, and zero-downtime deployments.

---

## 🔄 What is a Rolling Update?

A rolling update deploys a new version to servers **one at a time** (or in small batches), ensuring some servers always serve traffic. This achieves zero downtime during deployments.

```
Before update: web1(v1) web2(v1) web3(v1) web4(v1)  ← All serving traffic

Rolling update:
Step 1: web1(v2) web2(v1) web3(v1) web4(v1)  ← web1 updated, still 3 serving
Step 2: web1(v2) web2(v2) web3(v1) web4(v1)  ← 2 updated
Step 3: web1(v2) web2(v2) web3(v2) web4(v1)  ← 3 updated
Step 4: web1(v2) web2(v2) web3(v2) web4(v2)  ← All done

After update: web1(v2) web2(v2) web3(v2) web4(v2)  ← All on new version
```

---

## 📋 rolling-update.yml — Core Rolling Update Playbook

### Full File Breakdown:

```yaml
---
- name: Rolling update web application
  hosts: webservers
  serial: 1                    # Update one server at a time
  max_fail_percentage: 25      # Abort if more than 25% of hosts fail
  any_errors_fatal: false      # Continue with remaining serial batches

  pre_tasks:
    - name: Disable server in load balancer
      uri:
        url: "http://{{ lb_host }}/api/servers/{{ inventory_hostname }}/disable"
        method: POST
        status_code: 200
      delegate_to: localhost

    - name: Wait for connections to drain
      wait_for:
        timeout: 30

  tasks:
    - name: Pull latest application code
      git:
        repo: "{{ app_repo_url }}"
        dest: /opt/myapp
        version: "{{ app_version }}"
        force: yes

    - name: Install updated dependencies
      pip:
        requirements: /opt/myapp/requirements.txt
        virtualenv: /opt/myapp/venv

    - name: Run database migrations
      command: /opt/myapp/venv/bin/python manage.py migrate
      args:
        chdir: /opt/myapp
      run_once: true           # Migrations run only once, not per server

    - name: Restart application
      service:
        name: myapp
        state: restarted

    - name: Verify application is healthy
      uri:
        url: "http://{{ inventory_hostname }}:8080/health"
        status_code: 200
        timeout: 30
      retries: 5
      delay: 10

  post_tasks:
    - name: Re-enable server in load balancer
      uri:
        url: "http://{{ lb_host }}/api/servers/{{ inventory_hostname }}/enable"
        method: POST
        status_code: 200
      delegate_to: localhost
```

---

### `serial:` — Batch Size Control

**`serial: 1`**
- Update 1 host at a time
- Safest option — only 1 server ever out of rotation
- Slowest option for large fleets

**`serial: 2`** or **`serial: "25%"`**
- Update 2 hosts or 25% of hosts at a time
- Balance between speed and risk

**Progressive serial batches (most production-friendly):**
```yaml
serial:
  - 1          # First: update just 1 server (canary)
  - 25%        # Then: update 25% at a time
  - 50%        # Then: remaining 50%
```
- Catch failures with 1 server first (minimal blast radius)
- Scale up if canary succeeds

---

### `max_fail_percentage:` — Failure Threshold

```yaml
max_fail_percentage: 25
```
- If more than 25% of hosts in a serial batch fail → abort entire play
- **`0`** — Abort on any single failure (strictest)
- **`100`** — Never abort (runs regardless of failures)
- **Default: 0** — Any failure aborts

**Example:**
```yaml
hosts: 8 webservers
serial: 2
max_fail_percentage: 50

# If 1 of 2 hosts in a batch fails = 50% failure → DOES NOT abort (50% ≤ 50%)
# If 2 of 2 hosts in a batch fail = 100% failure → ABORTS (100% > 50%)
```

---

### `pre_tasks:` and `post_tasks:`

```yaml
pre_tasks:    # Run BEFORE roles and tasks
  - name: Remove from load balancer
    ...

tasks:        # Main deployment tasks
  - name: Deploy code
    ...

post_tasks:   # Run AFTER roles and tasks (even if tasks fail? No — only if tasks succeed)
  - name: Re-add to load balancer
    ...
```

**Execution order:**
```
pre_tasks → handlers triggered by pre_tasks → roles → tasks → handlers → post_tasks → handlers triggered by post_tasks
```

**Why remove from load balancer first?**
- Drain existing connections before stopping the app
- Prevents users hitting a server that's in the middle of updating

---

### `delegate_to: localhost`

```yaml
- name: Disable server in load balancer
  uri:
    url: "http://{{ lb_host }}/api/servers/{{ inventory_hostname }}/enable"
    method: POST
  delegate_to: localhost
```

- Runs the task on the **control machine** (not the remote server)
- `{{ inventory_hostname }}` still refers to the **current remote host** being iterated
- Used for: API calls, git operations, local script execution

**Why `delegate_to: localhost` for load balancer calls?**
- The load balancer API is called from your control machine
- The web server itself doesn't make the API call

---

### `wait_for:` — Connection Draining

```yaml
- name: Wait for active connections to drain
  wait_for:
    timeout: 30            # Wait 30 seconds for connections to finish
```

**More targeted wait:**
```yaml
- name: Wait for port 8080 to close (app stopped)
  wait_for:
    port: 8080
    state: stopped
    timeout: 60

- name: Wait for port 8080 to open (app restarted)
  wait_for:
    port: 8080
    state: started
    timeout: 120
```

**`wait_for` states:**
- `started` — Wait until port is accepting connections
- `stopped` — Wait until port is no longer listening
- `drained` — Wait until no active connections on port (TCP drain)
- `absent` — Wait until file/path doesn't exist
- `present` — Wait until file/path exists

---

### `uri:` — HTTP Health Check

```yaml
- name: Verify application is healthy
  uri:
    url: "http://{{ inventory_hostname }}:8080/health"
    status_code: 200
    timeout: 30
  retries: 5
  delay: 10
```

**`uri:` module**
- Makes HTTP/HTTPS requests
- Validates status code, response body, headers

**`retries: 5`** + **`delay: 10`**
- Retry the task up to 5 times
- Wait 10 seconds between retries
- Useful for: App needs time to start up before responding to health checks
- Total wait: up to 50 seconds (5 × 10s)

**More detailed health check:**
```yaml
- name: Verify application health response body
  uri:
    url: "http://{{ inventory_hostname }}:8080/health"
    method: GET
    status_code: 200
    return_content: yes
  register: health_response
  retries: 10
  delay: 15
  until: health_response.status == 200 and 'healthy' in health_response.content
```

**`until:` with `retries:`**
- Retries until the `until` condition is True
- More flexible than just checking status code

---

## 🔙 rollback.yml — Automatic Rollback

### Rolling Back on Failure:

```yaml
---
- name: Deploy with automatic rollback
  hosts: webservers
  serial: 1
  tasks:
    - name: Get current version before update
      command: cat /opt/myapp/CURRENT_VERSION
      register: current_version
      failed_when: false    # Don't fail if file doesn't exist

    - block:
        - name: Deploy new version
          git:
            repo: "{{ app_repo_url }}"
            dest: /opt/myapp
            version: "{{ new_version }}"

        - name: Install dependencies
          pip:
            requirements: /opt/myapp/requirements.txt
            virtualenv: /opt/myapp/venv

        - name: Restart application
          service:
            name: myapp
            state: restarted

        - name: Health check
          uri:
            url: "http://{{ inventory_hostname }}:8080/health"
            status_code: 200
          retries: 5
          delay: 10

      rescue:
        - name: ROLLBACK - Restore previous version
          git:
            repo: "{{ app_repo_url }}"
            dest: /opt/myapp
            version: "{{ current_version.stdout }}"

        - name: ROLLBACK - Restart with previous version
          service:
            name: myapp
            state: restarted

        - name: ROLLBACK - Notify team
          uri:
            url: "{{ slack_webhook }}"
            method: POST
            body_format: json
            body:
              text: "Rollback triggered on {{ inventory_hostname }}!"

        - name: ROLLBACK - Fail the play after rollback
          fail:
            msg: "Deployment failed, rollback completed on {{ inventory_hostname }}"
```

### `block:` / `rescue:` / `always:`

```yaml
block:          # Tasks to try
  - task1
  - task2

rescue:         # Run if ANY task in block fails
  - rollback_task1
  - rollback_task2

always:         # Always run, regardless of block/rescue outcome
  - cleanup_task
  - re_enable_load_balancer    # Always re-add to LB, even on failure!
```

**Why `always:` for load balancer re-enable?**
- If deployment fails AND you don't re-enable the LB → server stays out of rotation forever
- `always:` guarantees cleanup runs regardless of success or failure

---

## 🏃 run_once: — Single Execution Tasks

```yaml
- name: Run database migrations
  command: python manage.py migrate
  args:
    chdir: /opt/myapp
  run_once: true               # Run on first host only
  delegate_to: "{{ groups['webservers'][0] }}"  # Explicitly choose which host
```

**`run_once: true`**
- Executes task on **one host only** (the first in the batch)
- Result is **not** shared with other hosts (unlike `set_fact`)
- **Use case:** Database migrations, cache clearing, one-time setup

**Why not run migrations on every server?**
- Migrations modify database schema — running from 4 servers simultaneously = race condition
- One migration run is sufficient for all servers

---

## 📊 Canary Deployment Pattern

```yaml
---
# Play 1: Canary (1 server, validate before full rollout)
- name: Canary deployment
  hosts: webservers[0]      # Only the first server
  tasks:
    - name: Deploy to canary
      include_tasks: deploy-tasks.yml

    - name: Wait and monitor canary (5 minutes)
      wait_for:
        timeout: 300

    - name: Check canary error rate
      uri:
        url: "http://{{ monitoring_host }}/api/error-rate?host={{ inventory_hostname }}"
        return_content: yes
      register: error_rate
      failed_when: (error_rate.json.rate | float) > 0.01   # Fail if >1% errors

# Play 2: Full rollout (remaining servers, only if canary succeeded)
- name: Full rollout
  hosts: webservers[1:]     # All servers except the first (canary)
  serial: "25%"
  tasks:
    - name: Deploy to remaining servers
      include_tasks: deploy-tasks.yml
```

---

## 🎯 Best Practices

### 1. Always Drain Before Stopping
```yaml
pre_tasks:
  - name: Remove from load balancer
    uri:
      url: "http://lb/remove/{{ inventory_hostname }}"
      method: POST
    delegate_to: localhost

  - name: Drain connections (30s)
    wait_for:
      timeout: 30
```

### 2. Verify Health Before Re-enabling
```yaml
post_tasks:
  - name: Health check passes?
    uri:
      url: "http://{{ inventory_hostname }}:8080/health"
      status_code: 200
    retries: 10
    delay: 10

  - name: Re-enable in load balancer
    uri:
      url: "http://lb/add/{{ inventory_hostname }}"
      method: POST
    delegate_to: localhost
```

### 3. Use `always:` to Guarantee Cleanup
```yaml
block:
  - name: Deploy
    ...
rescue:
  - name: Rollback
    ...
always:
  - name: Re-enable in load balancer  # ALWAYS happens
    uri:
      url: "http://lb/add/{{ inventory_hostname }}"
      method: POST
    delegate_to: localhost
```

### 4. Progressive Batch Sizes
```yaml
# Start small, scale up
serial:
  - 1        # Canary: 1 server
  - 10%      # Small batch
  - 50%      # Medium batch
  - 100%     # Rest
```

---

## 🔍 Debugging Rolling Updates

```bash
# Dry run to see what would change
ansible-playbook rolling-update.yml --check --diff

# Limit to specific host (test on one server first)
ansible-playbook rolling-update.yml --limit web1

# Start from specific task (after previous failure)
ansible-playbook rolling-update.yml --start-at-task "Restart application"

# Step through tasks interactively
ansible-playbook rolling-update.yml --step

# See task timing
ansible-playbook rolling-update.yml --callback-whitelist timer

# Check which hosts failed
cat webservers.retry
ansible-playbook rolling-update.yml -i webservers.retry
```

---

## 🎓 Key Takeaways

1. **`serial:`** controls batch size — `1` safest, `"25%"` balances speed and risk
2. **`pre_tasks`/`post_tasks`** — remove from LB before, re-add after (always with `always:`)
3. **`max_fail_percentage:`** — sets abort threshold; `0` means abort on any failure
4. **`block/rescue/always`** — try/catch/finally for Ansible tasks; use `always` for cleanup
5. **`run_once: true`** — database migrations run once, not per-server
6. **`delegate_to: localhost`** — LB API calls run from control machine
7. **`uri:` + `retries:`** — health checks with retry logic wait for app startup
8. **Progressive serial** — canary first, then batch rollout validates before full deployment

---

*Rolling updates are the foundation of zero-downtime deployments. Combined with health checks and automatic rollback, this pattern safely deploys to production without user impact.*
