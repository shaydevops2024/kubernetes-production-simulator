# Full EKS Cluster
Provision a complete production-ready Amazon EKS cluster with managed node groups, OIDC provider, IAM Roles for Service Accounts (IRSA), and essential cluster add-ons.

## Learning Objectives
- Create an EKS cluster with proper IAM roles and security configuration
- Configure VPC networking with public and private subnets for the cluster
- Deploy managed node groups with appropriate instance types and scaling
- Set up an OIDC provider to enable IAM Roles for Service Accounts (IRSA)
- Configure IRSA for fine-grained pod-level IAM permissions
- Install essential cluster add-ons (vpc-cni, coredns, kube-proxy)
- Generate kubeconfig for kubectl access to the cluster

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- EKS cluster with dedicated IAM role
- VPC with public/private subnets and NAT gateway
- Managed node group with auto-scaling configuration
- OIDC identity provider for IRSA
- IAM role and policy for a sample service account
- EKS add-ons (vpc-cni, coredns, kube-proxy)
- Kubeconfig configuration for cluster access

## Cleanup
Run the cleanup command (last step) to remove all resources.
