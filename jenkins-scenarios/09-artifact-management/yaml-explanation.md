# Jenkinsfile Explanation - Artifact Management Scenario

This guide explains how Jenkins manages build artifacts, test results, HTML reports, and fingerprinting — covering `archiveArtifacts`, `junit`, `publishHTML`, and build retention policies.

---

## 📦 The `archiveArtifacts` Step

```groovy
stage('Archive') {
    steps {
        archiveArtifacts(
            artifacts: 'dist/**,reports/**,*.jar',
            fingerprint: true,
            allowEmptyArchive: true,
            excludes: 'dist/**/*.map'
        )
    }
}
```

**What it is:** Copies files from the Jenkins workspace to persistent storage attached to the build. Archived artifacts survive workspace cleanup and can be downloaded from the Jenkins build page.

### Parameters:

| Parameter | Type | Description |
|---|---|---|
| `artifacts` | String | Glob pattern of files to archive |
| `fingerprint` | Boolean | Compute MD5 hash for traceability (default: false) |
| `allowEmptyArchive` | Boolean | Don't fail if no files match (default: false) |
| `excludes` | String | Glob pattern of files to exclude from archiving |
| `caseSensitive` | Boolean | Case-sensitive glob matching (default: true) |
| `onlyIfSuccessful` | Boolean | Only archive if build succeeded (default: false) |

### Glob pattern examples:

```groovy
// Archive all JARs
artifacts: '**/*.jar'

// Archive everything in dist/
artifacts: 'dist/**'

// Archive multiple types
artifacts: 'dist/**,reports/**,target/*.jar'

// Archive specific files
artifacts: 'app.zip,coverage/index.html'

// Exclude source maps from the archive
artifacts: 'dist/**'
excludes: 'dist/**/*.map'
```

**Where artifacts are stored:**
- Jenkins stores them at: `$JENKINS_HOME/jobs/<job>/builds/<number>/archive/`
- Accessible via Jenkins UI: Build page → "Artifacts" link
- Downloadable via API: `http://jenkins/job/my-job/42/artifact/dist/app.zip`

---

## 🧪 The `junit` Step - Test Result Publishing

```groovy
post {
    always {
        junit(
            testResults: 'test-results/**/*.xml',
            allowEmptyResults: false,
            skipPublishingChecks: false
        )
    }
}
```

**What it is:** Parses JUnit-format XML test result files and publishes them to the Jenkins build as a structured test report.

**Why `post { always }`?**
Test results should be published even if the tests failed. Running `junit` in `always` ensures Jenkins captures results whether the pipeline passed or failed.

### What Jenkins does with JUnit XML:
1. **Parses** all matching XML files
2. **Displays** pass/fail counts on the build page
3. **Shows trends** across builds (test count, failure count, duration)
4. **Marks the build UNSTABLE** if tests fail (instead of FAILED, by default)
5. **Shows individual test failures** with stack traces
6. **Tracks flaky tests** by comparing with previous builds

### JUnit XML format (what tools produce):
```xml
<testsuite name="UserService" tests="5" failures="1" time="1.234">
    <testcase name="should create user" classname="UserService" time="0.123"/>
    <testcase name="should validate email" classname="UserService" time="0.456">
        <failure message="Expected 'valid' but got 'invalid'">
            at UserService.test.js:42
        </failure>
    </testcase>
    <testcase name="should hash password" classname="UserService" time="0.234"/>
</testsuite>
```

**Tools that produce JUnit XML:**
- Jest: `--reporter=jest-junit`
- pytest: `--junitxml=results.xml`
- Maven: built-in (in `target/surefire-reports/`)
- JUnit (Java): built-in
- Go: `go test -v ./... | go-junit-report > results.xml`
- Mocha: `mocha --reporter mocha-junit-reporter`

**Configuration:**
```groovy
junit(
    testResults: 'test-results/**/*.xml',
    allowEmptyResults: true,           // Don't fail if no XML found
    keepLongStdio: true,               // Keep full stdout in failed tests
    skipPublishingChecks: false        // Publish to GitHub/GitLab as checks
)
```

---

## 📊 The `publishHTML` Step - HTML Reports

```groovy
publishHTML(target: [
    allowMissing: false,
    alwaysLinkToLastBuild: true,
    keepAll: true,
    reportDir: 'coverage',
    reportFiles: 'index.html',
    reportName: 'Coverage Report',
    reportTitles: 'Test Coverage'
])
```

**What it is:** Creates a tab in the Jenkins build page that serves an HTML report directly from the Jenkins UI.

**Requires:** The `HTML Publisher` plugin.

### Parameters:

| Parameter | Description |
|---|---|
| `reportDir` | Directory containing the HTML report files |
| `reportFiles` | Entry point HTML file (relative to `reportDir`) |
| `reportName` | Tab name in Jenkins UI (becomes a link on the build page) |
| `reportTitles` | Title shown in the browser tab |
| `keepAll` | Keep the report for every build (not just the latest) |
| `alwaysLinkToLastBuild` | The job page links to the latest build's report |
| `allowMissing` | Don't fail if the report directory doesn't exist |

### Common use cases:

**Code coverage report (Istanbul/nyc):**
```groovy
sh 'npm test -- --coverage'
publishHTML(target: [
    reportDir: 'coverage/lcov-report',
    reportFiles: 'index.html',
    reportName: 'Coverage Report'
])
```

**API documentation (Swagger):**
```groovy
sh 'npm run docs'
publishHTML(target: [
    reportDir: 'docs',
    reportFiles: 'index.html',
    reportName: 'API Docs'
])
```

**Performance report (JMeter):**
```groovy
sh 'jmeter -n -t test-plan.jmx -l results.jtl -e -o report/'
publishHTML(target: [
    reportDir: 'report',
    reportFiles: 'index.html',
    reportName: 'Performance Report'
])
```

**⚠️ Note on CSP:** Jenkins applies a strict Content Security Policy (CSP) to embedded HTML, which can break JavaScript-heavy reports. To relax it:
```groovy
// Add to Jenkins startup: -Dhudson.model.DirectoryBrowserSupport.CSP=""
```
Or use the `Content Security Policy` plugin.

---

## 🔏 The `fingerprint` Step - Artifact Traceability

```groovy
fingerprint 'dist/**/*.jar'
```

Or via `archiveArtifacts` with `fingerprint: true`:
```groovy
archiveArtifacts artifacts: '*.jar', fingerprint: true
```

**What it is:** Computes the MD5 hash of a file and records which builds produced and consumed it.

**Why fingerprinting?**
When the same artifact flows through multiple Jenkins jobs (build job → test job → deploy job), fingerprinting answers: "Which build job produced the artifact that the deploy job just deployed?"

### How fingerprinting works:

```
Build Job #42:
  Creates: my-app-1.0.jar
  Fingerprint: md5=abc123...
  Records: Job "build", Build #42 produced abc123

Test Job #15:
  Uses: my-app-1.0.jar
  Fingerprint: md5=abc123...
  Records: Job "test", Build #15 used abc123

Jenkins now knows: Build #42 → Test #15 (linked via fingerprint)
```

**View fingerprint:** In Jenkins, go to any build that archives a file → click the file → click "See Fingerprint"

**Use fingerprints to track deployments:**
```groovy
// Build job
archiveArtifacts artifacts: 'app.jar', fingerprint: true

// Deploy job - find which build produced this artifact
def fingerprint = readFile('app.jar.md5')
echo "Deploying artifact from: ${fingerprint}"
```

---

## 🗑️ Build Retention Policies

### `buildDiscarder` in the `options {}` block:

```groovy
options {
    buildDiscarder(logRotator(
        daysToKeepStr: '30',          // Delete builds older than 30 days
        numToKeepStr: '20',           // Keep at most 20 builds
        artifactDaysToKeepStr: '7',   // Delete artifacts older than 7 days
        artifactNumToKeepStr: '5'     // Keep artifacts for the 5 most recent builds
    ))
}
```

**Why retention matters:**
- Each build can store hundreds of MB of artifacts, logs, and test results
- Without retention, `$JENKINS_HOME` grows indefinitely
- Artifacts are often larger than logs — keep them for fewer builds

### Retention strategy examples:

**Development branch (short retention):**
```groovy
buildDiscarder(logRotator(daysToKeepStr: '7', numToKeepStr: '5'))
```

**Main branch (longer retention):**
```groovy
buildDiscarder(logRotator(daysToKeepStr: '90', numToKeepStr: '50'))
```

**Release branch (keep everything):**
```groovy
// Don't use buildDiscarder - keep all release builds for audit trails
```

---

## 🗄️ Stash and Unstash - Sharing Within a Pipeline

`archiveArtifacts` is for long-term storage. For sharing files between stages in the same pipeline run, use `stash`/`unstash`:

```groovy
stage('Build') {
    steps {
        sh 'npm run build'
        stash name: 'dist-files', includes: 'dist/**'
    }
}

stage('Test E2E') {
    agent { label 'e2e-agent' }   // Different machine!
    steps {
        unstash 'dist-files'      // Retrieve from the stash
        sh 'npm run test:e2e'
    }
}
```

**`stash` vs `archiveArtifacts`:**

| Feature | `stash/unstash` | `archiveArtifacts` |
|---|---|---|
| Purpose | Share within a single pipeline run | Long-term storage across builds |
| Accessible after pipeline | ❌ | ✅ |
| Cross-agent sharing | ✅ | ✅ |
| Downloadable from UI | ❌ | ✅ |
| Lifetime | Current pipeline run only | Controlled by buildDiscarder |

---

## 📋 Complete Artifact Management Example

```groovy
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(
            daysToKeepStr: '30',
            numToKeepStr: '20',
            artifactDaysToKeepStr: '7',
            artifactNumToKeepStr: '5'
        ))
    }

    stages {
        stage('Build') {
            steps {
                sh 'npm install && npm run build'
                stash name: 'dist', includes: 'dist/**'
            }
        }

        stage('Test') {
            parallel {
                stage('Unit Tests') {
                    steps {
                        sh 'npm test -- --reporter=junit --outputFile=unit-results.xml --coverage'
                    }
                    post {
                        always {
                            junit 'unit-results.xml'
                            publishHTML(target: [
                                reportDir: 'coverage/lcov-report',
                                reportFiles: 'index.html',
                                reportName: 'Unit Test Coverage'
                            ])
                        }
                    }
                }
            }
        }

        stage('Archive Artifacts') {
            steps {
                unstash 'dist'
                archiveArtifacts(
                    artifacts: 'dist/**,*.json',
                    fingerprint: true,
                    excludes: 'dist/**/*.map',
                    allowEmptyArchive: false
                )
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
```

---

## 🎯 Key Takeaways

1. **`archiveArtifacts`** saves build outputs persistently — downloadable from the Jenkins build page
2. **`fingerprint: true`** computes MD5 hashes for cross-job artifact traceability
3. **`junit`** parses XML test results and shows them as structured reports in Jenkins UI
4. **Run `junit` in `post { always }`** to capture results even when tests fail
5. **`publishHTML`** creates a tab in Jenkins UI for HTML reports (coverage, docs, performance)
6. **`buildDiscarder(logRotator(...))`** controls how long builds and artifacts are retained
7. **`stash/unstash`** shares files within a pipeline run; `archiveArtifacts` for long-term storage
8. **`artifactDaysToKeepStr/artifactNumToKeepStr`** separate from build retention (artifacts often use more disk)

---

*Good artifact management makes CI/CD pipelines observable: you can see what was built, how tests performed over time, and download any build's output. Combined with fingerprinting, you get end-to-end traceability from code commit to deployed artifact.*
