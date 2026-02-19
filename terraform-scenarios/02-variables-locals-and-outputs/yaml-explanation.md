# Terraform Configuration Files Explanation - Variables, Locals, and Outputs

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## variables.tf - Input Variable Declarations

### What are Input Variables?

Input variables are the parameters of a Terraform module or configuration. They allow you to write reusable, configurable code instead of hardcoding values. When you run `terraform apply`, Terraform prompts for any variable without a default value (unless you supply it via a `.tfvars` file, `-var` flag, or environment variable).

Variables are declared in `variables.tf` by convention, but any `.tf` file works. The `variables.tf` file just makes it easy to find all inputs at a glance.

### Basic Variable Block Syntax:

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment: dev, staging, or prod"
  default     = "dev"
}
```

**`variable "environment"`**
- The name `environment` becomes how you reference this variable in configuration: `var.environment`
- Names should be lowercase with underscores, descriptive but not verbose

**`type = string`**
- Declares the expected type. Terraform validates input against this type at plan time.
- Options: `string`, `number`, `bool`, `list(string)`, `set(string)`, `map(string)`, `object({...})`, `tuple([...])`
- Omitting `type` allows any type — avoid this, it makes validation impossible

**`description = "..."`**
- Documents the purpose of the variable
- Shows up in `terraform plan` output and documentation tools like terraform-docs
- Always write a description — future you and teammates will thank you

**`default = "dev"`**
- Makes the variable optional — if not provided, this value is used
- Omitting `default` makes the variable required — Terraform will error if not supplied
- Use `default = null` for optional variables that should be null when not set

---

### Complex Type Variables:

```hcl
variable "availability_zones" {
  type        = list(string)
  description = "List of AWS availability zones to deploy into"
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
```

**`type = list(string)`**
- A list is an ordered collection of values of the same type
- Access elements: `var.availability_zones[0]` returns `"us-east-1a"`
- Get length: `length(var.availability_zones)` returns `3`
- Iterate: `for_each = toset(var.availability_zones)`

```hcl
variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}
```

**`type = map(string)`**
- A map is an unordered collection of string keys to string values
- Useful for resource tags, environment-specific config
- Access values: `var.tags["Team"]`
- Merge with other maps: `merge(var.tags, { Environment = var.environment })`

```hcl
variable "database_config" {
  type = object({
    instance_class    = string
    allocated_storage = number
    multi_az          = bool
  })
  description = "RDS database configuration parameters"
}
```

**`type = object({...})`**
- Structural type that requires specific named attributes with specified types
- Validation happens at plan time — if you pass `instance_class = 42`, Terraform errors
- Access attributes: `var.database_config.instance_class`
- More explicit than `map(any)` because it enforces a schema

---

### Validation Blocks:

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}
```

**`validation {}`**
- Runs a custom validation rule at plan time before any API calls
- A variable can have multiple `validation` blocks — all must pass

**`condition = contains(["dev", "staging", "prod"], var.environment)`**
- A boolean expression that must evaluate to `true` for the input to be valid
- Can use any Terraform functions and reference `var.<name>` (only the current variable)
- Other examples:
  - `condition = length(var.bucket_name) <= 63` — enforce string length
  - `condition = can(regex("^[a-z][a-z0-9-]*$", var.name))` — enforce naming pattern
  - `condition = var.min_size <= var.max_size` — cross-field validation (when in the same variable object)

**`error_message = "Environment must be one of: dev, staging, prod."`**
- Must be a non-empty string
- Shows up in the error output when validation fails
- Be specific — tell the user what valid values look like

---

### Variable Files (.tfvars):

```hcl
# terraform.tfvars  — loaded automatically
environment    = "dev"
project_name   = "webapp"
aws_region     = "us-east-1"

# production.tfvars — loaded with -var-file flag
environment    = "prod"
project_name   = "webapp"
aws_region     = "us-east-1"
```

**How Terraform finds variable values (precedence, highest wins):**
1. `-var="environment=prod"` flag on the command line
2. `-var-file=production.tfvars` flag on the command line
3. `*.auto.tfvars` files in the working directory (loaded alphabetically)
4. `terraform.tfvars` in the working directory (loaded automatically)
5. Environment variables: `TF_VAR_environment=prod`
6. The `default` value in the `variable` block

**What to commit to git:**
- `terraform.tfvars` — OK if it contains no secrets
- `production.tfvars` — OK if it contains no secrets
- Never commit `*.tfvars` files containing passwords, API keys, or private keys

### Best Practices for Variables:
- Always provide `type` and `description` for every variable
- Use `validation` blocks for variables with restricted value sets
- Use complex types (`object`, `list`) instead of many individual primitive variables for related config
- Use `sensitive = true` for variables containing secrets — Terraform will redact them from plan output

---

## locals.tf - Local Values

### What are Locals?

Local values are computed, named expressions within a module. Unlike variables (which are external inputs), locals are internal computations. Think of them as constants or computed intermediate values that you want to reuse without repeating the same expression everywhere.

### Basic Locals Block Syntax:

```hcl
locals {
  # Simple computed value
  name_prefix = "${var.project_name}-${var.environment}"

  # Conditional expression
  is_production = var.environment == "prod"

  # Resource naming with consistent prefix
  bucket_name = "${local.name_prefix}-artifacts"
  log_bucket  = "${local.name_prefix}-logs"

  # Merged tags
  common_tags = merge(var.tags, {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  })
}
```

**`locals {}`**
- A single `locals {}` block can contain as many local values as you want
- You can have multiple `locals {}` blocks in a file or across files — they are all merged
- Access local values with the `local.` prefix: `local.name_prefix`

**`name_prefix = "${var.project_name}-${var.environment}"`**
- String interpolation combines variables into a reusable prefix
- Without this local, every resource would need to repeat `"${var.project_name}-${var.environment}"` — if you ever change the naming scheme, you change it in one place

**`is_production = var.environment == "prod"`**
- A boolean local derived from a variable
- Can be used in conditionals: `count = local.is_production ? 2 : 1`
- Makes conditionals in resource blocks readable: `multi_az = local.is_production` instead of `multi_az = var.environment == "prod"`

**`common_tags = merge(var.tags, {...})`**
- `merge()` combines maps, with later maps overriding earlier ones on key conflicts
- Defining common tags as a local means every resource gets `tags = local.common_tags` — one line per resource instead of a large block

---

### When to Use Locals vs Variables:

```hcl
# Use a VARIABLE when:
# - The value changes between environments
# - A caller or operator needs to control it
variable "instance_type" {
  type    = string
  default = "t3.medium"
}

# Use a LOCAL when:
# - The value is computed from other values
# - It is an internal implementation detail
# - You want to avoid repeating a complex expression
locals {
  instance_profile_name = "${local.name_prefix}-instance-profile"
  vpc_cidr_base         = "10.${var.environment == "prod" ? "0" : "1"}.0.0"
}
```

**Rule of thumb:**
- If someone running `terraform apply` might reasonably want to change the value, make it a variable
- If it is an internal calculation that derives from other values, make it a local
- Locals cannot be overridden from outside the module — this is a feature, not a limitation

---

### String Interpolation and Expressions:

```hcl
locals {
  # Template strings
  bucket_name = "${var.project}-${var.environment}-${data.aws_region.current.name}"

  # Conditional (ternary) expressions
  retention_days = var.environment == "prod" ? 90 : 7

  # For expressions — transform a list
  subnet_names = [for az in var.availability_zones : "${local.name_prefix}-subnet-${az}"]

  # For expressions — transform a map
  resource_tags = { for k, v in var.tags : k => upper(v) }
}
```

**`condition ? true_value : false_value`**
- Ternary operator for conditional values
- Both branches must produce the same type

**`[for item in list : expression]`**
- Creates a new list by transforming each item
- Can add `if condition` to filter: `[for az in var.azs : az if az != "us-east-1d"]`

**`{ for k, v in map : k => expression }`**
- Creates a new map by transforming key-value pairs

### Best Practices for Locals:
- Use locals to avoid repeating complex expressions — the DRY principle applies to HCL
- Group related locals together with comments explaining their purpose
- Keep local names descriptive: `local.common_tags` not `local.t`
- Avoid deeply nested locals that reference other locals more than 2-3 levels deep — it becomes hard to follow

---

## outputs.tf - Output Values

### What are Outputs?

Output values export data from a Terraform configuration. They serve two purposes:
1. **Show information to the user** after `terraform apply` — like the URL of a created load balancer
2. **Pass data between modules** — a child module exposes outputs that a parent module reads

### Basic Output Block Syntax:

```hcl
output "bucket_name" {
  value       = aws_s3_bucket.app_artifacts.bucket
  description = "The name of the S3 bucket created for application artifacts"
}
```

**`output "bucket_name"`**
- The name `bucket_name` is how this output is referenced:
  - By users: `terraform output bucket_name`
  - By parent modules: `module.storage.bucket_name`

**`value = aws_s3_bucket.app_artifacts.bucket`**
- Any valid Terraform expression: resource attributes, local values, variable values, function calls
- Can be a complex type: a list of ARNs, a map of IDs, a nested object

**`description = "..."`**
- Documents what this output contains
- Shows up in `terraform output` and documentation tools

---

### Sensitive Outputs:

```hcl
output "database_password" {
  value       = random_password.db.result
  description = "Generated database password"
  sensitive   = true
}
```

**`sensitive = true`**
- Redacts the value from plan and apply output: shows `<sensitive>` instead of the actual value
- The value is still stored in plaintext in state — `sensitive = true` only controls display
- Use this for passwords, private keys, tokens, any credential
- When referencing a sensitive output in another resource, that resource attribute also becomes sensitive

---

### Complex Output Values:

```hcl
output "vpc_info" {
  description = "VPC identifiers for use by other modules"
  value = {
    vpc_id             = aws_vpc.main.id
    private_subnet_ids = aws_subnet.private[*].id
    public_subnet_ids  = aws_subnet.public[*].id
  }
}
```

**`aws_subnet.private[*].id`**
- Splat expression — collects the `id` attribute from every instance of `aws_subnet.private` (when using `count`)
- Returns a list of strings
- For `for_each` resources, use `values(aws_subnet.private)[*].id`

---

### Using Outputs in Module Composition:

```hcl
# In a parent module:
module "network" {
  source = "./modules/vpc"
  cidr   = "10.0.0.0/16"
}

module "compute" {
  source    = "./modules/ec2"
  vpc_id    = module.network.vpc_id          # read output from network module
  subnet_id = module.network.private_subnet_ids[0]
}
```

Outputs are the API surface of a module. A module with no outputs cannot pass any data to its caller. Design outputs to expose the IDs and ARNs that callers are likely to need.

### Using the `terraform output` Command:

```bash
# Show all outputs
terraform output

# Show a specific output value (useful in scripts)
terraform output -raw bucket_name

# Show as JSON (for programmatic processing)
terraform output -json

# Example: use in a shell script
BUCKET=$(terraform output -raw bucket_name)
aws s3 cp artifact.zip s3://$BUCKET/
```

**`-raw`** strips surrounding quotes from string outputs — use this in shell scripts to avoid having to process JSON.

---

## Type System Deep Dive

### Primitive Types:

```hcl
variable "name" {
  type = string   # "hello", "us-east-1"
}

variable "count_value" {
  type = number   # 42, 3.14
}

variable "enabled" {
  type = bool     # true, false
}
```

### Collection Types:

```hcl
variable "names" {
  type = list(string)   # ["a", "b", "c"] — ordered, duplicates allowed
}

variable "unique_names" {
  type = set(string)    # {"a", "b", "c"} — unordered, no duplicates
}

variable "config" {
  type = map(string)    # {"key1" = "val1", "key2" = "val2"} — string keys
}
```

### Structural Types:

```hcl
variable "server" {
  type = object({
    instance_type = string
    count         = number
    tags          = map(string)
  })
}

variable "mixed_list" {
  type = tuple([string, number, bool])   # ["name", 42, true] — fixed length, mixed types
}
```

### Type Constraints and Conversion:

```hcl
# Terraform performs automatic type conversion where possible
variable "port" {
  type    = number
  default = 8080
}

# These all work — Terraform converts the string "8080" to number 8080
resource "aws_security_group_rule" "app" {
  from_port = var.port        # number
  to_port   = var.port        # number
  protocol  = "tcp"
}
```

**`any` type:**
Allows any type — Terraform infers the type from the value. Avoid this in public modules — it removes type safety and makes usage confusing.

---

## Common Mistakes to Avoid

- **No `description` on variables or outputs**: Makes the configuration impossible for others to use without reading the implementation.
- **Using variables where locals are appropriate**: Locals derived from other values should not be exposed as variables — you lose control over their computation.
- **Missing `sensitive = true` on credential outputs**: Credentials appear in plaintext in CI/CD logs.
- **Over-validating variables**: Validation that is too strict (e.g., hardcoding a specific region) breaks reusability. Validate constraints that are business rules, not implementation details.
- **Deeply nested locals referencing other locals**: Creates evaluation chains that are hard to debug. Keep local dependency depth shallow.
- **Using `type = any` in reusable modules**: Removes the type safety that makes Terraform configurations predictable and debuggable.
- **Not providing outputs for module resources**: Modules without outputs cannot be composed — callers have no way to get resource IDs or ARNs.
