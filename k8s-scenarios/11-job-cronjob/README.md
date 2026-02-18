# Jobs and CronJobs Scenario

## Overview
Run batch processing with Jobs for one-time tasks and CronJobs for scheduled recurring tasks.

## What You'll Learn
- Creating Jobs for batch processing
- Configuring CronJobs for scheduled tasks
- Understanding job completion and failure handling
- Managing job history
- Parallel job execution

## Prerequisites
- Basic Kubernetes knowledge
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Job: batch-job-demo (one-time execution)
- CronJob: scheduled-job-demo (runs every 5 minutes)

## Scenario Flow
1. Create namespace
2. Create and run a Job
3. Watch job pod execute and complete
4. Verify job completion status
5. Create CronJob with schedule
6. Wait for scheduled execution
7. View CronJob history
8. Manually trigger CronJob
9. Observe multiple job instances

## Key Concepts
- **Job:** Runs pod to completion (success or failure)
- **CronJob:** Schedules Jobs on a time-based schedule
- **Completions:** How many successful runs needed
- **Parallelism:** How many pods to run simultaneously
- **Backoff Limit:** Max retries on failure

## Job Configuration
```yaml
spec:
  completions: 1         # Need 1 successful completion
  parallelism: 1         # Run 1 pod at a time
  backoffLimit: 4        # Retry up to 4 times
  template:
    spec:
      restartPolicy: Never   # Jobs must use Never or OnFailure
```

## CronJob Schedule
```yaml
spec:
  schedule: "*/5 * * * *"    # Every 5 minutes
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```

### Cron Schedule Format
```
┌─────── minute (0 - 59)
│ ┌────── hour (0 - 23)
│ │ ┌───── day of month (1 - 31)
│ │ │ ┌──── month (1 - 12)
│ │ │ │ ┌─── day of week (0 - 6, Sunday = 0)
│ │ │ │ │
* * * * *
```

## Expected Outcomes
- Job runs to completion then stops
- CronJob creates Jobs on schedule
- Understanding of batch processing patterns
- Knowledge of when to use Jobs vs Deployments

## Use Cases
- **Jobs:** Database migrations, batch processing, data exports
- **CronJobs:** Backups, reports, cleanup tasks, scheduled maintenance

## Job Patterns
1. **Single Job:** One completion (completions: 1)
2. **Fixed Completions:** Multiple completions (completions: N)
3. **Parallel Jobs:** Work queue pattern (parallelism: N)

## Best Practices
- Set appropriate backoffLimit
- Use Never or OnFailure restart policy
- Set activeDeadlineSeconds for timeout
- Configure history limits
- Monitor failed jobs

## Cleanup
Run the cleanup commands to remove Jobs and CronJobs.

## Time Required
Approximately 20 minutes

## Difficulty
Medium - Understanding scheduling and completion concepts