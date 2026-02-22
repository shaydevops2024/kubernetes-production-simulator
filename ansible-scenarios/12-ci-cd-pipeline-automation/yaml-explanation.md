# YAML Files Explanation - CI/CD Pipeline Automation with Ansible

This guide explains the playbook patterns for Git-based deployments, automated testing, blue/green deployments, and pipeline integration.

---

## 🚀 What is CI/CD Pipeline Automation with Ansible?

CI/CD (Continuous Integration/Continuous Deployment) automates the path from code commit to production:
- **CI** — Automatically test every code change
- **CD** — Automatically deploy passing builds to production

Ansible fits into CD: after tests pass in CI, Ansible deploys the new version safely.

```
Developer pushes code
        ↓
Jenkins/GitLab CI triggers
        ↓
Run tests (unit, integration)
        ↓
Tests pass → Ansible runs
        ↓
ansible-playbook deploy.yml -e version=1.2.3
        ↓
Blue/green switch → Zero downtime
        ↓
Smoke tests pass → Done!
```

---

## 📋 deploy-from-git.yml — Git-Based Deployment

### Full File Breakdown:

```yaml
---
- name: Deploy application from Git repository
  hosts: webservers
  become: yes
  vars:
    app_repo: "{{ git_repo_url }}"
    app_version: "{{ git_tag | default('main') }}"
    app_dir: /opt/myapp
    deploy_dir: "/opt/myapp/releases/{{ ansible_date_time.epoch }}"
    current_link: /opt/myapp/current

  tasks:
    - name: Ensure releases directory exists
      file:
        path: /opt/myapp/releases
        state: directory
        owner: www-data
        mode: '0755'

    - name: Clone specific version from Git
      git:
        repo: "{{ app_repo }}"
        dest: "{{ deploy_dir }}"
        version: "{{ app_version }}"
        depth: 1               # Shallow clone (faster, only latest commit)
        single_branch: yes

    - name: Install application dependencies
      pip:
        requirements: "{{ deploy_dir }}/requirements.txt"
        virtualenv: "{{ deploy_dir }}/venv"

    - name: Run database migrations (once only)
      command: "{{ deploy_dir }}/venv/bin/python manage.py migrate --noinput"
      args:
        chdir: "{{ deploy_dir }}"
      run_once: true
      environment:
        DATABASE_URL: "{{ vault_database_url }}"
        DJANGO_SETTINGS_MODULE: "myapp.settings.production"

    - name: Collect static files
      command: "{{ deploy_dir }}/venv/bin/python manage.py collectstatic --noinput"
      args:
        chdir: "{{ deploy_dir }}"
      run_once: true

    - name: Update symlink to new release (atomic switch)
      file:
        src: "{{ deploy_dir }}"
        dest: "{{ current_link }}"
        state: link
        force: yes             # Replace existing symlink atomically

    - name: Restart application
      service:
        name: myapp
        state: restarted

    - name: Verify deployment
      uri:
        url: "http://localhost:8080/health"
        status_code: 200
        return_content: yes
      register: health_check
      retries: 5
      delay: 10
      until: health_check.status == 200

    - name: Cleanup old releases (keep last 5)
      find:
        paths: /opt/myapp/releases
        file_type: directory
        age: "5d"
      register: old_releases

    - name: Delete old releases
      file:
        path: "{{ item.path }}"
        state: absent
      loop: "{{ (old_releases.files | sort(attribute='mtime'))[:-5] }}"
      # Keep the 5 most recent, delete the rest
```

**`git:` module**
- Clones or updates a Git repository
- `version:` — branch, tag, or commit SHA
- `depth: 1` — Shallow clone: only the latest commit (not full history)
  - **Why?** 10x faster for large repos (don't need all history to deploy)
- `single_branch: yes` — Only clone the specified branch (smaller clone)

**Symlink deployment pattern:**
```
/opt/myapp/
├── releases/
│   ├── 1705363200/   (old)
│   ├── 1705449600/   (old)
│   └── 1705536000/   (new)
└── current → releases/1705536000  (symlink, updated atomically)
```
- App reads from `/opt/myapp/current/` (the symlink)
- Updating the symlink switches versions atomically
- Old releases kept for instant rollback: `file: src: releases/1705449600 dest: current`

**`environment:` (command/shell)**
- Sets environment variables for the command
- Used here to pass database credentials and Django settings
- Safer than hardcoding in command string

**`args: chdir:`**
- Run the command in a specific directory
- Equivalent to `cd /opt/myapp/releases/... && python manage.py migrate`

---

## 📋 blue-green-deploy.yml — Zero-Downtime Blue/Green Deployment

### What is Blue/Green Deployment?

Two identical environments: **blue** (current live) and **green** (new version):

```
Before:  Load Balancer → [Blue: v1.0]    [Green: v1.0] (idle)
Deploy:  Load Balancer → [Blue: v1.0]    [Green: v2.0] (deploy to idle)
Switch:  Load Balancer → [Blue: v1.0]    [Green: v2.0] ← live
         (Blue now idle, instant rollback available)
```

### Full Playbook:

```yaml
---
- name: Blue/Green Deployment
  hosts: localhost
  connection: local
  gather_facts: no
  vars:
    lb_api: "http://{{ lb_host }}/api"
    new_version: "{{ deploy_version }}"

  tasks:
    - name: Determine current active color
      uri:
        url: "{{ lb_api }}/active-color"
        method: GET
        return_content: yes
      register: active_color_response

    - name: Set color variables
      set_fact:
        active_color: "{{ active_color_response.json.color }}"
        inactive_color: "{{ 'green' if active_color_response.json.color == 'blue' else 'blue' }}"

    - name: Display deployment plan
      debug:
        msg: |
          Deploying to {{ inactive_color }} environment
          Current live: {{ active_color }}
          New version: {{ new_version }}

    - name: Deploy new version to inactive environment
      include_tasks: deploy-to-environment.yml
      vars:
        target_env: "{{ inactive_color }}"
        target_hosts: "{{ groups[inactive_color + '_servers'] }}"

    - name: Run smoke tests on inactive environment
      uri:
        url: "http://{{ inactive_color }}-internal.example.com/health"
        status_code: 200
        return_content: yes
      register: smoke_test
      retries: 10
      delay: 15
      until:
        - smoke_test.status == 200
        - smoke_test.json.version == new_version

    - name: Run integration tests against inactive environment
      command: >
        pytest tests/integration/
        --base-url=http://{{ inactive_color }}-internal.example.com
        --junitxml=/tmp/test-results.xml
      delegate_to: test_runner
      register: test_results
      failed_when: test_results.rc != 0

    - name: Switch load balancer to new version
      uri:
        url: "{{ lb_api }}/switch"
        method: POST
        body_format: json
        body:
          color: "{{ inactive_color }}"
      when: test_results.rc == 0   # Only switch if all tests pass

    - name: Verify switch succeeded
      uri:
        url: "{{ lb_api }}/active-color"
        return_content: yes
      register: verify_switch
      failed_when: verify_switch.json.color != inactive_color

    - name: Monitor new live environment for 2 minutes
      pause:
        seconds: 120
        prompt: "Monitoring {{ inactive_color }} for 2 minutes... Press Ctrl+C to trigger rollback"

    - name: Check error rate on new live environment
      uri:
        url: "http://{{ monitoring_host }}/api/v1/query?query=rate(http_requests_total{status=~'5..', color='{{ inactive_color }}'}[5m])"
        return_content: yes
      register: error_rate
      failed_when: (error_rate.json.data.result[0].value[1] | float) > 0.01

  rescue:
    - name: Emergency rollback - switch back to previous environment
      uri:
        url: "{{ lb_api }}/switch"
        method: POST
        body_format: json
        body:
          color: "{{ active_color }}"    # Switch back to original

    - name: Notify team of rollback
      uri:
        url: "{{ slack_webhook }}"
        method: POST
        body_format: json
        body:
          text: ":rotating_light: Blue/green switch FAILED! Rolled back to {{ active_color }}. Error: {{ ansible_failed_result.msg }}"
```

**`set_fact:`**
- Creates a new variable available for the rest of the play
- `inactive_color: "{{ 'green' if active_color == 'blue' else 'blue' }}"` — Inline ternary
- Computed once and reused across multiple tasks

**`until:` with multiple conditions**
```yaml
until:
  - smoke_test.status == 200
  - smoke_test.json.version == new_version   # Confirm new version is live
```
- Both conditions must be true (AND logic)
- Prevents switching if health check passes but wrong version deployed

**`pause: seconds: 120`**
- Wait 2 minutes while observing the new environment
- CI/CD: skip with `--extra-vars "pause_seconds=0"` for automated runs

---

## 📋 rollback.yml — Instant Rollback

```yaml
---
- name: Rollback to previous version
  hosts: localhost
  connection: local
  gather_facts: no
  vars:
    rollback_color: "{{ previous_color | mandatory }}"  # Must be specified

  tasks:
    - name: Confirm rollback
      pause:
        prompt: "Rolling back to {{ rollback_color }}. Type 'yes' to confirm"
      register: confirm
      when: not (auto_rollback | default(false) | bool)

    - name: Abort if not confirmed
      fail:
        msg: "Rollback cancelled"
      when:
        - not (auto_rollback | default(false) | bool)
        - confirm.user_input != 'yes'

    - name: Switch load balancer to previous environment
      uri:
        url: "http://{{ lb_host }}/api/switch"
        method: POST
        body_format: json
        body:
          color: "{{ rollback_color }}"

    - name: Verify rollback
      uri:
        url: "http://{{ lb_host }}/api/active-color"
        return_content: yes
      register: verify
      failed_when: verify.json.color != rollback_color
```

**`| mandatory`**
- Jinja2 filter: fails if the variable is undefined
- Better error message than Ansible's default undefined variable error
- Use for required input variables that must be provided by the caller

**`auto_rollback | default(false) | bool`**
- `default(false)` — Use `false` if `auto_rollback` not defined
- `| bool` — Convert string `"true"`/`"false"` to Python `True`/`False`
- Allows both `--extra-vars "auto_rollback=true"` and `auto_rollback: true` in vars

---

## 📋 pipeline-integration.yml — Jenkinsfile / GitLab CI Integration

### Ansible Called from Jenkins:

```groovy
// Jenkinsfile
pipeline {
    agent any
    environment {
        VAULT_PASS = credentials('ansible-vault-password')
    }
    stages {
        stage('Test') {
            steps {
                sh 'pytest tests/'
            }
        }
        stage('Deploy to Staging') {
            steps {
                sh """
                    ansible-playbook deploy-from-git.yml \
                        --inventory inventories/staging/ \
                        --extra-vars git_tag=${GIT_TAG} \
                        --vault-password-file <(echo \$VAULT_PASS) \
                        --limit staging_servers
                """
            }
        }
        stage('Integration Tests') {
            steps {
                sh 'pytest tests/integration/ --base-url=https://staging.example.com'
            }
        }
        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            input {
                message "Deploy v${GIT_TAG} to production?"
                ok "Deploy"
            }
            steps {
                sh """
                    ansible-playbook blue-green-deploy.yml \
                        --inventory inventories/production/ \
                        --extra-vars "deploy_version=${GIT_TAG} auto_rollback=false" \
                        --vault-password-file <(echo \$VAULT_PASS)
                """
            }
        }
    }
    post {
        failure {
            sh """
                ansible-playbook rollback.yml \
                    --extra-vars "rollback_color=${PREVIOUS_COLOR} auto_rollback=true" \
                    --vault-password-file <(echo \$VAULT_PASS)
            """
        }
    }
}
```

### Ansible Trigger Playbook (from within Ansible):

```yaml
---
- name: Trigger CI/CD pipeline stages
  hosts: ci_servers
  tasks:
    - name: Trigger Jenkins build via API
      uri:
        url: "{{ jenkins_url }}/job/{{ job_name }}/buildWithParameters"
        method: POST
        user: "{{ vault_jenkins_user }}"
        password: "{{ vault_jenkins_token }}"
        force_basic_auth: yes
        body_format: form-urlencoded
        body:
          GIT_TAG: "{{ deploy_version }}"
          ENVIRONMENT: "{{ target_env }}"
        status_code: [201, 200]
      register: jenkins_build

    - name: Get Jenkins build number from Location header
      set_fact:
        build_number: "{{ jenkins_build.location | regex_search('(\\d+)/$', '\\1') | first }}"

    - name: Wait for Jenkins build to complete
      uri:
        url: "{{ jenkins_url }}/job/{{ job_name }}/{{ build_number }}/api/json"
        user: "{{ vault_jenkins_user }}"
        password: "{{ vault_jenkins_token }}"
        force_basic_auth: yes
        return_content: yes
      register: build_status
      until:
        - build_status.json.result is not none
        - build_status.json.result in ['SUCCESS', 'FAILURE', 'ABORTED']
      retries: 60
      delay: 30
      failed_when: build_status.json.result != 'SUCCESS'
```

**`body_format: form-urlencoded`**
- Sends POST body as HTML form data (not JSON)
- Required for Jenkins API (uses form-based auth)

**`status_code: [201, 200]`**
- Accept multiple valid status codes
- Jenkins returns 201 for new builds, some endpoints return 200

**`| regex_search('(\\d+)/$', '\\1') | first`**
- Extracts build number from URL like `http://jenkins/job/myapp/42/`
- `(\\d+)/$` — Capture digits before trailing slash
- `'\\1'` — Return the first capture group
- `| first` — regex_search returns a list, get first match

---

## 📋 smoke-tests.yml — Post-Deployment Validation

```yaml
---
- name: Run post-deployment smoke tests
  hosts: localhost
  connection: local
  gather_facts: no
  vars:
    app_url: "https://{{ target_environment }}.example.com"
    test_timeout: 30

  tasks:
    - name: Test homepage loads
      uri:
        url: "{{ app_url }}"
        status_code: 200
        timeout: "{{ test_timeout }}"

    - name: Test API health endpoint
      uri:
        url: "{{ app_url }}/api/health"
        status_code: 200
        return_content: yes
      register: health
      failed_when: health.json.status != 'healthy'

    - name: Test version matches deployed version
      uri:
        url: "{{ app_url }}/api/version"
        return_content: yes
      register: version_check
      failed_when: version_check.json.version != deploy_version

    - name: Test authentication works
      uri:
        url: "{{ app_url }}/api/auth/login"
        method: POST
        body_format: json
        body:
          username: "{{ test_user }}"
          password: "{{ vault_test_password }}"
        status_code: 200
        return_content: yes
      register: auth_response
      no_log: true                       # Don't log credentials

    - name: Test authenticated endpoint
      uri:
        url: "{{ app_url }}/api/user/profile"
        headers:
          Authorization: "Bearer {{ auth_response.json.token }}"
        status_code: 200

    - name: Test response time is acceptable
      uri:
        url: "{{ app_url }}"
      register: timing
      failed_when: timing.elapsed > 2.0   # Fail if response takes > 2 seconds

    - name: Generate test report
      copy:
        content: |
          Smoke Test Report
          =================
          Environment: {{ target_environment }}
          Version: {{ deploy_version }}
          Timestamp: {{ ansible_date_time.iso8601 }}
          Results: ALL PASSED
          Response time: {{ timing.elapsed }}s
        dest: "reports/smoke-test-{{ ansible_date_time.epoch }}.txt"
```

**`timing.elapsed`**
- The `uri` module returns `elapsed` (response time in seconds)
- Validates performance as part of deployment check
- `failed_when: timing.elapsed > 2.0` — Fail if too slow

**`no_log: true`** on auth task
- Credentials would appear in verbose output without this
- Always use on tasks that handle passwords, tokens, or API keys

---

## 🔄 Complete CI/CD Flow with Ansible

```
Git push to main branch
         ↓
Jenkins pipeline triggered
         ↓
Stage 1: Unit tests (pytest)
         ↓ (if pass)
Stage 2: ansible-playbook deploy-from-git.yml --limit staging
  → git clone v1.2.3
  → pip install requirements
  → migrate DB (run_once)
  → update symlink (atomic)
  → restart service
         ↓
Stage 3: Integration tests against staging
         ↓ (if pass)
Stage 4: Manual approval (human clicks "Deploy")
         ↓
Stage 5: ansible-playbook blue-green-deploy.yml --limit production
  → Deploy to green (inactive)
  → Smoke tests on green
  → Switch LB → green (atomic)
  → Monitor 2 minutes
  → Error rate check
         ↓
Success: green is now live, blue kept for rollback
         ↓
Failure: auto-rollback → switch back to blue
```

---

## 🎯 Best Practices

### 1. Pin Versions via Git Tags
```yaml
# In Jenkins, pass the exact Git tag
ansible-playbook deploy.yml -e git_tag=v1.2.3

# In playbook
git:
  version: "{{ git_tag }}"
```

### 2. Atomic Symlink Switch
```yaml
# Atomic - old version still accessible until switch
file:
  src: "{{ deploy_dir }}"
  dest: /opt/myapp/current
  state: link
  force: yes    # Atomic replacement
```

### 3. Run Migrations Once Only
```yaml
- command: python manage.py migrate
  run_once: true   # One server migrates, all use the result
  delegate_to: "{{ groups['webservers'][0] }}"
```

### 4. Always Run Smoke Tests Before Full Traffic
```yaml
# Test inactive environment before switching LB
- uri:
    url: "http://green-internal/health"
    status_code: 200
  until: result.status == 200
  retries: 10
```

### 5. Auto-Rollback on Failure
```yaml
rescue:
  - name: Emergency rollback
    uri:
      url: "{{ lb_api }}/switch"
      body: {color: "{{ previous_color }}"}
```

---

## 🔍 Debugging Commands

```bash
# Test deployment to staging (dry run)
ansible-playbook deploy-from-git.yml --check --diff -e "git_tag=v1.2.3" --limit staging

# Deploy specific version
ansible-playbook deploy-from-git.yml -e "git_tag=v1.2.3 target_env=staging"

# Trigger blue/green switch
ansible-playbook blue-green-deploy.yml -e "deploy_version=v1.2.3"

# Emergency rollback
ansible-playbook rollback.yml -e "rollback_color=blue auto_rollback=true"

# Run smoke tests only
ansible-playbook smoke-tests.yml -e "target_environment=staging deploy_version=v1.2.3"

# Check what's currently deployed
ansible webservers -m command -a "cat /opt/myapp/current/VERSION"

# List all releases
ansible webservers -m find -a "paths=/opt/myapp/releases file_type=directory"
```

---

## 🎓 Key Takeaways

1. **`git: depth: 1`** — Shallow clone for fast deployments (no full history needed)
2. **Symlink atomic switch** — `/opt/app/current` symlink updated atomically; old version accessible for rollback
3. **`run_once: true`** — Database migrations run on one host, not all (prevents race conditions)
4. **`set_fact:` for color logic** — Compute active/inactive color once, reuse everywhere
5. **`until:` + version check** — Confirm the right version is live, not just any healthy response
6. **`no_log: true`** — Suppress output for tasks handling auth tokens and passwords
7. **`timing.elapsed`** — `uri` module returns response time; use for performance assertions
8. **`rescue:` for auto-rollback** — Any failure in the blue/green play triggers automatic switchback
9. **`| mandatory`** — Fail early with clear message when required variables aren't provided

---

*CI/CD pipeline automation with Ansible closes the loop between code and production. By codifying your deployment process as Ansible playbooks, you make it repeatable, testable, and trustworthy — the same play that works in staging works in production.*
