# Terraform Configuration Files Explanation - Remote State Backend

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## backend.tf - Remote State Configuration

### What is Remote State and Why Does it Matter?

By default, Terraform stores state in a local file called `terraform.tfstate`. This works for individual developers experimenting locally, but breaks down immediately in a team environment:

- **No sharing**: Your teammates cannot see your state — they cannot know what infrastructure currently exists
- **No locking**: Two people running `terraform apply` simultaneously will corrupt the state file
- **No backup**: A lost laptop means lost state — Terraform no longer knows what it manages
- **Security risk**: State contains secrets. A local file might end up in git.

Remote backends solve all of these problems by storing state in a shared, versioned, encrypted, lockable location.

### The Backend Block:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-company-terraform-state"
    key            = "environments/prod/vpc/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

**Where does this block live?**
The `backend` block lives inside the `terraform {}` block, typically in a file called `backend.tf` or at the top of `provider.tf`. It must be in the root configuration — backend blocks are not allowed inside modules.

**`bucket = "my-company-terraform-state"`**
- The S3 bucket that will hold the state file
- This bucket must already exist — Terraform cannot create it for you (chicken-and-egg: you need state to track the bucket, but you need the bucket to store state)
- Create this bucket manually or with a separate "bootstrap" Terraform configuration that uses local state
- Enable versioning on this bucket — if state gets corrupted, you can roll back to a previous version

**`key = "environments/prod/vpc/terraform.tfstate"`**
- The path within the bucket where the state file is stored
- This is the most important field for state isolation — different stacks must use different keys
- Common patterns:
  - `{component}/{environment}/terraform.tfstate` — component-first, good for multi-environment components
  - `{environment}/{component}/terraform.tfstate` — environment-first, good for environment isolation
  - `{environment}/{region}/{component}/terraform.tfstate` — for multi-region setups

**`region = "us-east-1"`**
- The region where the S3 bucket and DynamoDB table live
- Does not need to match the region you are deploying infrastructure into
- Often a dedicated "management" region is used for shared infrastructure like state storage

**`encrypt = true`**
- Enables server-side encryption for the state file at rest in S3
- Uses the bucket's default encryption key (or you can specify a KMS key ID with `kms_key_id`)
- State files often contain database passwords and private keys — encrypt them

**`dynamodb_table = "terraform-state-lock"`**
- Tells Terraform to use this DynamoDB table for state locking
- If omitted, there is no locking — dangerous for teams
- The table must exist before running `terraform init`

---

## DynamoDB State Locking

### How State Locking Works:

```hcl
resource "aws_dynamodb_table" "terraform_lock" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name      = "Terraform State Lock Table"
    ManagedBy = "Terraform"
  }
}
```

**`hash_key = "LockID"`**
- The `LockID` attribute name is required exactly as shown — Terraform hardcodes this name
- Do not change it — any other name and locking will not work
- `type = "S"` means string — the lock ID is a string in the format `<bucket>/<key>.tfstate-md5`

**`billing_mode = "PAY_PER_REQUEST"`**
- Lock operations are infrequent — PAY_PER_REQUEST (on-demand) is almost always cheaper than PROVISIONED for this use case
- A DynamoDB table with a single item write per `terraform apply` invocation does not need provisioned throughput

### What Happens During a Lock:

1. Engineer A runs `terraform apply` — Terraform writes a lock item to DynamoDB with a unique lock ID and timestamp
2. Engineer B runs `terraform apply` before A finishes — Terraform attempts to write a lock item, fails because the item already exists, and outputs:
   ```
   Error: Error acquiring the state lock
   
   Error message: ConditionalCheckFailedException: The conditional request failed
   Lock Info:
     ID:        3d3c2f60-7fb7-dc50-bc0f-5c5bb41af53e
     Path:      my-company-terraform-state/environments/prod/vpc/terraform.tfstate
     Operation: OperationTypeApply
     Who:       engineer-a@company.com
     Version:   1.6.6
     Created:   2024-01-15 10:30:00.123456789 +0000 UTC
   ```
3. Engineer A finishes — Terraform deletes the lock item from DynamoDB

### Force-Unlocking a Stuck Lock:

Sometimes a Terraform process crashes or is killed mid-apply, leaving the lock in place. Use the lock ID from the error message to force-unlock:

```bash
terraform force-unlock 3d3c2f60-7fb7-dc50-bc0f-5c5bb41af53e
```

Only do this when you are certain no other process is actually running. Force-unlocking while another process is applying will corrupt state.

---

## data "terraform_remote_state" - Cross-Stack References

### What is Cross-Stack State Reading?

Large infrastructure is split into multiple independent Terraform configurations (stacks) for safety and separation of concerns. A "network" stack creates the VPC. A "compute" stack creates EC2 instances that need to know the VPC ID. The compute stack cannot import the VPC resource (that would duplicate ownership), but it can read the network stack's outputs from remote state.

```hcl
data "terraform_remote_state" "network" {
  backend = "s3"

  config = {
    bucket = "my-company-terraform-state"
    key    = "environments/prod/network/terraform.tfstate"
    region = "us-east-1"
  }
}
```

**`data "terraform_remote_state" "network"`**
- A data source (reads existing data, does not create anything)
- The label `"network"` is the local name — used to reference outputs: `data.terraform_remote_state.network.outputs.vpc_id`

**`backend = "s3"`**
- Specifies the backend type of the state file being read
- Must match the backend type the other stack uses

**`config = {...}`**
- The configuration needed to find the state file — bucket, key, and region for S3 backends
- This points to the OTHER stack's state file, not your own

### Reading the Remote Outputs:

```hcl
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.medium"
  subnet_id     = data.terraform_remote_state.network.outputs.private_subnet_ids[0]

  vpc_security_group_ids = [
    data.terraform_remote_state.network.outputs.app_security_group_id
  ]
}
```

**`data.terraform_remote_state.network.outputs.private_subnet_ids[0]`**
- `data` — namespace for all data sources
- `terraform_remote_state` — the data source type
- `network` — local name you gave this data source
- `outputs` — the key to access the outputs map from the remote state
- `private_subnet_ids[0]` — index into the list output named `private_subnet_ids`

**What must the network stack export?**
The network stack must have an output named `private_subnet_ids`:
```hcl
# In the network stack's outputs.tf
output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "IDs of private subnets"
}
```

If the output does not exist in the remote state, Terraform will error.

### When to Use Remote State vs Module Outputs:

| Situation | Use |
|-----------|-----|
| Different Terraform configurations (separate state files) | `terraform_remote_state` data source |
| Same configuration, different modules | Module outputs: `module.network.vpc_id` |
| Shared infrastructure owned by another team | `terraform_remote_state` data source |
| Infrastructure created outside Terraform | `data "aws_vpc"` or similar AWS data sources |

---

## Backend Initialization Commands

### Initializing a Backend for the First Time:

```bash
terraform init
```
Downloads providers and configures the backend. If a `backend` block exists, Terraform prompts to copy any existing local state to the remote backend.

### Changing the Backend Configuration:

```bash
# When you change the backend block (e.g., different S3 bucket or key)
terraform init -reconfigure
```
`-reconfigure` discards the existing backend configuration and sets up the new one. It does NOT migrate state — if you want to move state to the new location, use `-migrate-state` instead.

```bash
# Migrate state from local to S3, or from one S3 location to another
terraform init -migrate-state
```
`-migrate-state` copies the existing state to the new backend. Use this when reorganizing state storage. Always back up state before migrating.

### Partial Backend Configuration:

For security, you can omit sensitive values from the `backend` block and pass them at `init` time:

```hcl
# In backend.tf — no secrets in code
terraform {
  backend "s3" {
    key    = "environments/prod/vpc/terraform.tfstate"
    region = "us-east-1"
  }
}
```

```bash
# Pass bucket at runtime
terraform init -backend-config="bucket=my-secret-bucket-name"

# Or from a file
terraform init -backend-config=backend-prod.conf
```

This pattern is common when the bucket name itself is sensitive or changes per environment.

---

## State Isolation Patterns

### Per-Environment Isolation:

The most common pattern — each environment has its own state file:

```
s3://terraform-state/
  environments/
    dev/
      vpc/terraform.tfstate
      eks/terraform.tfstate
      rds/terraform.tfstate
    staging/
      vpc/terraform.tfstate
      eks/terraform.tfstate
    prod/
      vpc/terraform.tfstate
      eks/terraform.tfstate
      rds/terraform.tfstate
```

**Benefit**: A mistake in dev never touches prod state. You can destroy dev without affecting prod.

### Per-Component Isolation:

Each component (network, compute, data layer) has its own state:

```
s3://terraform-state/
  network/prod/terraform.tfstate
  compute/prod/terraform.tfstate
  database/prod/terraform.tfstate
```

**Benefit**: Changes to the compute layer do not require loading the 500-resource network state. Plan is faster. Blast radius of mistakes is smaller.

### Per-Account Isolation:

Each AWS account has its own state bucket (recommended for multi-account setups):

```
# In the dev AWS account
s3://dev-account-terraform-state/
  vpc/terraform.tfstate

# In the prod AWS account  
s3://prod-account-terraform-state/
  vpc/terraform.tfstate
```

**Benefit**: A compromised CI/CD pipeline for dev cannot read or corrupt prod state.

---

## Creating the State Bootstrap Resources

The S3 bucket and DynamoDB table used for state storage must exist before you can use them as a backend. The standard approach:

```hcl
# bootstrap/main.tf — uses local state (or manually created)
resource "aws_s3_bucket" "terraform_state" {
  bucket = "my-company-terraform-state"
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_dynamodb_table" "terraform_lock" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}
```

Run this bootstrap configuration once with local state, then never touch it again. The bootstrap configuration itself does not use remote state — that would be circular.

---

## Common Mistakes to Avoid

- **Using the same state key for multiple configurations**: Two configurations writing to the same state file will corrupt each other's resources. Every configuration must have a unique key.
- **Not enabling versioning on the state bucket**: If state gets corrupted (by a crashed apply or a bug), you cannot recover without S3 versioning.
- **Not enabling encryption on the state bucket**: State files contain database passwords and private keys in plaintext. Always encrypt.
- **Forgetting `dynamodb_table` in the backend block**: Without it, Terraform has no locking — two simultaneous applies will corrupt state.
- **Hardcoding the backend config with secrets**: If your bucket name or account ID is sensitive, use partial backend configuration and pass secrets at `init` time.
- **Using `terraform_remote_state` for everything**: It creates tight coupling between stacks. For shared data that is not Terraform-managed (like an AMI ID or Account ID), use AWS data sources instead.
- **Force-unlocking without checking if another process is running**: Force-unlocking while an apply is in progress will corrupt state. Always verify the lock owner before force-unlocking.
