# Infrastructure Drift Detection and Compliance
Detect and remediate infrastructure drift using terraform plan as an audit tool, enforce compliance policies with OPA/Rego, implement mandatory tagging, and build automated drift remediation workflows for CI pipelines.

## Learning Objectives
- Understand what infrastructure drift is and how it occurs
- Use terraform plan with -detailed-exitcode as an automated audit tool
- Detect and categorize different types of drift (configuration, state, desired)
- Write OPA/Rego policies for infrastructure compliance checks
- Enforce mandatory tagging policies across all resources
- Build automated drift remediation workflows
- Integrate compliance checks into CI/CD pipelines

## Prerequisites
- Completed earlier Terraform scenarios (state management, modules)
- Understanding of Terraform plan output and state concepts
- Familiarity with JSON processing (jq)
- Basic understanding of policy-as-code concepts

## Resources Created
- Terraform plan configurations for drift detection examples
- OPA/Rego policy files for compliance enforcement
- Tagging policy enforcement rules
- Automated drift detection and remediation scripts
- CI pipeline configuration for compliance gates

## Cleanup
Run the cleanup command (last step) to remove all resources.
