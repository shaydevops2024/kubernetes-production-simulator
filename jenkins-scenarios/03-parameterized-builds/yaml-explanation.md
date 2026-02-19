# Jenkinsfile Explanation - Parameterized Builds Scenario

This guide explains the `parameters {}` block, all parameter types, the `when {}` directive, and how to build flexible multi-environment pipelines from a single Jenkinsfile.

---

## 📝 The `parameters {}` Block

```groovy
parameters {
    choice(
        name: 'ENVIRONMENT',
        choices: ['dev', 'staging', 'production'],
        description: 'Target deployment environment'
    )
    string(
        name: 'IMAGE_TAG',
        defaultValue: 'latest',
        description: 'Docker image tag to deploy'
    )
    booleanParam(
        name: 'RUN_TESTS',
        defaultValue: true,
        description: 'Run test suite before deploying'
    )
    booleanParam(
        name: 'FORCE_DEPLOY',
        defaultValue: false,
        description: 'Skip approval gate for production'
    )
}
```

**What it is:** Defines a form in the Jenkins UI that users fill out before running the pipeline.

**How it works:**
1. Jenkins parses the `parameters {}` block and renders a form
2. User clicks "Build with Parameters" in the Jenkins UI
3. User fills in values (or keeps defaults)
4. Jenkins runs the pipeline with those values available as `params.NAME`

**Important:** The first run of a new parameterized pipeline always uses defaults because Jenkins needs to parse the file to discover the parameters. After the first run, the form appears.

---

## 🔤 Parameter Types In Detail

### 1. `string` - Free text input

```groovy
string(
    name: 'IMAGE_TAG',
    defaultValue: 'latest',
    description: 'Docker image tag to deploy'
)
```

**UI:** Single-line text field
**Access:** `params.IMAGE_TAG`
**When to use:** Version numbers, branch names, free-form values

```groovy
// Usage in stages
sh "docker pull my-app:${params.IMAGE_TAG}"
echo "Deploying version: ${params.IMAGE_TAG}"
```

---

### 2. `choice` - Dropdown selector

```groovy
choice(
    name: 'ENVIRONMENT',
    choices: ['dev', 'staging', 'production'],
    description: 'Target deployment environment'
)
```

**UI:** Dropdown menu (select one option)
**Access:** `params.ENVIRONMENT`
**First in list = default selection**
**When to use:** Environments, regions, tiers — anything with a fixed set of valid values

```groovy
// Usage in stages
sh "kubectl apply -f k8s/${params.ENVIRONMENT}/"
echo "Deploying to: ${params.ENVIRONMENT}"
```

**Why `choice` over `string` for environments?**
- Prevents typos (`produciton` vs `production`)
- Limits the blast radius of mistakes
- Self-documenting — users see what options exist

---

### 3. `booleanParam` - Toggle checkbox

```groovy
booleanParam(
    name: 'RUN_TESTS',
    defaultValue: true,
    description: 'Run test suite before deploying'
)
```

**UI:** Checkbox (checked = `true`, unchecked = `false`)
**Access:** `params.RUN_TESTS` → returns `true` or `false`
**When to use:** Feature flags, skip-gates, optional steps

```groovy
// Usage with when{}
when {
    expression { params.RUN_TESTS == true }
}
```

**⚠️ Gotcha:** `params.RUN_TESTS` returns a String `"true"` or `"false"` in some Jenkins versions. Compare safely:
```groovy
// Safe comparison
when {
    expression { params.RUN_TESTS.toBoolean() == true }
}
// Or simply
when {
    expression { params.RUN_TESTS }
}
```

---

### 4. `password` - Masked input

```groovy
password(
    name: 'API_KEY',
    defaultValue: '',
    description: 'External API key'
)
```

**UI:** Password field (input hidden with asterisks)
**Access:** `params.API_KEY`
**Masked in console output:** `****`
**When to use:** Tokens, API keys passed at runtime (prefer Jenkins Credentials Store for static secrets)

---

### 5. `text` - Multi-line text area

```groovy
text(
    name: 'RELEASE_NOTES',
    defaultValue: '',
    description: 'Release notes for this deployment'
)
```

**UI:** Multi-line text area
**Access:** `params.RELEASE_NOTES`
**When to use:** JSON configs, release notes, multi-line scripts

---

## 🎛️ The `when {}` Directive

```groovy
stage('Test') {
    when {
        expression { params.RUN_TESTS == true }
    }
    steps {
        sh 'npm test'
    }
}
```

**What it is:** A directive that determines whether a stage runs. If the condition is false, the stage is **skipped** (shown in gray in the Jenkins UI — not failed).

**Key difference:** `when` = skip (gray) vs failure = fail (red).

---

### `when` condition types:

### `expression` - Groovy boolean expression (most flexible)

```groovy
when { expression { params.ENVIRONMENT == 'production' } }
when { expression { env.BRANCH_NAME == 'main' } }
when { expression { currentBuild.result == null } }  // No previous failures
```

### `branch` - Run only on specific branch names

```groovy
when { branch 'main' }
when { branch 'release/*' }     // Wildcard matching
when { branch pattern: 'release/.*', comparator: 'REGEXP' }  // Regex
```

### `tag` - Run only when a git tag is present

```groovy
when { tag 'v*' }               // Any tag starting with 'v'
when { tag 'v1.*' }             // Version 1.x tags only
```

### `environment` - Match environment variable value

```groovy
when { environment name: 'DEPLOY_ENV', value: 'production' }
```

### `changeset` - Run only if specific files changed

```groovy
when { changeset '**/*.js' }          // Only if JS files changed
when { changeset 'k8s/**' }           // Only if k8s manifests changed
```

### `not` - Negation

```groovy
when { not { branch 'dev' } }          // All branches except dev
when { not { expression { params.SKIP_TESTS } } }
```

---

## 🔗 Combining Conditions: `allOf` and `anyOf`

### `allOf` - AND logic (ALL conditions must be true)

```groovy
stage('Approval') {
    when {
        allOf {
            expression { params.ENVIRONMENT == 'production' }
            expression { params.FORCE_DEPLOY == false }
        }
    }
    steps {
        input message: 'Deploy to production?', ok: 'Approve'
    }
}
```

**Logic:** Stage runs only when BOTH `ENVIRONMENT == production` AND `FORCE_DEPLOY == false`.

### `anyOf` - OR logic (AT LEAST ONE condition must be true)

```groovy
stage('Integration Tests') {
    when {
        anyOf {
            branch 'main'
            branch 'release/*'
            expression { params.ENVIRONMENT == 'staging' }
        }
    }
    steps {
        sh 'npm run test:integration'
    }
}
```

**Logic:** Stage runs when building from `main`, any `release/` branch, OR staging environment.

### Nested combinations:

```groovy
when {
    allOf {
        branch 'main'
        anyOf {
            expression { params.ENVIRONMENT == 'staging' }
            expression { params.ENVIRONMENT == 'production' }
        }
    }
}
```

**Logic:** On `main` branch AND (staging OR production environment).

---

## 🛑 The `input` Step - Manual Approval Gate

```groovy
stage('Approval') {
    when {
        allOf {
            expression { params.ENVIRONMENT == 'production' }
            expression { params.FORCE_DEPLOY == false }
        }
    }
    steps {
        input message: 'Deploy to production?', ok: 'Approve'
    }
}
```

**What it is:** Pauses the pipeline and waits for a human to click a button in the Jenkins UI.

**Options:**

```groovy
input(
    message: 'Deploy to production?',     // Message shown to the approver
    ok: 'Yes, Deploy!',                   // Label for the approve button
    submitter: 'admin,ops-team',          // Only these users can approve
    submitterParameter: 'APPROVED_BY',    // Capture who approved
    parameters: [                          // Additional input at approval time
        string(name: 'DEPLOY_NOTE', defaultValue: '', description: 'Reason for deploy')
    ]
)
```

**Timeout the input gate:**
```groovy
timeout(time: 30, unit: 'MINUTES') {
    input message: 'Approve deploy?', ok: 'Deploy'
}
```
If nobody approves within 30 minutes, the pipeline automatically aborts.

**Capturing who approved:**
```groovy
script {
    def approver = input(
        message: 'Approve production deploy?',
        ok: 'Approve',
        submitterParameter: 'APPROVED_BY'
    )
    echo "Approved by: ${approver}"
}
```

---

## 🗂️ Environment-Specific ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-staging
  labels:
    app: parameterized-app
    environment: staging
data:
  APP_ENV: "staging"
  LOG_LEVEL: "debug"
  DB_HOST: "staging-db.internal"
  FEATURE_FLAGS: "new-ui=true,beta-api=true"
```

**What it is:** A Kubernetes ConfigMap that holds environment-specific configuration.

**Why labels matter here:**
- `environment: staging` → makes it easy to query: `kubectl get cm -l environment=staging`
- `app: parameterized-app` → links to the deployment

**In the Jenkinsfile, this is selected by:**
```groovy
sh "kubectl apply -f k8s/${params.ENVIRONMENT}/"
```
This applies all manifests in the `k8s/staging/` or `k8s/production/` directory.

**Injecting ConfigMap into pods with `envFrom`:**
```yaml
containers:
- name: app
  envFrom:
  - configMapRef:
      name: app-config-staging   # Injects ALL keys as env vars
```

vs. selecting specific keys with `env`:
```yaml
env:
- name: LOG_LEVEL
  valueFrom:
    configMapKeyRef:
      name: app-config-staging
      key: LOG_LEVEL
```

**Verify config was applied:**
```bash
kubectl get pods -l app=parameterized-app -o name | \
  xargs -I{} kubectl exec {} -- env | grep APP_ENV
```

---

## 📋 Parameterized Pipeline Patterns

### Pattern 1: Environment-aware deploy
```groovy
pipeline {
    parameters {
        choice(name: 'ENV', choices: ['dev', 'staging', 'prod'])
    }
    stages {
        stage('Deploy') {
            steps {
                sh "kubectl apply -f k8s/${params.ENV}/"
            }
        }
    }
}
```

### Pattern 2: Skip-able test stage
```groovy
stage('Test') {
    when { expression { !params.SKIP_TESTS } }
    steps { sh 'make test' }
}
```

### Pattern 3: Protected production with approval
```groovy
stage('Gate') {
    when { expression { params.ENV == 'prod' } }
    steps {
        timeout(time: 1, unit: 'HOURS') {
            input 'Deploy to production?'
        }
    }
}
```

### Pattern 4: Hotfix fast path (skip tests + approval)
```groovy
// FORCE_DEPLOY=true + RUN_TESTS=false → hotfix path
stage('Test') {
    when { expression { params.RUN_TESTS } }
    steps { sh 'make test' }
}
stage('Approval') {
    when {
        allOf {
            expression { params.ENV == 'prod' }
            expression { !params.FORCE_DEPLOY }
        }
    }
    steps { input 'Approve?' }
}
```

---

## 🎯 Key Takeaways

1. **`parameters {}`** defines a UI form; users fill it out before each build run
2. **Five parameter types:** `string`, `choice`, `booleanParam`, `password`, `text`
3. **Access values** with `params.NAME` anywhere in the pipeline
4. **`when {}`** conditionally skips a stage — skipped ≠ failed (gray vs red)
5. **`allOf`** = AND logic; **`anyOf`** = OR logic; **`not`** = negation
6. **`input`** pauses the pipeline for human approval — use with `timeout()` to auto-abort
7. **One Jenkinsfile** handles dev, staging, and production with different behaviors
8. **`choice` > `string`** for environments — prevents typos and limits blast radius

---

*Parameterized pipelines are the foundation of flexible CI/CD. Master these patterns and you can build pipelines that safely handle everything from quick dev deploys to gated production releases.*
