# Scenario 01: Pipeline Fundamentals - Multi-Stage Build & Deploy

## Overview
Learn the core structure of a GitLab CI/CD pipeline by building a `.gitlab-ci.yml` from scratch. You will understand stages, jobs, scripts, rules, and artifacts - the building blocks of every CI/CD pipeline.

## What You Will Learn
- How `.gitlab-ci.yml` defines your pipeline structure
- The relationship between stages, jobs, and scripts
- How artifacts pass data between stages
- Using rules to control when jobs execute
- The pipeline execution model (parallel within stages, sequential between stages)

## Key Concepts
- **Stages**: Define the order of pipeline phases (lint → test → build → deploy)
- **Jobs**: Individual units of work that run in a stage
- **Scripts**: Shell commands executed by the GitLab Runner
- **Artifacts**: Files passed between jobs across stages
- **Rules**: Conditions that control whether a job runs

## Prerequisites
- kubectl access to the cluster
- Understanding of YAML syntax
