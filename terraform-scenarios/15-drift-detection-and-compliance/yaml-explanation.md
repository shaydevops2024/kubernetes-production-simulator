# Terraform Configuration Files Explanation - Drift Detection and Compliance

This guide explains the Terraform configuration patterns for detecting infrastructure drift, enforcing compliance policies, and validating configurations before and after deployment.

---

## Understanding Drift in Terraform

### What is Infrastructure Drift?
Drift occurs when your real infrastructure diverges from your Terraform configuration and state. Common causes:
- Manual changes via AWS Console (ClickOps)
- Other automation tools modifying resources
- AWS services auto-modifying resource attributes
- Security teams making emergency changes
- Expired certificates auto-renewed by AWS

### Types of Drift:

```
Terraform Config ← (what you want)
Terraform State  ← (what Terraform thinks exists)
Real Infrastructure ← (what actually exists)

Scenario 1: State matches config, but reality differs
   → AWS Console change not reflected in state

Scenario 2: State differs from config (planned change)
   → terraform plan shows changes pending

Scenario 3: All three differ
   → Requires both state refresh + configuration update
```

---

## terraform apply -refresh-only - Detecting Drift

### What does -refresh-only do?
Updates Terraform state to match real infrastructure, but does NOT create/modify/delete any resources. It shows you what has drifted and lets you decide what to do.

### Commands:

```bash
# Preview drift (no state changes, just show what differs)
terraform plan -refresh-only

# Apply state refresh (updates state to match reality)
terraform apply -refresh-only

# Example output showing drift:
# ~ aws_security_group.web has been changed
#   ~ ingress = [
#       + {
#           cidr_blocks = ["10.0.0.0/8"]
#           from_port   = 22
#           to_port     = 22
#         }  # SSH rule added manually
#     ]
```

### After Detecting Drift:

**Option A — Accept the drift (update .tf config to match reality):**
```hcl
# Add the manually-added SSH rule to your configuration
resource "aws_security_group_rule" "ssh_internal" {
  type        = "ingress"
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/8"]
  security_group_id = aws_security_group.web.id
}
```

**Option B — Reject the drift (run terraform apply to revert to config):**
```bash
# Plan shows it will REMOVE the manually-added SSH rule
terraform plan
# After reviewing, apply to restore desired state
terraform apply
```

**Option C — Ignore drift (lifecycle ignore_changes):**
```hcl
resource "aws_security_group" "web" {
  lifecycle {
    ignore_changes = [ingress]  # Ignore all ingress rule changes
  }
}
```

---

## precondition and postcondition - Validation at Plan Time

### What are precondition and postcondition?
Introduced in Terraform 1.2, these blocks add validation checks to resources and data sources:
- `precondition`: Checked BEFORE creating/modifying the resource (at plan time)
- `postcondition`: Checked AFTER the resource is created/modified

### HCL Structure Breakdown:

```hcl
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = var.instance_type

  lifecycle {
    precondition {
      condition     = contains(["t3.medium", "m5.large", "m5.xlarge"], var.instance_type)
      error_message = "Instance type must be t3.medium, m5.large, or m5.xlarge for production."
    }

    precondition {
      condition     = var.environment == "production" ? var.enable_monitoring : true
      error_message = "Monitoring must be enabled in production environments."
    }

    postcondition {
      condition     = self.public_ip == null
      error_message = "Web instances must not have public IPs. Check subnet configuration."
    }
  }
}

data "aws_ami" "app" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["app-*"]
  }

  lifecycle {
    postcondition {
      condition     = self.tags["Validated"] == "true"
      error_message = "AMI must be validated before use in production. Tag 'Validated=true' is missing."
    }
  }
}
```

**`condition`:** A boolean expression. If `false`, Terraform stops with the error message.
**`error_message`:** Human-readable message explaining what failed and how to fix it.
**`self`:** In `postcondition`, refers to the resource's current attributes after creation.

**Benefits:**
- Catch configuration errors before deploying
- Enforce policies without external policy-as-code tools
- Self-documenting — the error message explains the rule

---

## check Block - Non-Blocking Assertions (Terraform 1.5+)

### What is the check Block?
Unlike `precondition`, a `check` block failure does NOT block apply. It generates a warning and continues. Useful for assertions that should be visible but not blocking.

### HCL Structure Breakdown:

```hcl
check "s3_bucket_versioning" {
  assert {
    condition     = aws_s3_bucket_versioning.main.versioning_configuration[0].status == "Enabled"
    error_message = "S3 bucket versioning should be enabled for production data protection."
  }
}

check "rds_backup_retention" {
  assert {
    condition     = aws_db_instance.main.backup_retention_period >= 7
    error_message = "RDS backup retention should be at least 7 days. Current: ${aws_db_instance.main.backup_retention_period}"
  }
}

# Checks can use data sources to validate external resources
check "certificate_expiry" {
  data "http" "cert_check" {
    url = "https://api.example.com/health"
  }

  assert {
    condition     = data.http.cert_check.status_code == 200
    error_message = "Health check endpoint returned ${data.http.cert_check.status_code}, expected 200."
  }
}
```

**When to use `check` vs `precondition`:**
- `precondition`: Hard requirements — configuration is wrong if this fails (blocks apply)
- `check`: Soft requirements — something is non-ideal but recoverable (warns but continues)
- `check`: External validations — website is up, certificate valid, DNS resolves (can't block apply since external)

---

## aws_config_rule - AWS Config Compliance Rules

### What is AWS Config?
AWS Config continuously records resource configuration changes and evaluates them against your rules. It provides a compliance audit trail — who changed what, when, and does it comply with your policies?

### HCL Structure Breakdown:

```hcl
# Enable Config recording
resource "aws_config_configuration_recorder" "main" {
  name     = "production-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

# Deliver Config snapshots to S3
resource "aws_config_delivery_channel" "main" {
  name           = "production-delivery"
  s3_bucket_name = aws_s3_bucket.config.bucket
  sns_topic_arn  = aws_sns_topic.config_alerts.arn

  snapshot_delivery_properties {
    delivery_frequency = "TwentyFour_Hours"
  }

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_configuration_recorder_status" "main" {
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true
  depends_on = [aws_config_delivery_channel.main]
}

# Managed rule: Ensure EBS volumes are encrypted
resource "aws_config_rule" "ebs_encryption" {
  name        = "ebs-volume-encrypted"
  description = "Checks whether EBS volumes are encrypted."

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }

  depends_on = [aws_config_configuration_recorder_status.main]
}

# Managed rule: Ensure S3 buckets are not public
resource "aws_config_rule" "s3_no_public_read" {
  name        = "s3-bucket-no-public-read"
  description = "Checks that S3 buckets do not allow public read access."

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_PUBLIC_READ_PROHIBITED"
  }
}

# Custom rule using Lambda
resource "aws_config_rule" "required_tags" {
  name        = "required-tags"
  description = "Checks that all resources have required tags."

  source {
    owner             = "CUSTOM_LAMBDA"
    source_identifier = aws_lambda_function.tag_checker.arn

    source_detail {
      message_type = "ConfigurationItemChangeNotification"
    }
  }

  input_parameters = jsonencode({
    tag1Key   = "Environment"
    tag2Key   = "CostCenter"
    tag3Key   = "Owner"
  })
}
```

**`source.owner`:** `AWS` for managed rules, `CUSTOM_LAMBDA` for custom rules.
**`source.source_identifier`:** The managed rule identifier. Browse at [AWS Config Managed Rules](https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html).

**Common managed rule identifiers:**
- `ENCRYPTED_VOLUMES` — EBS volumes must be encrypted
- `S3_BUCKET_PUBLIC_READ_PROHIBITED` — S3 buckets must not be publicly readable
- `RDS_STORAGE_ENCRYPTED` — RDS storage must be encrypted
- `CLOUD_TRAIL_ENABLED` — CloudTrail must be enabled
- `IAM_ROOT_ACCESS_KEY_CHECK` — Root account must not have access keys
- `MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS` — IAM users must use MFA

---

## Tagging Policies with precondition

### Enforcing Required Tags:

```hcl
variable "required_tags" {
  type = object({
    Environment = string
    CostCenter  = string
    Owner       = string
    Project     = string
  })

  validation {
    condition     = contains(["production", "staging", "development"], var.required_tags.Environment)
    error_message = "Environment tag must be 'production', 'staging', or 'development'."
  }

  validation {
    condition     = can(regex("^CC-[0-9]{4}$", var.required_tags.CostCenter))
    error_message = "CostCenter must match format CC-XXXX (e.g., CC-1234)."
  }
}

resource "aws_instance" "web" {
  # ...

  tags = merge(var.required_tags, {
    Name = "web-server"
  })

  lifecycle {
    precondition {
      condition     = length(var.required_tags.Owner) > 0
      error_message = "Owner tag must not be empty. Use team or individual email."
    }
  }
}
```

---

## Drift Detection in CI/CD

### Automated Drift Detection Pipeline:

```hcl
# null_resource to run drift detection and alert
resource "null_resource" "drift_check_schedule" {
  # This represents the concept — in practice, use Lambda + EventBridge

  triggers = {
    always = timestamp()  # Force re-run on every apply
  }

  provisioner "local-exec" {
    command = <<-EOT
      terraform plan -refresh-only -detailed-exitcode
      EXIT_CODE=$?
      if [ $EXIT_CODE -eq 2 ]; then
        echo "DRIFT DETECTED" | aws sns publish \
          --topic-arn ${var.alert_topic_arn} \
          --message "Terraform drift detected in ${var.environment}. Run 'terraform apply -refresh-only' to review."
      fi
    EOT
  }
}
```

**`terraform plan -detailed-exitcode`:**
- Exit code `0` — No changes, no drift
- Exit code `1` — Error
- Exit code `2` — Changes present (drift detected or pending changes)

### Best Practices for Drift Detection and Compliance:
- Run drift detection daily in CI/CD pipelines
- Alert immediately when drift is detected
- Document approved exceptions (resources intentionally managed outside Terraform)
- Use `lifecycle { ignore_changes = [...] }` for attributes that are allowed to drift (ASG desired count, tags set by external tools)
- Enforce no manual changes in production using AWS SCPs (Service Control Policies)
- Use AWS Config for continuous compliance monitoring — Terraform compliance checks only run when `terraform plan` runs
- Review AWS Config compliance reports in your security dashboard
