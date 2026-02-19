# Terraform Configuration Files Explanation - Auto Scaling Group with ALB

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## launch_template.tf - EC2 Launch Template

### What is a Launch Template?

A Launch Template defines the configuration for EC2 instances that will be created by an Auto Scaling Group. Think of it as a blueprint: every time the ASG needs to launch a new instance (on scale-out or to replace a failed instance), it uses this template to know what AMI, instance type, storage, IAM role, and startup script to use.

Launch templates replaced the older Launch Configurations (which are immutable — you cannot edit them). Launch templates support versioning: you can update a template and roll out the new version gradually.

### aws_launch_template Resource:

```hcl
resource "aws_launch_template" "app" {
  name_prefix   = "${local.name_prefix}-app-"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_app.name
  }

  vpc_security_group_ids = [aws_security_group.app.id]

  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tpl", {
    environment  = var.environment
    project_name = var.project_name
    db_endpoint  = aws_db_instance.main.endpoint
  }))

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.common_tags, {
      Name = "${local.name_prefix}-app"
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags = local.common_tags
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**`name_prefix = "${local.name_prefix}-app-"`**
- When a launch template is updated, the ASG can create a new version rather than modifying in-place
- `name_prefix` combined with `create_before_destroy` ensures the new version gets a unique name before the old one is removed
- Terraform appends a random suffix when `name_prefix` is used: `webapp-prod-app-20240115100000`

**`image_id = data.aws_ami.ubuntu.id`**
- The Amazon Machine Image (AMI) to use for instances — defines the OS and base software
- Using a `data` source to look up the latest Ubuntu AMI rather than hardcoding an AMI ID keeps the template current
- AMI IDs are region-specific — `ami-0abcdef1234567890` in `us-east-1` does not exist in `us-west-2`

**`instance_type = var.instance_type`**
- The EC2 instance type determines CPU, memory, and network capacity
- Common types: `t3.micro` (dev), `t3.medium` (small prod), `c5.xlarge` (compute-intensive)
- Can be overridden by the ASG's `mixed_instances_policy` for cost optimization with Spot Instances

**`iam_instance_profile { name = ... }`**
- Attaches an IAM instance profile to instances, giving them AWS permissions without hardcoded credentials
- The application running on the instance uses the profile's role to make AWS API calls
- See scenario 05 for IAM instance profile details

**`vpc_security_group_ids = [...]`**
- List of security group IDs to attach to launched instances
- Controls what traffic the instance can send and receive
- Use security group IDs, not names — IDs are stable, names can change

---

### user_data Field:

```hcl
user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tpl", {
  environment  = var.environment
  project_name = var.project_name
  db_endpoint  = aws_db_instance.main.endpoint
}))
```

**`user_data`**
- A script that runs automatically when an EC2 instance first starts (via cloud-init)
- Used to install software, configure the application, pull code, set environment variables
- Must be base64-encoded — AWS expects base64 in launch templates
- Maximum size: 16 KB

**`base64encode(...)`**
- Terraform built-in function that base64-encodes a string
- Required because the `user_data` field in AWS accepts only base64-encoded content

**`templatefile("${path.module}/templates/user_data.sh.tpl", { ... })`**
- Reads a template file and renders it with the provided variables
- `${path.module}` is the directory of the current Terraform module — ensures the path works regardless of where `terraform` is run from
- Variables in the template are referenced as `${variable_name}` in the template file

### Template File (user_data.sh.tpl):

```bash
#!/bin/bash
set -euo pipefail

# Set environment variables
export APP_ENV="${environment}"
export PROJECT="${project_name}"
export DB_ENDPOINT="${db_endpoint}"

# Install application
apt-get update -y
apt-get install -y nodejs npm

# Pull application code
aws s3 cp s3://${project_name}-${environment}-artifacts/app.zip /opt/app.zip
cd /opt && unzip app.zip

# Start application
systemctl start app
```

The `${variable_name}` placeholders in the template are replaced by Terraform at plan time using the variables passed to `templatefile()`. This is cleaner than embedding a large heredoc directly in the `.tf` file.

---

### tag_specifications Block:

```hcl
tag_specifications {
  resource_type = "instance"
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-app"
  })
}

tag_specifications {
  resource_type = "volume"
  tags = local.common_tags
}
```

**`resource_type`**
- The type of resource to apply these tags to when launched
- Options: `"instance"`, `"volume"`, `"network-interface"`, `"spot-instances-request"`
- Without `tag_specifications`, instances and volumes launched by the ASG will not have tags — they become impossible to identify in the AWS console

**Why separate `tag_specifications` for instances and volumes?**
EBS volumes (the storage disks attached to EC2 instances) are separate resources from the instances themselves. If you tag only instances, volumes are untagged and cannot be identified for cost allocation or cleanup.

---

## autoscaling.tf - Auto Scaling Group

### aws_autoscaling_group Resource:

```hcl
resource "aws_autoscaling_group" "app" {
  name                = "${local.name_prefix}-app-asg"
  vpc_zone_identifier = var.private_subnet_ids
  target_group_arns   = [aws_lb_target_group.app.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_capacity

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-app"
    propagate_at_launch = true
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}
```

**`vpc_zone_identifier = var.private_subnet_ids`**
- List of subnet IDs where the ASG will launch instances
- The ASG distributes instances across these subnets (and their AZs) for high availability
- Use private subnets — instances should not be directly internet-accessible
- Include subnets from at least 2 AZs

**`target_group_arns = [aws_lb_target_group.app.arn]`**
- Registers new instances automatically with the ALB target group when they launch
- Deregisters instances from the target group before terminating them (connection draining)
- This is how the ALB knows to send traffic to the new instances

**`health_check_type = "ELB"`**
- Options: `"EC2"` or `"ELB"`
- `"EC2"` — considers an instance healthy if it is running (not terminated/stopped). Basic check.
- `"ELB"` — considers an instance healthy only if the load balancer's health check passes. Recommended for web services.
- With `"ELB"`, if your application crashes but the EC2 instance keeps running, the ASG will eventually replace the instance because the ALB marks it unhealthy

**`health_check_grace_period = 300`**
- Seconds to wait after an instance launches before starting health checks
- Give the instance time to fully initialize (install software, start the application) before the ASG might terminate it as "unhealthy"
- Tune this based on your startup time. If initialization takes 2 minutes, set at least 180 seconds.

**`min_size`, `max_size`, `desired_capacity`**
- `min_size` — never scale below this number of instances (even if all traffic stops)
- `max_size` — never scale above this number (cost control, resource limit)
- `desired_capacity` — initial number of instances. Scaling policies will change this at runtime.

**`launch_template { version = "$Latest" }`**
- `"$Latest"` — always use the latest version of the launch template
- `"$Default"` — use the version marked as default in the launch template
- Specific version: `"3"` — always use version 3 (most predictable for blue/green)

**`instance_refresh`**
- When the launch template changes (e.g., new AMI), triggers a rolling replacement of instances
- `strategy = "Rolling"` — replaces instances in batches
- `min_healthy_percentage = 50` — always keep at least 50% of instances healthy during refresh
- Without instance_refresh, you must manually terminate instances to get them replaced with the new template

**`lifecycle { ignore_changes = [desired_capacity] }`**
- Tells Terraform to ignore changes to `desired_capacity` in state
- When a scaling policy changes desired_capacity (from 3 to 5), Terraform would otherwise try to "fix" it back to 3 on the next apply
- `ignore_changes` prevents Terraform from interfering with the ASG's autonomy to scale

---

## autoscaling_policy.tf - Scaling Policies

### aws_autoscaling_policy with Target Tracking:

```hcl
resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                   = "${local.name_prefix}-cpu-target-tracking"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

**`policy_type = "TargetTrackingScaling"`**
- The most modern and recommended scaling policy type
- Options: `"TargetTrackingScaling"`, `"StepScaling"`, `"SimpleScaling"`
- `TargetTrackingScaling` — set a target metric value, AWS manages the scaling math
- `StepScaling` — define scaling steps based on breach thresholds (more control, more config)
- `SimpleScaling` — legacy, triggers a single scaling action on alarm (avoid for new workloads)

**`predefined_metric_type = "ASGAverageCPUUtilization"`**
- The metric AWS uses to track and scale
- Predefined options: `"ASGAverageCPUUtilization"`, `"ASGAverageNetworkIn"`, `"ASGAverageNetworkOut"`, `"ALBRequestCountPerTarget"`
- `"ALBRequestCountPerTarget"` scales based on request count per instance — good for web services

**`target_value = 70.0`**
- Target 70% CPU utilization across all instances in the ASG
- AWS will add instances when average CPU exceeds 70%, remove when it drops well below
- AWS adds a stabilization period to prevent thrashing (rapid scale-up and scale-down)

### Custom Metric Scaling Policy:

```hcl
resource "aws_autoscaling_policy" "request_count" {
  name                   = "${local.name_prefix}-request-count"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    customized_metric_specification {
      metric_name = "RequestCountPerTarget"
      namespace   = "MyApp/Performance"
      statistic   = "Average"

      metric_dimension {
        name  = "Environment"
        value = var.environment
      }
    }
    target_value = 100.0  # 100 requests per instance
  }
}
```

Use a `customized_metric_specification` when your application publishes custom CloudWatch metrics that better reflect load than CPU or network.

---

## alb.tf - Application Load Balancer

### aws_lb Resource:

```hcl
resource "aws_lb" "app" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.environment == "prod"

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb"
    enabled = true
  }

  tags = local.common_tags
}
```

**`internal = false`**
- `false` — Internet-facing ALB, publicly reachable from the internet. Use for external-facing applications.
- `true` — Internal ALB, only reachable from within the VPC. Use for internal services, microservices, or for load balancing traffic that already passed an external ALB.

**`load_balancer_type = "application"`**
- Options: `"application"` (ALB), `"network"` (NLB), `"gateway"` (GLB)
- `"application"` — HTTP/HTTPS, path-based and host-based routing, WebSocket support
- `"network"` — TCP/UDP/TLS, extreme performance and low latency, static IPs, no HTTP-level features
- Use ALB for most web applications; NLB for TCP applications or when you need a static IP

**`security_groups = [aws_security_group.alb.id]`**
- Security groups for the ALB itself — typically allows ports 80 and 443 from anywhere
- Only supported for Application Load Balancers — NLBs do not have security groups

**`subnets = var.public_subnet_ids`**
- The subnets where the ALB deploys its load balancer nodes
- Must be public subnets for an internet-facing ALB (each subnet needs an IGW route)
- Must include subnets from at least 2 AZs for the ALB to be created

**`enable_deletion_protection = var.environment == "prod"`**
- Prevents accidental deletion of the ALB via the console or Terraform
- Only enabled in prod — in dev/staging you want to be able to destroy freely
- To delete an ALB with deletion protection, you must first disable it

---

### aws_lb_target_group:

```hcl
resource "aws_lb_target_group" "app" {
  name     = "${local.name_prefix}-app-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = local.common_tags
}
```

**`port = 8080` and `protocol = "HTTP"`**
- The port and protocol that the ALB uses to forward traffic to registered targets (EC2 instances)
- This must match the port your application is listening on

**`health_check` block**
- The ALB periodically sends requests to this path on each registered target to determine if it is healthy
- `path = "/health"` — your application must expose this endpoint and return a 2xx status when healthy
- `healthy_threshold = 2` — 2 consecutive successes to mark a target healthy
- `unhealthy_threshold = 3` — 3 consecutive failures to mark a target unhealthy
- `interval = 30` — seconds between health check probes
- `timeout = 5` — seconds to wait for a health check response before counting as failure
- `matcher = "200"` — only HTTP 200 counts as healthy (can use ranges: `"200-299"`)

**`deregistration_delay = 30`**
- Seconds to wait after removing an instance from the target group before closing existing connections
- The instance continues receiving requests during this window, allowing in-flight requests to complete
- Also called "connection draining"
- 30 seconds is appropriate for applications with short request durations. Increase for long-running operations.

---

### aws_lb_listener:

```hcl
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.app.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
```

**Port 80 listener with redirect:**
- Best practice: redirect all HTTP traffic to HTTPS
- `status_code = "HTTP_301"` — permanent redirect (browsers cache it)
- `"HTTP_302"` — temporary redirect (browsers do not cache)

**`ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"`**
- Defines the TLS versions and cipher suites supported by the HTTPS listener
- `TLS13-1-2-2021-06` — supports TLS 1.2 and 1.3, disables TLS 1.0 and 1.1
- Always use a policy that disables TLS 1.0 and 1.1 — they have known vulnerabilities
- AWS updates policy names when security recommendations change — check for the latest

**`certificate_arn = aws_acm_certificate.app.arn`**
- The ACM (AWS Certificate Manager) certificate for HTTPS
- ACM certificates are free and auto-renew

**`default_action { type = "forward" }`**
- Forwards all traffic matching this listener to the specified target group
- Other `type` options: `"redirect"`, `"fixed-response"`, `"authenticate-cognito"`, `"authenticate-oidc"`
- `"fixed-response"` is useful for returning a maintenance page or 404 for unmatched paths

---

## base64encode() and templatefile() Functions

### base64encode():

```hcl
# Encoding a simple string
user_data = base64encode("#!/bin/bash\napt-get update")

# Encoding a template
user_data = base64encode(templatefile("user_data.sh.tpl", {
  app_version = var.app_version
}))

# Encoding an inline heredoc
user_data = base64encode(<<-EOF
  #!/bin/bash
  echo "Hello, ${var.environment}" > /tmp/greeting.txt
EOF
)
```

**Why base64?**
The EC2 user_data field is transmitted as base64-encoded data in the API. The AWS provider requires you to provide it already encoded. Cloud-init decodes it automatically when the instance starts.

### templatefile():

```hcl
# templatefile(path, vars)
templatefile("${path.module}/templates/nginx.conf.tpl", {
  server_name = var.domain_name
  upstream    = aws_lb.app.dns_name
})
```

**`${path.module}`**
- The filesystem path of the directory containing the current `.tf` file
- Always use `path.module` instead of relative paths like `"./templates/"` — relative paths are evaluated from the directory where Terraform is run, which can vary

**Template file syntax:**
```bash
# templates/user_data.sh.tpl
#!/bin/bash
export ENVIRONMENT="${environment}"
export DB_HOST="${db_endpoint}"

# Conditional in template
%{ if environment == "prod" ~}
systemctl enable datadog-agent
%{ endif ~}

# Loop in template
%{ for subnet in subnet_ids ~}
echo "Subnet: ${subnet}"
%{ endfor ~}
```

The `~` at the end of template directives strips trailing whitespace/newlines for cleaner output.

---

## Common Mistakes to Avoid

- **Using `desired_capacity` without `ignore_changes`**: Terraform will reset desired capacity to the value in configuration on every apply, fighting with the ASG's own scaling decisions.
- **Setting `health_check_type = "EC2"` for web services**: EC2 health checks only detect instance-level failures. An application crash that keeps the process running will not be detected. Use `"ELB"` for web services.
- **`health_check_grace_period` too short**: If your application takes 3 minutes to start and grace period is 60 seconds, the ASG will terminate and replace instances in a loop before they ever become healthy.
- **ALB in private subnets for internet-facing load balancer**: Internet-facing ALBs must be in public subnets (subnets with routes to an IGW). The EC2 instances behind the ALB should be in private subnets.
- **Not setting `deregistration_delay`**: The default is 300 seconds (5 minutes). For applications that process requests quickly, this unnecessarily delays deployments and scale-in. Set it to match your longest expected request duration.
- **Not enabling ALB access logs**: Access logs are critical for security analysis and debugging. The S3 cost is minimal. Always enable them in production.
- **Using `"$Latest"` launch template version in production**: If someone updates the launch template, the next scale-out event immediately uses the new, untested template. For production, use a specific version number and update it deliberately.
- **Forgetting `tag_specifications` in the launch template**: Instances and volumes launched by the ASG will have no tags, making them unidentifiable and unattributable for cost allocation.
