# Terraform Configuration Files Explanation - State Surgery: Import, Move, Replace

This guide explains the Terraform state manipulation concepts and configuration patterns in this scenario. These are the techniques used when Terraform's state doesn't match reality — whether due to manual changes, migrations, or refactoring.

---

## Understanding Terraform State

### What is Terraform State?
Terraform state is a JSON file that maps your configuration to real-world infrastructure. Every resource Terraform manages has an entry that includes:
- The resource address (e.g., `aws_s3_bucket.my_bucket`)
- The real-world resource ID (e.g., `my-bucket-name`)
- All resource attributes at last-known state

When state diverges from reality (drift), Terraform makes incorrect plans.

### The State File Structure:

```hcl
# terraform.tfstate (simplified)
{
  "version": 4,
  "terraform_version": "1.5.7",
  "serial": 42,
  "lineage": "a1b2c3d4-...",
  "resources": [
    {
      "mode": "managed",
      "type": "aws_s3_bucket",
      "name": "my_bucket",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [{
        "attributes": {
          "id": "my-actual-bucket-name",
          "bucket": "my-actual-bucket-name",
          "region": "us-east-1"
        }
      }]
    }
  ]
}
```

**`serial`:** Increments on every state change. Used for optimistic locking — prevents two applies from clobbering each other.
**`lineage`:** UUID that uniquely identifies this state. Prevents applying the wrong state to the wrong workspace.

### Golden Rules of State:
- **Never edit `terraform.tfstate` manually** — use `terraform state` commands
- **Never commit to git** — add to `.gitignore`, use remote backend
- **Always use remote state in teams** — S3, GCS, or Terraform Cloud
- **Enable state locking** — DynamoDB for S3 backend

---

## terraform import - Adopting Existing Resources

### What is terraform import?
`terraform import` brings existing infrastructure under Terraform management. It reads the current resource attributes from the cloud provider and writes them to state — without modifying the real resource.

### When to Use Import:
- Resources created manually (ClickOps) that you want to manage with Terraform
- Migrating from another IaC tool (CloudFormation, CDK, Pulumi)
- Recovering after state loss
- Onboarding inherited infrastructure

### Basic import workflow:

```hcl
# 1. Write the resource block in your .tf file FIRST
resource "aws_s3_bucket" "legacy_bucket" {
  bucket = "my-existing-bucket-name"
  # Don't add other attributes yet — let import fill them in
}
```

```bash
# 2. Run the import command
terraform import aws_s3_bucket.legacy_bucket my-existing-bucket-name
#                ^resource_address              ^resource_id
```

```bash
# 3. View what was imported
terraform state show aws_s3_bucket.legacy_bucket

# 4. Run plan to check for differences
terraform plan
# If plan shows changes, update your .tf file to match reality
```

### Common Import IDs for AWS Resources:

```bash
# S3 Bucket
terraform import aws_s3_bucket.example bucket-name

# EC2 Instance
terraform import aws_instance.example i-0123456789abcdef0

# VPC
terraform import aws_vpc.example vpc-12345678

# Security Group
terraform import aws_security_group.example sg-12345678

# IAM Role
terraform import aws_iam_role.example role-name

# RDS Instance
terraform import aws_db_instance.example db-identifier

# EKS Cluster
terraform import aws_eks_cluster.example cluster-name
```

**Finding the import ID:** Check the AWS provider documentation for each resource — the "Import" section shows the exact ID format. Usually it's the resource's primary identifier (name, ID, or ARN).

---

## Import Blocks - Declarative Imports (Terraform 1.5+)

### What are Import Blocks?
Instead of running `terraform import` imperatively, you can declare imports in `.tf` files. This is version-controllable and reviewable in PRs.

### HCL Structure Breakdown:

```hcl
import {
  to = aws_s3_bucket.legacy_bucket
  id = "my-existing-bucket-name"
}

resource "aws_s3_bucket" "legacy_bucket" {
  bucket = "my-existing-bucket-name"
}
```

**`to`:** The resource address in your configuration.
**`id`:** The real-world resource ID (same as the CLI import ID).

### Generate Configuration (Terraform 1.5+):

```bash
# Let Terraform generate the resource block for you
terraform plan -generate-config-out=generated.tf
```

This generates a complete resource block from the imported resource's actual attributes, saving you from manually writing it.

### After import:
```bash
# Remove the import block after first apply
# It only needs to run once
terraform apply  # Performs the import and removes the import block
```

---

## moved Block - Renaming Without Destroy/Recreate

### What is the moved Block?
The `moved` block lets you rename or restructure resources in your configuration without destroying and recreating them. Terraform updates only the state, leaving real infrastructure untouched.

### HCL Structure Breakdown:

```hcl
# Rename a resource
moved {
  from = aws_s3_bucket.old_name
  to   = aws_s3_bucket.new_name
}

# Move a resource into a module
moved {
  from = aws_s3_bucket.my_bucket
  to   = module.storage.aws_s3_bucket.main
}

# Move when adding count/for_each
moved {
  from = aws_instance.web
  to   = aws_instance.web[0]
}
```

**`from`:** Old resource address (the address currently in state).
**`to`:** New resource address (the address in your updated configuration).

### When to Use moved vs terraform state mv:
| Feature | `moved` block | `terraform state mv` |
|---|---|---|
| Version controlled | Yes (in .tf file) | No (CLI command) |
| Reviewable in PRs | Yes | No |
| Works in modules | Yes | Limited |
| Terraform version | 1.1+ | All versions |

**Prefer `moved` blocks** — they are declarative and reviewable.

### Cleanup:
```hcl
# After everyone on the team has applied, you can remove the moved block
# (the state has been updated, the block is no longer needed)
# Wait until the old address no longer exists in any state file
```

---

## terraform state Commands - CLI State Surgery

### terraform state list

```bash
# List all resources in state
terraform state list

# Filter by type
terraform state list aws_s3_bucket.*

# In a specific module
terraform state list module.vpc.*
```

### terraform state show

```bash
# Show all attributes of a resource
terraform state show aws_db_instance.main

# Output example:
# resource "aws_db_instance" "main" {
#     allocated_storage = 100
#     arn               = "arn:aws:rds:..."
#     endpoint          = "mydb.xxx.us-east-1.rds.amazonaws.com:5432"
#     ...
# }
```

### terraform state mv

```bash
# Rename a resource (older approach, prefer moved block)
terraform state mv aws_s3_bucket.old aws_s3_bucket.new

# Move into a module
terraform state mv aws_s3_bucket.main module.storage.aws_s3_bucket.main

# Move when refactoring count
terraform state mv 'aws_instance.web[0]' aws_instance.web_primary
```

**Always run `terraform state pull > backup.tfstate` before state surgery.**

### terraform state rm

```bash
# Remove from state WITHOUT destroying the real resource
terraform state rm aws_s3_bucket.orphaned

# Use cases:
# - Resource was deleted manually, remove stale state entry
# - You want Terraform to "forget" a resource (stop managing it)
# - Cleaning up after a failed migration
```

**Warning:** After `state rm`, Terraform will try to CREATE the resource on next apply (since it's not in state). Add it to `.tf` config and re-import if needed, or remove from config entirely.

### terraform state pull / push

```bash
# Download state to local file (useful for inspection)
terraform state pull > current.tfstate

# Upload modified state (DANGEROUS — bypasses locking)
terraform state push modified.tfstate
# Only use as last resort for recovery scenarios
```

---

## lifecycle Meta-Argument - Controlling Resource Behavior

### What is the lifecycle Block?
Every Terraform resource supports a `lifecycle` block that controls how Terraform handles resource changes.

### HCL Structure Breakdown:

```hcl
resource "aws_db_instance" "main" {
  # ...

  lifecycle {
    prevent_destroy       = true
    create_before_destroy = true
    ignore_changes        = [
      password,
      tags["LastModified"],
    ]
  }
}
```

**`prevent_destroy = true`:** Terraform will error if you try to destroy this resource.
**When to use:** Production databases, S3 buckets with data, Route53 hosted zones — anything catastrophic to delete accidentally.
**Note:** This only prevents `terraform destroy` and plan-triggered destruction. It does NOT prevent `terraform state rm` followed by manual deletion.

**`create_before_destroy = true`:** Creates the replacement resource before destroying the old one.
**When to use:** Resources that other resources depend on (e.g., TLS certificates, launch templates). Prevents downtime.
**Default behavior:** Destroy first, then create — which can cause brief outages.

**`ignore_changes`:** List of attributes Terraform should ignore when planning.
**When to use:**
- Passwords managed outside Terraform (rotated by Secrets Manager)
- Tags set by other tools (cost allocation, compliance scanners)
- Attributes that drift intentionally (ASG desired count)

```hcl
lifecycle {
  ignore_changes = [
    password,              # Rotated by Secrets Manager
    tags["CostCenter"],    # Set by finance tooling
    desired_count,         # Managed by autoscaling
  ]
}
```

**`replace_triggered_by`:** Force replacement when another resource changes.

```hcl
resource "aws_instance" "web" {
  # ...
  lifecycle {
    replace_triggered_by = [
      aws_launch_template.web.latest_version
    ]
  }
}
```

---

## -replace Flag - Forced Recreation

### When to Use -replace:
Use `-replace` when a resource is in a bad state but Terraform's plan shows no changes (state matches config but reality is broken).

```bash
# Force recreation of a specific resource
terraform apply -replace="aws_instance.web"

# Multiple resources
terraform apply \
  -replace="aws_instance.web" \
  -replace="aws_eip.web"
```

**Use cases:**
- EC2 instance became unresponsive (hardware issue)
- RDS instance has corruption (restore from snapshot)
- Certificate needs renewal
- Container failed to start and won't recover

**Equivalent to:** Adding `lifecycle { replace_triggered_by = [...] }` temporarily, or the old `terraform taint` command (deprecated in 1.0).

---

## terraform apply -refresh-only - Detecting Drift

### What is Drift?
Drift occurs when real infrastructure differs from Terraform state. Causes:
- Manual changes in AWS Console
- Other tools modifying resources
- AWS services modifying attributes automatically

### Detecting and Reconciling Drift:

```bash
# Step 1: Detect drift (updates state to match reality, no infra changes)
terraform apply -refresh-only

# Output shows what has drifted:
# ~ aws_security_group.web (drift detected)
#     ~ ingress = [
#         + {
#             + cidr_blocks = ["10.0.0.0/8"]
#             + from_port   = 22
#             + to_port     = 22
#           },  # manually added SSH rule
#       ]

# Step 2: Decide what to do
# Option A: Accept the drift (add the change to your .tf config)
# Option B: Reject the drift (run terraform apply to revert to config)
```

**`-refresh-only` vs old `terraform refresh`:**
- `terraform refresh` (deprecated): Silently updates state, no review
- `terraform apply -refresh-only`: Shows you what changed, requires confirmation — much safer

### Best Practices:
- Run drift detection on a schedule (daily/weekly) in CI/CD
- Alert on unexpected drift
- Never allow manual changes in production — enforce with SCPs and IAM policies
