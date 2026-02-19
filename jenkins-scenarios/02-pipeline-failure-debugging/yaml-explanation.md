# Jenkinsfile Explanation - Pipeline Failure Debugging Scenario

This guide explains the Jenkinsfile patterns used for building debuggable pipelines, covering console log reading, error handling, `withCredentials`, and rollout verification.

---

## 🔍 Reading the Jenkins Console Log

The Jenkins console log is your primary debugging tool. Understanding its format is essential.

### Console output structure:

```
[Pipeline] Start of Pipeline
[Pipeline] node
Running on agent-1 in /home/jenkins/workspace/my-app-pipeline

[Pipeline] { (Checkout)          ← Stage name in brackets
+ git branch: main ...           ← + prefix = actual command executed
Cloning into /home/jenkins/...
Checkout complete.

[Pipeline] { (Build)
+ npm install
+ npm run build

ERROR in ./src/components/Dashboard.jsx
Module not found: Error: Cannot resolve module "react-charts"

script returned exit code 1     ← Exit code tells you the failure type
[Pipeline] End of Pipeline
Finished: FAILURE
```

**Key elements to find:**
- `[Pipeline] { (StageName) }` → which stage failed
- `+` prefix → the exact command Jenkins ran
- `ERROR` / `error` messages → what went wrong
- `script returned exit code X` → failure type indicator

### Exit code reference:

| Exit Code | Meaning | Common Cause |
|---|---|---|
| `0` | Success | Command completed normally |
| `1` | General failure | Test failed, build error, app crash |
| `2` | Misuse of command | Wrong arguments passed to a command |
| `126` | Permission denied | Script not executable (`chmod +x`) |
| `127` | Command not found | Missing binary, wrong PATH |
| `130` | Interrupted | Ctrl+C or killed manually |
| `137` | OOM killed | Container ran out of memory |

**Debugging strategy:**
1. Scroll to the **first** error (not the last — later errors are often cascading)
2. Find the stage using `[Pipeline] { (StageName) }`
3. Find the command with the `+` prefix
4. Read the error message immediately after

---

## 🔒 The `withCredentials()` Step

```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-hub',
    usernameVariable: 'USER',
    passwordVariable: 'PASS'
)]) {
    sh "docker login ${REGISTRY} -u ${USER} -p ${PASS}"
    sh "docker push ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER}"
}
```

**What it is:** A step that securely injects credentials into a limited scope, then removes them.

**Why use it instead of environment variables?**
- Credentials are masked in the console log (`****` appears instead of the actual value)
- Variables are only available inside the `withCredentials` block (scoped)
- Credentials are never written to disk in plaintext
- If the pipeline is replayed or shared, credentials aren't exposed

### Credential types available:

**Username + Password:**
```groovy
withCredentials([usernamePassword(
    credentialsId: 'my-creds',
    usernameVariable: 'USERNAME',
    passwordVariable: 'PASSWORD'
)]) {
    sh "curl -u ${USERNAME}:${PASSWORD} https://api.example.com"
}
```

**Secret Text (API tokens, single values):**
```groovy
withCredentials([string(credentialsId: 'api-token', variable: 'TOKEN')]) {
    sh "curl -H 'Authorization: Bearer ${TOKEN}' https://api.example.com"
}
```

**SSH Private Key:**
```groovy
withCredentials([sshUserPrivateKey(
    credentialsId: 'git-ssh-key',
    keyFileVariable: 'SSH_KEY'
)]) {
    sh "ssh -i ${SSH_KEY} user@server.com 'deploy.sh'"
}
```

**Secret File:**
```groovy
withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
    sh "kubectl --kubeconfig=${KUBECONFIG} apply -f k8s/"
}
```

**Certificate:**
```groovy
withCredentials([certificate(
    credentialsId: 'ssl-cert',
    keystoreVariable: 'KEYSTORE',
    passwordVariable: 'KEYSTORE_PASS'
)]) {
    sh "keytool -list -keystore ${KEYSTORE} -storepass ${KEYSTORE_PASS}"
}
```

**Multiple credentials at once:**
```groovy
withCredentials([
    usernamePassword(credentialsId: 'docker-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS'),
    string(credentialsId: 'slack-token', variable: 'SLACK_TOKEN')
]) {
    sh "docker login -u ${DOCKER_USER} -p ${DOCKER_PASS}"
    // both credentials available here
}
```

**⚠️ Important:** Even though Jenkins masks credentials in logs, never print them explicitly:
```groovy
// DANGEROUS - Jenkins masks it, but don't get in the habit
echo "Password is: ${PASSWORD}"

// CORRECT - never echo credentials
sh "docker login -u ${USER} -p ${PASS}"
```

---

## ✅ The `kubectl rollout status` Step

```groovy
sh "kubectl rollout status deployment/${APP_NAME} -n production --timeout=120s"
```

**What it is:** A blocking command that waits until a Kubernetes deployment is fully rolled out (or times out and fails).

**Why it matters for pipelines:**
Without this check, Jenkins marks the deploy stage as successful the instant `kubectl apply` runs — even if pods immediately crash or fail to pull the image.

```
WRONG flow (without rollout status):
  kubectl apply → EXIT 0 → Jenkins: "SUCCESS ✅" → Pods crash → Nobody knows

CORRECT flow (with rollout status):
  kubectl apply → kubectl rollout status (blocks) → Pods healthy → Jenkins: "SUCCESS ✅"
                                                  → Pods crash → Jenkins: "FAILURE ❌"
```

**Options:**

```bash
# Basic - wait up to default timeout
kubectl rollout status deployment/my-app -n production

# With explicit timeout
kubectl rollout status deployment/my-app -n production --timeout=120s

# Watch mode (streams progress)
kubectl rollout status deployment/my-app -n production -w

# Multiple deployments
kubectl rollout status deployment/frontend -n production && \
kubectl rollout status deployment/backend -n production
```

**Exit codes:**
- `0` → Rollout successful (all pods healthy)
- `1` → Timed out or rollout failed

---

## 🏗️ The Fixed Jenkinsfile Structure

```groovy
pipeline {
    agent any

    environment {
        REGISTRY = 'my-registry.com'
        APP_NAME = 'my-app'
    }

    stages {
        stage('Checkout')    { ... }
        stage('Build')       { ... }
        stage('Test')        { ... }
        stage('Docker Build') { ... }
        stage('Deploy')      { ... }
    }

    post {
        success { ... }
        failure { ... }
        always  { ... }
    }
}
```

**What changed from the broken version:**

| Issue | Before (broken) | After (fixed) |
|---|---|---|
| Missing dependency | No error handling | react-charts added to package.json |
| Syntax error | No check | async/await fixed in source |
| Docker auth | Plain `docker push` | `withCredentials` block added |
| Deploy verification | Just `kubectl set image` | `kubectl rollout status` added |
| No notifications | No post block | Full post block with success/failure |
| No cleanup | Files left behind | `cleanWs()` in always |

---

## 🐛 Common Failure Patterns and Console Log Signatures

### 1. Dependency Failure (Build stage)
```
+ npm install
npm ERR! code ETARGET
npm ERR! No matching version found for react-charts@3.0.0

script returned exit code 1
```
**Fix:** Update `package.json`, run `npm install` locally, commit the lockfile.

### 2. Test Failure (Test stage)
```
+ npm test
FAIL src/components/__tests__/Dashboard.test.js
  ● Dashboard renders correctly
    Expected: "Hello"
    Received: "Bye"

script returned exit code 1
```
**Fix:** Fix the failing test or the code under test.

### 3. Authentication Failure (Docker Build/Push)
```
+ docker push my-registry.com/my-app:42
denied: access forbidden
unauthorized: authentication required

script returned exit code 1
```
**Fix:** Add credentials to Jenkins → use `withCredentials`.

### 4. Infrastructure Failure (Deploy stage)
```
+ kubectl apply -f k8s/deployment.yaml
The connection to the server localhost:8080 was refused
did you specify the right host or port?

script returned exit code 1
```
**Fix:** Check kubeconfig, cluster connectivity, Jenkins agent network access.

### 5. Syntax Error (Pipeline fails before any stage)
```
[Pipeline] Start of Pipeline
org.codehaus.groovy.control.MultipleCompilationErrorsException: startup failed:
WorkflowScript: 15: expecting '}', found 'stage' @ line 15, column 5.

Finished: FAILURE
```
**Fix:** Check Jenkinsfile for unclosed braces, missing quotes, invalid Groovy syntax.

---

## 🔁 The Replay Feature

The **Replay** button in Jenkins allows you to re-run a build with a modified Jenkinsfile without committing to git.

**How to use it:**
1. Open any build in Jenkins UI
2. Click **"Replay"** in the left sidebar
3. Edit the Jenkinsfile inline
4. Click **"Run"**

**When to use it:**
- Quickly testing a fix to the Jenkinsfile
- Debugging a specific stage without going through all previous stages
- Trying different `sh` commands to diagnose a problem

**Limitation:** Replay changes are not saved. Always commit the working fix back to the repo.

---

## 🔧 Debugging Techniques Inside `sh` Steps

### Enable verbose output with `set -ex`:
```groovy
sh '''
    set -e    # Exit immediately if any command fails
    set -x    # Print each command before executing (verbose)
    npm install
    npm run build
'''
```
Output with `set -x`:
```
+ npm install
...
+ npm run build
...
```

### Capture command output for later use:
```groovy
script {
    def version = sh(script: 'cat package.json | jq -r .version', returnStdout: true).trim()
    echo "Deploying version: ${version}"
    env.APP_VERSION = version
}
```

### Return exit code instead of failing:
```groovy
script {
    def exitCode = sh(script: 'npm test', returnStatus: true)
    if (exitCode != 0) {
        echo "Tests failed with exit code ${exitCode}"
        currentBuild.result = 'UNSTABLE'  // Mark as unstable instead of failed
    }
}
```

### Try/catch for custom error handling:
```groovy
script {
    try {
        sh 'deploy.sh'
    } catch (Exception e) {
        echo "Deploy failed: ${e.message}"
        sh 'rollback.sh'
        throw e   // Re-throw to fail the build
    }
}
```

---

## 📊 The `options {}` Block for Debugging

Add these options to make pipelines easier to debug:

```groovy
options {
    timestamps()                    // Add timestamps to every console line
    timeout(time: 30, unit: 'MINUTES')  // Kill hung pipelines
    buildDiscarder(logRotator(numToKeepStr: '30'))  // Keep 30 builds
}
```

With timestamps enabled, console output looks like:
```
14:32:01  [Pipeline] { (Build)
14:32:01  + npm install
14:32:45  added 847 packages in 44s
14:32:45  + npm run build
```
This tells you exactly how long each command took.

---

## 🎯 Key Takeaways

1. **Read from the first error** — later errors are usually cascading from the first
2. **`+` prefix** = the exact command Jenkins executed
3. **Exit codes** tell you the failure type: `1`=general, `127`=not found, `126`=permission denied
4. **`withCredentials`** = secure credential injection, masked in logs, scoped to block
5. **`kubectl rollout status`** = blocks until deploy is truly healthy (not just applied)
6. **`set -ex`** in sh blocks gives verbose, fail-fast debugging output
7. **Replay** = test Jenkinsfile fixes without git commits
8. **`post { always { cleanWs() } }`** = always clean up, like a finally block

---

*Debugging Jenkins pipelines is a skill that comes with practice. The most important habit: always read the full console output from the first error, not just the last line.*
