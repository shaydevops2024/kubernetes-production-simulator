# Jenkinsfile Explanation - First Pipeline Scenario

This guide breaks down every block and directive in a declarative Jenkinsfile, explaining each field in detail and providing context for how and why pipelines are structured this way.

---

## 🚀 The `pipeline {}` Block

### What is it?
The top-level wrapper for every declarative Jenkins pipeline. Nothing outside this block is part of the pipeline.

```groovy
pipeline {
    // everything goes here
}
```

**Why it exists:**
- Declares to Jenkins that this file uses the Declarative Pipeline syntax (as opposed to Scripted syntax)
- Provides a clear boundary around all pipeline configuration
- Enables the Jenkins UI to parse and visualize the pipeline as stages

**Declarative vs Scripted:**
- **Declarative** (used here): Structured, validated by Jenkins, easier to read, enforces best practices
- **Scripted**: Pure Groovy code, more flexible but harder to maintain and validate

---

## 🤖 The `agent` Directive

```groovy
agent any
```

**What it is:** Specifies where the pipeline (or a stage) will run.

**Options:**

| Option | Description |
|---|---|
| `any` | Run on any available Jenkins executor |
| `none` | Don't allocate an agent at the top level (define per stage) |
| `label 'linux'` | Run on a node with a specific label |
| `docker 'node:18'` | Run inside a Docker container |
| `kubernetes { ... }` | Run as a Kubernetes pod |

**Example with Docker agent:**
```groovy
agent {
    docker {
        image 'node:18-alpine'
        args '-v /tmp:/tmp'
    }
}
```

**Example with Kubernetes agent:**
```groovy
agent {
    kubernetes {
        yaml '''
        spec:
          containers:
          - name: build
            image: node:18
        '''
    }
}
```

**Why `agent any` for learning?**
- Simplest option - works on any Jenkins setup without extra configuration
- In production, you'd pin to a specific label or Docker image for reproducibility

---

## 🌍 The `environment {}` Block

```groovy
environment {
    APP_NAME = 'my-web-app'
    IMAGE_TAG = "${BUILD_NUMBER}"
}
```

**What it is:** Defines environment variables available to all stages in the pipeline.

**Key points:**
- Variables are accessible in `sh` steps as `$APP_NAME` (shell) or `${APP_NAME}` (Groovy)
- Access in Groovy: `env.APP_NAME` or just `APP_NAME` inside `"${...}"`
- Single quotes `'...'` → no interpolation (literal string)
- Double quotes `"..."` → Groovy string interpolation

**Built-in Jenkins environment variables:**

| Variable | Value |
|---|---|
| `BUILD_NUMBER` | Current build number (e.g., `42`) |
| `BUILD_URL` | Full URL to the build |
| `JOB_NAME` | Name of the pipeline job |
| `WORKSPACE` | Path to the workspace directory |
| `BRANCH_NAME` | Branch being built (Multibranch pipelines) |
| `GIT_COMMIT` | Full git commit SHA |

**Stage-level environment (override or extend):**
```groovy
stage('Deploy') {
    environment {
        DEPLOY_ENV = 'production'   // Only available in this stage
    }
    steps { ... }
}
```

**⚠️ Common mistake:** Using single quotes when you need variable expansion:
```groovy
// WRONG - IMAGE_TAG won't be interpolated
sh 'docker build -t my-app:${IMAGE_TAG} .'

// CORRECT - double quotes enable interpolation
sh "docker build -t my-app:${IMAGE_TAG} ."
```

---

## 📦 The `stages {}` Block

```groovy
stages {
    stage('Build') { ... }
    stage('Test') { ... }
    stage('Deploy') { ... }
}
```

**What it is:** The container for all stage definitions. Every pipeline must have exactly one `stages` block.

**Stage execution rules:**
- Stages run **sequentially** by default (Build → Test → Deploy)
- If a stage **fails**, all subsequent stages are **skipped**
- The pipeline ends and the `post {}` block runs

**Visual representation in Jenkins Blue Ocean:**
```
[Build] ──success──► [Test] ──success──► [Deploy]
   │                    │                    │
   └─failure──────────► [SKIP Test] [SKIP Deploy]
                                  ↓
                          [post { failure }]
```

---

## 🎭 The `stage('Name') {}` Block

```groovy
stage('Build') {
    steps {
        echo 'Building application...'
        sh 'npm install'
        sh 'npm run build'
    }
}
```

**What it is:** A named logical phase of work within the pipeline.

**Stage structure:**
```groovy
stage('Name') {
    agent { ... }          // Optional: override top-level agent
    environment { ... }    // Optional: stage-specific variables
    when { ... }           // Optional: conditional execution
    steps { ... }          // Required: the actual work
    post { ... }           // Optional: stage-level post actions
}
```

**Why give stages names?**
- Names appear in the Jenkins UI as column headers
- Used in build history and notifications ("Stage 'Build' failed")
- Helps teammates understand what the pipeline is doing at a glance

**Best practices for stage names:**
- Use action verbs: `Build`, `Test`, `Deploy`, `Verify`
- Keep names short and descriptive
- Match names to the logical phase (don't name it `Step1`)

---

## 🔧 The `steps {}` Block

```groovy
steps {
    echo 'Building application...'
    sh 'npm install'
    sh 'npm run build'
}
```

**What it is:** Contains the actual commands that run within a stage.

**Common step types:**

### `echo` - Print to console log
```groovy
echo 'Deployment started'
echo "Building version: ${IMAGE_TAG}"
```

### `sh` - Run a shell command (Linux/macOS)
```groovy
sh 'npm install'                    // Simple command
sh "docker build -t app:${TAG} ."  // With interpolation
sh '''                              // Multi-line block
    cd /app
    npm install
    npm run build
'''
```

### `bat` - Run a Windows batch command
```groovy
bat 'npm install'   // Windows equivalent of sh
```

### `script {}` - Run arbitrary Groovy code
```groovy
script {
    def result = sh(script: 'cat version.txt', returnStdout: true).trim()
    env.VERSION = result
    echo "Version is: ${result}"
}
```

### `dir()` - Change working directory
```groovy
dir('frontend') {
    sh 'npm install && npm run build'
}
```

### `timeout()` - Set maximum execution time
```groovy
timeout(time: 5, unit: 'MINUTES') {
    sh 'npm test'
}
```

### `retry()` - Retry on failure
```groovy
retry(3) {
    sh 'npm install'   // Retry up to 3 times if it fails
}
```

### `sleep()` - Wait between operations
```groovy
sleep(time: 30, unit: 'SECONDS')
```

---

## 📬 The `post {}` Block

```groovy
post {
    success {
        echo 'Pipeline completed successfully!'
    }
    failure {
        echo 'Pipeline failed. Check logs above.'
    }
    always {
        echo 'Cleaning up workspace...'
        cleanWs()
    }
}
```

**What it is:** Defines actions that run after all stages complete, regardless of the outcome.

**Post conditions:**

| Condition | When it runs |
|---|---|
| `always` | Every time, no matter what |
| `success` | Only when the pipeline succeeded |
| `failure` | Only when the pipeline failed |
| `unstable` | When marked unstable (e.g., test warnings) |
| `changed` | When build status differs from the previous build |
| `fixed` | When a previously failing build now succeeds |
| `aborted` | When the pipeline was manually stopped |
| `unsuccessful` | When not successful (failure + unstable + aborted) |
| `cleanup` | Always, runs last (after other post conditions) |

**Execution order:**
```
stages complete
  ↓
success / failure / unstable / changed (whichever applies)
  ↓
always
  ↓
cleanup (runs after always)
```

**Why `cleanWs()` in `always`?**
- Removes all files from the Jenkins workspace
- Prevents stale files from previous builds affecting future ones
- Frees disk space on the Jenkins agent
- Equivalent to: `deleteDir()` in a scripted pipeline

**Production post block example:**
```groovy
post {
    success {
        slackSend(
            channel: '#deployments',
            color: 'good',
            message: "✅ ${JOB_NAME} #${BUILD_NUMBER} deployed successfully"
        )
    }
    failure {
        emailext(
            to: 'team@company.com',
            subject: "❌ ${JOB_NAME} #${BUILD_NUMBER} FAILED",
            body: "Check: ${BUILD_URL}"
        )
    }
    always {
        archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true
        cleanWs()
    }
}
```

---

## 🔄 How Everything Works Together

### Pipeline execution flow:

```
1. Jenkins reads Jenkinsfile
2. Allocates agent (any available executor)
3. Sets environment variables (APP_NAME, IMAGE_TAG)
4. Runs stages in order:
   a. [Build] → sh 'npm install' → sh 'npm run build'
   b. [Test]  → sh 'npm test'
   c. [Deploy]→ sh 'kubectl apply -f k8s/deployment.yaml'
              → sh 'kubectl set image ...'
5. Runs post block:
   - On success: echo success message
   - On failure: echo failure message
   - Always: cleanWs()
```

### The Kubernetes Deploy step explained:
```groovy
sh 'kubectl apply -f k8s/deployment.yaml'
sh 'kubectl set image deployment/my-web-app app=my-web-app:${IMAGE_TAG}'
```

- `kubectl apply` - Creates or updates the Kubernetes deployment manifest
- `kubectl set image` - Updates the container image in the running deployment
- `${IMAGE_TAG}` = `${BUILD_NUMBER}` → each build produces a unique image tag
- This enables traceability: you can see exactly which Jenkins build deployed which image

---

## 🎯 Best Practices

### 1. Always use `cleanWs()` in post
Prevents workspace pollution between builds.

### 2. Pin image tags (never use `latest`)
```groovy
// WRONG - not reproducible
sh 'docker build -t my-app:latest .'

// CORRECT - tied to specific build
sh "docker build -t my-app:${BUILD_NUMBER} ."
```

### 3. Use multi-line sh blocks for complex commands
```groovy
sh '''
    set -e             # Exit on any error
    npm install
    npm run lint
    npm run build
'''
```

### 4. Test your Jenkinsfile without committing using "Replay"
Jenkins UI → Build History → Select a build → "Replay" → Edit Jenkinsfile → Run

### 5. Add `options {}` for pipeline-wide settings
```groovy
options {
    timeout(time: 30, unit: 'MINUTES')   // Kill if runaway
    buildDiscarder(logRotator(numToKeepStr: '20'))  // Keep last 20 builds
    timestamps()                          // Add timestamps to console output
    disableConcurrentBuilds()            // Prevent parallel pipeline runs
}
```

---

## 📚 Key Takeaways

1. **`pipeline {}`** is the mandatory top-level wrapper
2. **`agent any`** runs on any available executor; use `docker` or `kubernetes` for reproducibility
3. **`environment {}`** sets variables for all stages; use double quotes for interpolation
4. **`stages {}`** contains ordered stage definitions; they run sequentially and fail fast
5. **`steps {}`** contains the actual work: `echo`, `sh`, `retry`, `timeout`, etc.
6. **`post {}`** handles cleanup and notifications; `always` is like a `finally` block
7. Single quotes = no interpolation; double quotes = Groovy string interpolation

---

*Master this skeleton and you can build any CI/CD pipeline. Every advanced Jenkins feature is just an extension of this foundation.*
