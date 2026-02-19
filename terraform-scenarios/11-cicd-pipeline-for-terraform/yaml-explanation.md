# Terraform Configuration Files Explanation - CI/CD Pipeline for Terraform

This guide explains the configuration patterns, commands, and concepts used when integrating Terraform into CI/CD pipelines, breaking down every step and setting with context for production use.

---

## The Terraform CI/CD Workflow

### Overview
A production Terraform CI/CD pipeline typically follows this flow:

```
PR opened
    └── terraform fmt -check        (formatting check)
    └── terraform validate          (syntax + logic check)
    └── terraform plan              (show changes, save to file)
    └── Post plan as PR comment     (review before merge)

PR merged to main
    └── terraform apply tfplan      (apply the saved plan)
    └── Notify on success/failure
```

### Why This Order?
1. **fmt** — Fast, no API calls, catches style issues early
2. **validate** — Fast, no API calls, catches config errors
3. **plan** — Requires AWS credentials, shows exactly what will change
4. **apply** — Only runs the approved plan (not a fresh plan)

The key insight: **apply the saved plan file**, not a fresh plan. This ensures exactly what was reviewed gets applied, even if configuration changed between plan and apply.

---

## terraform fmt - Code Formatting

### What does terraform fmt do?
`terraform fmt` reformats HCL files to the canonical Terraform style. It's like `gofmt`, `prettier`, or `black` for Terraform.

### Commands:

```bash
# Format all .tf files in current directory and subdirectories
terraform fmt -recursive

# Check formatting without making changes (exit code 0 = OK, 3 = needs formatting)
terraform fmt -check -recursive

# Show which files would be changed
terraform fmt -check -diff -recursive
```

**In CI, use `-check` flag:**

```yaml
# GitHub Actions step
- name: Check Terraform formatting
  run: terraform fmt -check -recursive
  # Fails the pipeline if any file is not formatted
```

**Why enforce formatting in CI?**
- Consistent code style across all team members
- Reduces noise in code reviews (no style debates)
- Makes diffs cleaner (only logic changes, not whitespace)

### What terraform fmt fixes:
- Indentation (2 spaces)
- Spacing around `=` signs
- Alignment of `=` signs in blocks
- Blank lines between blocks

---

## terraform validate - Configuration Validation

### What does terraform validate do?
Validates the syntax and logical consistency of your Terraform configuration without making any API calls. It checks:
- Valid HCL syntax
- Required arguments are present
- Argument types match expected types
- References to undefined resources or variables
- Circular dependencies

### Commands:

```bash
# Validate current directory
terraform validate

# Output as JSON (for CI parsing)
terraform validate -json
```

**Output:**
```json
{
  "valid": false,
  "error_count": 1,
  "warning_count": 0,
  "diagnostics": [{
    "severity": "error",
    "summary": "Reference to undeclared resource",
    "detail": "A managed resource \"aws_vpc\" \"main\" has not been declared...",
    "range": {
      "filename": "main.tf",
      "start": { "line": 12, "column": 15 }
    }
  }]
}
```

**Requirements:** Must run `terraform init` first (provider schemas are needed for validation).

### What validate does NOT check:
- Whether your AWS credentials are valid
- Whether resources actually exist in AWS
- Whether your IAM permissions are sufficient
- Cost of the infrastructure

---

## terraform plan -out - Saving Plans

### Why Save the Plan?

```bash
# Generate and save plan to file
terraform plan -out=tfplan

# Apply the EXACT saved plan (no confirmation required)
terraform apply tfplan

# View the saved plan as JSON (for automation/PR comments)
terraform show -json tfplan | jq '.resource_changes'
```

**The Problem with not saving plans:**
1. PR review shows plan at time of `plan` command
2. Someone merges another PR between plan and apply
3. Apply now shows a different plan than what was reviewed
4. Unexpected changes slip through

**With saved plans:**
1. `terraform plan -out=tfplan` captures the exact planned changes
2. Reviewer approves the plan
3. `terraform apply tfplan` applies exactly that plan — no surprises

### Plan Files in CI:

```yaml
# GitHub Actions example
- name: Terraform Plan
  run: terraform plan -out=tfplan -no-color 2>&1 | tee plan-output.txt

- name: Upload Plan
  uses: actions/upload-artifact@v3
  with:
    name: tfplan
    path: |
      tfplan
      plan-output.txt

- name: Comment Plan on PR
  uses: actions/github-script@v6
  with:
    script: |
      const fs = require('fs');
      const plan = fs.readFileSync('plan-output.txt', 'utf8');
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '```hcl\n' + plan + '\n```'
      });
```

---

## .terraform.lock.hcl in CI

### Why the Lock File Matters in CI

```hcl
# .terraform.lock.hcl (commit this to git!)
provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.72.1"
  constraints = "~> 5.0"
  hashes = [
    "h1:abc123...",
    "zh:def456...",
  ]
}
```

**`version`:** The exact installed version.
**`constraints`:** The version constraint from your configuration.
**`hashes`:** Cryptographic hashes for each platform's provider binary.

### Lock File in CI:

```bash
# In CI, use -lockfile=readonly to enforce the lock file
# Fails if providers don't match the lock file
terraform init -lockfile=readonly

# This prevents:
# - Accidentally upgrading providers in CI
# - Different provider versions between dev and CI
# - "It works on my machine" provider version issues
```

**Always commit `.terraform.lock.hcl` to version control.** It's the Terraform equivalent of `package-lock.json` or `Gemfile.lock`.

---

## Environment Variables in CI

### TF_VAR_* - Setting Variables Without -var Flags

```bash
# Instead of:
terraform plan -var="db_password=secret" -var="environment=prod"

# Use environment variables (safer, don't appear in command history)
export TF_VAR_db_password="secret"
export TF_VAR_environment="prod"
terraform plan
```

**Naming convention:** `TF_VAR_` prefix + variable name (exact case match).

### Other Terraform Environment Variables:

```bash
# AWS credentials (automatically picked up)
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"

# Logging
export TF_LOG="DEBUG"        # TRACE, DEBUG, INFO, WARN, ERROR
export TF_LOG_PATH="/tmp/terraform.log"

# Disable color output (for CI logs)
export TF_CLI_ARGS_plan="-no-color"
export TF_CLI_ARGS_apply="-no-color"

# Auto-approve (use carefully!)
export TF_CLI_ARGS_apply="-auto-approve -no-color"

# Workspace
export TF_WORKSPACE="production"
```

---

## Backend Configuration in CI

### Partial Backend Configuration

```hcl
# backend.tf - partial config (safe to commit)
terraform {
  backend "s3" {
    # Don't hardcode sensitive values here
    # Pass them at init time
  }
}
```

```bash
# CI: Pass backend config at init time
terraform init \
  -backend-config="bucket=my-terraform-state-prod" \
  -backend-config="key=production/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=terraform-state-lock"
```

**Why partial config?**
- Different environments use different S3 buckets
- Sensitive values (bucket names, account IDs) not hardcoded in git
- Same configuration can be used across environments

### CI Backend Config Files:

```bash
# Create per-environment backend config files
# backends/production.hcl
bucket         = "my-terraform-state-prod"
key            = "production/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-lock-prod"
encrypt        = true

# Usage in CI
terraform init -backend-config=backends/production.hcl
```

---

## OIDC Authentication - GitHub Actions to AWS

### What is OIDC?
OpenID Connect (OIDC) allows GitHub Actions to assume AWS IAM roles without storing long-lived AWS credentials as secrets. GitHub gets a short-lived JWT token that AWS verifies.

### HCL for the OIDC Provider:

```hcl
# Create OIDC provider in AWS
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

# IAM Role that GitHub Actions can assume
resource "aws_iam_role" "github_actions" {
  name = "github-actions-terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github_actions.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # Only allow from specific repo and branch
          "token.actions.githubusercontent.com:sub" = "repo:myorg/myrepo:ref:refs/heads/main"
        }
      }
    }]
  })
}
```

### GitHub Actions Workflow:

```yaml
# .github/workflows/terraform.yml
name: Terraform CI/CD

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  id-token: write   # Required for OIDC
  contents: read
  pull-requests: write

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS Credentials (OIDC - no stored secrets!)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-terraform
          aws-region: us-east-1

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1.5"

      - name: Terraform Init
        run: terraform init -lockfile=readonly

      - name: Terraform Fmt Check
        run: terraform fmt -check -recursive

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        id: plan
        run: terraform plan -no-color -out=tfplan

      - name: Terraform Apply (main branch only)
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve tfplan
```

**Benefits of OIDC:**
- No AWS credentials stored as GitHub secrets
- Short-lived tokens (1 hour max)
- Scoped to specific repos and branches
- Full audit trail in CloudTrail

---

## TF_LOG - Debugging CI Failures

### Log Levels:

```bash
export TF_LOG=TRACE   # Most verbose — provider HTTP calls, all internals
export TF_LOG=DEBUG   # Detailed provider calls
export TF_LOG=INFO    # Normal operation messages
export TF_LOG=WARN    # Warnings only
export TF_LOG=ERROR   # Errors only (least verbose)
```

**For CI debugging:**
```yaml
- name: Terraform Plan (with debug logging)
  env:
    TF_LOG: DEBUG
    TF_LOG_PATH: /tmp/terraform-debug.log
  run: terraform plan -out=tfplan

- name: Upload Debug Logs
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: terraform-debug-logs
    path: /tmp/terraform-debug.log
```

**Warning:** `TRACE` log level includes API requests and responses which may contain sensitive data. Never upload trace logs publicly.

### Best Practices for Terraform CI/CD:
- Always use OIDC instead of long-lived credentials
- Always save and apply plan files (never `apply -auto-approve` without a plan file)
- Run `fmt -check` and `validate` on every PR
- Post plan output as PR comment for review
- Use separate AWS accounts for each environment (not just workspaces)
- Enable Terraform state locking to prevent concurrent applies
- Set `TF_CLI_ARGS_plan="-no-color"` in CI for cleaner logs
