# Jenkinsfile Explanation - Parallel Stages and Matrix Scenario

This guide explains the `parallel {}` block for concurrent stage execution, the `matrix {}` directive for cross-platform testing, the `failFast` option, and how to optimize pipeline execution time.

---

## ⚡ The `parallel {}` Block

```groovy
stage('Parallel Tests') {
    parallel {
        stage('Unit Tests') {
            steps {
                sh 'npm test -- --testPathPattern=unit'
            }
        }
        stage('Integration Tests') {
            steps {
                sh 'npm test -- --testPathPattern=integration'
            }
        }
        stage('E2E Tests') {
            steps {
                sh 'npm run test:e2e'
            }
        }
    }
}
```

**What it is:** Runs multiple stages concurrently (at the same time) instead of sequentially.

**The time saving:**
```
Sequential:
  [Unit Tests: 3min] → [Integration: 5min] → [E2E: 4min] = 12 minutes total

Parallel:
  [Unit Tests: 3min]     ─┐
  [Integration: 5min]    ─┤ all running at the same time
  [E2E: 4min]            ─┘
  = 5 minutes total (time of the SLOWEST stage)
```

**Rules for parallel stages:**
- Each parallel branch needs its own agent executor to run truly concurrently
- If only one executor is available, stages will queue (still works, just not parallel)
- All parallel branches must complete before the next sequential stage begins
- If any branch fails, the remaining parallel branches continue by default (override with `failFast`)

---

## 🚀 `failFast: true` - Early Failure Detection

```groovy
stage('Parallel Tests') {
    failFast true    // Stop all parallel stages if ANY one fails
    parallel {
        stage('Unit Tests') {
            steps { sh 'npm test -- --testPathPattern=unit' }
        }
        stage('Integration Tests') {
            steps { sh 'npm test -- --testPathPattern=integration' }
        }
    }
}
```

**With `failFast true`:**
```
Unit Tests:         [Running] → [FAILED ❌] → pipeline aborts
Integration Tests:  [Running] → [ABORTED] ← stopped by failFast
Result: Pipeline fails immediately
```

**With `failFast false` (default):**
```
Unit Tests:         [Running] → [FAILED ❌]
Integration Tests:  [Running] → [Passes] → complete
Result: Pipeline fails after ALL parallel stages finish
```

**When to use `failFast true`:**
- When all tests share the same code version (one failure means the code is broken)
- When subsequent stages depend on all parallel stages passing
- When you want to save time and resources (no point completing remaining tests)

**When to use `failFast false` (default):**
- When you want full test results even if some fail (useful for debugging)
- When parallel stages test different features independently

---

## 🏭 Parallel Stages with Different Agents

```groovy
stage('Cross-Platform Build') {
    parallel {
        stage('Build Linux') {
            agent { label 'linux' }
            steps { sh 'make build-linux' }
        }
        stage('Build Windows') {
            agent { label 'windows' }
            steps { bat 'make build-windows' }
        }
        stage('Build macOS') {
            agent { label 'macos' }
            steps { sh 'make build-macos' }
        }
    }
}
```

Each parallel stage can declare its own `agent`, running on a completely different machine simultaneously.

---

## 📊 The `matrix {}` Directive

The `matrix` directive is designed specifically for running the same steps across multiple combinations of variables.

```groovy
stage('Test Matrix') {
    matrix {
        axes {
            axis {
                name: 'NODE_VERSION'
                values: '16', '18', '20'
            }
            axis {
                name: 'OS'
                values: 'ubuntu', 'centos'
            }
        }
        stages {
            stage('Test') {
                steps {
                    sh "node --version"
                    sh "npm test"
                }
            }
        }
    }
}
```

**What combinations this generates:**

| NODE_VERSION | OS | Stage Name |
|---|---|---|
| 16 | ubuntu | `Test (NODE_VERSION=16, OS=ubuntu)` |
| 16 | centos | `Test (NODE_VERSION=16, OS=centos)` |
| 18 | ubuntu | `Test (NODE_VERSION=18, OS=ubuntu)` |
| 18 | centos | `Test (NODE_VERSION=18, OS=centos)` |
| 20 | ubuntu | `Test (NODE_VERSION=20, OS=ubuntu)` |
| 20 | centos | `Test (NODE_VERSION=20, OS=centos)` |

3 Node versions × 2 OS = **6 parallel test jobs**, all running simultaneously.

**Inside the matrix stages, variables are automatically available:**
```groovy
stages {
    stage('Setup') {
        steps {
            echo "Testing Node ${NODE_VERSION} on ${OS}"
            sh "nvm use ${NODE_VERSION}"
        }
    }
    stage('Test') {
        steps {
            sh 'npm test'
        }
    }
}
```

---

## 🚫 The `excludes {}` Block

Not all matrix combinations are valid. Use `excludes` to skip specific combinations:

```groovy
matrix {
    axes {
        axis {
            name: 'PYTHON_VERSION'
            values: '3.9', '3.10', '3.11'
        }
        axis {
            name: 'FRAMEWORK'
            values: 'django', 'flask', 'fastapi'
        }
    }
    excludes {
        exclude {
            axis {
                name: 'PYTHON_VERSION'
                values: '3.9'  // Exclude 3.9 entirely
            }
            axis {
                name: 'FRAMEWORK'
                values: 'fastapi'  // from fastapi
            }
        }
    }
    stages {
        stage('Test') {
            steps { sh 'pytest' }
        }
    }
}
```

**This excludes:** `PYTHON_VERSION=3.9` AND `FRAMEWORK=fastapi` → reduces 9 to 8 combinations.

**Multiple excludes:**
```groovy
excludes {
    exclude {
        axis { name: 'OS'; values: 'windows' }
        axis { name: 'ARCH'; values: 'arm64' }
    }
    exclude {
        axis { name: 'NODE_VERSION'; values: '14' }
        axis { name: 'FRAMEWORK'; values: 'next14' }
    }
}
```

---

## 📦 Matrix with Agent Selection

```groovy
matrix {
    axes {
        axis {
            name: 'PLATFORM'
            values: 'linux', 'windows', 'macos'
        }
    }
    agent {
        label "${PLATFORM}-agent"   // Selects 'linux-agent', 'windows-agent', 'macos-agent'
    }
    stages {
        stage('Build') {
            steps {
                sh 'make build'
            }
        }
    }
}
```

---

## 🔀 `parallel {}` vs `matrix {}` - When to Use Which

| Feature | `parallel {}` | `matrix {}` |
|---|---|---|
| Use case | Different tasks running at the same time | Same task across multiple variable combinations |
| Configuration | Each branch is hand-written | Combinations generated automatically |
| Scalability | Manual (add more blocks) | Automatic (add more axis values) |
| Variable access | Not automatic | Variables from `axes` are automatically available |
| Excludes | Not supported | `excludes {}` block |
| Best for | Unit tests + integration + security scan | Cross-version testing, cross-platform builds |

**Use `parallel` when:** You have different types of work that can run concurrently.
**Use `matrix` when:** You have the same work that needs to run across multiple configurations.

---

## 🎯 Parallel Stages Best Practices

### 1. Ensure stages are truly independent
Parallel stages must NOT write to the same files or resources — they run simultaneously and will cause race conditions.
```groovy
// BAD - both stages write to the same file
parallel {
    stage('A') { steps { sh 'echo result >> output.txt' } }
    stage('B') { steps { sh 'echo result >> output.txt' } }
}

// GOOD - each stage uses its own workspace or temp file
parallel {
    stage('A') { steps { sh 'echo result > output-a.txt' } }
    stage('B') { steps { sh 'echo result > output-b.txt' } }
}
```

### 2. Use `stash` and `unstash` to share artifacts between stages
```groovy
stage('Build') {
    steps {
        sh 'npm run build'
        stash name: 'dist', includes: 'dist/**'   // Save for later
    }
}

stage('Parallel Tests') {
    parallel {
        stage('Unit Tests') {
            steps {
                unstash 'dist'   // Retrieve the built artifacts
                sh 'npm test'
            }
        }
        stage('E2E Tests') {
            steps {
                unstash 'dist'   // Each parallel stage gets its own copy
                sh 'npm run test:e2e'
            }
        }
    }
}
```

### 3. Collect test results from all parallel stages
```groovy
stage('Unit Tests') {
    steps {
        sh 'npm test -- --reporter=junit --outputFile=unit-results.xml'
    }
    post {
        always {
            junit 'unit-results.xml'   // Publish test results from this parallel branch
        }
    }
}
```

### 4. Limit concurrency with `throttle` plugin
```groovy
options {
    throttleJobProperty(
        maxConcurrentTotal: 5,       // No more than 5 parallel builds total
        throttleEnabled: true
    )
}
```

---

## 🕐 Visualizing Time Savings

### Example pipeline: 3 test suites

**Sequential (before parallelism):**
```
[Build: 2min] → [Unit: 4min] → [Integration: 8min] → [E2E: 6min] → [Deploy: 2min]
Total: 22 minutes
```

**With parallel tests:**
```
[Build: 2min] → [Unit: 4min]         ─┐
               → [Integration: 8min] ─┤ → [Deploy: 2min]
               → [E2E: 6min]         ─┘
Total: 2 + 8 + 2 = 12 minutes (45% faster!)
```

**Matrix with 3 Node versions:**
```
[Build: 2min] → [Test Node 16: 5min] ─┐
               → [Test Node 18: 5min] ─┤ → [Deploy: 2min]
               → [Test Node 20: 5min] ─┘
Total: 2 + 5 + 2 = 9 minutes (instead of 2+5+5+5+2 = 19 minutes sequential)
```

---

## 🎯 Key Takeaways

1. **`parallel {}`** runs different stages simultaneously — total time = slowest stage's duration
2. **`failFast true`** aborts all parallel stages the moment one fails (saves time when code is broken)
3. **`matrix {}`** generates all combinations of multiple `axis` values automatically
4. **`excludes {}`** skips invalid or unneeded matrix combinations
5. **Each parallel branch can have its own `agent`** — enabling truly distributed builds
6. **`stash/unstash`** shares build artifacts between parallel stages safely
7. **Independent stages are key** — parallel stages must not write to shared resources
8. **Parallel = different work at the same time; Matrix = same work across many configs**

---

*Parallelism is one of the most impactful optimizations you can add to a slow Jenkins pipeline. A 20-minute sequential test suite can become a 5-minute parallel one — making developers iterate faster and ship more confidently.*
