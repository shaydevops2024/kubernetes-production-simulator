# Terraform Configuration Files Explanation - RDS Multi-AZ with Backups

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## aws_db_subnet_group - Database Subnet Group

### What is a DB Subnet Group?
A DB subnet group tells RDS which subnets to use when placing database instances. RDS requires at least two subnets in different Availability Zones, enabling Multi-AZ deployments and ensuring high availability.

### HCL Structure Breakdown:

```hcl
resource "aws_db_subnet_group" "main" {
  name        = "production-db-subnet-group"
  description = "Subnet group for production RDS instances"
  subnet_ids  = module.vpc.private_subnet_ids

  tags = {
    Name        = "production-db-subnet-group"
    Environment = var.environment
  }
}
```

**`name`:** Unique identifier for the subnet group within your account and region.
**Why:** RDS references this name when launching instances, so keep it descriptive.

**`subnet_ids`:** List of private subnet IDs. Always use private subnets for databases — never public ones.
**Why:** Databases should never be directly reachable from the internet. Private subnets have no internet gateway route.

**`description`:** Human-readable description shown in the AWS Console.

### Best Practices:
- Always use private subnets (no route to internet gateway)
- Span at least 3 AZs for maximum availability
- Keep the subnet group separate from application subnets for network isolation

---

## aws_db_instance - The RDS Instance

### What is aws_db_instance?
The core resource for creating a managed relational database. AWS handles patching, backups, failover, and hardware replacement.

### HCL Structure Breakdown:

```hcl
resource "aws_db_instance" "main" {
  identifier        = "production-postgres"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "appdb"
  username = "dbadmin"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az               = true
  publicly_accessible    = false
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "production-postgres-final"

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_monitoring.arn

  tags = {
    Environment = var.environment
  }
}
```

**`identifier`:** Unique name for the RDS instance. Used in the endpoint hostname.
**Options:** Lowercase letters, numbers, hyphens. Max 63 characters.

**`engine`:** The database engine.
**Options:** `postgres`, `mysql`, `mariadb`, `oracle-se2`, `sqlserver-ex`, `aurora-postgresql`, `aurora-mysql`

**`engine_version`:** Specific version. Pin to a specific minor version in production.
**Why:** Auto-upgrades can break applications. Control when you upgrade.

**`instance_class`:** The compute and memory capacity.
**Options:** `db.t3.micro` (dev), `db.t3.medium`, `db.r6g.large` (prod), `db.r6g.4xlarge` (large workloads)
**Why:** `t3` instances are burstable (good for dev/test), `r6g` instances have dedicated CPU and memory (good for production).

**`allocated_storage`:** Storage size in GiB. Can be increased but never decreased.
**`storage_type`:** `gp2` (older), `gp3` (recommended, cheaper with better baseline performance), `io1` (provisioned IOPS for highest performance)

**`storage_encrypted = true`:** Encrypts the database storage with KMS. Always enable in production.

**`multi_az = true`:** Creates a standby replica in a different AZ. Automatic failover in 1-2 minutes if primary fails.
**Important:** Multi-AZ is for high availability, NOT for read scaling. The standby cannot serve reads — use read replicas for that.

**`publicly_accessible = false`:** Database is only reachable from within the VPC. Never set to `true` in production.

**`deletion_protection = true`:** Prevents `terraform destroy` from deleting the database.
**Why:** Accidentally deleting a production database is catastrophic. Always enable this.

**`skip_final_snapshot = false`:** Takes a final snapshot before deletion.
**`final_snapshot_identifier`:** Name for the final snapshot. Required when `skip_final_snapshot = false`.

**`backup_retention_period`:** How many days to keep automated backups. `0` disables backups.
**Options:** 0-35 days. Use at least 7 in production, 14-35 for critical databases.

**`backup_window`:** UTC time window for automated backups. Choose a low-traffic period.
**Format:** `"HH:MM-HH:MM"` in UTC. Must not overlap with `maintenance_window`.

**`maintenance_window`:** UTC time window for AWS maintenance (minor version patches, hardware updates).
**Format:** `"Ddd:HH:MM-Ddd:HH:MM"`. Example: `"Mon:04:00-Mon:05:00"`

**`performance_insights_enabled`:** Enables Performance Insights — a database monitoring tool showing query-level performance.
**`monitoring_interval`:** Enhanced Monitoring interval in seconds (0 = disabled, 60 = recommended).
**`monitoring_role_arn`:** IAM role that allows RDS to publish metrics to CloudWatch.

### Best Practices:
- Always enable `deletion_protection` in production
- Always enable `storage_encrypted`
- Set `backup_retention_period` to at least 7 days
- Use `gp3` storage (cheaper than `gp2` and better performance)
- Never use `skip_final_snapshot = true` in production
- Store passwords in Secrets Manager, not in `.tfvars` files

---

## random_password - Generating Secure Passwords

### What is the random provider?
The `hashicorp/random` provider generates random values that are stored in Terraform state. Unlike regular resources, random values are generated once and remain stable across applies.

### HCL Structure Breakdown:

```hcl
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%^&*()-_=+[]{}|;:,.<>?"
  min_upper        = 4
  min_lower        = 4
  min_numeric      = 4
  min_special      = 4
}
```

**`length`:** Total password length. Use at least 16, prefer 32 for databases.
**`special`:** Include special characters.
**`override_special`:** Limit special characters to those accepted by your database engine. Some engines reject `@`, `/`, `"`, `'`.
**`min_upper/min_lower/min_numeric/min_special`:** Enforce character class minimums for compliance requirements.

### Important Warning:
Random passwords are stored in plaintext in Terraform state. Always:
1. Use remote state with encryption (S3 + KMS)
2. Store the password in Secrets Manager immediately after generation
3. Mark outputs as `sensitive = true`

---

## aws_secretsmanager_secret - Storing Database Credentials

### Why Secrets Manager Instead of tfvars?
Storing passwords in `.tfvars` files means they end up in version control or CI/CD logs. Secrets Manager provides:
- Automatic rotation
- Fine-grained IAM access control
- Audit logging via CloudTrail
- Encryption at rest with KMS

### HCL Structure Breakdown:

```hcl
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "/${var.environment}/rds/postgres/credentials"
  description             = "RDS PostgreSQL credentials for production"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 30

  tags = {
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = aws_db_instance.main.username
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    dbname   = aws_db_instance.main.db_name
  })
}
```

**`name`:** Path-like naming (e.g., `/prod/rds/postgres/credentials`) helps organize secrets by environment and service.
**`recovery_window_in_days`:** After deletion, secret is recoverable for this many days. Use 30 in production.
**`kms_key_id`:** Custom KMS key for encrypting the secret (default uses AWS managed key).
**`secret_string`:** The actual secret value. Using `jsonencode()` stores structured data as JSON.

**Why store host/port/dbname alongside credentials?**
Applications retrieve a single secret and get everything needed to connect. No need to hardcode hostnames.

---

## aws_db_parameter_group - Database Tuning

### What is a Parameter Group?
A parameter group controls database engine configuration settings (equivalent to `postgresql.conf` or `my.cnf`). Always create a custom parameter group — never rely on the default.

### HCL Structure Breakdown:

```hcl
resource "aws_db_parameter_group" "postgres" {
  name   = "production-postgres15"
  family = "postgres15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
    apply_method = "immediate"
  }

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  tags = {
    Environment = var.environment
  }
}
```

**`family`:** Parameter group family tied to engine + major version. `postgres15`, `mysql8.0`, `aurora-postgresql15`.
**Warning:** Changing `family` requires replacing the parameter group and the DB instance.

**`parameter` blocks:**
- `name`: The parameter name (engine-specific)
- `value`: The parameter value (always a string in Terraform, even for numbers)
- `apply_method`: `immediate` applies without restart, `pending-reboot` requires maintenance window restart

**Common PostgreSQL parameters:**
- `log_min_duration_statement`: Log queries slower than N milliseconds (good for identifying slow queries)
- `shared_preload_libraries`: Load extensions at startup (`pg_stat_statements` for query statistics)
- `work_mem`: Memory per sort/hash operation (affects query performance)
- `max_connections`: Maximum concurrent connections

### Best Practices:
- Always create a custom parameter group — you cannot modify the default
- Test parameter changes in staging before production
- `pending-reboot` parameters require a maintenance window restart — plan accordingly

---

## Read Replicas - Scaling Read Traffic

### What is a Read Replica?
A read replica is an asynchronous copy of the primary database. It can serve `SELECT` queries, offloading read traffic from the primary. Unlike Multi-AZ standbys, read replicas are accessible.

### HCL Structure Breakdown:

```hcl
resource "aws_db_instance" "replica" {
  identifier             = "production-postgres-replica-1"
  replicate_source_db    = aws_db_instance.main.identifier
  instance_class         = "db.t3.medium"
  storage_encrypted      = true
  publicly_accessible    = false
  backup_retention_period = 0
  skip_final_snapshot    = true

  tags = {
    Role = "read-replica"
  }
}
```

**`replicate_source_db`:** The identifier of the primary instance. This is what makes it a read replica.
**`backup_retention_period = 0`:** Read replicas don't need their own backup (primary is backed up).
**`skip_final_snapshot = true`:** Replicas can be deleted and recreated easily — no need for final snapshot.

**Key differences: Multi-AZ vs Read Replica:**
- Multi-AZ standby: Same region, same data, automatic failover, NOT accessible
- Read replica: Can be cross-region, slightly behind primary, accessible for reads, manual promotion

### Best Practices:
- Monitor replica lag (`ReplicaLag` CloudWatch metric)
- Use replicas for reporting/analytics workloads to avoid impacting primary
- Cross-region replicas provide DR capability

---

## sensitive Outputs - Protecting Secrets

### Why Use sensitive = true?

```hcl
output "db_password" {
  value     = random_password.db.result
  sensitive = true
}

output "db_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "db_connection_string" {
  value     = "postgresql://${aws_db_instance.main.username}:${random_password.db.result}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive = true
}
```

**`sensitive = true`:** Redacts the value in `terraform plan` and `terraform apply` output, showing `(sensitive value)` instead.

**Important:** `sensitive = true` does NOT:
- Remove the value from state (it's still in plaintext in `.tfstate`)
- Encrypt the value
- Prevent access via `terraform output -json`

It only prevents accidental display in terminal output and CI/CD logs.

### Best Practices:
- Mark any output containing passwords, keys, or tokens as `sensitive = true`
- Prefer storing credentials in Secrets Manager rather than outputting them
- Use `terraform output -raw db_password` (not `-json`) to retrieve sensitive values in scripts
