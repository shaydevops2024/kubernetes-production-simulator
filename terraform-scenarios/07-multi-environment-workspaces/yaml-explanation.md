# Terraform Configuration Files Explanation - Multi-Environment Workspaces

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## Workspaces Overview

### What are Terraform Workspaces?

A Terraform workspace is a named instance of state. Every Terraform configuration starts with one workspace called `default`. When you create additional workspaces, each one gets its own isolated state file, while sharing the same configuration code.

**Think of workspaces like this:**
- Same `.tf` files
- Same provider configuration
- Different state file per workspace → different real infrastructure per workspace

In S3 backend, workspaces create separate state files:
```
s3://terraform-state/
  env:/
    dev/
      app/terraform.tfstate
    staging/
      app/terraform.tfstate
    prod/
      app/terraform.tfstate
  app/terraform.tfstate    # default workspace
```

---

## Workspace Commands

### Core Workspace Operations:

```bash
# List all workspaces (* marks current)
terraform workspace list
# Output:
#   default
# * dev
#   staging
#   prod

# Create and switch to a new workspace
terraform workspace new staging

# Switch to an existing workspace
terraform workspace select prod

# Show the current workspace name
terraform workspace show
# Output: prod

# Delete a workspace (must switch away first, workspace must be empty)
terraform workspace delete dev
```

**`terraform workspace new <name>`**
- Creates a new workspace with an empty state file
- Automatically switches to the new workspace
- The workspace name becomes available as `terraform.workspace` expression in configuration

**`terraform workspace select <name>`**
- Switches to an existing workspace
- All subsequent `plan`, `apply`, and `destroy` commands operate against this workspace's state

**`terraform workspace delete <name>`**
- Deletes the workspace and its state file
- You cannot delete the `default` workspace
- You cannot delete the currently active workspace — switch to another workspace first
- Does NOT destroy the infrastructure — it only removes the state tracking. Always run `terraform destroy` before deleting a workspace, or you will have orphaned resources.

---

## main.tf - Using terraform.workspace Expression

### The terraform.workspace Expression:

```hcl
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = local.instance_type

  tags = {
    Name        = "${var.project_name}-app-${terraform.workspace}"
    Environment = terraform.workspace
  }
}
```

**`terraform.workspace`**
- A built-in expression that returns the name of the current workspace as a string
- Returns `"default"` in the default workspace, `"dev"`, `"staging"`, `"prod"` in named workspaces
- Can be used anywhere an expression is valid: resource names, tags, locals, conditions

**Why include the workspace name in resource names?**
If you apply the same configuration in two workspaces simultaneously (e.g., dev and prod), both would try to create an EC2 instance named `"myapp-app"`. Including the workspace name ensures uniqueness: `"myapp-app-dev"` and `"myapp-app-prod"`.

---

### Per-Workspace Configuration with locals:

```hcl
locals {
  # Per-workspace configuration map
  workspace_config = {
    dev = {
      instance_type    = "t3.micro"
      min_size         = 1
      max_size         = 2
      desired_capacity = 1
      multi_az         = false
    }
    staging = {
      instance_type    = "t3.small"
      min_size         = 1
      max_size         = 4
      desired_capacity = 2
      multi_az         = true
    }
    prod = {
      instance_type    = "t3.medium"
      min_size         = 2
      max_size         = 10
      desired_capacity = 3
      multi_az         = true
    }
  }

  # Get config for current workspace, fall back to dev defaults
  config = lookup(local.workspace_config, terraform.workspace, local.workspace_config["dev"])

  # Extract individual values for use in resources
  instance_type    = local.config.instance_type
  min_size         = local.config.min_size
  max_size         = local.config.max_size
  desired_capacity = local.config.desired_capacity
}
```

**`lookup(map, key, default)`**
- Retrieves the value for a given key from a map
- If the key is not found, returns the `default` value
- `lookup(local.workspace_config, terraform.workspace, local.workspace_config["dev"])` reads the configuration for the current workspace name, falling back to the `dev` config if the workspace name is not found in the map

**Why a nested map for workspace configs?**
This pattern keeps all per-environment configuration in one place. Adding a new environment means adding one entry to the map. Changing a setting for one environment means changing one value.

**Alternative — direct conditional:**
```hcl
locals {
  instance_type = terraform.workspace == "prod" ? "t3.medium" : "t3.micro"
  multi_az      = terraform.workspace == "prod" ? true : false
}
```
This is simpler but does not scale beyond two or three environments.

---

## lookup() Function

### Detailed Explanation:

```hcl
# lookup(map, key, default)
lookup({"dev" = "t3.micro", "prod" = "t3.medium"}, "prod", "t3.micro")
# Returns: "t3.medium"

lookup({"dev" = "t3.micro", "prod" = "t3.medium"}, "staging", "t3.micro")
# Returns: "t3.micro" (default, because "staging" is not in the map)

# Without a default — errors if key not found
lookup({"dev" = "t3.micro"}, "staging")
# Error: lookup failed to find key "staging"
```

**Always provide a default value** when the key might not exist. In workspace scenarios, a new workspace name that is not in your config map should fall back to a safe default.

---

## Variable Files per Environment

### terraform.tfvars vs Workspace Variable Files:

```hcl
# terraform.tfvars — loaded automatically for all workspaces
project_name = "webapp"
aws_region   = "us-east-1"

# dev.tfvars — loaded with: terraform apply -var-file=dev.tfvars
environment      = "dev"
vpc_cidr         = "10.1.0.0/16"
instance_type    = "t3.micro"

# prod.tfvars — loaded with: terraform apply -var-file=prod.tfvars
environment      = "prod"
vpc_cidr         = "10.0.0.0/16"
instance_type    = "t3.large"
```

**When to use `-var-file` with workspaces:**
```bash
# Select workspace and apply with matching var file
terraform workspace select prod
terraform apply -var-file=prod.tfvars
```

This approach works but requires the operator to remember to use the right var file for the right workspace. Using the `lookup(local.workspace_config, ...)` pattern avoids this human error.

**`terraform.tfvars` vs `terraform.tfvars.json`:**
- `terraform.tfvars` uses HCL syntax — human-friendly
- `terraform.tfvars.json` uses JSON syntax — machine-friendly, easier to generate programmatically
- Both are loaded automatically — if both exist, both are read

---

## Workspace State Isolation

### How State is Stored per Workspace:

With the S3 backend:
```hcl
terraform {
  backend "s3" {
    bucket = "my-company-terraform-state"
    key    = "app/terraform.tfstate"
    region = "us-east-1"
  }
}
```

When workspaces are used, the actual state file paths become:
- `default` workspace: `app/terraform.tfstate` (the `key` value as-is)
- `dev` workspace: `env:/dev/app/terraform.tfstate`
- `prod` workspace: `env:/prod/app/terraform.tfstate`

The `env:/` prefix and workspace name are automatically prepended by Terraform.

---

### Workspaces vs Separate State Files:

| Aspect | Workspaces | Separate Configurations |
|--------|-----------|------------------------|
| Code reuse | Same code for all environments | Need to copy or use modules |
| State isolation | Isolated per workspace | Completely separate |
| Access control | All workspaces share IAM permissions | Can have separate AWS accounts/roles |
| Blast radius | Mistake in one workspace could affect others | Fully isolated |
| Best for | Lightweight, similar environments | Enterprise multi-account setups |

---

## Workspace Limitations

### When Workspaces Are Not Enough:

Workspaces are good for environments that are structurally identical and share the same AWS account. For enterprise production setups, separate AWS accounts per environment (dev account, staging account, prod account) provide stronger isolation:

- **Blast radius**: A bug that deletes all EC2 instances in dev cannot touch prod (different account)
- **Access control**: Developers can have broad access to dev but read-only in prod
- **Cost allocation**: Per-account billing makes cost attribution trivial
- **Compliance**: Audit trails are fully separated — prod changes cannot be confused with dev changes

In multi-account setups, use separate Terraform configurations per account (not workspaces), with separate backends and state files.

---

## local-exec Provisioner

### What is a Provisioner?

Provisioners are a last resort mechanism in Terraform for running scripts after a resource is created or before it is destroyed. They run local commands (`local-exec`) or remote commands via SSH (`remote-exec`).

```hcl
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.medium"

  provisioner "local-exec" {
    command = "echo ${self.public_ip} >> inventory.txt"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "sed -i '/${self.public_ip}/d' inventory.txt"
  }
}
```

**`provisioner "local-exec"`**
- Runs a command on the machine running Terraform (not on the created resource)
- `command` — the shell command to execute
- `when = destroy` — runs this provisioner when the resource is being destroyed (default is on create)

**`self`**
- Inside a provisioner block, `self` refers to the resource the provisioner is attached to
- `self.public_ip` is the EC2 instance's public IP address

### Why Provisioners Should Be Avoided:

- **Not declarative**: Provisioner commands are not tracked in state — Terraform cannot show their diff in `plan`
- **Not idempotent**: If a `local-exec` command fails midway, re-running `apply` will not retry just that command
- **Hard to debug**: Errors in provisioner scripts are harder to diagnose than errors in resource creation
- **Ordering issues**: Complex `depends_on` chains are needed when multiple resources use provisioners

**Better alternatives to provisioners:**
- Use `user_data` for EC2 bootstrap scripts (cloud-init)
- Use AWS Systems Manager for post-creation configuration
- Use configuration management tools (Ansible, Chef, Puppet) triggered separately from Terraform
- Use Lambda functions for post-creation hooks

**When provisioners are acceptable:**
- Local test setups where you need a quick integration test after a resource is created
- Generating a local `kubeconfig` or inventory file after creating a cluster
- Triggering an external webhook on resource creation

---

## Workspace-Aware Infrastructure Example

### Full Example Combining Workspaces with Conditionals:

```hcl
locals {
  env = terraform.workspace

  # Resource counts based on environment
  nat_gateway_count = local.env == "prod" ? length(var.availability_zones) : 1

  # Feature flags
  enable_deletion_protection = local.env == "prod"
  enable_backups             = contains(["staging", "prod"], local.env)
  log_retention_days         = local.env == "prod" ? 90 : 7
}

resource "aws_db_instance" "main" {
  identifier           = "${var.project_name}-db-${local.env}"
  instance_class       = local.config.db_instance_class
  deletion_protection  = local.enable_deletion_protection
  backup_retention_period = local.enable_backups ? 7 : 0
  multi_az             = local.config.multi_az
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/app/${var.project_name}/${local.env}"
  retention_in_days = local.log_retention_days
}
```

This pattern uses `terraform.workspace` only in `locals {}` and uses the local values in resources. This makes the actual resource blocks clean and easy to read, with all workspace-conditional logic centralized in `locals.tf`.

---

## Common Mistakes to Avoid

- **Running `terraform destroy` in the wrong workspace**: Always run `terraform workspace show` before a destructive operation. A destroy in `prod` when you meant `dev` is catastrophic.
- **Forgetting to switch workspaces before running commands**: If you just ran `terraform apply` in `dev` and now want to plan `prod`, you must run `terraform workspace select prod` first.
- **Deleting a workspace without destroying infrastructure**: `terraform workspace delete dev` removes the state file. Any infrastructure tracked by that state is now orphaned — not destroyed, just untracked. You must `terraform destroy` first.
- **Using workspaces as a substitute for separate AWS accounts in production**: Workspaces share IAM credentials. If those credentials are compromised or a policy is too permissive, all workspaces are affected.
- **Hardcoding environment-specific values instead of using workspace lookup**: Hardcoded values must be changed manually per workspace, defeating the purpose of workspace-based multi-environment management.
- **Not including workspace name in resource names**: Creating a bucket named `"app-artifacts"` in both `dev` and `prod` workspaces will fail — S3 bucket names are globally unique. Always include `terraform.workspace` or a derived variable in resource names.
- **Using workspaces for completely different infrastructure architectures**: If dev has 1 tier and prod has 3 tiers, the same configuration cannot serve both cleanly. Use separate configurations for fundamentally different architectures.
