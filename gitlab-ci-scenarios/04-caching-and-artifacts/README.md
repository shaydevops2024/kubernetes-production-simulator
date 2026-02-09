# Scenario 04: Caching & Artifacts - Pipeline Performance Optimization

## Overview
A slow pipeline kills developer productivity. Learn how to use caching, artifacts, and DAG execution to cut your pipeline time dramatically. Master cache keys, policies, artifact expiration, and the 'needs' keyword for parallel execution.

## What You Will Learn
- The difference between cache and artifacts
- How to configure cache keys for optimal hit rates
- Cache policies (pull, push, pull-push)
- How to use artifacts to pass data between stages
- DAG execution with 'needs:' keyword
- How to measure and optimize pipeline duration

## Key Concepts
- **Cache**: Speeds up jobs by reusing files from PREVIOUS pipelines (e.g., node_modules)
- **Artifacts**: Passes files between JOBS in the SAME pipeline (e.g., build output)
- **Cache Key**: Determines when to reuse or rebuild the cache
- **DAG (needs:)**: Allows jobs to start as soon as their dependencies finish, not waiting for the entire stage
- **Cache Policy**: Controls whether a job reads, writes, or both with the cache

## Prerequisites
- kubectl access to the cluster
- Completed Scenario 01 (Pipeline Fundamentals)
