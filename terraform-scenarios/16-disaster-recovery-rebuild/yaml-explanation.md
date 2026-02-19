# Terraform Configuration Files Explanation - Disaster Recovery Rebuild

This guide explains the Terraform configuration patterns for disaster recovery, covering backup strategies, restore procedures, and the infrastructure-as-code principles that make DR actually achievable.

---

## Disaster Recovery Fundamentals

### RTO and RPO Explained

```
RTO (Recovery Time Objective):
   How long can the business tolerate the system being down?
   "We must be back online within 4 hours."

RPO (Recovery Point Objective):
   How much data loss is acceptable?
   "We can lose at most 1 hour of data."

Example targets:
  Tier 1 (critical): RTO < 1hr, RPO < 15min
  Tier 2 (important): RTO < 4hr, RPO < 1hr
  Tier 3 (standard):  RTO < 24hr, RPO < 24hr
```

### Why Terraform Enables Real DR
Without IaC, rebuilding infrastructure during a disaster requires:
- Remembering every resource that existed
- Manually recreating configurations
- Hoping documentation was kept up to date

With Terraform:
- Your `.tf` files ARE the documentation
- `terraform apply` rebuilds the entire infrastructure
- DR test = running `terraform apply` in a new account/region
- RTO is bounded by the time Terraform takes to run

---

## aws_backup_plan - Automated Backups

### What is AWS Backup?
AWS Backup provides a centralized service to automate backups across AWS services: RDS, EBS, EFS, DynamoDB, S3, EC2, and more. Define backup policies once, apply them to many resources.

### HCL Structure Breakdown:

```hcl
resource "aws_backup_plan" "production" {
  name = "production-backup-plan"

  rule {
    rule_name         = "daily-backups"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 3 * * ? *)"  # 3 AM UTC daily

    lifecycle {
      delete_after = 30  # Keep daily backups for 30 days
    }

    recovery_point_tags = {
      BackupType  = "daily"
      Environment = "production"
    }
  }

  rule {
    rule_name         = "weekly-backups"
    target_vault_name = aws_backup_vault.long_term.name
    schedule          = "cron(0 3 ? * 1 *)"  # Every Sunday 3 AM UTC

    lifecycle {
      cold_storage_after = 30   # Move to cold storage after 30 days
      delete_after       = 365  # Keep for 1 year
    }
  }

  advanced_backup_setting {
    backup_options = {
      WindowsVSS = "enabled"
    }
    resource_type = "EC2"
  }
}

resource "aws_backup_vault" "main" {
  name        = "production-backup-vault"
  kms_key_arn = aws_kms_key.backup.arn

  tags = {
    Environment = "production"
  }
}

resource "aws_backup_vault_lock_configuration" "main" {
  backup_vault_name   = aws_backup_vault.main.name
  min_retention_days  = 7
  max_retention_days  = 90
  changeable_for_days = 3  # Vault lock becomes immutable after 3 days
}
```

**`schedule`:** AWS EventBridge cron expression. Format: `cron(minutes hours day-of-month month day-of-week year)`.
**`lifecycle.delete_after`:** Days to retain the backup.
**`lifecycle.cold_storage_after`:** Days before moving to cold storage (cheaper but slower restore).
**`aws_backup_vault_lock_configuration`:** Vault Lock makes backups immutable — protection against ransomware that tries to delete backups.

### aws_backup_selection - What to Back Up:

```hcl
resource "aws_backup_selection" "production" {
  name         = "production-resources"
  plan_id      = aws_backup_plan.production.id
  iam_role_arn = aws_iam_role.backup.arn

  # Tag-based selection — back up everything tagged with Backup=true
  selection_tag {
    type  = "STRINGEQUALS"
    key   = "Backup"
    value = "true"
  }

  # Specific resource ARNs
  resources = [
    aws_db_instance.main.arn,
    aws_efs_file_system.data.arn,
  ]
}
```

**Tag-based selection** is powerful — add `Backup = "true"` to any resource and it automatically gets backed up. No need to update the Terraform configuration when adding new resources.

---

## data "aws_ami" - Finding the Latest AMI

### What is an AMI Data Source?
Rather than hardcoding AMI IDs (which vary by region and become outdated), use the `aws_ami` data source to dynamically find the right AMI.

### HCL Structure Breakdown:

```hcl
# Find your organization's latest validated AMI
data "aws_ami" "app" {
  most_recent = true
  owners      = ["self"]  # Your own account's AMIs

  filter {
    name   = "name"
    values = ["app-server-*"]  # AMIs named "app-server-*"
  }

  filter {
    name   = "tag:Environment"
    values = ["production"]
  }

  filter {
    name   = "tag:Validated"
    values = ["true"]  # Only AMIs that passed validation
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# Find the latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Use the AMI
resource "aws_instance" "app" {
  ami           = data.aws_ami.app.id
  instance_type = "m5.large"

  # ...
}
```

**`most_recent = true`:** If multiple AMIs match, use the newest.
**`owners`:** `"self"` = your account, `"amazon"` = Amazon-owned, `"aws-marketplace"` = marketplace.
**`filter` blocks:** Narrow down by name pattern, tags, architecture, state, etc.

**AMI Golden Image Pipeline:**
1. Packer builds AMI from base AMI + application code
2. Automated tests validate the AMI
3. Tags `Validated = true` on success
4. Terraform finds the latest validated AMI via data source
5. `terraform apply` uses the new AMI (rolling update or blue-green)

---

## Restoring from RDS Snapshots

### HCL for Snapshot-Based Restore:

```hcl
# Find the latest automated snapshot
data "aws_db_snapshot" "latest" {
  db_instance_identifier = "production-postgres"
  most_recent            = true
  snapshot_type          = "automated"
}

# Restore from snapshot (creates new DB instance)
resource "aws_db_instance" "restored" {
  identifier        = "production-postgres-restored"
  snapshot_identifier = data.aws_db_snapshot.latest.id

  # These must match or be compatible with the snapshot
  instance_class    = "db.r6g.large"
  storage_encrypted = true

  # Override network settings for the new environment
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Don't re-take a snapshot of the restore target
  skip_final_snapshot = true

  # Disable deletion protection during DR testing (re-enable after)
  deletion_protection = false

  lifecycle {
    ignore_changes = [snapshot_identifier]  # Don't replace when new snapshot is available
  }
}
```

**`snapshot_identifier`:** The snapshot to restore from. Using the data source ensures you always restore from the latest.
**`lifecycle { ignore_changes = [snapshot_identifier] }`:** After initial restore, don't replace the instance when a newer snapshot becomes available — that would destroy your running restored database.

---

## terraform graph - Visualizing Dependencies

### What is terraform graph?
Generates a DOT language representation of the Terraform dependency graph. Useful for understanding complex infrastructure and debugging circular dependency errors.

### Commands:

```bash
# Generate dependency graph
terraform graph | dot -Tpng > graph.png

# Generate plan graph (shows what will change)
terraform graph -type=plan | dot -Tsvg > plan-graph.svg

# Generate destroy graph (shows destroy order)
terraform graph -type=plan-destroy | dot -Tpng > destroy-graph.png
```

**Requires Graphviz:**
```bash
# Install Graphviz
sudo apt-get install graphviz  # Ubuntu/Debian
brew install graphviz           # macOS
```

**Reading the graph:**
- Arrows point from dependent → dependency
- Resources are evaluated in reverse arrow direction (dependency first)
- Parallel branches can be created/destroyed simultaneously

---

## DR Runbook in Terraform

### Using Locals and Outputs as Documentation:

```hcl
locals {
  dr_runbook = {
    rto_target = "4 hours"
    rpo_target = "1 hour"

    steps = [
      "1. Declare disaster: notify stakeholders",
      "2. Activate DR: cd dr-region && terraform apply",
      "3. Verify: run smoke tests against DR endpoint",
      "4. Update DNS: change Route53 weights to DR region",
      "5. Communicate: notify users of DR activation",
      "6. Monitor: watch error rates and latency",
      "7. Recovery: when primary is restored, run failback procedure",
    ]

    contacts = {
      incident_commander = "oncall@example.com"
      database_team      = "dba@example.com"
      networking_team    = "netops@example.com"
    }
  }
}

output "dr_runbook" {
  description = "Disaster Recovery runbook for this environment"
  value       = local.dr_runbook
}
```

**Why embed runbooks in Terraform?**
- Runbooks stay in version control alongside the infrastructure they describe
- `terraform output dr_runbook` shows the runbook at any time
- Changes to infrastructure and runbook are reviewed together in PRs

---

## terraform test - Native Infrastructure Testing (Terraform 1.6+)

### What is terraform test?
Terraform 1.6 introduced native testing with `.tftest.hcl` files. Write tests that create real infrastructure, run assertions, and clean up.

### HCL Structure Breakdown:

```hcl
# tests/s3.tftest.hcl
run "s3_bucket_exists_and_versioned" {
  command = plan

  assert {
    condition     = aws_s3_bucket.main.bucket == "my-production-bucket"
    error_message = "S3 bucket name is incorrect"
  }

  assert {
    condition     = aws_s3_bucket_versioning.main.versioning_configuration[0].status == "Enabled"
    error_message = "S3 bucket versioning must be enabled"
  }
}

run "apply_and_verify" {
  command = apply

  assert {
    condition     = output.bucket_arn != ""
    error_message = "bucket_arn output must not be empty"
  }
}
```

**`command = plan`:** Run assertions against the plan (fast, no real resources created).
**`command = apply`:** Actually create infrastructure, run assertions, then destroy.

### Running Tests:
```bash
terraform test              # Run all .tftest.hcl files
terraform test -filter=s3   # Run only tests matching "s3"
```

### Best Practices for Disaster Recovery:
- Test DR regularly — at least quarterly (some organizations do monthly)
- Document the actual observed RTO/RPO from DR tests
- Keep DR infrastructure costs low by using smaller instance sizes and scale up only during actual DR
- Use separate AWS accounts for DR (not just separate VPCs) — account-level isolation protects against account-level issues
- Automate DR activation — reduce human error during high-stress scenarios
- Practice failback as much as failover — many teams test DR but never practice returning to primary
- The best DR test is an unannounced one — if your team can't execute the runbook without preparation, it's not ready
