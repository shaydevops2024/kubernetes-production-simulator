# Scenario 11: Compliance & Governance (Pipeline Standards)

## Overview
Enforce pipeline standards across an entire GitLab group. Every repository MUST run security scans, MUST have approval gates for production, and CANNOT skip stages. Learn how platform teams control CI/CD governance at scale.

## What You Will Learn
- Compliance pipelines (group-level enforcement)
- Protected environments with required approvers
- Manual approval gates for production deployments
- Deployment freeze windows
- Break-glass emergency procedures
- Audit trail and compliance reporting

## Key Concepts
- **Compliance Pipeline**: Group-level pipeline that runs alongside project pipelines
- **Protected Environments**: Require specific users/groups to approve deployments
- **Deployment Freeze**: Block deployments during critical periods
- **Break Glass**: Emergency override for deployment freezes
- **Audit Trail**: Tracking who approved what and when

## Prerequisites
- Completed Scenario 01 (Pipeline Fundamentals)
- Completed Scenario 08 (Security Scanning)
