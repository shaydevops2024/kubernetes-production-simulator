# Scenario 08: Security Scanning Pipeline (SAST, DAST, Dependency Scanning)

## Overview
Build a security-focused pipeline with GitLab's built-in security scanners. Learn to detect vulnerabilities in code (SAST), dependencies (SCA), container images, and secrets before they reach production. This is mandatory for SOC2/PCI-compliant organizations.

## What You Will Learn
- How to add SAST (Static Application Security Testing) to your pipeline
- Dependency scanning for vulnerable packages
- Secret detection to prevent credential leaks
- Container image scanning
- How to configure severity thresholds and fail pipelines on findings

## Key Concepts
- **SAST**: Analyzes source code for vulnerabilities without running it
- **Dependency Scanning**: Checks package dependencies against CVE databases
- **Secret Detection**: Finds leaked passwords, API keys, tokens in code
- **Container Scanning**: Scans Docker images for OS and library vulnerabilities
- **Security Reports**: GitLab UI integration showing findings in MR diffs

## Prerequisites
- Completed Scenario 01 (Pipeline Fundamentals)
