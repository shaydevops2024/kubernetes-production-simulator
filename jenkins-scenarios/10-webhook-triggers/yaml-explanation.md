# Jenkinsfile Explanation - Webhook Triggers Scenario

This guide explains the `triggers {}` block, `githubPush()`, SCM polling with cron syntax, the `GenericTrigger` plugin, and how to configure automatic pipeline triggering from external events.

---

## 🔔 The `triggers {}` Block

```groovy
triggers {
    githubPush()
    pollSCM('H/5 * * * *')
}
```

**What it is:** Defines how and when the pipeline is automatically triggered, without a human clicking "Build Now".

**Location:** Inside the `pipeline {}` block, alongside `agent`, `stages`, etc.

```groovy
pipeline {
    agent any
    triggers {
        // trigger definitions here
    }
    stages { ... }
}
```

**Important:** Triggers must be registered before they work. On the first pipeline run, Jenkins reads the `triggers {}` block and configures the job accordingly. Subsequent runs use the trigger as configured.

---

## 🐙 `githubPush()` - GitHub Webhook Trigger

```groovy
triggers {
    githubPush()
}
```

**What it is:** Triggers the pipeline whenever a push event is received from GitHub.

**How it works:**
1. You configure a webhook in the GitHub repository
2. GitHub sends an HTTP POST to Jenkins when someone pushes code
3. Jenkins receives the event and triggers the pipeline

**Configuring the GitHub webhook:**

In GitHub: Repository → Settings → Webhooks → Add webhook:
- **Payload URL:** `https://your-jenkins.com/github-webhook/`
- **Content type:** `application/json`
- **Events:** `Just the push event` (or select specific events)
- **Active:** ✅

**Jenkins GitHub plugin must be installed** (`GitHub plugin`).

**Trigger flow:**
```
Developer pushes code
  ↓
GitHub webhook fires (HTTP POST to Jenkins)
  ↓
Jenkins GitHub plugin receives webhook
  ↓
Jenkins checks which jobs monitor this repository
  ↓
Matching jobs are triggered immediately
```

**Advantages:**
- Instant — pipeline starts within seconds of a push
- No polling overhead
- Real-time CI feedback

**Disadvantages:**
- Requires Jenkins to be publicly accessible (or use a reverse proxy/tunnel)
- Webhook can fail silently if Jenkins is down
- Requires GitHub admin access to configure webhooks

---

## ⏰ `pollSCM()` - SCM Polling Fallback

```groovy
triggers {
    pollSCM('H/5 * * * *')
}
```

**What it is:** Jenkins periodically checks the source code repository for new commits and triggers a build if changes are found.

**When to use polling instead of webhooks:**
- Jenkins is behind a firewall (GitHub can't reach it)
- Testing locally with Ngrok/Tailscale not set up yet
- As a fallback alongside webhooks

**Polling overhead:** Each poll makes an API call to GitHub/GitLab. For 100 jobs polling every minute = 6000 API calls/hour. Use `H` (hash) to distribute load.

---

## ⏲️ Jenkins Cron Syntax

Both `pollSCM()` and `cron()` use a 5-field cron expression:

```
MINUTE HOUR DAY_OF_MONTH MONTH DAY_OF_WEEK
```

| Field | Range | Special values |
|---|---|---|
| MINUTE | 0-59 | `*` (every), `H` (hash), `*/5` (every 5) |
| HOUR | 0-23 | `*` (every), `H` (hash), `0-8` (range) |
| DAY_OF_MONTH | 1-31 | `*` (every), `H` (hash) |
| MONTH | 1-12 | `*` (every) |
| DAY_OF_WEEK | 0-7 (0=Sunday) | `*` (every), `H` (hash) |

### Common cron expressions:

```groovy
// Every 5 minutes
pollSCM('H/5 * * * *')

// Every hour
pollSCM('H * * * *')

// Every day at midnight
pollSCM('H 0 * * *')

// Weekdays at midnight
pollSCM('H 0 * * 1-5')

// Every 15 minutes during business hours, weekdays
pollSCM('H/15 9-17 * * 1-5')

// Twice a day (8am and 8pm)
pollSCM('H 8,20 * * *')

// Weekly nightly builds (Sunday at 1am)
cron('H 1 * * 0')
```

### The `H` (Hash) Value - Why It Matters

`H` distributes jobs across the time window to avoid all jobs triggering at the exact same moment.

```groovy
pollSCM('H/5 * * * *')  // Every 5 minutes, but offset by job hash
```

Without `H`:
```
All 50 jobs poll at :00, :05, :10, :15...    ← Burst of 50 simultaneous polls
```

With `H`:
```
Job A polls at :01, :06, :11...
Job B polls at :03, :08, :13...
Job C polls at :04, :09, :14...              ← Load distributed across the minute
```

`H` computes a hash of the job name and uses it to determine the offset. Same job always polls at the same minute, but different jobs are offset from each other.

---

## 🔁 `cron()` - Time-Based Triggering (Not SCM)

```groovy
triggers {
    cron('H 2 * * *')     // Trigger pipeline every day at ~2am, regardless of code changes
}
```

**`cron` vs `pollSCM`:**
- `cron` → always triggers at the scheduled time (even if no code changes)
- `pollSCM` → only triggers if the repository has new commits

**Use cases for `cron`:**
- Nightly builds / regression test suites
- Weekly security scans
- Scheduled database backups
- Periodic cleanup jobs

---

## 🪝 The `GenericTrigger` Plugin

For triggering from ANY external system (not just GitHub), the `Generic Webhook Trigger` plugin provides maximum flexibility:

```groovy
triggers {
    GenericTrigger(
        genericVariables: [
            [key: 'BRANCH', value: '$.ref'],           // Extract from JSON body
            [key: 'AUTHOR', value: '$.pusher.name'],
            [key: 'REPO', value: '$.repository.full_name']
        ],
        token: 'my-secret-token-123',                   // Authenticate the webhook
        causeString: 'Push to $BRANCH by $AUTHOR',
        regexpFilterText: '$BRANCH',
        regexpFilterExpression: '^refs/heads/(main|develop|release/.*)$'  // Only trigger for matching branches
    )
}
```

### Parameters explained:

**`genericVariables`:** Extract values from the webhook payload using JSONPath.

```groovy
genericVariables: [
    // $.ref extracts "refs/heads/main" from the GitHub push payload
    [key: 'GIT_REF', value: '$.ref'],
    // $.head_commit.id extracts the commit SHA
    [key: 'GIT_SHA', value: '$.head_commit.id'],
    // Nested field: $.repository.name
    [key: 'REPO_NAME', value: '$.repository.name'],
    // With default value if field is missing
    [key: 'PR_NUMBER', value: '$.pull_request.number', defaultValue: 'none']
]
```

**`token`:** A secret token that must be included in the webhook URL. Prevents unauthorized triggering.

Webhook URL format: `https://jenkins.com/generic-webhook-trigger/invoke?token=my-secret-token-123`

**`regexpFilterText` + `regexpFilterExpression`:** Filter which webhook events actually trigger the build.

```groovy
regexpFilterText: '$BRANCH',
// Only trigger for main, develop, or release/* branches
regexpFilterExpression: '^refs/heads/(main|develop|release/.*)$'

// After extraction, BRANCH = "refs/heads/main"
// matches ^refs/heads/(main|develop|release/.*)$ → trigger ✅

// BRANCH = "refs/heads/feature/my-feature"
// does NOT match → no trigger ❌
```

**`causeString`:** The message shown in Jenkins for why the build was triggered.

---

## 🔗 Webhook Payload Reference

### GitHub Push Event payload (relevant fields):
```json
{
  "ref": "refs/heads/main",
  "before": "abc123",
  "after": "def456",
  "pusher": {
    "name": "john.doe",
    "email": "john@company.com"
  },
  "repository": {
    "id": 12345,
    "name": "my-app",
    "full_name": "company/my-app",
    "clone_url": "https://github.com/company/my-app.git"
  },
  "head_commit": {
    "id": "def456abc",
    "message": "Fix login bug",
    "timestamp": "2024-01-15T14:30:00Z",
    "author": {
      "name": "John Doe",
      "email": "john@company.com"
    }
  }
}
```

**JSONPath extraction examples:**
- `$.ref` → `"refs/heads/main"`
- `$.pusher.name` → `"john.doe"`
- `$.repository.full_name` → `"company/my-app"`
- `$.head_commit.message` → `"Fix login bug"`

---

## 🔐 Webhook Security Best Practices

### 1. Always use a token
```groovy
// GenericTrigger
token: 'my-secret-webhook-token-456'

// Webhook URL:
// https://jenkins.com/generic-webhook-trigger/invoke?token=my-secret-webhook-token-456
```

### 2. Validate the webhook signature (GitHub)
```groovy
// Store the GitHub webhook secret in Jenkins credentials
withCredentials([string(credentialsId: 'github-webhook-secret', variable: 'WEBHOOK_SECRET')]) {
    // GitHub signs the payload with HMAC-SHA256
    // Validate the X-Hub-Signature-256 header
}
```

### 3. Use HTTPS for webhook endpoints
Never expose Jenkins webhook endpoints over plain HTTP.

### 4. Filter by repository/branch in `regexpFilterExpression`
Prevent rogue repositories from triggering your pipeline.

---

## 📊 Choosing the Right Trigger Strategy

| Scenario | Recommended Trigger |
|---|---|
| GitHub public/accessible Jenkins | `githubPush()` (webhook) |
| Jenkins behind firewall | `pollSCM('H/5 * * * *')` |
| Jenkins behind firewall (backup) | Both: `githubPush()` + `pollSCM()` |
| Non-GitHub source (GitLab, Bitbucket) | `GenericTrigger` |
| Nightly regression tests | `cron('H 2 * * *')` |
| Trigger from external system | `GenericTrigger` with token |
| Multibranch pipeline | Webhook scan triggers (configured in job, not Jenkinsfile) |

---

## ✅ Complete Trigger Configuration Example

```groovy
pipeline {
    agent any

    triggers {
        // Instant trigger on push (requires public Jenkins + GitHub webhook)
        githubPush()

        // Fallback polling every 5 minutes (if webhook fails)
        pollSCM('H/5 * * * *')

        // Nightly regression suite (always, regardless of commits)
        cron('H 3 * * 1-5')    // Weekdays at ~3am
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    // Show what triggered this build
                    echo "Build triggered by: ${currentBuild.getBuildCauses()[0].shortDescription}"
                }
            }
        }

        stage('Build and Test') {
            steps {
                sh 'npm install && npm run build && npm test'
            }
        }
    }
}
```

---

## 🎯 Key Takeaways

1. **`triggers {}`** defines automated build triggers — webhook push, scheduled polling, or time-based cron
2. **`githubPush()`** enables instant triggering via GitHub webhooks (requires public Jenkins or tunnel)
3. **`pollSCM('H/5 * * * *')`** polls Git every 5 minutes and triggers only if commits are found
4. **`cron('H 2 * * *')`** triggers on a schedule regardless of code changes — use for nightly builds
5. **`H` (hash)** distributes polling across the minute window to prevent simultaneous load spikes
6. **`GenericTrigger`** enables webhook triggering from ANY external system with JSONPath payload extraction
7. **`regexpFilterExpression`** filters which webhook events trigger the pipeline (e.g., only specific branches)
8. **`token`** in `GenericTrigger` authenticates webhook calls — always use it in production

---

*Proper trigger configuration is what makes CI/CD "continuous" — developers get feedback within minutes of every push, not hours. Webhooks are the fastest path; polling is the reliable fallback.*
