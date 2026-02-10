# Multi-Tier Application Deployment

## Overview
Deploy a complete 3-tier application stack (nginx frontend, application backend, PostgreSQL database) using Ansible roles and playbooks.

## What You'll Learn
- Organizing playbooks with roles
- Managing service dependencies
- Multi-host orchestration
- Handler usage for service restarts
- Inter-service communication

## Prerequisites
- Ansible installed locally
- Docker installed (for target hosts)
- Understanding of application architecture

## Resources Created
- Docker containers: frontend, backend, database (3-tier stack)
- Nginx frontend (reverse proxy)
- Flask/Python backend application
- PostgreSQL database
- Network connectivity between tiers

## Cleanup
Run the cleanup commands to stop and remove all Docker containers created in this scenario.
