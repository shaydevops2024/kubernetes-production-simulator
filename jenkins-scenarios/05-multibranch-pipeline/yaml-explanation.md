# Jenkinsfile Explanation - Multibranch Pipeline Scenario

This guide explains multibranch pipeline configuration, branch-based `when {}` conditions, automatic branch discovery, and per-branch deployment strategies.

---

## 🌿 What is a Multibranch Pipeline?

A **Multibranch Pipeline** is a special Jenkins job type that:
1. **Scans** a Git repository for branches and pull requests
2. **Automatically creates** a separate pipeline job for each branch containing a Jenkinsfile
3. **Deletes** the pipeline job when the branch is deleted
4. **Runs** the pipeline whenever that branch receives a new commit

**Single Pipeline vs Multibranch:**

| Single Pipeline | Multibranch Pipeline |
|---|---|
| One job, one branch | One job per branch |
| Manual branch configuration | Automatic branch discovery |
| No PR support | PR validation built-in |
| Requires Jenkinsfile parameter | Uses Jenkinsfile from each branch |

---

## 🌿 Branch-Based `when {}` Conditions

### `when { branch '...' }` - The Core Pattern

```groovy
stage('Deploy to Production') {
    when {
        branch 'main'
    }
    steps {
        sh "kubectl apply -f k8s/production/"
    }
}
```

**What it does:** This stage only runs when the pipeline is executing on the `main` branch. On any other branch, it is skipped (shown as gray in Jenkins UI).

**Branch matching options:**

```groovy
// Exact match
when { branch 'main' }
when { branch 'develop' }

// Wildcard - any branch starting with 'release/'
when { branch 'release/*' }
when { branch 'feature/*' }

// Regex matching
when { branch pattern: 'release/v\\d+\\.\\d+', comparator: 'REGEXP' }

// Negation - everything except main
when { not { branch 'main' } }
```

---

## 🔀 Pull Request Variables

In a Multibranch Pipeline, when Jenkins builds a Pull Request, special variables are available:

| Variable | Value | When available |
|---|---|---|
| `BRANCH_NAME` | Branch name (e.g., `feature/login` or `PR-42`) | Always |
| `CHANGE_ID` | PR number (e.g., `42`) | PR builds only |
| `CHANGE_TARGET` | Target branch (e.g., `main`) | PR builds only |
| `CHANGE_AUTHOR` | Git username of the PR author | PR builds only |
| `CHANGE_TITLE` | PR title | PR builds only |
| `CHANGE_URL` | URL to the PR on GitHub/GitLab | PR builds only |

**How to detect if this is a PR build:**
```groovy
when {
    expression { env.CHANGE_ID != null }   // True if it's a PR
}
```

**PR validation stage example:**
```groovy
stage('PR Checks') {
    when {
        expression { env.CHANGE_ID != null }  // Only for PRs
    }
    steps {
        echo "Validating PR #${CHANGE_ID}: ${CHANGE_TITLE}"
        echo "Merging into: ${CHANGE_TARGET}"
        sh 'npm test -- --coverage'
        sh 'npm run lint'
    }
}
```

---

## 📐 Branching Strategy Patterns

### Gitflow-style branching:

```groovy
pipeline {
    agent any

    stages {
        stage('Build') {
            steps { sh 'make build' }
        }

        stage('Unit Tests') {
            steps { sh 'make test' }
        }

        stage('Deploy Dev') {
            when { branch 'develop' }
            steps {
                sh 'kubectl apply -f k8s/dev/'
            }
        }

        stage('Deploy Staging') {
            when { branch 'release/*' }
            steps {
                sh 'kubectl apply -f k8s/staging/'
            }
        }

        stage('Deploy Production') {
            when { branch 'main' }
            steps {
                sh 'kubectl apply -f k8s/production/'
            }
        }

        stage('Feature Branch Validation') {
            when {
                allOf {
                    not { branch 'main' }
                    not { branch 'develop' }
                    not { branch 'release/*' }
                }
            }
            steps {
                echo "Feature branch validation only - no deploy"
                sh 'make lint'
            }
        }
    }
}
```

**Branch → Stage mapping:**
```
main          → Build → Test → Deploy Production
develop       → Build → Test → Deploy Dev
release/*     → Build → Test → Deploy Staging
feature/*     → Build → Test → Validate only
PR-*          → Build → Test → PR Checks only
```

---

## 📊 The `BRANCH_NAME` Variable

`BRANCH_NAME` is the most important multibranch variable. It's always set to the current branch being built.

```groovy
environment {
    // Use branch name in image tag for traceability
    IMAGE_TAG = "${BRANCH_NAME}-${BUILD_NUMBER}"
    // Example: "feature-login-42" or "main-100"
}
```

**Sanitizing branch names for Docker tags** (branch names can contain `/` which Docker doesn't allow):
```groovy
script {
    // Replace slashes and other invalid chars
    def sanitizedBranch = BRANCH_NAME.replaceAll('[^a-zA-Z0-9_.-]', '-')
    env.SAFE_TAG = "${sanitizedBranch}-${BUILD_NUMBER}"
}
```
`feature/login-page` → `feature-login-page-42`

---

## 🔍 Branch Discovery Configuration

In the Jenkins UI, a Multibranch Pipeline is configured with:

### Branch sources:
- GitHub
- GitLab
- Bitbucket
- Generic Git

### Branch discovery strategies:
- **All branches** - Build every branch
- **Branches not filed as a PR** - Ignore branches that have open PRs (avoids double builds)
- **Only branches that are also filed as a PR** - Build only PRs

### Build strategies:
- **Regular branches** - Build commits on any branch
- **Pull Requests** - Build PR branches (using a merge commit or the PR head)
- **Tags** - Build git tags

### Scan triggers:
```
Scan interval: 1 minute / 5 minutes / 1 hour
Webhook: GitHub/GitLab webhook → instant discovery
```

---

## 🎯 Per-Environment Deployment Pattern

### Directory structure in the repo:
```
k8s/
├── dev/
│   ├── deployment.yaml    # replicas: 1, image: app:dev-latest
│   └── configmap.yaml     # DB_HOST: dev-db.internal
├── staging/
│   ├── deployment.yaml    # replicas: 2, image: app:staging-latest
│   └── configmap.yaml     # DB_HOST: staging-db.internal
└── production/
    ├── deployment.yaml    # replicas: 5, image: app:v1.0.0
    └── configmap.yaml     # DB_HOST: prod-db.internal
```

### Jenkinsfile that uses this structure:
```groovy
stage('Deploy') {
    when {
        anyOf {
            branch 'main'
            branch 'develop'
            branch 'release/*'
        }
    }
    steps {
        script {
            def targetEnv
            if (BRANCH_NAME == 'main') {
                targetEnv = 'production'
            } else if (BRANCH_NAME == 'develop') {
                targetEnv = 'dev'
            } else if (BRANCH_NAME.startsWith('release/')) {
                targetEnv = 'staging'
            }
            sh "kubectl apply -f k8s/${targetEnv}/"
        }
    }
}
```

---

## 🏷️ Tag-Based Releases

Multibranch pipelines also discover git tags:

```groovy
stage('Publish Release') {
    when { tag 'v*' }    // Only runs on tags like v1.0.0, v2.1.3
    steps {
        echo "Publishing release: ${TAG_NAME}"
        sh """
            docker tag my-app:${BUILD_NUMBER} my-app:${TAG_NAME}
            docker push my-app:${TAG_NAME}
            docker push my-app:latest
        """
    }
}
```

**Available tag variables:**

| Variable | Value |
|---|---|
| `TAG_NAME` | The tag name (e.g., `v1.0.0`) |
| `TAG_TIMESTAMP` | When the tag was created |

---

## 🔔 PR Comment Integration

With the GitHub Branch Source or GitLab Branch Source plugin, Jenkins can post build results back to the PR:

```groovy
post {
    success {
        githubNotify(
            description: 'CI passed',
            status: 'SUCCESS',
            context: 'jenkins/pipeline'
        )
    }
    failure {
        githubNotify(
            description: 'CI failed',
            status: 'FAILURE',
            context: 'jenkins/pipeline'
        )
    }
}
```

This creates a green/red check mark on the GitHub PR, enabling **branch protection rules** that block merging if CI fails.

---

## 🗑️ Automatic Stale Branch Cleanup

Configure Jenkins to automatically remove pipeline jobs for deleted branches:

In Jenkins Multibranch Pipeline configuration:
- **Orphaned Item Strategy**: `Discard old items`
- **Days to keep old items**: `7`
- **Max # of old items to keep**: `10`

Or in Jenkinsfile with the `properties()` step:
```groovy
properties([
    buildDiscarder(logRotator(
        daysToKeepStr: '30',        // Keep build history 30 days
        numToKeepStr: '20'          // Keep last 20 builds per branch
    ))
])
```

---

## ✅ Multibranch Pipeline Best Practices

### 1. Protect `main` and `release` branches
In GitHub: Settings → Branches → Add rule:
- Required status checks: Jenkins CI
- Require PR before merging
- No direct pushes

### 2. Use different replica counts per environment
```yaml
# k8s/dev/deployment.yaml
spec:
  replicas: 1    # Save resources in dev

# k8s/production/deployment.yaml
spec:
  replicas: 5    # High availability in production
```

### 3. Add PR validation for code quality
```groovy
stage('PR Validation') {
    when { expression { env.CHANGE_ID != null } }
    steps {
        sh 'npm run lint'
        sh 'npm test -- --coverage --coverageThreshold=\'{"global":{"lines":80}}\''
    }
}
```

### 4. Use different timeouts per branch
```groovy
stage('Integration Tests') {
    options {
        timeout(time: BRANCH_NAME == 'main' ? 30 : 10, unit: 'MINUTES')
    }
    steps { sh 'make test:integration' }
}
```

### 5. Notify on production deployments only
```groovy
post {
    success {
        script {
            if (BRANCH_NAME == 'main') {
                slackSend(message: "🚀 Production deployed: ${BUILD_URL}")
            }
        }
    }
}
```

---

## 🎯 Key Takeaways

1. **Multibranch Pipelines** auto-discover branches and create/delete jobs automatically
2. **`when { branch 'main' }`** gates deployment stages to specific branches
3. **`BRANCH_NAME`** is always available; `CHANGE_ID` is only set for PR builds
4. **`CHANGE_TARGET`** tells you which branch the PR targets — useful for validation
5. **`when { branch 'release/*' }`** uses wildcards to match branch name patterns
6. **`when { tag 'v*' }`** enables tag-based release pipelines
7. **`allOf` / `anyOf`** combine branch conditions for complex routing logic
8. **GitHub/GitLab status checks** from Jenkins enable branch protection rules

---

*Multibranch pipelines are the right choice for any team practicing trunk-based development or GitFlow. They enforce that every branch has a pipeline and that production is only deployed from protected branches.*
