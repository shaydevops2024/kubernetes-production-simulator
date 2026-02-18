# Security Groups and IAM Roles
Learn how to secure AWS infrastructure using Security Groups for network access control and IAM Roles for identity-based permissions following the principle of least privilege.

## Learning Objectives
- Create and configure AWS Security Groups with ingress and egress rules
- Understand the difference between ingress (inbound) and egress (outbound) traffic rules
- Create IAM Roles with trust policies for EC2 assume role
- Write IAM Policies that follow the principle of least privilege
- Attach policies to roles and create instance profiles
- Build a complete security layer for production workloads

## Prerequisites
- Basic understanding of Terraform HCL syntax
- Familiarity with AWS networking concepts (VPC, CIDR blocks)
- Completed scenarios 01-04 or equivalent Terraform experience

## Resources Created
- AWS Security Group with custom ingress and egress rules
- IAM Role with EC2 assume role trust policy
- IAM Policy with least-privilege S3 and CloudWatch permissions
- IAM Role Policy Attachment
- IAM Instance Profile for EC2

## Cleanup
The final step removes all simulated resources and configuration files created during this scenario.
