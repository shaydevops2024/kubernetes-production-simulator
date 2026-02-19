# Terraform Configuration Files Explanation - Zero-Downtime Blue-Green Deployments

This guide explains the Terraform configuration patterns for implementing blue-green deployments with zero downtime, covering lifecycle rules, ALB weighted routing, and traffic shifting strategies.

---

## lifecycle { create_before_destroy } - Zero-Downtime Resource Replacement

### What is create_before_destroy?
By default, Terraform destroys the old resource before creating the new one. `create_before_destroy = true` reverses this — creating the replacement first, then destroying the old one. This eliminates the brief downtime that would otherwise occur.

### HCL Structure Breakdown:

```hcl
resource "aws_launch_template" "app" {
  name_prefix   = "app-"
  image_id      = var.ami_id
  instance_type = "m5.large"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "app" {
  name_prefix         = "app-"
  min_size            = 2
  max_size            = 10
  desired_capacity    = 3

  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**Why use `name_prefix` with `create_before_destroy`?**
If both old and new resources must exist simultaneously, they can't have the same name. `name_prefix` + random suffix ensures unique names. When the lifecycle is `create_before_destroy`, Terraform handles the naming conflict automatically.

**Without `create_before_destroy`:**
1. Old ASG destroyed (instances terminated, brief outage)
2. New ASG created (new instances launch, takes time to become healthy)
3. Total downtime: instance termination time + new instance boot time

**With `create_before_destroy`:**
1. New ASG created (new instances launch alongside old)
2. New instances become healthy (traffic continues to old ASG)
3. Old ASG destroyed (only after new is healthy)
4. Total downtime: 0

---

## Blue-Green Architecture with ALB

### The Pattern Explained

```
Internet
    │
    ▼
ALB Listener (port 443)
    │
    ├── Blue Target Group  (weight: 100%)  ← active
    └── Green Target Group (weight: 0%)    ← standby

                    AFTER DEPLOYMENT:
    │
    ├── Blue Target Group  (weight: 0%)    ← draining
    └── Green Target Group (weight: 100%)  ← active
```

### HCL Structure Breakdown:

```hcl
# Blue target group (current active environment)
resource "aws_lb_target_group" "blue" {
  name     = "app-blue"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Green target group (new version being deployed)
resource "aws_lb_target_group" "green" {
  name     = "app-green"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**Two separate target groups** maintain two independent sets of instances. Swapping traffic between them is instantaneous at the ALB level.

---

## aws_lb_listener_rule - Traffic Routing

### What is a Listener Rule?
ALB listener rules evaluate incoming requests and route them based on conditions (path, host, headers). Weighted forward actions split traffic between multiple target groups.

### HCL Structure Breakdown:

```hcl
variable "traffic_dist" {
  description = "Traffic distribution between blue and green"
  type = object({
    blue  = number
    green = number
  })
  default = {
    blue  = 100
    green = 0
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type = "forward"

    forward {
      target_group {
        arn    = aws_lb_target_group.blue.arn
        weight = var.traffic_dist.blue
      }
      target_group {
        arn    = aws_lb_target_group.green.arn
        weight = var.traffic_dist.green
      }

      stickiness {
        enabled  = true
        duration = 600  # 10 minutes — same user goes to same version
      }
    }
  }
}
```

**`weight`:** Relative weight for traffic distribution. `blue = 100, green = 0` sends 100% to blue. `blue = 50, green = 50` splits evenly.
**Note:** Weights are relative, not percentages. `blue = 3, green = 1` sends 75% to blue.

**`stickiness`:** Session stickiness (sticky sessions). Users are routed to the same target group for the duration. Important during blue-green to prevent users from bouncing between versions mid-session.

### Deployment Process:

```hcl
# Stage 1: 100% blue (before deployment)
traffic_dist = {
  blue  = 100
  green = 0
}

# Stage 2: 10% canary (initial validation)
traffic_dist = {
  blue  = 90
  green = 10
}

# Stage 3: 50/50 (broader validation)
traffic_dist = {
  blue  = 50
  green = 50
}

# Stage 4: Complete cutover
traffic_dist = {
  blue  = 0
  green = 100
}
```

Each stage is applied with `terraform apply -var='traffic_dist={"blue":90,"green":10}'`.

---

## null_resource - Running Scripts in Terraform

### What is null_resource?
`null_resource` is a resource that creates nothing real in the cloud. It's used to run scripts (via `local-exec` or `remote-exec` provisioners) triggered by infrastructure changes.

### HCL Structure Breakdown:

```hcl
resource "null_resource" "wait_for_instances" {
  triggers = {
    asg_name = aws_autoscaling_group.green.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for green ASG instances to become healthy..."
      aws autoscaling wait instance-in-service \
        --auto-scaling-group-name ${aws_autoscaling_group.green.name}
      echo "All green instances are healthy!"
    EOT
  }
}
```

**`triggers`:** A map of values that, when changed, cause the `null_resource` to be replaced (re-running the provisioner).
**`local-exec`:** Runs a command on the machine running Terraform (your laptop or CI server).
**`remote-exec`:** Runs a command on the remote resource (requires SSH/WinRM access).

**When to use `null_resource`:**
- Waiting for an ASG to become healthy before switching traffic
- Running database migrations after RDS creation
- Calling an external API or webhook

**Warning:** Avoid provisioners when possible — they make Terraform less declarative and harder to test. Prefer using AWS-native mechanisms (user data, Lambda functions, AWS Systems Manager).

---

## time_sleep Resource - Adding Delays

### What is the time Provider?
The `hashicorp/time` provider provides resources for working with time, including adding deliberate delays between operations.

### HCL Structure Breakdown:

```hcl
terraform {
  required_providers {
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

resource "time_sleep" "wait_for_deployment" {
  depends_on = [aws_autoscaling_group.green]

  create_duration = "120s"  # Wait 2 minutes after ASG creation
}

resource "aws_lb_listener" "https" {
  depends_on = [time_sleep.wait_for_deployment]
  # This listener update only runs after the 120s wait
  # ...
}
```

**`create_duration`:** How long to wait on resource creation.
**`destroy_duration`:** How long to wait on resource destruction (useful for graceful draining).

**Use cases:**
- Wait for instances to become healthy after ASG scaling
- Allow DNS propagation after Route53 changes
- Give applications time to start after deployment

**Warning:** `time_sleep` makes your apply take longer and is a code smell — it means you're working around eventual consistency. Prefer using proper health checks and waiters (like `null_resource` with `aws autoscaling wait`).

---

## Canary Deployment Pattern

### What is Canary Deployment?
A canary deployment gradually shifts traffic to the new version, monitoring for errors before committing to full rollout. Named after the canary in a coal mine — small exposure before full deployment.

### Implementation with Variables:

```hcl
variable "canary_percentage" {
  description = "Percentage of traffic sent to new (green) version"
  type        = number
  default     = 0

  validation {
    condition     = var.canary_percentage >= 0 && var.canary_percentage <= 100
    error_message = "Canary percentage must be between 0 and 100."
  }
}

locals {
  blue_weight  = 100 - var.canary_percentage
  green_weight = var.canary_percentage
}
```

### Rollback:

```bash
# Full rollback: set canary percentage to 0
terraform apply -var="canary_percentage=0"

# This is the key advantage of Terraform blue-green:
# Rollback is just changing a variable and re-applying
# No complex rollback procedures needed
```

### Automated Canary with CloudWatch:

```hcl
resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "green-error-rate-too-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10

  dimensions = {
    TargetGroup  = aws_lb_target_group.green.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  # When this alarm fires, trigger rollback via Lambda/CI pipeline
}
```

### Best Practices:
- Always keep the previous version (blue) running during deployment
- Use health checks that test actual application functionality, not just port availability
- Monitor error rates, latency, and business metrics during canary phase
- Automate rollback based on CloudWatch alarms
- Test rollback as often as you test deployment
- Keep blue-green color labels consistent (don't rename after each deploy)
