# CI/CD Pipeline for Terraform
Build a production-grade GitHub Actions CI/CD pipeline for Terraform with fmt checks, validation, plan artifacts, approval gates, and automated apply on merge.

## Learning Objectives
- Design a CI/CD workflow for Infrastructure as Code
- Implement terraform fmt and validate as automated checks
- Save terraform plan output as artifacts for audit trails
- Configure manual approval gates before applying infrastructure changes
- Automate terraform apply on merge to the main branch
- Apply best practices for secure and reliable IaC pipelines

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- GitHub Actions workflow file for Terraform CI/CD
- Fmt check stage configuration
- Validate stage configuration
- Plan stage with artifact storage
- Manual approval gate configuration
- Apply stage triggered on merge to main

## Cleanup
Run the cleanup command (last step) to remove all resources.
