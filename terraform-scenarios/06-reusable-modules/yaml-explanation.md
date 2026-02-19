# Terraform Configuration Files Explanation - Reusable Modules

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## What is a Terraform Module?

A module is a container for multiple resources that are used together. Every Terraform configuration is technically a module (the "root module"). When you create subdirectories with `.tf` files and call them from the root, those are "child modules."

Modules enable:
- **Reusability**: Write networking code once, use it for dev, staging, and prod
- **Encapsulation**: Hide implementation details, expose only the inputs and outputs callers need
- **Consistency**: Every environment uses the same tested, reviewed code
- **Composability**: Combine modules like LEGO bricks to build larger systems

---

## Module Directory Structure

### Standard Module Layout:

```
modules/
  vpc/
    main.tf        # resource definitions
    variables.tf   # input variable declarations
    outputs.tf     # output value declarations
    versions.tf    # required_providers (optional but recommended)
    README.md      # documentation
  rds/
    main.tf
    variables.tf
    outputs.tf
  ec2/
    main.tf
    variables.tf
    outputs.tf
```

**`main.tf`** — All resource blocks. The core of the module.

**`variables.tf`** — All variable declarations with types, descriptions, and defaults. This is the module's "API" — it defines what callers must provide.

**`outputs.tf`** — All output declarations. Defines what information the module exposes to its caller.

**`versions.tf`** — Optional file for `terraform {}` block with `required_providers`. Useful for modules that use provider-specific features requiring minimum provider versions.

This layout is a convention, not a requirement. Terraform reads all `.tf` files in a directory. But following this convention makes modules immediately understandable to other Terraform users.

---

## module Block - Calling a Module

### Calling a Local Module:

```hcl
module "vpc" {
  source = "./modules/vpc"

  # Input variables — every variable without a default must be provided
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  environment        = var.environment
  project_name       = var.project_name
}
```

**`module "vpc"`**
- The label `"vpc"` is the local name — used to reference outputs: `module.vpc.vpc_id`
- Multiple instances of the same module source can be called with different names: `module "vpc_primary"` and `module "vpc_secondary"`

**`source = "./modules/vpc"`**
- Relative path to the module directory
- The path is relative to the calling configuration's directory, not the current working directory
- Must start with `./` or `../` to be recognized as a local path (otherwise Terraform tries to look it up as a registry module)

**Input variable assignments**
- Every variable declared in the module's `variables.tf` without a `default` must be provided here
- You can pass Terraform expressions, not just literal values: `availability_zones = var.azs`

---

### Calling a Registry Module:

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = "10.0.0.0/16"

  azs             = var.availability_zones
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false

  tags = local.common_tags
}
```

**`source = "terraform-aws-modules/vpc/aws"`**
- Format: `<namespace>/<module_name>/<provider>`
- This refers to `registry.terraform.io/terraform-aws-modules/vpc/aws`
- The Terraform Registry at registry.terraform.io hosts thousands of community modules
- `terraform-aws-modules` is one of the most widely-used community module organizations

**`version = "~> 5.0"`**
- Version constraint for registry modules — same syntax as provider versions
- Always pin a version for registry modules — an unexpected major version upgrade can break your infrastructure
- Run `terraform init -upgrade` to update to the latest version satisfying the constraint

---

### Calling a Git Module:

```hcl
module "vpc" {
  source = "git::https://github.com/my-company/terraform-modules.git//vpc?ref=v2.1.0"
}
```

**`git::https://...`**
- Terraform clones the git repository to `.terraform/modules/`
- The `//vpc` after `.git` specifies a subdirectory within the repo
- `?ref=v2.1.0` pins to a specific git tag — always pin for production

**When to use git modules:**
- Private company modules not publishable to the public registry
- You need to use a specific commit or branch
- Cross-team module sharing within an organization

---

## Writing a Module: variables.tf

```hcl
# modules/vpc/variables.tf

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC (e.g., 10.0.0.0/16)"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "The vpc_cidr value must be a valid CIDR block."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "List of AWS availability zones to create subnets in"

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least 2 availability zones required for high availability."
  }
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Whether to create NAT gateways for private subnets"
  default     = true
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use a single NAT gateway instead of one per AZ (reduces cost, reduces HA)"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}
```

**Principles for module variables:**
- Every variable must have `type` and `description`
- Provide sensible defaults where possible — callers should not need to specify obvious values
- Add `validation` blocks to catch invalid inputs early with helpful error messages
- Think about what the caller needs to control vs what is an internal implementation detail

---

## Writing a Module: outputs.tf

```hcl
# modules/vpc/outputs.tf

output "vpc_id" {
  value       = aws_vpc.main.id
  description = "The ID of the VPC"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "List of IDs of private subnets"
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "List of IDs of public subnets"
}

output "private_route_table_ids" {
  value       = aws_route_table.private[*].id
  description = "List of IDs of private route tables"
}

output "nat_gateway_ids" {
  value       = aws_nat_gateway.main[*].id
  description = "List of NAT Gateway IDs"
}
```

**Principles for module outputs:**
- Export every resource ID and ARN that callers might need
- Do not over-output: avoid exporting internal computed values callers would never use
- Add `description` to every output — it becomes the module's documentation
- Mark sensitive outputs with `sensitive = true` (passwords, private keys)

---

## Module Composition

### Using One Module's Output as Another Module's Input:

```hcl
# Root module: main.tf

module "network" {
  source             = "./modules/vpc"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = var.availability_zones
  environment        = var.environment
}

module "security" {
  source   = "./modules/security_groups"
  vpc_id   = module.network.vpc_id          # output from network module
  vpc_cidr = "10.0.0.0/16"
}

module "compute" {
  source             = "./modules/ec2_asg"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids  # output from network
  app_sg_id          = module.security.app_security_group_id  # output from security
  environment        = var.environment
}

module "data_layer" {
  source             = "./modules/rds"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  db_sg_id           = module.security.db_security_group_id
}
```

**`module.network.vpc_id`**
- How to reference a module's output from the calling configuration
- Format: `module.<module_name>.<output_name>`
- Creates an implicit dependency: `compute` module will not be created until `network` module completes

**Dependency chain:**
1. `network` module creates first (no dependencies)
2. `security` module creates after `network` (needs `vpc_id`)
3. `compute` and `data_layer` create after both `network` and `security`

---

## Module Versioning

### Why Pin Module Versions:

```hcl
# RISKY — uses latest version every time
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  # no version constraint
}

# SAFE — pinned version
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.2"
}

# FLEXIBLE but bounded
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.1"  # allows 5.1.x, 5.2.x but not 6.0
}
```

Without a version constraint on a registry or git module, `terraform init -upgrade` can pull breaking changes that modify your infrastructure without warning. Pin versions for all external modules used in production.

### Updating Module Versions:

```bash
# Show what versions are available
terraform registry list-versions hashicorp/consul/aws

# Update the .terraform.lock.hcl to use latest within constraints
terraform init -upgrade

# Then review the plan carefully
terraform plan
```

---

## Module Caching

### Where Modules are Stored:

```bash
.terraform/
  modules/
    modules.json          # index of all installed modules
    vpc/                  # local module (symlinked)
    terraform-aws-modules__vpc__aws/   # registry module download
    my-company__modules__vpc__2.1.0/  # git module clone
```

**`terraform get`**
Downloads and updates modules (without initializing providers). Usually you just run `terraform init`, which handles both providers and modules.

**`.terraform/modules/` directory:**
- Generated on `terraform init` — do not commit to git
- Can be regenerated from the lock file and module sources at any time
- Add `.terraform/` to your `.gitignore`

---

## When to Write a Module

### The Rule of Three:

Write a module when you find yourself copying the same resource group to three or more places. One copy is fine. Two copies are manageable. Three copies mean it is time to abstract.

### Good Candidates for Modules:
- VPC with all networking components (subnets, route tables, gateways)
- RDS instance with parameter group, subnet group, security group, and backup config
- EKS cluster with node groups, IAM roles, and addons
- Standard EC2 Auto Scaling Group with ALB, target group, and health checks

### When NOT to Write a Module:
- A single resource that is only used once — just write the resource directly
- When you are trying to make infrastructure "DRY" before you understand the duplication — premature abstraction creates modules with too many variables
- When the abstraction is thinner than the underlying resource — if your module has 50 input variables for a resource with 50 attributes, you have added complexity without value

### Signs Your Module is Too Complex:
- More than 20 input variables
- Variables that control other variables' behavior (feature flags inside modules)
- Callers frequently need to work around the module's opinions
- Module's README is longer than the AWS documentation for the underlying service

---

## Common Mistakes to Avoid

- **Not pinning module versions**: A registry or git module update can change resource behavior, causing unplanned infrastructure changes.
- **Exposing too many variables**: Every variable you add is a decision burden on the caller. Use opinionated defaults and only expose variables that callers genuinely need to control.
- **Not providing outputs for key resources**: A module with no outputs cannot be composed. Always output at least the IDs and ARNs of the main resources.
- **Using relative paths without `./` prefix**: `source = "modules/vpc"` is not a local path — Terraform treats it as a registry module lookup and fails. Use `source = "./modules/vpc"`.
- **Putting provider blocks inside modules**: Provider configuration belongs in the root module only. Modules should accept provider instances via the `providers` argument if needed.
- **Creating modules for single resources**: A module wrapping one `aws_s3_bucket` with the same attributes is pure overhead. Modules earn their complexity by combining multiple related resources.
- **Not testing modules**: Changes to a module affect every caller. Use `terraform plan` against all consumers before merging module changes, or use a testing framework like Terratest.
