# Scenario 06: Merge Request Pipelines & Review Apps

## Overview
Set up pipelines that trigger on merge requests and create ephemeral review environments. Reviewers can click a URL to see the exact code from the MR running live, then the environment auto-cleans on merge.

## What You Will Learn
- How to configure merge request pipelines
- Creating dynamic review environments per MR
- Auto-stopping review apps on merge or after timeout
- The difference between branch pipelines and MR pipelines
- Environment cleanup strategies

## Key Concepts
- **MR Pipeline**: Pipeline triggered by merge request events
- **Review App**: Ephemeral deployment of MR code for review
- **Dynamic Environment**: Environment name includes branch/MR identifier
- **on_stop**: Job that runs when environment is stopped
- **auto_stop_in**: Automatic environment cleanup after timeout

## Prerequisites
- kubectl access to the cluster
- Completed Scenario 01 (Pipeline Fundamentals)
