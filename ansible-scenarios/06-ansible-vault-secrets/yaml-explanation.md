# YAML Files Explanation - Ansible Vault: Secrets Management

This guide explains the Ansible Vault file formats, encrypted variable files, and playbook patterns for securely managing secrets.

---

## 🔐 What is Ansible Vault?

Ansible Vault encrypts sensitive data (passwords, API keys, certificates) using AES-256 encryption. Encrypted files are safe to commit to Git — they're unreadable without the vault password.

**The problem Vault solves:**
```yaml
# BAD - Never commit plaintext secrets to Git!
db_password: SuperSecret123
api_key: sk-prod-abc123xyz
ssl_private_key: |
  -----BEGIN RSA PRIVATE KEY-----
  ...
```

```yaml
# GOOD - Encrypted with Vault (safe to commit)
$ANSIBLE_VAULT;1.1;AES256
61376461303265613063393...
```

---

## 📄 vault.yml — Encrypted Variables File

### What is a Vault File?
A YAML file encrypted with Ansible Vault. When Ansible reads it, it automatically decrypts the content if the correct password is provided.

### Creating a Vault File:
```bash
# Create new encrypted file
ansible-vault create group_vars/all/vault.yml

# Edit existing encrypted file
ansible-vault edit group_vars/all/vault.yml

# Encrypt an existing plaintext file
ansible-vault encrypt secrets.yml

# Decrypt to plaintext (careful — don't commit!)
ansible-vault decrypt secrets.yml

# View contents without decrypting to disk
ansible-vault view group_vars/all/vault.yml
```

### Vault File Content (before encryption):
```yaml
# group_vars/all/vault.yml (content before ansible-vault encrypt)
---
vault_db_password: "SuperSecret123!"
vault_api_key: "sk-prod-abc123xyz789"
vault_redis_password: "R3disP@ssw0rd"
vault_jwt_secret: "jwt-secret-key-32-chars-minimum"

# SSL/TLS certificates
vault_ssl_certificate: |
  -----BEGIN CERTIFICATE-----
  MIIDazCCAlOgAwIBAgIUe...
  -----END CERTIFICATE-----

vault_ssl_private_key: |
  -----BEGIN RSA PRIVATE KEY-----
  MIIEowIBAAKCAQEA...
  -----END RSA PRIVATE KEY-----
```

**Naming convention: `vault_` prefix**
- All vault variables prefixed with `vault_` (industry convention)
- Easy to identify which variables are sensitive
- Reference in non-vault files: `db_password: "{{ vault_db_password }}"`

---

## 📋 vars.yml — Plaintext Variables (References Vault)

### Best Practice: Separate Plaintext and Encrypted Variables

```yaml
# group_vars/all/vars.yml (PLAINTEXT - safe to commit)
---
db_host: "postgres.example.com"
db_port: 5432
db_name: "myapp_production"
db_user: "myapp_user"
db_password: "{{ vault_db_password }}"    # References vault variable

api_endpoint: "https://api.example.com"
api_key: "{{ vault_api_key }}"            # References vault variable

app_config:
  debug: false
  log_level: INFO
  max_connections: 100
  secret_key: "{{ vault_jwt_secret }}"    # References vault variable
```

**Why split into two files?**
- `vars.yml` — Visible, reviewable, shows structure without exposing values
- `vault.yml` — Encrypted, contains actual secrets
- Code reviewers see the variable names and usage without seeing values
- Easy to audit what's secret vs what's just config

---

## 🎭 deploy-secrets.yml — Playbook Using Vault Variables

### Complete Vault-Aware Playbook:

```yaml
---
- name: Deploy application with encrypted secrets
  hosts: webservers
  become: yes
  vars_files:
    - group_vars/all/vars.yml        # Load plaintext vars
    - group_vars/all/vault.yml       # Load encrypted vars (auto-decrypted)
  tasks:
    - name: Deploy database configuration
      template:
        src: templates/database.conf.j2
        dest: /etc/myapp/database.conf
        owner: www-data
        mode: '0640'            # Restricted: secret file

    - name: Deploy API configuration
      template:
        src: templates/api.conf.j2
        dest: /etc/myapp/api.conf
        owner: www-data
        mode: '0640'

    - name: Deploy SSL certificate
      copy:
        content: "{{ vault_ssl_certificate }}"
        dest: /etc/ssl/certs/myapp.crt
        owner: root
        mode: '0644'

    - name: Deploy SSL private key
      copy:
        content: "{{ vault_ssl_private_key }}"
        dest: /etc/ssl/private/myapp.key
        owner: root
        mode: '0600'            # Private key: owner-only readable
      no_log: true              # Don't show key content in output
```

**`vars_files:`**
- Explicitly load variable files for this play
- Vault files are automatically decrypted if vault password provided
- **Alternative:** Put vault files in `group_vars/` and they load automatically

**`mode: '0640'`** for config with secrets
- Owner: read/write (www-data)
- Group: read only (www-data group)
- Others: no access
- Prevents other users from reading secrets

**`mode: '0600'`** for private keys
- Owner only: read/write
- Group: no access
- Others: no access
- SSL requires this strict permission

**`no_log: true`**
- Suppresses task output to prevent secrets appearing in logs
- **Critical for:** Tasks that output passwords, keys, tokens
- Use on any task that handles `vault_*` variables directly

---

## 🔑 Multiple Vault IDs (Multi-Environment)

### What are Vault IDs?
Different vault passwords for different environments. Dev uses one password, production uses another.

```bash
# Create dev vault with 'dev' label
ansible-vault create --vault-id dev@prompt group_vars/dev/vault.yml

# Create prod vault with 'prod' label
ansible-vault create --vault-id prod@prompt group_vars/prod/vault.yml

# Run with multiple vault passwords
ansible-playbook site.yml \
  --vault-id dev@~/.vault-pass-dev \
  --vault-id prod@~/.vault-pass-prod
```

### Dev Vault (group_vars/dev/vault.yml):
```yaml
# Dev secrets (lower security requirements)
vault_db_password: "devpassword123"
vault_api_key: "test-api-key-not-real"
```

### Prod Vault (group_vars/prod/vault.yml):
```yaml
# Prod secrets (different password, rotated regularly)
vault_db_password: "Tr$3c0mpl3xPr0dPw!"
vault_api_key: "sk-prod-real-key-keep-secret"
```

**Header shows vault ID:**
```
$ANSIBLE_VAULT;1.2;AES256;dev   ← 'dev' vault ID label
61376461303265613...
```

---

## 🔄 Credential Rotation Playbook

### Rotating Secrets Without Downtime:

```yaml
---
- name: Rotate database password
  hosts: databases
  become: yes
  vars_files:
    - vault.yml
  tasks:
    - name: Generate new password
      set_fact:
        new_db_password: "{{ lookup('password', '/dev/null length=32 chars=ascii_letters,digits') }}"
      run_once: true    # Generate once, use everywhere

    - name: Update database password
      community.postgresql.postgresql_user:
        name: "{{ db_user }}"
        password: "{{ new_db_password }}"
      become_user: postgres

    - name: Update vault file with new password
      delegate_to: localhost    # Run on control machine
      community.general.yaml_edit:
        path: vault.yml
        key: vault_db_password
        value: "{{ new_db_password }}"

    - name: Re-encrypt vault
      delegate_to: localhost
      command: ansible-vault encrypt vault.yml
```

**`run_once: true`**
- Executes the task on only the first host in the group
- Result is shared with all hosts (via `set_fact`)
- Useful for generating shared values (passwords, tokens)

**`delegate_to: localhost`**
- Run this task on the control machine, not the remote host
- Used here to update the vault file on the machine running ansible-playbook

---

## 📱 Using Vault with lookup() Plugin

### Reading Vault Secrets Dynamically:

```yaml
tasks:
  - name: Configure app with vault secret from file
    template:
      src: app.conf.j2
      dest: /etc/myapp/app.conf
    vars:
      # Read from Vault-encrypted file at runtime
      api_token: "{{ lookup('file', 'secrets/api_token.txt') | vault_decrypt }}"

  - name: Use password lookup
    debug:
      msg: "Password: {{ lookup('password', 'credentials/db length=20') }}"
      # Generates and stores password in 'credentials/db' file
```

---

## 🔐 Vault Best Practices Playbook Structure

### Recommended Directory Layout:

```
ansible-project/
├── site.yml
├── group_vars/
│   ├── all/
│   │   ├── vars.yml          ← Plaintext (commit to git)
│   │   └── vault.yml         ← ENCRYPTED (safe to commit)
│   ├── production/
│   │   ├── vars.yml          ← Plaintext prod config
│   │   └── vault.yml         ← Prod secrets (different vault password)
│   └── staging/
│       ├── vars.yml          ← Staging config
│       └── vault.yml         ← Staging secrets
├── .gitignore                ← Contains: .vault-pass, *.tmp
└── .vault-pass               ← DO NOT COMMIT (in .gitignore)
```

### .gitignore for Ansible Projects:
```gitignore
# Vault passwords - NEVER commit these
.vault-pass
.vault-pass-dev
.vault-pass-prod
vault-pass.txt

# Decrypted secrets (if accidentally created)
*.decrypted
secrets.yml.bak

# Retry files
*.retry
```

---

## 🔍 Debugging Vault Issues

```bash
# Verify vault file is encrypted
head -1 group_vars/all/vault.yml
# Should show: $ANSIBLE_VAULT;1.1;AES256

# Test vault password
ansible-vault view group_vars/all/vault.yml --ask-vault-pass

# Use password file instead of prompt
ansible-vault view group_vars/all/vault.yml --vault-password-file .vault-pass

# Run playbook with vault password
ansible-playbook site.yml --ask-vault-pass

# Run with vault password file (CI/CD friendly)
ansible-playbook site.yml --vault-password-file ~/.vault-pass

# Re-key vault (change vault password)
ansible-vault rekey group_vars/all/vault.yml
# Asks for old password, then new password

# Check which variables are in vault
ansible-vault view vault.yml | grep "vault_"

# Debug: show variable value (careful in production!)
ansible webservers -m debug -a "var=db_password" --ask-vault-pass
```

---

## 🎯 Best Practices Summary

### 1. Always Use `no_log: true` for Secret Tasks
```yaml
- name: Set database password
  community.postgresql.postgresql_user:
    name: myapp
    password: "{{ vault_db_password }}"
  no_log: true        # Password won't appear in logs/output
```

### 2. Restrict Permissions on Deployed Secret Files
```yaml
- name: Deploy .env file with secrets
  template:
    src: .env.j2
    dest: /opt/myapp/.env
    owner: www-data
    group: www-data
    mode: '0600'        # Owner only
```

### 3. Never Decrypt to Disk on CI/CD
```bash
# BAD - Decrypted file on disk
ansible-vault decrypt vault.yml
ansible-playbook site.yml

# GOOD - Vault password from environment variable
export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault-pass
ansible-playbook site.yml
# Vault is decrypted in memory only, never written to disk
```

### 4. Rotate Vault Passwords Regularly
```bash
# Change vault password without changing encrypted content
ansible-vault rekey --new-vault-password-file new-pass.txt vault.yml
```

### 5. Use `prefix: vault_` Convention
```yaml
# In vault.yml (encrypted)
vault_db_password: "secret123"

# In vars.yml (plaintext reference)
db_password: "{{ vault_db_password }}"
```

---

## 🎓 Key Takeaways

1. **Vault = AES-256 encryption** for sensitive variables — safe to commit to Git
2. **`vault_` prefix convention** — easy to identify which variables are secrets
3. **Separate `vars.yml` + `vault.yml`** — structure visible, values encrypted
4. **`no_log: true`** — prevent secrets from appearing in logs/output
5. **`mode: '0600'`** for secret files — only the owner can read them
6. **Multiple vault IDs** — different passwords per environment (dev/staging/prod)
7. **`delegate_to: localhost`** — run tasks on control machine (updating vault files, git commits)
8. **Never commit `.vault-pass`** — add to `.gitignore`, store in secrets manager

---

*Ansible Vault is the standard way to manage secrets in Ansible. Combined with Git, it provides version-controlled, encrypted secret management without a separate secrets manager.*
