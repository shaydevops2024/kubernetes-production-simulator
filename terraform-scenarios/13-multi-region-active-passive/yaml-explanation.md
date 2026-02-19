# Terraform Configuration Files Explanation - Multi-Region Active-Passive

This guide explains the Terraform configuration patterns for deploying infrastructure across multiple AWS regions, covering provider aliases, Route53 failover routing, and cross-region replication.

---

## Multiple Provider Aliases - Multi-Region Setup

### What are Provider Aliases?
By default, Terraform uses one provider configuration. Provider aliases allow you to configure the same provider multiple times with different settings — essential for multi-region deployments.

### HCL Structure Breakdown:

```hcl
# Primary region (default provider — no alias required)
provider "aws" {
  region = "us-east-1"
}

# Secondary region (alias required)
provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "ap_southeast_1"
  region = "ap-southeast-1"
}
```

**`alias`:** An identifier for this provider configuration. Used when referencing the provider in resources.
**Default provider:** The provider WITHOUT an alias is the default, used by all resources that don't specify `provider`.

### Using Provider Aliases in Resources:

```hcl
# Uses default provider (us-east-1)
resource "aws_s3_bucket" "primary" {
  bucket = "my-app-primary-us"
}

# Explicitly uses the eu-west-1 provider
resource "aws_s3_bucket" "secondary" {
  provider = aws.eu_west_1
  bucket   = "my-app-secondary-eu"
}
```

### Passing Providers to Modules:

```hcl
module "app_primary" {
  source = "./modules/app"
  # Module uses default provider (us-east-1)
}

module "app_secondary" {
  source = "./modules/app"
  providers = {
    aws = aws.eu_west_1    # Override the default provider for this module instance
  }
}
```

**`providers` in module block:** Maps the calling module's providers to the module's expected provider names. This is how you deploy the same module to multiple regions.

### Module Provider Declaration:

```hcl
# modules/app/versions.tf — declare expected providers
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      # No 'configuration_aliases' needed for simple cases
    }
  }
}
```

---

## for_each with Maps - Regional Configuration

### What is for_each?
`for_each` creates one resource instance per map entry or set element — much more flexible than `count` because instances have meaningful keys.

### HCL Structure Breakdown:

```hcl
variable "regions" {
  default = {
    primary = {
      region     = "us-east-1"
      is_primary = true
    }
    secondary = {
      region     = "eu-west-1"
      is_primary = false
    }
  }
}

# Creates one CloudWatch alarm per region
resource "aws_cloudwatch_metric_alarm" "health" {
  for_each = var.regions

  alarm_name          = "health-check-${each.key}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1

  dimensions = {
    HealthCheckId = aws_route53_health_check.endpoint[each.key].id
  }

  provider = each.value.is_primary ? aws : aws.eu_west_1
}
```

**`each.key`:** The map key (e.g., `"primary"`, `"secondary"`).
**`each.value`:** The map value (the nested object with `region`, `is_primary`, etc.).

### for_each vs count:
- `count = 2` creates `resource[0]` and `resource[1]` — fragile, order-dependent
- `for_each = {...}` creates `resource["primary"]` and `resource["secondary"]` — stable keys
- If you remove an item from the middle of a `count` list, all subsequent resources are destroyed and recreated. With `for_each`, only the removed item is affected.

---

## aws_route53_health_check - Endpoint Monitoring

### What is a Route53 Health Check?
Route53 health checks continuously monitor your endpoints from AWS's global network. Failed health checks trigger failover routing.

### HCL Structure Breakdown:

```hcl
resource "aws_route53_health_check" "primary" {
  fqdn              = "api.us-east-1.example.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = {
    Name = "primary-region-health-check"
  }
}
```

**`fqdn`:** The endpoint to check. Use your load balancer's DNS name or a dedicated health endpoint.
**`port`:** Port to check. `443` for HTTPS, `80` for HTTP.
**`type`:** Check type.
**Options:** `HTTP`, `HTTPS`, `TCP`, `HTTP_STR_MATCH`, `HTTPS_STR_MATCH`, `CALCULATED`

**`resource_path`:** URL path to check. Return 2xx for healthy, anything else for unhealthy.
**Best practice:** Create a dedicated `/health` endpoint that checks your application's dependencies (database, cache).

**`failure_threshold`:** Number of consecutive failures before marking unhealthy (1-10).
**`request_interval`:** How often to check, in seconds. `10` (fast) or `30` (standard).

---

## aws_route53_record with Failover Routing

### What is Failover Routing?
Route53 Failover routing returns the PRIMARY record when healthy, automatically switching to SECONDARY when the primary health check fails.

### HCL Structure Breakdown:

```hcl
# Primary record (active)
resource "aws_route53_record" "api_primary" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.example.com"
  type    = "A"

  alias {
    name                   = aws_lb.primary.dns_name
    zone_id                = aws_lb.primary.zone_id
    evaluate_target_health = true
  }

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary.id
}

# Secondary record (passive — only used when primary is unhealthy)
resource "aws_route53_record" "api_secondary" {
  provider = aws.eu_west_1
  zone_id  = data.aws_route53_zone.main.zone_id
  name     = "api.example.com"
  type     = "A"

  alias {
    name                   = aws_lb.secondary.dns_name
    zone_id                = aws_lb.secondary.zone_id
    evaluate_target_health = true
  }

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary"
  # Secondary doesn't need its own health check (Route53 uses primary's)
}
```

**`failover_routing_policy.type`:** `PRIMARY` or `SECONDARY`. Only one PRIMARY and one SECONDARY per name+type.
**`set_identifier`:** Unique identifier to distinguish records with the same name and type. Required for routing policies.
**`health_check_id`:** The health check that determines whether to serve this record. Only required on PRIMARY.
**`evaluate_target_health = true`:** Also check the target's own health (ALB health checks) in addition to Route53 health check.

### How Failover Works:
1. Route53 continuously polls the health check endpoint
2. After `failure_threshold` consecutive failures, primary is marked unhealthy
3. DNS responses switch to the SECONDARY record
4. TTL determines how quickly clients see the change
5. When primary recovers, Route53 automatically switches back

**RTO (Recovery Time Objective):** TTL + health check interval × failure_threshold
- Example: 60s TTL + 30s interval × 3 failures = 150 seconds maximum failover time

---

## aws_s3_bucket_replication_configuration - Cross-Region Replication

### What is S3 Cross-Region Replication?
Asynchronously copies objects from a source bucket to a destination bucket in another region. Useful for:
- DR (data available in secondary region before disaster)
- Compliance (data residency requirements)
- Latency reduction (users access nearby region)

### HCL Structure Breakdown:

```hcl
resource "aws_s3_bucket_replication_configuration" "primary_to_secondary" {
  depends_on = [aws_s3_bucket_versioning.primary]

  role   = aws_iam_role.s3_replication.arn
  bucket = aws_s3_bucket.primary.id

  rule {
    id     = "replicate-all"
    status = "Enabled"

    filter {
      prefix = ""  # Replicate everything
    }

    destination {
      bucket        = aws_s3_bucket.secondary.arn
      storage_class = "STANDARD_IA"  # Cheaper storage class for replica

      replication_time {
        status  = "Enabled"
        time { minutes = 15 }  # SLA: 99.99% of objects within 15 minutes
      }
    }

    delete_marker_replication {
      status = "Enabled"
    }
  }
}
```

**Prerequisites:**
- Both buckets must have versioning enabled
- Replication IAM role with `s3:ReplicateObject` and `s3:GetObjectVersion` permissions

**`role`:** IAM role that S3 uses to replicate objects. Must allow `s3.amazonaws.com` to assume it.
**`filter.prefix`:** Only replicate objects matching this prefix. Empty string = replicate everything.
**`destination.storage_class`:** Objects in the replica bucket can use cheaper storage class (STANDARD_IA, GLACIER).
**`replication_time`:** S3 Replication Time Control (STC) — an SLA that 99.99% of objects replicate within 15 minutes. Has an additional cost.
**`delete_marker_replication`:** Whether to replicate deletion markers. Enable to keep replica in sync with deletions.

---

## data "terraform_remote_state" - Cross-Stack References

### What is terraform_remote_state?
Read outputs from another Terraform state file. Used when infrastructure is split across multiple state files (recommended pattern for large systems).

### HCL Structure Breakdown:

```hcl
# In the secondary region stack, read outputs from primary
data "terraform_remote_state" "primary" {
  backend = "s3"

  config = {
    bucket = "my-terraform-state"
    key    = "production/primary-region/terraform.tfstate"
    region = "us-east-1"
  }
}

# Use outputs from the primary stack
resource "aws_route53_record" "api_secondary" {
  zone_id = data.terraform_remote_state.primary.outputs.route53_zone_id
  # ...
}
```

**When to use `terraform_remote_state`:**
- Sharing Route53 zone IDs across regional stacks
- Referencing VPC IDs from a networking stack
- Cross-environment references (read prod VPC ID from staging)

**Alternatives:**
- AWS SSM Parameter Store: Store values as parameters, read with `data "aws_ssm_parameter"`
- Direct data sources: Use `data "aws_route53_zone"` instead of remote state when possible
- Prefer data sources over remote state — less coupling between stacks

### Best Practices for Multi-Region:
- Use separate state files per region (not one state with multiple providers)
- Always test failover — simulate primary failure regularly
- Set low DNS TTLs (60s) on failover records
- Monitor replication lag for S3 and RDS replicas
- Document RTO/RPO targets and verify with actual failover tests
- Consider using AWS Global Accelerator for faster failover (sub-30-second)
