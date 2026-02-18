# YAML Files Explanation - Job & CronJob Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 📦 job.yaml

### What is a Job?
A Job creates one or more pods and ensures they successfully complete. Unlike Deployments that run continuously, Jobs are for **run-to-completion** tasks like batch processing, data migration, or one-time scripts.

### YAML Structure Breakdown:

```yaml
apiVersion: batch/v1
```
**What it is:** Batch API group, version 1
**Why:** Jobs are in the batch API group (not apps/v1 like Deployments)
**Also includes:** CronJob (scheduled jobs)

```yaml
kind: Job
```
**What it is:** Declares this is a Job resource
**Purpose:** Run a task until it successfully completes
**Alternatives:**
- `CronJob` - Scheduled, recurring jobs
- `Deployment` - Continuous, long-running services
- `Pod` - Single pod (no retry/completion tracking)

```yaml
metadata:
  name: job-demo
  namespace: scenarios
```
**What it is:** Job metadata
- `name`: Job name (used in kubectl commands)
- `namespace`: Logical grouping

**Pod naming convention:**
```
<job-name>-<random-suffix>

Example:
job-demo-7xk2p
```

**Why random names?**
- Jobs may create multiple pods (parallelism)
- Failed pods are kept for debugging
- Each attempt gets unique name

```yaml
spec:
  template:
```
**What it is:** Pod template (similar to Deployment)
**Important:** Job spec contains `template`, not `replicas`

**Why?**
- Jobs don't have "replicas" (ongoing pods)
- They have "completions" (successful runs needed)

```yaml
    metadata:
      labels:
        app: job-demo
```
**What it is:** Labels applied to pods created by the Job

**Why labels matter:**
- Find pods created by this job: `kubectl get pods -l app=job-demo`
- Monitor job pods in logging/metrics
- Apply network policies

**Note:** Job controller also adds its own labels:
- `job-name: job-demo`
- `controller-uid: <uid>`

```yaml
    spec:
      containers:
      - name: busybox
        image: busybox:1.34
```
**What it is:** Container specification
- `name`: Container name
- `image`: Lightweight Linux image with shell utilities

**Why busybox?**
- ✅ Tiny (1-5 MB)
- ✅ Fast download
- ✅ Has shell for running commands
- ✅ Perfect for demo/testing
- ✅ Common for init containers and jobs

**Alternatives:**
- `alpine` - Similar size, has package manager
- `ubuntu` - Larger, more utilities
- `python:3.9-slim` - For Python scripts
- Custom image with your code

```yaml
        command: ["sh", "-c", "echo 'Processing batch job...' && sleep 10 && echo 'Job completed!'"]
```
**What it is:** Command to run in the container
**Format:** Array of strings (shell command)

**Breakdown:**
- `sh` - Shell executable
- `-c` - Run the following command string
- `"echo ... && sleep 10 && echo ..."` - The actual script

**Command behavior:**
```
1. Print "Processing batch job..."
2. Sleep for 10 seconds
3. Print "Job completed!"
4. Exit with code 0 (success)
5. Pod status: Completed
6. Job status: Complete
```

**Exit codes matter:**
- `0` = Success → Job considers it complete
- `1-255` = Failure → Job may retry (based on backoffLimit)

**Real-world examples:**
```yaml
# Data processing
command: ["python", "process_data.py", "--input", "/data/input.csv"]

# Database migration
command: ["python", "manage.py", "migrate"]

# Backup
command: ["sh", "-c", "mysqldump -h mysql -u root db > /backup/db.sql"]

# ETL job
command: ["java", "-jar", "etl.jar", "--config", "/config/etl.yaml"]
```

```yaml
      restartPolicy: Never
```
**What it is:** What to do if container fails
**Options for Jobs:**
- **Never** ✅ (used here)
  - Failed container → Pod fails
  - Job creates new pod (up to backoffLimit)
  - Good for idempotent jobs

- **OnFailure**
  - Failed container → Restart container in same pod
  - Good for non-idempotent jobs (don't want multiple pods)

**⚠️ NOT allowed for Jobs:** `Always` (only for Deployments/DaemonSets)

**Why "Never" for this job?**
- Simple demo job
- If it fails, create fresh pod
- Easier to debug (failed pods remain)

**When to use "OnFailure"?**
```yaml
# Example: Job that writes to database
# Don't want multiple pods writing if one fails and retries
restartPolicy: OnFailure
```

**Comparison:**

| restartPolicy | Container fails | Pod created | Use case |
|---------------|-----------------|-------------|----------|
| Never | Pod fails | New pod created | Idempotent tasks |
| OnFailure | Container restarts | Same pod | Non-idempotent tasks |

```yaml
  backoffLimit: 4
```
**What it is:** Maximum number of retries before marking Job as failed
**Default:** 6
**Set to 4:** Allows 4 failed attempts before giving up

**How it works:**
```
Attempt 1: Pod fails → Wait 10s, retry
Attempt 2: Pod fails → Wait 20s, retry
Attempt 3: Pod fails → Wait 40s, retry
Attempt 4: Pod fails → Wait 80s, retry
Attempt 5: Pod fails → Job marked as Failed (backoffLimit reached)
```

**Backoff delays (exponential):**
- 10s, 20s, 40s, 80s, 160s, 320s (caps at 6 minutes)

**Why 4 retries?**
- Balance between reliability and quick failure
- Prevents infinite retry loops
- Good for transient failures (network hiccups, temporary resource issues)

**Production settings:**
```yaml
# No retries (fail fast)
backoffLimit: 0

# Conservative (more retries)
backoffLimit: 10

# Infinite retries (dangerous!)
# Don't set backoffLimit too high
```

**When job fails:**
```bash
$ kubectl get job job-demo
NAME       COMPLETIONS   DURATION   AGE
job-demo   0/1           5m         5m

$ kubectl describe job job-demo
...
Events:
  Type     Reason                Age   Message
  ----     ------                ----  -------
  Warning  BackoffLimitExceeded  30s   Job has reached the specified backoff limit
```

```yaml
  completions: 1
```
**What it is:** How many successful pod completions are needed
**Default:** 1
**Set to 1:** Job succeeds after 1 pod completes successfully

**How it works:**
```
completions: 1
- Run 1 pod to completion
- Job status: Complete

completions: 5
- Run pods until 5 complete successfully
- If parallelism: 1, runs sequentially (one at a time)
- If parallelism: 3, runs 3 at a time until 5 total completions
```

**Use cases:**

| completions | Use case |
|-------------|----------|
| 1 | Single task (data migration, one-time script) |
| 5 | Process 5 items (different shards, partitions) |
| 100 | Process 100 work items |

**Example - Processing 10 files:**
```yaml
completions: 10  # Need 10 successful completions
parallelism: 3   # Run 3 pods at a time

# Behavior:
# Start: Pod 1, Pod 2, Pod 3
# Pod 1 completes: Start Pod 4
# Pod 2 completes: Start Pod 5
# ...
# After 10 successful completions: Job complete
```

```yaml
  parallelism: 1
```
**What it is:** How many pods to run simultaneously
**Default:** 1
**Set to 1:** Run 1 pod at a time (sequential)

**How it works:**
```
parallelism: 1
- Run 1 pod at a time
- Wait for completion before starting next

parallelism: 3
- Run 3 pods simultaneously
- When one completes, start another (if more completions needed)

parallelism: 0
- Job paused (no pods running)
- Can resume by setting parallelism > 0
```

**Parallelism patterns:**

```yaml
# Sequential processing (safe, slow)
completions: 10
parallelism: 1
# Runs 10 pods one at a time

# Parallel processing (fast, more resources)
completions: 10
parallelism: 5
# Runs 5 pods at a time until 10 complete

# Work queue pattern (unlimited parallelism)
completions: <empty>  # Omit completions
parallelism: 5
# Keep 5 pods running until work queue is empty
```

**Why parallelism: 1 for this demo?**
- Simple to understand
- Low resource usage
- Easier to observe behavior

**Production example - Process 1000 items:**
```yaml
completions: 1000
parallelism: 50
# 50 pods run simultaneously until 1000 completions
```

---

## ⏰ cronjob.yaml

### What is a CronJob?
A CronJob creates Jobs on a **scheduled basis**. Like Unix cron, it runs tasks at specified times/intervals. Perfect for periodic tasks like backups, reports, cleanup jobs.

### YAML Structure Breakdown:

```yaml
apiVersion: batch/v1
```
**What it is:** Batch API group, version 1
**History:**
- `batch/v1beta1` - Old version (deprecated)
- `batch/v1` - Current stable version (Kubernetes 1.21+)

**If using older Kubernetes (<1.21):**
```yaml
apiVersion: batch/v1beta1  # Use this for K8s < 1.21
```

```yaml
kind: CronJob
```
**What it is:** Declares this is a CronJob resource
**Purpose:** Run Jobs on a schedule (like crontab)

```yaml
metadata:
  name: cronjob-demo
  namespace: scenarios
```
**What it is:** CronJob metadata
- `name`: CronJob name
- `namespace`: Logical grouping

**Job naming convention:**
```
<cronjob-name>-<timestamp>

Examples:
cronjob-demo-1640000400  (timestamp: Unix epoch)
cronjob-demo-1640000700
cronjob-demo-1640001000
```

**Why timestamps?**
- Each scheduled run creates a new Job
- Unique names for each execution
- Easy to identify which run failed

```yaml
spec:
  schedule: "*/5 * * * *"
```
**What it is:** **CRITICAL** - Cron schedule expression
**Format:** Same as Unix cron (5 fields)

### 🕐 Cron Schedule Format:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

**Common patterns:**

| Schedule | Meaning |
|----------|---------|
| `*/5 * * * *` | Every 5 minutes (used here) |
| `0 * * * *` | Every hour at minute 0 |
| `0 0 * * *` | Every day at midnight |
| `0 2 * * *` | Every day at 2:00 AM |
| `0 0 * * 0` | Every Sunday at midnight |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `*/15 * * * *` | Every 15 minutes |
| `0 */6 * * *` | Every 6 hours |
| `0 0 1 * *` | First day of month at midnight |
| `30 3 15 * *` | 15th of month at 3:30 AM |

**Special strings (some K8s versions):**
```yaml
@hourly    # Same as "0 * * * *"
@daily     # Same as "0 0 * * *"
@weekly    # Same as "0 0 * * 0"
@monthly   # Same as "0 0 1 * *"
@yearly    # Same as "0 0 1 1 *"
```

**⚠️ Important:** CronJobs use UTC timezone (not local time)

**Testing your cron expression:**
- Use https://crontab.guru/ for validation
- Use https://crontab.cronhub.io/ for testing

**Examples:**

```yaml
# Backup every night at 2 AM
schedule: "0 2 * * *"

# Send report every Monday at 9 AM
schedule: "0 9 * * 1"

# Cleanup every 30 minutes
schedule: "*/30 * * * *"

# Process data every 6 hours
schedule: "0 */6 * * *"
```

```yaml
  jobTemplate:
    spec:
```
**What it is:** Template for Jobs created by CronJob
**Structure:** Same as Job spec (without `apiVersion`, `kind`, `metadata.name`)

**Why nested?**
```
CronJob creates → Job creates → Pod
```

**Inheritance:**
- CronJob defines schedule
- Job template defines what to run
- Pod template defines container

```yaml
      template:
        metadata:
          labels:
            app: cronjob-demo
```
**What it is:** Pod template labels
**Purpose:** Identify pods created by this CronJob

**Automatic labels added:**
- `job-name: cronjob-demo-1640000400`
- `controller-uid: <uid>`

**Finding all pods from all CronJob runs:**
```bash
kubectl get pods -l app=cronjob-demo -n scenarios
```

```yaml
        spec:
          containers:
          - name: busybox
            image: busybox:1.34
            command: ["sh", "-c", "date && echo 'Scheduled task executed'"]
```
**What it is:** Container specification
**Command breakdown:**
- `date` - Print current date/time
- `&&` - AND (run next command if previous succeeded)
- `echo 'Scheduled task executed'` - Print message

**Why print date?**
- Verify when job actually ran
- Useful for debugging schedule issues
- Logs show execution time

**Real-world CronJob examples:**

```yaml
# Database backup
command: ["sh", "-c", "mysqldump -h mysql -u root -p$PASSWORD db > /backup/db-$(date +%Y%m%d).sql"]

# Cleanup old logs
command: ["sh", "-c", "find /logs -name '*.log' -mtime +30 -delete"]

# Send daily report
command: ["python", "send_report.py", "--date", "yesterday"]

# Sync data from API
command: ["sh", "-c", "curl https://api.example.com/data | jq . > /data/sync-$(date +%s).json"]
```

```yaml
          restartPolicy: OnFailure
```
**What it is:** What to do if container fails
**Options for CronJob Jobs:**
- **OnFailure** ✅ (used here - recommended for CronJobs)
- **Never** (creates new pod on failure)

**Why OnFailure for CronJobs?**
- Don't want multiple pods for same scheduled run
- Retry in same pod if transient failure
- Prevents pod proliferation

**Comparison:**

| restartPolicy | Failure behavior | Use case |
|---------------|------------------|----------|
| OnFailure | Restart container in same pod | CronJobs (recommended) |
| Never | Create new pod | One-off Jobs |

**Example:**
```
Schedule: Every 5 minutes
restartPolicy: OnFailure

5:00 - Job starts, fails → Restart container in same pod
5:01 - Container succeeds → Job complete
5:05 - Next scheduled job starts (new Job, new Pod)
```

```yaml
  successfulJobsHistoryLimit: 3
```
**What it is:** How many completed Jobs to keep
**Default:** 3
**Set to 3:** Keep last 3 successful Jobs

**Why keep completed Jobs?**
- View logs from recent runs
- Debug issues
- Audit trail

**What happens when limit exceeded:**
```
Successful jobs: 1, 2, 3, 4
After job 4 completes:
- Job 1 deleted (oldest)
- Jobs 2, 3, 4 kept
```

**Storage consideration:**
```yaml
# Keep many (good for debugging, uses more storage)
successfulJobsHistoryLimit: 10

# Keep few (saves resources)
successfulJobsHistoryLimit: 1

# Keep none (no audit trail)
successfulJobsHistoryLimit: 0
```

**View job history:**
```bash
kubectl get jobs -n scenarios -l app=cronjob-demo
```

```yaml
  failedJobsHistoryLimit: 1
```
**What it is:** How many failed Jobs to keep
**Default:** 1
**Set to 1:** Keep last 1 failed Job

**Why keep failed Jobs?**
- Debug what went wrong
- View failure logs
- Investigate errors

**Why keep fewer failed than successful?**
- Failed jobs need attention (investigate and fix)
- Once investigated, can delete
- Successful jobs are routine (keep more for audit)

**Recommended settings:**

| Environment | successfulJobsHistoryLimit | failedJobsHistoryLimit |
|-------------|---------------------------|------------------------|
| Development | 3 | 3 |
| Production | 5-10 | 1-3 |
| High frequency | 1 | 1 |
| Low frequency | 10 | 5 |

---

## 🔄 How CronJob Works - Complete Flow

### Initial Setup:

1. **Apply CronJob:**
   ```bash
   kubectl apply -f cronjob.yaml
   ```
   - CronJob controller starts
   - Schedules next run based on cron expression
   - Waits for scheduled time

2. **No pods yet:**
   ```bash
   $ kubectl get pods -n scenarios
   No resources found.
   ```
   - CronJob doesn't create pods immediately
   - Waits for scheduled time

### First Scheduled Run (5 minutes later):

```
Time: 00:05:00
- CronJob controller triggers
- Creates Job: cronjob-demo-28272827
- Job controller creates Pod: cronjob-demo-28272827-xk9ls
- Pod runs: date && echo 'Scheduled task executed'
- Container exits with code 0
- Pod status: Completed
- Job status: Complete

Time: 00:10:00
- Next scheduled run
- Creates Job: cronjob-demo-28273027
- (repeat process)
```

### Job History Management:

```
After 6 runs (30 minutes):

Jobs created:
1. cronjob-demo-28272827 (00:05) - Successful ✅
2. cronjob-demo-28273027 (00:10) - Successful ✅
3. cronjob-demo-28273227 (00:15) - Successful ✅
4. cronjob-demo-28273427 (00:20) - Successful ✅
5. cronjob-demo-28273627 (00:25) - Successful ✅
6. cronjob-demo-28273827 (00:30) - Successful ✅

successfulJobsHistoryLimit: 3
→ Keep only jobs 4, 5, 6
→ Delete jobs 1, 2, 3
```

### Failed Job Scenario:

```
Time: 00:35:00
- Create Job: cronjob-demo-28274027
- Pod runs command
- Command exits with code 1 (failure)
- restartPolicy: OnFailure → Restart container
- Retry with backoff
- After multiple retries, Job marked Failed ❌

Time: 00:40:00
- Create next scheduled Job (new Job, fresh attempt)

Job history:
- cronjob-demo-28274027 (Failed) kept (failedJobsHistoryLimit: 1)
- 3 successful jobs kept
```

---

## 📊 Advanced CronJob Features

### 1. Concurrency Policy

```yaml
spec:
  concurrencyPolicy: Allow  # Default
```

**Options:**

1. **Allow** (default):
   - Multiple jobs can run simultaneously
   - New job starts even if previous still running
   - **Use case:** Independent jobs

   ```
   00:00 - Job 1 starts (takes 10 minutes)
   00:05 - Job 2 starts (Job 1 still running) ✅
   00:10 - Job 3 starts (Job 1, 2 still running) ✅
   ```

2. **Forbid**:
   - Skip new job if previous still running
   - **Use case:** Jobs that shouldn't overlap

   ```
   00:00 - Job 1 starts (takes 10 minutes)
   00:05 - Job 2 skipped (Job 1 still running) ❌
   00:10 - Job 3 starts (Job 1 finished) ✅
   ```

3. **Replace**:
   - Kill running job, start new one
   - **Use case:** Only latest run matters

   ```
   00:00 - Job 1 starts (takes 10 minutes)
   00:05 - Job 1 killed, Job 2 starts
   00:10 - Job 2 killed, Job 3 starts
   ```

**Example:**
```yaml
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid  # Don't overlap
  jobTemplate:
    spec:
      activeDeadlineSeconds: 300  # Kill after 5 minutes
      template:
        spec:
          containers:
          - name: backup
            image: backup-tool
            command: ["backup.sh"]
          restartPolicy: OnFailure
```

### 2. Starting Deadline

```yaml
spec:
  startingDeadlineSeconds: 600  # 10 minutes
```

**What it is:** Maximum time to start job after scheduled time
**Why needed:** If CronJob controller is down/busy

**Example:**
```
Scheduled: 02:00:00
CronJob controller down until 02:08:00
startingDeadlineSeconds: 600

02:08:00 - Controller back up
02:08:01 - Checks: 8 minutes late, within 10-minute deadline ✅
02:08:02 - Starts job

If startingDeadlineSeconds: 300 (5 minutes):
02:08:01 - Checks: 8 minutes late, exceeds 5-minute deadline ❌
02:08:02 - Skips job, waits for next schedule
```

### 3. Suspend CronJob

```yaml
spec:
  suspend: true  # Stop creating new jobs
```

**What it is:** Pause CronJob without deleting it

**Use cases:**
- Maintenance window
- Debugging issues
- Temporarily disable automated tasks

**Example:**
```bash
# Suspend CronJob
kubectl patch cronjob cronjob-demo -n scenarios -p '{"spec":{"suspend":true}}'

# Resume CronJob
kubectl patch cronjob cronjob-demo -n scenarios -p '{"spec":{"suspend":false}}'
```

### 4. Timezone (Kubernetes 1.25+)

```yaml
spec:
  timeZone: "America/New_York"
  schedule: "0 9 * * *"  # 9 AM EST/EDT
```

**What it is:** Run jobs in specific timezone (not UTC)
**Requires:** Kubernetes 1.25+

**Common timezones:**
- `America/New_York` - Eastern Time
- `America/Los_Angeles` - Pacific Time
- `Europe/London` - GMT/BST
- `Asia/Tokyo` - JST
- `UTC` - Universal Time (default)

---

## 🎯 Best Practices

### 1. Make Jobs Idempotent

✅ **Jobs should be safe to run multiple times**

**Why?**
- CronJob might create duplicate jobs (clock skew, controller issues)
- Retries may re-process same data

**Example - Non-idempotent (BAD):**
```yaml
# Appends to file without checking
command: ["sh", "-c", "echo 'New entry' >> /data/log.txt"]
# Running twice creates duplicate entries
```

**Example - Idempotent (GOOD):**
```yaml
# Writes with timestamp (unique)
command: ["sh", "-c", "echo '$(date +%s) New entry' >> /data/log.txt"]
# Or use database with unique constraints
```

### 2. Set Resource Limits

```yaml
spec:
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: busybox
            resources:
              requests:
                cpu: 100m
                memory: 128Mi
              limits:
                cpu: 500m
                memory: 256Mi
```

**Why?**
- Prevents runaway resource usage
- Ensures cluster stability
- Helps scheduler place pods

### 3. Set activeDeadlineSeconds

```yaml
spec:
  jobTemplate:
    spec:
      activeDeadlineSeconds: 3600  # Kill after 1 hour
```

**Why?**
- Prevent stuck jobs from running forever
- Free up resources
- Detect hanging jobs

### 4. Use Proper Logging

```yaml
command:
- sh
- -c
- |
  echo "Job started at $(date)"
  # Do work
  process_data.py
  echo "Job completed at $(date)"
  echo "Processed $COUNT items"
```

**Why?**
- Debug failures
- Monitor progress
- Audit trail

### 5. Monitor CronJob Health

**Metrics to monitor:**
- Failed jobs count
- Job duration
- Jobs skipped (concurrency conflicts)
- Jobs timing out (activeDeadlineSeconds)

**Alerting rules:**
```yaml
# Alert if CronJob hasn't succeeded in 24 hours
alert: CronJobFailing
expr: (time() - kube_cronjob_status_last_schedule_time) > 86400
```

---

## 🔍 Debugging Commands

```bash
# Get CronJobs
kubectl get cronjobs -n scenarios

# Describe CronJob (see schedule, last run)
kubectl describe cronjob cronjob-demo -n scenarios

# Get Jobs created by CronJob
kubectl get jobs -n scenarios -l app=cronjob-demo

# Get Pods from specific Job
kubectl get pods -n scenarios -l job-name=cronjob-demo-28272827

# View CronJob logs (latest job)
kubectl logs -n scenarios -l app=cronjob-demo --tail=50

# View specific Job logs
kubectl logs job/cronjob-demo-28272827 -n scenarios

# Manually trigger Job (create from CronJob)
kubectl create job --from=cronjob/cronjob-demo manual-run-1 -n scenarios

# Suspend CronJob
kubectl patch cronjob cronjob-demo -p '{"spec":{"suspend":true}}' -n scenarios

# Resume CronJob
kubectl patch cronjob cronjob-demo -p '{"spec":{"suspend":false}}' -n scenarios

# Delete old Jobs manually
kubectl delete job -n scenarios -l app=cronjob-demo

# See CronJob events
kubectl get events -n scenarios --field-selector involvedObject.name=cronjob-demo
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Job not running at scheduled time

**Debug:**
```bash
kubectl describe cronjob cronjob-demo -n scenarios
```

**Causes:**
1. CronJob controller not running
2. Invalid cron expression
3. CronJob suspended
4. startingDeadlineSeconds exceeded

**Solution:**
```bash
# Validate cron expression at https://crontab.guru/
# Check controller:
kubectl get pods -n kube-system | grep cronjob-controller
# Unsuspend:
kubectl patch cronjob cronjob-demo -p '{"spec":{"suspend":false}}'
```

### Issue 2: Too many jobs running (resource exhaustion)

**Cause:** Jobs not completing before next schedule

**Solution:**
```yaml
spec:
  concurrencyPolicy: Forbid  # Don't start if previous running
  jobTemplate:
    spec:
      activeDeadlineSeconds: 600  # Kill after 10 minutes
```

### Issue 3: Jobs disappearing (can't find logs)

**Cause:** successfulJobsHistoryLimit set too low

**Solution:**
```yaml
successfulJobsHistoryLimit: 5  # Keep more jobs
failedJobsHistoryLimit: 3
```

### Issue 4: Duplicate job executions

**Cause:** Clock skew, CronJob controller restart

**Solution:** Make jobs idempotent (use unique IDs, check before processing)

---

## 🎓 Key Takeaways

### Jobs:
1. **Run-to-completion** - Jobs run until successful (or backoffLimit reached)
2. **completions** - How many successful pod runs needed
3. **parallelism** - How many pods to run simultaneously
4. **backoffLimit** - Max retries before giving up
5. **restartPolicy** - Never or OnFailure (not Always)

### CronJobs:
1. **Scheduled Jobs** - Create Jobs on cron schedule
2. **Cron syntax** - Standard 5-field format (minute hour day month weekday)
3. **UTC timezone** - Default (can override in K8s 1.25+)
4. **History limits** - Control how many completed/failed jobs to keep
5. **Concurrency policy** - Allow, Forbid, or Replace overlapping jobs
6. **Make idempotent** - Jobs should be safe to run multiple times

---

*This explanation provides deep insights into Jobs and CronJobs for batch processing and scheduled tasks in Kubernetes!*
