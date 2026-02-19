# Terraform Configuration Files Explanation - VPC Networking from Scratch

This guide explains the Terraform configuration files and concepts in this scenario, breaking down every block and field with context for why and how to write them.

---

## main.tf - VPC Core Resources

### What is a VPC?

A Virtual Private Cloud (VPC) is an isolated, logically-defined network in AWS. Every resource you create in AWS (EC2 instances, RDS databases, Lambda functions in a VPC) lives inside a VPC. Think of it as your private data center's network, but in the cloud.

A production VPC typically has:
- **Public subnets** — directly reachable from the internet (load balancers, NAT gateways, bastion hosts)
- **Private subnets** — not directly reachable from internet (application servers, databases)
- **Internet Gateway** — the door between your VPC and the public internet
- **NAT Gateway** — lets private subnet resources initiate outbound internet connections without being reachable inbound

### aws_vpc Resource:

```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}
```

**`cidr_block = var.vpc_cidr`**
- CIDR notation defines the IP address range for the entire VPC (e.g., `10.0.0.0/16`)
- `/16` gives you 65,536 IP addresses — the maximum VPC CIDR prefix is `/16`, minimum is `/28`
- Common choices: `10.0.0.0/16`, `172.16.0.0/16`, `192.168.0.0/16`
- Plan your CIDR carefully — once set, a VPC CIDR cannot be changed (you must recreate the VPC)
- If you need to peer VPCs or connect to on-premises networks, all CIDRs must be non-overlapping

**`enable_dns_hostnames = true`**
- Assigns DNS hostnames to EC2 instances launched in the VPC (e.g., `ec2-54-1-2-3.compute-1.amazonaws.com`)
- Required if you want EC2 instances to have resolvable public DNS names
- Must be `true` for EKS, ECS, and many other services to function correctly

**`enable_dns_support = true`**
- Enables the Amazon-provided DNS resolver in the VPC (at the `+2` address of your CIDR, e.g., `10.0.0.2`)
- Required for DNS resolution to work within the VPC
- Almost always `true` — turning it off breaks DNS for all VPC resources

---

### aws_subnet Resources:

```hcl
resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Tier = "Public"
  }
}

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Tier = "Private"
  }
}
```

**`count = length(var.availability_zones)`**
- Creates one subnet per availability zone
- `length(["us-east-1a", "us-east-1b", "us-east-1c"])` returns `3` — creates 3 subnets
- Each instance is accessed by index: `aws_subnet.public[0]`, `aws_subnet.public[1]`, etc.

**`count.index`**
- The current iteration number (0-based) when using `count`
- Use it for unique naming, unique CIDR assignment, and selecting the right AZ

**`cidrsubnet(var.vpc_cidr, 8, count.index)`**
- Built-in function that calculates subnet CIDR blocks from a parent CIDR
- `cidrsubnet("10.0.0.0/16", 8, 0)` → `"10.0.0.0/24"` (256 addresses)
- `cidrsubnet("10.0.0.0/16", 8, 1)` → `"10.0.1.0/24"`
- `cidrsubnet("10.0.0.0/16", 8, 2)` → `"10.0.2.0/24"`
- Second argument (`8`) is the number of additional bits — adds 8 bits to `/16` to get `/24`
- Third argument is the subnet number within the space

**`availability_zone = var.availability_zones[count.index]`**
- Pins this subnet to a specific AZ
- Subnets in different AZs provide high availability — if one AZ goes down, the others continue serving traffic
- Resources in different AZs in the same region have very low latency between them

**`map_public_ip_on_launch = true`**
- Automatically assigns a public IP to any EC2 instance launched in this subnet
- Set this on public subnets, not private subnets
- Even with this set, the instance is not reachable unless a route to an Internet Gateway exists

---

## Internet Gateway and NAT Gateway

### aws_internet_gateway:

```hcl
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}
```

**What it is:** The Internet Gateway (IGW) is a highly available AWS-managed component that enables communication between instances in your VPC and the internet. It performs NAT for instances with public IPs.

**`vpc_id = aws_vpc.main.id`**
- Attaches the IGW to the VPC
- Each VPC can have at most one IGW attached
- Detaching the IGW cuts off all public internet access for the entire VPC

**Why the IGW alone is not enough for internet access:**
Just having an IGW attached is not sufficient. You also need:
1. A route in the subnet's route table pointing `0.0.0.0/0` at the IGW
2. A public IP address on the instance (or Elastic IP)
3. A security group that allows the traffic

---

### Elastic IP for NAT Gateway:

```hcl
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "${local.name_prefix}-nat-eip-${count.index}"
  }
}
```

**`domain = "vpc"`**
- Allocates the EIP in the VPC scope (as opposed to the deprecated `standard` scope for EC2-Classic)
- Always use `domain = "vpc"` for modern AWS accounts

**`depends_on = [aws_internet_gateway.main]`**
- An **explicit dependency** — tells Terraform the EIP should not be created until the Internet Gateway exists
- This is needed because there is no attribute reference between EIP and IGW, so Terraform cannot infer the dependency automatically
- Without this, Terraform might try to allocate the EIP before the IGW is ready, which can cause issues in some regions

---

### aws_nat_gateway:

```hcl
resource "aws_nat_gateway" "main" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "${local.name_prefix}-nat-${var.availability_zones[count.index]}"
  }
}
```

**What it does:** A NAT Gateway allows instances in private subnets to initiate outbound connections to the internet (for package downloads, API calls, etc.) without being reachable from the internet inbound.

**`allocation_id = aws_eip.nat[count.index].id`**
- Associates this NAT Gateway with a specific Elastic IP address
- The NAT Gateway's public IP (used for all outbound traffic from private subnets) is this EIP
- Note `[count.index]` — the first NAT Gateway gets the first EIP, second gets second, etc.

**`subnet_id = aws_subnet.public[count.index].id`**
- NAT Gateways must be placed in **public subnets** — they need direct internet access via the IGW
- One NAT Gateway per AZ is the recommended production configuration
- Using a single NAT Gateway across all AZs saves cost but creates a single point of failure

**Why one NAT Gateway per AZ?**
If you use a single NAT Gateway and that AZ has an outage, private subnet instances in other AZs lose outbound internet access. One per AZ costs more (~$32/month per gateway) but provides true multi-AZ resilience.

---

## Route Tables

### aws_route_table:

```hcl
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-public-rt"
  }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}
```

**Why separate `aws_route` resources instead of inline `route` blocks?**
You can define routes inline inside `aws_route_table`, but using separate `aws_route` resources is better because:
- Terraform can create routes without destroying and recreating the route table
- You avoid the "route already exists" error when Terraform tries to recreate inline routes
- It is clearer which routes are being added

**`destination_cidr_block = "0.0.0.0/0"`**
- The default route — matches all traffic not matched by more specific routes
- Points all outbound traffic to the Internet Gateway
- This is what makes a subnet "public" — having a default route to an IGW

---

```hcl
resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-private-rt-${count.index}"
  }
}

resource "aws_route" "private_internet" {
  count = length(var.availability_zones)

  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[count.index].id
}
```

**Why one private route table per AZ?**
Each private route table points to the NAT Gateway in the same AZ. This ensures traffic from private subnets stays within the AZ (lower latency, no cross-AZ data transfer costs) and maintains availability when a single AZ fails.

---

### Route Table Associations:

```hcl
resource "aws_route_table_association" "public" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

**What this does:** Associates a subnet with a route table, making the subnet use those routing rules. Without an explicit association, a subnet uses the VPC's "main" route table (which only has local routes and no internet access by default).

**`subnet_id` and `route_table_id` pairing:**
- Public subnet `[0]` → Public route table (with IGW route)
- Private subnet `[0]` → Private route table `[0]` (with NAT Gateway `[0]` in AZ `[0]`)
- Private subnet `[1]` → Private route table `[1]` (with NAT Gateway `[1]` in AZ `[1]`)

---

## The `count` Meta-Argument

### What is count?

`count` is a meta-argument that creates multiple instances of a resource from a single block. It is available on every resource and module block.

```hcl
resource "aws_subnet" "public" {
  count = 3
  # ...
}
```

This creates three resources: `aws_subnet.public[0]`, `aws_subnet.public[1]`, `aws_subnet.public[2]`.

### count vs for_each:

```hcl
# count — good for homogeneous resources where order matters
resource "aws_subnet" "public" {
  count             = length(var.availability_zones)
  availability_zone = var.availability_zones[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
}

# for_each — good for heterogeneous resources identified by a key
resource "aws_subnet" "public" {
  for_each          = toset(var.availability_zones)
  availability_zone = each.key
  cidr_block        = var.subnet_cidrs[each.key]
}
```

**When to use `count`:** Resources that are identical except for a sequential index (subnets, AZs, replicas).

**When to use `for_each`:** Resources identified by a meaningful key (named environments, named services). With `for_each`, removing an item from the middle of a list does not destroy all subsequent items (unlike `count`).

---

## Terraform Functions for Networking

### cidrsubnet():

```hcl
# cidrsubnet(prefix, newbits, netnum)
cidrsubnet("10.0.0.0/16", 8, 0)   # "10.0.0.0/24"
cidrsubnet("10.0.0.0/16", 8, 1)   # "10.0.1.0/24"
cidrsubnet("10.0.0.0/16", 4, 0)   # "10.0.0.0/20"
cidrsubnet("10.0.0.0/16", 4, 1)   # "10.0.16.0/20"
```

- `prefix` — the parent CIDR block
- `newbits` — number of additional bits for the subnet mask
- `netnum` — which subnet number to generate

### element():

```hcl
# element(list, index) — wraps around using modulo
element(["a", "b", "c"], 0)  # "a"
element(["a", "b", "c"], 3)  # "a" (wraps: 3 % 3 = 0)
element(["a", "b", "c"], 4)  # "b" (wraps: 4 % 3 = 1)
```

Useful for distributing resources across a fixed set of options (e.g., AZs) when you have more resources than options.

### cidrhost():

```hcl
# Get a specific host address within a CIDR block
cidrhost("10.0.1.0/24", 1)   # "10.0.1.1"  (gateway)
cidrhost("10.0.1.0/24", 10)  # "10.0.1.10"
```

---

## Explicit vs Implicit Dependencies

### Implicit Dependencies (Preferred):

```hcl
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat[count.index].id  # implicit: eip must exist first
  subnet_id     = aws_subnet.public[count.index].id  # implicit: subnet must exist first
}
```

When you reference another resource's attribute, Terraform automatically adds a dependency edge in the graph. The NAT Gateway will not be created until both the EIP and the public subnet exist.

### Explicit Dependencies (When Needed):

```hcl
resource "aws_eip" "nat" {
  domain = "vpc"
  depends_on = [aws_internet_gateway.main]  # explicit: no attribute reference exists
}
```

Use `depends_on` when:
- There is no attribute reference between the resources
- The relationship is implied by behavior (the IGW must be attached before EIPs are useful)
- A module has hidden dependencies you want to make explicit

**Important:** `depends_on` forces sequential creation. Overusing it removes parallelism. Only use it when truly necessary.

---

## Common Mistakes to Avoid

- **Overlapping CIDR blocks**: If you plan to peer VPCs or connect to on-premises, plan your CIDRs upfront. Overlapping CIDRs prevent peering.
- **Putting all resources in one subnet**: Use public subnets only for resources that must be internet-facing. Everything else belongs in private subnets.
- **Single NAT Gateway for all AZs**: Saves ~$32/month but creates an AZ-level single point of failure for all private subnet egress.
- **Missing route table associations**: A subnet not associated with a route table uses the main (default) route table, which has no internet route.
- **Using `count` for resources you might remove individually**: If you have 3 subnets using `count` and remove the second AZ, Terraform destroys subnet `[1]` and recreates `[2]` as the new `[1]`. Use `for_each` with AZ names as keys to avoid this.
- **Forgetting `enable_dns_hostnames`**: Required for EKS, ECS, and many AWS services. Always set it to `true`.
- **Not tagging subnets for Kubernetes**: EKS requires specific tags on subnets to discover them. Public subnets need `kubernetes.io/role/elb = 1`, private subnets need `kubernetes.io/role/internal-elb = 1`.
