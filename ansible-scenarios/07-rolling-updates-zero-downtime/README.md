# Rolling Updates and Zero Downtime Deployments

## Overview
Master rolling update strategies to deploy application updates across multiple servers without downtime. Learn serial execution, health checks, delegation, and automatic rollback on failure.

## What You'll Learn
- Performing rolling updates with serial execution
- Implementing health checks between updates
- Using delegation and run_once for orchestration tasks
- Handling failures and triggering rollbacks
- Load balancer integration during updates
- Zero-downtime deployment patterns

## Prerequisites
- Ansible installed locally
- Docker installed (for web server targets)
- Understanding of Ansible playbooks and handlers
- Basic knowledge of HTTP health checks

## Resources Created
- Docker containers running nginx web servers
- Load balancer configuration
- Application deployment scripts
- Health check endpoints
- Rollback playbooks

## Cleanup
Run the cleanup commands to stop and remove all Docker containers created in this scenario.
