# Terraform Configuration Files Explanation - Full EKS Cluster

This guide explains the Terraform configuration files used to build a production-ready EKS cluster from scratch, covering every resource and why it's needed.

---

## aws_eks_cluster - The Control Plane

### What is aws_eks_cluster?
This resource creates the EKS control plane — the Kubernetes API server, etcd, and controller manager managed by AWS. You don't manage control plane nodes; AWS handles patching, scaling, and availability.

### HCL Structure Breakdown:

```hcl
resource "aws_eks_cluster" "main" {
  name     = "production-eks"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.29"

  vpc_config {
    subnet_ids              = concat(
      module.vpc.private_subnet_ids,
      module.vpc.public_subnet_ids
    )
    security_group_ids      = [aws_security_group.eks_cluster.id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["YOUR_OFFICE_IP/32"]
  }

  enabled_cluster_log_types = [
    "api", "audit", "authenticator",
    "controllerManager", "scheduler"
  ]

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_cloudwatch_log_group.eks,
  ]

  tags = {
    Environment = var.environment
  }
}
```

**`role_arn`:** IAM role for the EKS control plane. AWS uses this role to make AWS API calls on your behalf (e.g., creating ENIs, managing load balancers).

**`version`:** Kubernetes version. Pin to a specific minor version. AWS EKS typically supports the latest 3-4 minor versions.
**Warning:** Kubernetes upgrades are one minor version at a time and cannot be downgraded.

**`vpc_config`:**
- `subnet_ids`: Include both private and public subnets. Worker nodes go in private, load balancers in public.
- `endpoint_private_access = true`: Nodes can reach API server via private IP (within VPC). Required for private node groups.
- `endpoint_public_access = true`: API server reachable from internet (for `kubectl` from your laptop). Consider setting `public_access_cidrs` to restrict.
- `public_access_cidrs`: Restrict public API access to specific IPs (office IPs, VPN IPs).

**`enabled_cluster_log_types`:** Ship control plane logs to CloudWatch.
- `api`: API server access logs
- `audit`: Kubernetes audit logs (who did what, when) — critical for security
- `authenticator`: Auth logs
- `controllerManager` and `scheduler`: Control plane component logs

**`encryption_config`:** Encrypt Kubernetes secrets at rest using your own KMS key.
**Why:** By default, K8s secrets are base64-encoded (not encrypted) in etcd. This adds real encryption.

---

## EKS IAM Roles - Cluster and Node Permissions

### Cluster IAM Role

```hcl
resource "aws_iam_role" "eks_cluster" {
  name = "eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
```

**`AmazonEKSClusterPolicy`:** AWS managed policy that allows EKS to manage EC2, ELB, and CloudWatch resources for the cluster.

### Node Group IAM Role

```hcl
resource "aws_iam_role" "eks_nodes" {
  name = "eks-node-group-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_ecr_read" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
```

**Three required policies for worker nodes:**
- `AmazonEKSWorkerNodePolicy`: Allows nodes to connect to the cluster, describe EC2 resources
- `AmazonEKS_CNI_Policy`: Allows the VPC CNI plugin to manage ENIs and IP addresses
- `AmazonEC2ContainerRegistryReadOnly`: Allows nodes to pull images from ECR

---

## aws_eks_node_group - Worker Nodes

### What is aws_eks_node_group?
Managed node groups are EC2 instances managed by EKS. AWS handles node provisioning, patching, and graceful draining during updates.

### HCL Structure Breakdown:

```hcl
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "production-nodes"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = module.vpc.private_subnet_ids

  instance_types = ["m5.large"]
  capacity_type  = "ON_DEMAND"
  ami_type       = "AL2_x86_64"
  disk_size      = 50

  scaling_config {
    desired_size = 3
    min_size     = 2
    max_size     = 10
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role        = "application"
    environment = var.environment
  }

  taint {
    key    = "dedicated"
    value  = "gpu"
    effect = "NO_SCHEDULE"
  }

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node,
    aws_iam_role_policy_attachment.eks_cni,
    aws_iam_role_policy_attachment.eks_ecr_read,
  ]
}
```

**`subnet_ids`:** Always use private subnets for worker nodes. They have no public IP, reducing attack surface.

**`instance_types`:** List of instance types. EKS tries them in order.
**Common choices:**
- `m5.large` / `m5.xlarge` — general purpose (good default)
- `c5.xlarge` — compute-optimized (CPU-heavy workloads)
- `r5.xlarge` — memory-optimized (caching, in-memory databases)
- `g4dn.xlarge` — GPU instances (ML/AI workloads)

**`capacity_type`:**
- `ON_DEMAND` — always available, higher cost (use for critical workloads)
- `SPOT` — up to 90% cheaper, can be interrupted (use for batch/stateless workloads)

**`ami_type`:** Node OS image.
- `AL2_x86_64` — Amazon Linux 2 (x86, most common)
- `AL2_ARM_64` — Amazon Linux 2 (ARM/Graviton, cheaper)
- `BOTTLEROCKET_x86_64` — Bottlerocket OS (more secure, immutable)

**`scaling_config`:** Min/max/desired node count.
**Important:** Add `lifecycle { ignore_changes = [scaling_config[0].desired_size] }` — otherwise Cluster Autoscaler changes will be reverted by Terraform.

**`update_config`:**
- `max_unavailable`: Maximum nodes unavailable during rolling update. `1` = zero-downtime rolling update.

**`taint`:** Kubernetes taints applied to all nodes in the group. Used for dedicated node pools (GPU, spot-only, etc.).

---

## aws_iam_openid_connect_provider - IRSA

### What is IRSA?
IAM Roles for Service Accounts (IRSA) allows Kubernetes pods to assume AWS IAM roles without node-level credentials. Each pod gets its own IAM identity.

### Why IRSA Instead of Node IAM Role?
Without IRSA: All pods on a node share the node's IAM role — overly permissive.
With IRSA: Each pod/service account gets its own minimal IAM role — least privilege.

### HCL Structure Breakdown:

```hcl
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# Example: IAM role for a service account
resource "aws_iam_role" "s3_reader" {
  name = "eks-s3-reader"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" =
            "system:serviceaccount:my-app:my-service-account"
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" =
            "sts.amazonaws.com"
        }
      }
    }]
  })
}
```

**`url`:** The EKS cluster's OIDC issuer URL. Each cluster gets a unique OIDC endpoint.
**`thumbprint_list`:** TLS fingerprint of the OIDC endpoint's certificate (for trust verification).
**`client_id_list`:** Always `["sts.amazonaws.com"]` for EKS IRSA.

**The trust policy condition** scopes the role to a specific Kubernetes service account:
`system:serviceaccount:<namespace>:<service-account-name>`

---

## aws_eks_addon - Managed Add-ons

### What are EKS Managed Add-ons?
AWS manages the lifecycle (installation, updates) of core cluster components.

### HCL Structure Breakdown:

```hcl
resource "aws_eks_addon" "vpc_cni" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "vpc-cni"
  addon_version            = "v1.16.0-eksbuild.1"
  resolve_conflicts_on_update = "OVERWRITE"
  service_account_role_arn = aws_iam_role.vpc_cni.arn
}

resource "aws_eks_addon" "coredns" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "coredns"
  addon_version            = "v1.11.1-eksbuild.4"
  resolve_conflicts_on_update = "OVERWRITE"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "kube-proxy"
  addon_version = "v1.29.0-eksbuild.3"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = aws_iam_role.ebs_csi.arn
}
```

**Essential add-ons:**
- `vpc-cni`: AWS VPC CNI — assigns VPC IPs to pods, enables pod-to-pod communication
- `coredns`: Cluster DNS resolution
- `kube-proxy`: Network rules on each node
- `aws-ebs-csi-driver`: Required for EBS persistent volumes in Kubernetes 1.23+

**`service_account_role_arn`:** IRSA role for add-ons that need AWS API access (vpc-cni, ebs-csi-driver).
**`resolve_conflicts_on_update`:** `OVERWRITE` — AWS overwrites custom configurations during updates. `NONE` — preserves customizations but may fail updates.

---

## kubernetes and helm Providers - Deploying to EKS

### Configuring the kubernetes Provider:

```hcl
data "aws_eks_cluster" "main" {
  name = aws_eks_cluster.main.name
}

data "aws_eks_cluster_auth" "main" {
  name = aws_eks_cluster.main.name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.main.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.main.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.main.token
  }
}
```

**`host`:** The Kubernetes API server endpoint.
**`cluster_ca_certificate`:** The cluster's CA certificate for TLS verification (base64 decoded).
**`token`:** Short-lived authentication token (valid for ~15 minutes).

### Deploying with the helm Provider:

```hcl
resource "helm_release" "nginx_ingress" {
  name             = "nginx-ingress"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.9.0"
  namespace        = "ingress-nginx"
  create_namespace = true

  set {
    name  = "controller.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "controller.replicaCount"
    value = "2"
  }

  depends_on = [aws_eks_node_group.main]
}
```

### Best Practices for EKS with Terraform:
- Separate EKS cluster creation from add-on/application deployment into different state files
- Use IRSA for all AWS API access from pods — never use node IAM roles for pod permissions
- Enable envelope encryption for Kubernetes secrets
- Restrict `public_access_cidrs` on the API server endpoint
- Enable all control plane log types for security auditing
- Use managed node groups instead of self-managed nodes — AWS handles patching and draining
- Add `lifecycle { ignore_changes = [scaling_config[0].desired_size] }` to node groups to prevent Cluster Autoscaler conflicts
