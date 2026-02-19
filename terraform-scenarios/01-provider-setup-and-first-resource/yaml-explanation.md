# Terraform Configuration Files Explanation - Provider Setup and First Resource

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## provider.tf - AWS Provider Configuration

### What is the Provider Block?

A provider in Terraform is a plugin that knows how to communicate with a specific API. The AWS provider translates your HCL resource declarations into AWS API calls. Without a provider, Terraform has no idea what AWS even is. The provider block lives in `provider.tf` by convention (though Terraform does not enforce file names — all `.tf` files in a directory are merged at runtime).

### HCL Structure Breakdown:

```hcl
terraform {
  required_version = "~> 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

**What it is:** The `terraform {}` block configures Terraform itself, not any provider. `required_version` pins the Terraform CLI version. `required_providers` tells Terraform which plugins to download and from where.

**`required_version = "~> 1.6"`**
- The `~>` operator is the pessimistic constraint — it allows patch and minor updates but not major version bumps
- `~> 1.6` allows `1.6.x`, `1.7.x`, `1.8.x` but NOT `2.0`
- `>= 1.6, < 2.0` is equivalent and more explicit
- `= 1.6.3` pins to an exact version (useful in CI/CD pipelines for strict reproducibility)

**Why pin the version?** Terraform 1.x introduced features that do not exist in 0.15. Someone on your team running Terraform 0.14 would get cryptic errors. Pinning ensures every contributor uses a compatible CLI version.

**`source = "hashicorp/aws"`**
- Format is `<namespace>/<provider>` on the default registry `registry.terraform.io`
- Full form is `registry.terraform.io/hashicorp/aws`
- Community providers use their own namespace: `mongodb/mongodbatlas`

**`version = "~> 5.0"`**
- Same pessimistic constraint — allows `5.1`, `5.9` but not `6.0`
- Provider versions matter: AWS provider 4.x vs 5.x have breaking changes in S3 resource structure
- Always check the provider changelog before upgrading major versions

---

```hcl
provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      ManagedBy   = "Terraform"
      Environment = var.environment
      Project     = var.project_name
    }
  }
}
```

**What it is:** The `provider "aws"` block configures the AWS provider instance. The label `"aws"` matches the key declared in `required_providers`.

**`region = "us-east-1"`**
- Tells the AWS provider which region to make API calls against
- Override per-resource using provider aliases: `provider = aws.us-west-2`
- Can use a variable: `region = var.aws_region` for multi-region setups
- Can also be set via environment variable `AWS_DEFAULT_REGION` — the provider checks env vars before reading the block

**`default_tags {}`**
- Applies these tags to every AWS resource created by this provider instance automatically
- Before `default_tags`, every resource needed `tags = { ... }` repeated — a maintenance nightmare across hundreds of resources
- Tags are critical for cost allocation (AWS Cost Explorer filters by tag), security audits, and automation runbooks
- `ManagedBy = "Terraform"` is a widely-used convention to signal that a resource should not be manually edited in the console

**Why use `var.environment` in tags?**
The same provider configuration can be reused across dev/staging/prod by changing the variable value. The state file records which environment owns which resource, making cost breakdowns accurate.

### Authentication

Terraform needs credentials to call AWS APIs. Never hardcode credentials in `.tf` files.

```hcl
# NEVER DO THIS
provider "aws" {
  region     = "us-east-1"
  access_key = "AKIAIOSFODNN7EXAMPLE"
  secret_key = "wJalrXUtnFEMI/K7MDENG..."
}
```

**Correct authentication approaches (in order of preference):**

1. **IAM roles for EC2/ECS/Lambda/CodeBuild** — no credentials needed, the compute resource has an attached role:
   ```hcl
   provider "aws" {
     region = "us-east-1"
     # credentials come from instance metadata service automatically
   }
   ```

2. **Environment variables** — set before running Terraform commands:
   ```bash
   export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
   export AWS_SECRET_ACCESS_KEY="wJalrXUtn..."
   export AWS_SESSION_TOKEN="..."  # required for assumed roles
   ```

3. **AWS credentials file** at `~/.aws/credentials`:
   ```ini
   [default]
   aws_access_key_id = AKIAIOSFODNN7EXAMPLE
   aws_secret_access_key = wJalrXUtn...

   [production]
   aws_access_key_id = AKID...
   ```
   Reference a named profile: `provider "aws" { profile = "production" }`

4. **`assume_role` block** — used in CI/CD pipelines and cross-account deployments:
   ```hcl
   provider "aws" {
     region = "us-east-1"
     assume_role {
       role_arn     = "arn:aws:iam::123456789012:role/TerraformDeployer"
       session_name = "TerraformSession"
     }
   }
   ```

### Best Practices:
- Always declare `required_version` and `required_providers` — leaving them absent means any Terraform version will be accepted
- Use `default_tags` to enforce tagging standards across all resources without repetition
- Use IAM roles over static credentials wherever compute infrastructure allows it
- Commit `provider.tf` to version control — it is the contract for which provider and Terraform versions are required
- Use separate provider aliases for multi-region or multi-account infrastructure

---

## main.tf - Resource Definitions

### What is a Resource Block?

A `resource` block declares a piece of infrastructure you want Terraform to create and manage. The block type (`resource`), the resource type (`aws_s3_bucket`), and the local name (`app_artifacts`) together form a unique address: `aws_s3_bucket.app_artifacts`. This address is how you reference this resource elsewhere in configuration and how Terraform tracks it in state.

### Basic Resource Block Syntax:

```hcl
resource "aws_s3_bucket" "app_artifacts" {
  bucket = "my-company-app-artifacts-${var.environment}"

  tags = {
    Name    = "App Artifacts Bucket"
    Purpose = "CI/CD artifact storage"
  }
}
```

**`resource "aws_s3_bucket" "app_artifacts"`**
- `aws_s3_bucket` — the resource type. The first part (`aws`) is the provider, the second part (`s3_bucket`) is the resource kind. Look these up in the Terraform AWS provider documentation at registry.terraform.io.
- `app_artifacts` — your local name. Used only within this Terraform configuration to reference this resource. It does not set the AWS resource name.
- Together they form the address `aws_s3_bucket.app_artifacts` used in attribute references, `terraform state` commands, and plan output.

**`bucket = "my-company-app-artifacts-${var.environment}"`**
- Sets the actual S3 bucket name in AWS
- S3 bucket names are globally unique across all AWS accounts and regions — name collisions cause errors
- String interpolation `${var.environment}` embeds the variable value directly in the string
- Omitting `bucket` lets AWS generate a random name — this is almost never desired

---

### Versioning as a Separate Resource:

```hcl
resource "aws_s3_bucket_versioning" "app_artifacts" {
  bucket = aws_s3_bucket.app_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}
```

**Why is versioning a separate resource block and not a nested block inside the bucket?**

In AWS provider version 4+, the monolithic S3 bucket resource was split into many separate resources (`aws_s3_bucket_versioning`, `aws_s3_bucket_server_side_encryption_configuration`, `aws_s3_bucket_public_access_block`, etc.). This was done to fix circular dependency problems and to align with how the AWS S3 API itself is structured.

**`bucket = aws_s3_bucket.app_artifacts.id`**
- This is an **attribute reference** — it reads the `id` attribute of the `aws_s3_bucket.app_artifacts` resource at plan time
- `.id` for S3 buckets resolves to the bucket name string
- This creates an **implicit dependency**: Terraform knows the bucket must be created before versioning can be configured. No `depends_on` is needed.
- Format: `<resource_type>.<local_name>.<attribute_name>`

**`status = "Enabled"`**
- Options: `"Enabled"`, `"Suspended"`, `"Disabled"`
- `"Suspended"` stops creating new versions but preserves existing ones — useful during cost investigations
- Never disable versioning on a bucket storing CI/CD artifacts, database backups, or Terraform state

---

### Public Access Block:

```hcl
resource "aws_s3_bucket_public_access_block" "app_artifacts" {
  bucket = aws_s3_bucket.app_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**What it does:** Prevents the bucket from ever being made public, regardless of bucket policy or object ACLs.

**Why all four settings?**
- `block_public_acls` — prevents adding public ACLs to new objects uploaded
- `block_public_policy` — prevents bucket policies that grant public access from being applied
- `ignore_public_acls` — ignores existing public ACLs already set on objects (retroactive protection)
- `restrict_public_buckets` — restricts public and cross-account access even if a public bucket policy exists

**Best practice:** Set all four to `true` for any bucket not intentionally serving public content. The exception is a static website hosting bucket.

---

### KMS Encryption:

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "app_artifacts" {
  bucket = aws_s3_bucket.app_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3_key.arn
    }
    bucket_key_enabled = true
  }
}
```

**`sse_algorithm = "aws:kms"`**
- Options: `"aws:kms"` (KMS-managed keys), `"AES256"` (S3-managed keys, also called SSE-S3)
- `aws:kms` gives you an audit trail in CloudTrail, key rotation control, and the ability to revoke access by disabling the key
- `AES256` is simpler but you lose key management granularity

**`kms_master_key_id = aws_kms_key.s3_key.arn`**
- References a KMS key resource defined elsewhere in configuration
- If omitted with `aws:kms`, AWS uses the default S3 KMS key — acceptable but you lose per-bucket key isolation

**`bucket_key_enabled = true`**
- Reduces KMS API calls by generating a short-lived bucket-level data key
- Can reduce KMS costs by up to 99% for high-throughput buckets
- Always enable this when using `aws:kms` — there is no downside

---

## Terraform Workflow

### The Four Core Commands:

```bash
terraform init
```
Downloads provider plugins declared in `required_providers`. Creates the `.terraform/` directory and `.terraform.lock.hcl`. Must be run first and after any provider or module source change. Safe to re-run at any time.

```bash
terraform plan
```
Shows what changes Terraform will make without making them. Reads current state, calls AWS APIs to check real infrastructure, computes the diff. Symbols in plan output:
- `+` create a new resource
- `~` update a resource in-place
- `-` destroy a resource
- `-/+` destroy and recreate (some changes cannot be made in-place)

Always read the full plan output before running apply.

```bash
terraform apply
```
Executes the plan. Prompts for confirmation (type `yes`). Pass `-auto-approve` in CI/CD pipelines. Updates `terraform.tfstate` after each resource operation completes. If interrupted mid-apply, re-run `apply` — Terraform is designed to be idempotent and resumes from where it left off.

```bash
terraform destroy
```
Removes all resources managed by this configuration. Shows a destruction plan first and requires confirmation. Use `-target=aws_s3_bucket.app_artifacts` to destroy only a specific resource.

### Dependency Graph:

Terraform builds a directed acyclic graph (DAG) from attribute references and explicit `depends_on` declarations. Resources with no dependencies are created in parallel. The bucket versioning resource depends on the bucket because it references `aws_s3_bucket.app_artifacts.id`, so Terraform automatically sequences them correctly.

---

## .terraform.lock.hcl - Dependency Lock File

### What is it?

The lock file records the exact provider versions and cryptographic hashes selected during `terraform init`. It is analogous to `package-lock.json` in Node.js or `Gemfile.lock` in Ruby.

```hcl
# This file is maintained automatically by "terraform init".
# Manual edits may be lost in future updates.

provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.31.0"
  constraints = "~> 5.0"
  hashes = [
    "h1:rgpNfyNKOCtlIYAHKbFQoJGTHhOobWWlCR/UHSRL9+Y=",
    "zh:0843017ecc24385f2b45f2c5fce79dc25b258e50d516877b3affee3bef34f060",
  ]
}
```

**`version = "5.31.0"`**
The exact version selected that satisfies the constraint `~> 5.0`. This is what gets installed on every machine running `terraform init` with this lock file present.

**`hashes`**
Cryptographic hashes (SHA-256) of the provider binary for multiple platforms. Terraform verifies these on download to detect tampering or corruption.
- `h1:` prefix — hash of the zip archive
- `zh:` prefix — hash of individual files within the zip

### Why commit the lock file to git?

Committing `.terraform.lock.hcl` ensures every team member and CI/CD pipeline installs the exact same provider version. Without it, `terraform init` might install `5.32.0` on your laptop and `5.29.0` in CI, causing subtle plan differences that are hard to debug.

### Updating the lock file:

```bash
# Upgrade providers to latest versions satisfying constraints
terraform init -upgrade

# Add hashes for additional platforms (e.g., add Linux hashes when developing on macOS)
terraform providers lock -platform=linux_amd64 -platform=darwin_amd64
```

---

## terraform.tfstate - State File

### What is State?

Terraform state is a JSON file that maps your HCL resource declarations to real infrastructure objects. When you write `resource "aws_s3_bucket" "app_artifacts"`, Terraform records the AWS-assigned resource ID in state. On the next `plan`, Terraform reads state to know what it last created, calls AWS to check current real configuration, and computes the diff between desired and actual.

```json
{
  "version": 4,
  "terraform_version": "1.6.6",
  "resources": [
    {
      "mode": "managed",
      "type": "aws_s3_bucket",
      "name": "app_artifacts",
      "instances": [
        {
          "attributes": {
            "id": "my-company-app-artifacts-dev",
            "arn": "arn:aws:s3:::my-company-app-artifacts-dev",
            "bucket": "my-company-app-artifacts-dev"
          }
        }
      ]
    }
  ]
}
```

### Rules for State:

1. **Never edit state manually** — use `terraform state mv`, `terraform state rm`, `terraform import` for state operations
2. **Never commit state to git** — it contains secrets (database passwords, private keys) in plaintext
3. **Use remote backends** — S3 + DynamoDB, Terraform Cloud, or GitLab-managed state for team environments
4. **State locking** — remote backends provide locking to prevent concurrent applies from corrupting state

### Common state commands:

```bash
# List all resources tracked in state
terraform state list

# Show detailed attributes of a specific resource
terraform state show aws_s3_bucket.app_artifacts

# Remove a resource from state without destroying the real resource
terraform state rm aws_s3_bucket.app_artifacts

# Move a resource to a new address (used when refactoring)
terraform state mv aws_s3_bucket.app_artifacts aws_s3_bucket.artifacts
```

---

## Common Mistakes to Avoid

- **Forgetting `required_providers`**: Terraform may install any available version, causing unpredictable behavior across team environments.
- **Hardcoding AWS credentials**: They end up in git history and in the state file. Always use env vars or IAM roles.
- **Not using `default_tags`**: Leads to untagged resources, making cost attribution and security audits painful.
- **Committing `terraform.tfstate` to git**: The state file often contains database passwords and other secrets in plaintext.
- **Ignoring the plan output**: Always read the full plan. A `-` destroy line on a production database should stop you immediately.
- **Using the old S3 bucket versioning syntax**: In AWS provider 4+, versioning is a separate `aws_s3_bucket_versioning` resource. Using the deprecated inline block causes conflicts.
- **Not pinning provider versions**: A provider major version update can change resource attribute names and behavior, causing unexpected plan diffs or apply failures.
