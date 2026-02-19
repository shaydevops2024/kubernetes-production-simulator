# Terraform Configuration Files Explanation - Security Groups and IAM Roles

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## security_groups.tf - Network Access Control

### What are Security Groups?

Security groups are virtual firewalls attached to AWS resources (EC2 instances, RDS databases, Lambda functions in VPCs, etc.). They control inbound and outbound traffic at the resource level. Unlike traditional firewalls, security groups are stateful — if an inbound rule allows a request, the response is automatically allowed, regardless of outbound rules.

### aws_security_group Resource:

```hcl
resource "aws_security_group" "web" {
  name        = "${local.name_prefix}-web-sg"
  description = "Security group for web tier instances"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-web-sg"
    Tier = "Web"
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**`name = "${local.name_prefix}-web-sg"`**
- The security group name in AWS — must be unique within the VPC
- Changing the name forces replacement (destroy and recreate)

**`description = "..."`**
- Required field — cannot be empty
- Changing the description forces replacement of the security group
- Write a description that explains the purpose, not just the name

**`vpc_id = aws_vpc.main.id`**
- Associates the security group with a specific VPC
- Security groups cannot be moved between VPCs after creation
- If omitted, the security group is created in the default VPC

**`lifecycle { create_before_destroy = true }`**
- When Terraform needs to replace a security group (e.g., name change), it creates the new one before destroying the old one
- Without this, resources attached to the security group would briefly have no SG during replacement
- Essential for security groups attached to running instances

---

### Security Group Rules as Separate Resources:

```hcl
resource "aws_security_group_rule" "web_ingress_http" {
  type              = "ingress"
  security_group_id = aws_security_group.web.id

  from_port   = 80
  to_port     = 80
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]

  description = "Allow HTTP from anywhere"
}

resource "aws_security_group_rule" "web_ingress_https" {
  type              = "ingress"
  security_group_id = aws_security_group.web.id

  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]

  description = "Allow HTTPS from anywhere"
}
```

**`type = "ingress"` vs `type = "egress"`**
- `ingress` — incoming traffic (to the resource)
- `egress` — outgoing traffic (from the resource)

**`from_port` and `to_port`**
- Define a port range. When `from_port == to_port`, it is a single port rule.
- For port ranges: `from_port = 8080, to_port = 8090` allows ports 8080 through 8090
- For ICMP: `from_port = -1, to_port = -1` means all ICMP types

**`protocol = "tcp"`**
- Options: `"tcp"`, `"udp"`, `"icmp"`, `"icmpv6"`, `"-1"` (all protocols)
- `"-1"` with `from_port = 0` and `to_port = 0` allows all traffic — use with extreme caution

**`cidr_blocks = ["0.0.0.0/0"]`**
- List of IPv4 CIDR ranges allowed by this rule
- `"0.0.0.0/0"` means any IPv4 address — appropriate only for public-facing load balancers
- For IPv6: use `ipv6_cidr_blocks = ["::/0"]`
- For a specific IP: `cidr_blocks = ["203.0.113.42/32"]`

---

### Source Security Group Rules:

```hcl
resource "aws_security_group_rule" "app_ingress_from_web" {
  type              = "ingress"
  security_group_id = aws_security_group.app.id

  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.web.id

  description = "Allow traffic from web tier security group"
}
```

**`source_security_group_id = aws_security_group.web.id`**
- Instead of a CIDR range, allows traffic from any resource that belongs to the specified security group
- This is how you create security group chaining: web tier can talk to app tier, app tier can talk to DB tier
- More secure than CIDR-based rules — as instances scale out or change IPs, the rule remains correct
- Use this instead of `cidr_blocks` for all internal traffic between tiers

**Why separate rule resources instead of inline `ingress`/`egress` blocks?**

You can define rules inline inside `aws_security_group`:
```hcl
# Inline approach — AVOID for complex configurations
resource "aws_security_group" "web" {
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

The problem with inline rules: when two security groups reference each other (circular dependency), inline rules cause a Terraform dependency cycle. Separate `aws_security_group_rule` resources break the cycle because the security groups can be created first (empty), then rules added to reference each other.

**When to use inline rules:**
- Simple security groups with no circular dependencies
- When you want to manage all rules in one block for simplicity

**When to use separate rule resources:**
- When two security groups need to reference each other
- When managing many rules that might be added/removed independently
- In modules where the caller might add additional rules to a base security group

---

### Default Egress Rule:

```hcl
resource "aws_security_group_rule" "web_egress_all" {
  type              = "egress"
  security_group_id = aws_security_group.web.id

  from_port   = 0
  to_port     = 0
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]

  description = "Allow all outbound traffic"
}
```

By default, security groups allow all outbound traffic. If you define any egress rule in Terraform, the default is removed and only your explicit rules apply. The pattern above restores the "allow all outbound" default explicitly.

For security-sensitive workloads, replace this with specific egress rules pointing only to required destinations.

---

## iam.tf - Identity and Access Management

### What is IAM?

AWS IAM controls who and what can access AWS services. IAM uses a policy language based on JSON to define permissions. The key concepts:

- **IAM Role**: An identity with permissions. Cannot log in with a password. Resources (EC2, Lambda) assume roles to get permissions.
- **IAM Policy**: A document defining allowed or denied actions on resources.
- **Trust Policy**: Defines who/what is allowed to assume a role (which services or accounts).
- **Instance Profile**: A container for an IAM role that EC2 instances can use.

### aws_iam_role Resource:

```hcl
resource "aws_iam_role" "ec2_app" {
  name = "${local.name_prefix}-ec2-app-role"

  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name = "${local.name_prefix}-ec2-app-role"
  }
}
```

**`assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json`**
- The trust policy — defines who can assume this role
- This is a **JSON string** containing an IAM policy document
- Using `data.aws_iam_policy_document` generates the JSON for you in HCL

---

### data "aws_iam_policy_document" for Trust Policies:

```hcl
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
```

**`data "aws_iam_policy_document"`**
- A Terraform data source that generates IAM policy JSON from HCL syntax
- Generates the same JSON as writing the policy by hand, but with HCL type checking and interpolation
- Produces the `.json` attribute containing the rendered JSON string

**`statement {}`**
- Each statement block is one permission statement in the policy
- Multiple statements can be in one document — they are combined with logical OR

**`effect = "Allow"`**
- Options: `"Allow"` or `"Deny"`
- `"Deny"` is explicit and overrides any `"Allow"` from other policies

**`actions = ["sts:AssumeRole"]`**
- The AWS API actions this statement applies to
- Format: `"<service>:<Action>"` — e.g., `"s3:GetObject"`, `"ec2:DescribeInstances"`
- Wildcards supported: `"s3:*"` means all S3 actions (use carefully)

**`principals { type = "Service"; identifiers = ["ec2.amazonaws.com"] }`**
- For trust policies — specifies who can assume the role
- `type = "Service"` means an AWS service (EC2, Lambda, etc.)
- `type = "AWS"` means an IAM user, role, or account: `identifiers = ["arn:aws:iam::123456789012:root"]`
- `identifiers = ["ec2.amazonaws.com"]` — EC2 instances can assume this role

---

### Permission Policies:

```hcl
data "aws_iam_policy_document" "app_permissions" {
  # S3 read access for config bucket
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.config.arn,
      "${aws_s3_bucket.config.arn}/*"
    ]
  }

  # CloudWatch logs write access
  statement {
    effect  = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  # SSM Parameter Store read access
  statement {
    effect    = "Allow"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.aws_region}:*:parameter/${local.name_prefix}/*"]
  }
}
```

**`resources`**
- Specifies which AWS resources the action applies to, using ARN format
- `"*"` means all resources of that type (use with caution)
- Resource-level permissions are more secure than `"*"` — grant access only to specific buckets/tables/etc.

**The `arn` and `arn/*` pattern for S3:**
- `aws_s3_bucket.config.arn` — grants access to the bucket itself (for `ListBucket`)
- `"${aws_s3_bucket.config.arn}/*"` — grants access to objects within the bucket (for `GetObject`)
- Both are needed because S3 has separate permissions for bucket-level and object-level operations

---

### Creating and Attaching the Policy:

```hcl
resource "aws_iam_policy" "app_permissions" {
  name        = "${local.name_prefix}-app-permissions"
  description = "Permissions for application EC2 instances"
  policy      = data.aws_iam_policy_document.app_permissions.json
}

resource "aws_iam_role_policy_attachment" "app_permissions" {
  role       = aws_iam_role.ec2_app.name
  policy_arn = aws_iam_policy.app_permissions.arn
}
```

**`aws_iam_policy`**
- Creates a standalone (managed) policy in IAM
- Managed policies can be attached to multiple roles — useful for shared permissions
- Alternative: `aws_iam_role_policy` creates an inline policy attached directly to one role (not reusable)

**`aws_iam_role_policy_attachment`**
- Connects the managed policy to the role
- A role can have multiple policy attachments — all permissions are combined

**Attaching AWS Managed Policies:**
```hcl
resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2_app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
```
AWS provides hundreds of managed policies (prefixed `arn:aws:iam::aws:policy/`). Use them for common use cases like SSM management, but always review what permissions they grant.

---

### IAM Instance Profile:

```hcl
resource "aws_iam_instance_profile" "ec2_app" {
  name = "${local.name_prefix}-ec2-app-profile"
  role = aws_iam_role.ec2_app.name
}
```

**What is an instance profile?**
EC2 instances cannot use IAM roles directly — they need an instance profile, which is a container that holds exactly one IAM role. When you launch an EC2 instance, you attach an instance profile, not a role directly.

**How it works at runtime:**
1. EC2 instance is launched with instance profile attached
2. Applications on the instance call the Instance Metadata Service (IMDS) at `169.254.169.254`
3. IMDS returns temporary credentials (access key, secret key, session token)
4. AWS SDK/CLI automatically retrieves and refreshes these credentials
5. Applications make API calls with these credentials — no hardcoded keys needed

**Using the instance profile:**
```hcl
resource "aws_instance" "app" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = "t3.medium"
  iam_instance_profile = aws_iam_instance_profile.ec2_app.name
  # ...
}
```

---

## Least Privilege Principle

### What is Least Privilege?

Grant only the minimum permissions required to perform the intended function. This limits the blast radius if a resource is compromised.

### Examples of Applying Least Privilege:

```hcl
# BAD - wildcard on S3
statement {
  effect    = "Allow"
  actions   = ["s3:*"]              # all S3 actions
  resources = ["*"]                 # all buckets and objects
}

# GOOD - only what is needed
statement {
  effect    = "Allow"
  actions   = ["s3:GetObject", "s3:ListBucket"]   # read only
  resources = [
    aws_s3_bucket.app_config.arn,           # specific bucket only
    "${aws_s3_bucket.app_config.arn}/*"
  ]
}
```

```hcl
# BAD - PassRole wildcard
statement {
  effect    = "Allow"
  actions   = ["iam:PassRole"]
  resources = ["*"]   # can pass ANY role to ANY service
}

# GOOD - PassRole restricted
statement {
  effect    = "Allow"
  actions   = ["iam:PassRole"]
  resources = [aws_iam_role.lambda_execution.arn]  # only this specific role
}
```

### IAM Policy Conditions:

Add conditions to restrict when a policy applies:

```hcl
statement {
  effect    = "Allow"
  actions   = ["s3:PutObject"]
  resources = ["${aws_s3_bucket.uploads.arn}/*"]

  condition {
    test     = "StringEquals"
    variable = "s3:x-amz-server-side-encryption"
    values   = ["aws:kms"]
  }
}
```

This only allows uploading objects if they include KMS encryption — the application cannot accidentally upload unencrypted data.

---

## Common Mistakes to Avoid

- **Using inline security group rules when circular references exist**: Causes Terraform dependency cycles. Use separate `aws_security_group_rule` resources instead.
- **Allowing `0.0.0.0/0` on all ports**: Only public load balancers should accept traffic from anywhere. Application and database tiers should only allow traffic from specific security groups.
- **Using `Effect: Allow` with `Action: "*"` and `Resource: "*"`**: This is administrator access. Avoid it for application roles — enumerate the specific actions required.
- **Forgetting the `/*` suffix for S3 object permissions**: `s3:GetObject` requires the resource to be `arn:aws:s3:::bucket/*`, not `arn:aws:s3:::bucket`. A common source of "Access Denied" errors.
- **Changing security group names**: Name changes force replacement of the security group, which can disrupt attached resources.
- **Not using `aws_iam_policy_document` data source**: Writing raw JSON strings in HCL is error-prone. The data source validates structure and handles escaping.
- **Attaching roles directly to EC2 without instance profiles**: EC2 instances require an instance profile (container for the role), not the role directly.
- **Overly permissive egress rules**: Locking down egress prevents compromised instances from communicating with attacker-controlled servers or exfiltrating data.
