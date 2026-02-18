# Reusable Modules
Learn how to build reusable Terraform modules with proper structure, input variables, outputs, and module composition for DRY infrastructure code.

## Learning Objectives
- Understand the Terraform module concept and directory structure
- Create a module with main.tf, variables.tf, and outputs.tf
- Define input variables with types, defaults, and validation
- Write a module that provisions an ALB, EC2 instances, and security groups
- Define outputs to expose key resource attributes from a module
- Call a module from a root configuration
- Instantiate the same module multiple times with different parameters

## Prerequisites
- Kubernetes cluster running (Kind cluster)
- kubectl configured and accessible

## Resources Created
- Module directory layout (modules/web-app/)
- Module input variables (variables.tf)
- Module main configuration with ALB, EC2, and Security Group (main.tf)
- Module outputs (outputs.tf)
- Root module calling the web-app module
- Multiple module instances with different configurations

## Cleanup
Run the cleanup command (last step) to remove all resources.
