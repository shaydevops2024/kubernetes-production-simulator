# Jenkinsfile Explanation - Shared Library Scenario

This guide explains Jenkins Shared Libraries: how they're structured, how to write reusable pipeline steps in the `vars/` directory, how to use Groovy helper classes in `src/`, and how to import and version libraries.

---

## 📚 What is a Jenkins Shared Library?

A **Shared Library** is a Git repository containing reusable Groovy code that multiple pipelines can import. Instead of copying the same pipeline logic into every Jenkinsfile, you write it once in the library and reference it by name.

**Without shared library:**
```groovy
// Jenkinsfile in project A
pipeline {
    stages {
        stage('Docker Build') {
            steps {
                sh "docker build -t ${IMAGE} ."
                withCredentials([...]) {
                    sh "docker login && docker push ${IMAGE}"
                }
            }
        }
    }
}

// Jenkinsfile in project B - same code duplicated!
pipeline {
    stages {
        stage('Docker Build') {
            steps {
                sh "docker build -t ${IMAGE} ."
                withCredentials([...]) {
                    sh "docker login && docker push ${IMAGE}"
                }
            }
        }
    }
}
```

**With shared library:**
```groovy
// In shared library: vars/dockerBuildAndPush.groovy
// In project A's Jenkinsfile:
@Library('jenkins-shared-lib') _
pipeline {
    stages {
        stage('Docker Build') {
            steps {
                dockerBuildAndPush(image: 'project-a', tag: BUILD_NUMBER)
            }
        }
    }
}

// In project B's Jenkinsfile:
@Library('jenkins-shared-lib') _
pipeline {
    stages {
        stage('Docker Build') {
            steps {
                dockerBuildAndPush(image: 'project-b', tag: BUILD_NUMBER)
            }
        }
    }
}
```

---

## 📁 Shared Library Directory Structure

```
jenkins-shared-lib/                    ← Git repository root
├── vars/                              ← Global variables/steps (most used)
│   ├── dockerBuildAndPush.groovy      ← Custom step: dockerBuildAndPush(...)
│   ├── deployToKubernetes.groovy      ← Custom step: deployToKubernetes(...)
│   ├── notifySlack.groovy             ← Custom step: notifySlack(...)
│   └── runTests.groovy                ← Custom step: runTests(...)
├── src/                               ← Groovy classes (for complex logic)
│   └── com/
│       └── company/
│           └── pipeline/
│               ├── Docker.groovy      ← Helper class
│               └── Kubernetes.groovy  ← Helper class
├── resources/                         ← Non-Groovy files (scripts, templates)
│   ├── scripts/
│   │   └── deploy.sh
│   └── templates/
│       └── deployment.yaml.template
└── README.md
```

**Key rules:**
- `vars/` → Files become callable pipeline steps (filename = step name)
- `src/` → Groovy classes, imported like regular Java/Groovy classes
- `resources/` → Non-code files accessible via `libraryResource()`

---

## 🔧 The `vars/` Directory - Custom Steps

Each `.groovy` file in `vars/` becomes a callable pipeline step with the same name as the file.

### Basic `vars/` step:

**`vars/dockerBuildAndPush.groovy`:**
```groovy
def call(Map config = [:]) {
    // config is a map of named parameters
    def image    = config.image    ?: error('image is required')
    def tag      = config.tag      ?: 'latest'
    def registry = config.registry ?: 'docker.io'

    // Use env for credentials from Jenkins store
    withCredentials([usernamePassword(
        credentialsId: 'docker-registry-creds',
        usernameVariable: 'DOCKER_USER',
        passwordVariable: 'DOCKER_PASS'
    )]) {
        sh "docker build -t ${registry}/${image}:${tag} ."
        sh "docker login ${registry} -u ${DOCKER_USER} -p ${DOCKER_PASS}"
        sh "docker push ${registry}/${image}:${tag}"
    }
}
```

**Usage in Jenkinsfile:**
```groovy
dockerBuildAndPush(
    image: 'my-web-app',
    tag: BUILD_NUMBER,
    registry: 'registry.company.com'
)
```

### Calling `def call()` - The convention:
- The function MUST be named `call`
- `Map config = [:]` accepts named parameters as a map
- `config.key ?: 'default'` uses Groovy's Elvis operator for defaults

### Step with multiple signatures:

```groovy
// Call with a string
def call(String message) {
    slackSend(message: message, channel: '#builds')
}

// Or call with a map
def call(Map config) {
    slackSend(
        message: config.message,
        channel: config.channel ?: '#builds',
        color: config.color ?: 'good'
    )
}
```

---

## 📦 The `src/` Directory - Groovy Classes

For complex logic that spans multiple functions, use Groovy classes in `src/`.

**`src/com/company/pipeline/Docker.groovy`:**
```groovy
package com.company.pipeline

class Docker implements Serializable {
    // IMPORTANT: Must implement Serializable for Jenkins pipeline compatibility

    private def script    // Reference to the pipeline script (for sh, echo, etc.)
    private String registry

    Docker(def script, String registry = 'docker.io') {
        this.script = script
        this.registry = registry
    }

    def build(String image, String tag) {
        script.sh "docker build -t ${registry}/${image}:${tag} ."
    }

    def push(String image, String tag) {
        script.sh "docker push ${registry}/${image}:${tag}"
    }

    def buildAndPush(String image, String tag) {
        build(image, tag)
        push(image, tag)
    }
}
```

**Usage in Jenkinsfile (with import):**
```groovy
@Library('jenkins-shared-lib') _
import com.company.pipeline.Docker

pipeline {
    stages {
        stage('Build') {
            steps {
                script {
                    def docker = new Docker(this, 'registry.company.com')
                    docker.buildAndPush('my-app', BUILD_NUMBER)
                }
            }
        }
    }
}
```

**Why `implements Serializable`?**
Jenkins pipelines are durable — they can survive Jenkins restarts and resume. To do this, Jenkins serializes (saves) the pipeline state to disk. Any object held by the pipeline must be serializable. Without it, you get: `java.io.NotSerializableException`.

**Why pass `script` (or `this`) to the class?**
Groovy classes in `src/` don't have direct access to pipeline DSL methods (`sh`, `echo`, `withCredentials`, etc.). You must pass a reference to the pipeline context:
```groovy
class MyHelper implements Serializable {
    def script   // 'this' from the pipeline
    MyHelper(def script) { this.script = script }

    def runCommand(String cmd) {
        script.sh cmd   // Uses the pipeline's sh step
    }
}
```

---

## 📌 The `@Library()` Annotation

### Loading a library by name:
```groovy
@Library('jenkins-shared-lib') _
```

The `_` after the annotation is a Groovy convention — it's a placeholder import that tells Groovy "load this library into scope." Without it, the annotation would be a compile error.

### Loading a specific version/branch/tag:
```groovy
// Use a specific git branch
@Library('jenkins-shared-lib@develop') _

// Use a specific git tag
@Library('jenkins-shared-lib@v2.1.0') _

// Use a specific git commit SHA
@Library('jenkins-shared-lib@abc1234') _
```

**Why version pinning matters:**
- Without pinning (`@Library('lib') _`), you get the latest version automatically
- This can break pipelines if the library changes
- Pin to a tag for production pipelines: `@Library('jenkins-shared-lib@v2.1.0') _`

### Loading multiple libraries:
```groovy
@Library(['jenkins-shared-lib', 'company-utils@v1.0']) _
```

### Dynamic loading inside the pipeline:
```groovy
pipeline {
    stages {
        stage('Load Lib') {
            steps {
                script {
                    def lib = library(
                        identifier: 'jenkins-shared-lib@main',
                        retriever: modernSCM([
                            $class: 'GitSCMSource',
                            remote: 'https://github.com/company/jenkins-shared-lib.git'
                        ])
                    )
                }
            }
        }
    }
}
```

---

## ⚙️ Configuring Libraries in Jenkins

Libraries must be registered in Jenkins before they can be used.

**Global configuration:**
`Manage Jenkins` → `Configure System` → `Global Pipeline Libraries` → Add:
- **Name:** `jenkins-shared-lib` (this is what `@Library('...')` references)
- **Default version:** `main` (branch, tag, or commit SHA)
- **Retrieval method:** Modern SCM
- **Source:** Git → `https://github.com/company/jenkins-shared-lib.git`
- **Allow default version to be overridden:** ✅ (enables `@Library('lib@v2.0')`)
- **Load implicitly:** ✅ (makes the library available in all pipelines without `@Library`)

---

## 📄 The `resources/` Directory

For non-Groovy files (shell scripts, YAML templates, JSON configs):

```
resources/
├── scripts/
│   └── health-check.sh
└── templates/
    └── k8s-deployment.yaml.template
```

**Access in pipeline:**
```groovy
// In vars/deployToKubernetes.groovy
def call(Map config) {
    // Load a script from resources/
    def script = libraryResource('scripts/health-check.sh')
    writeFile file: 'health-check.sh', text: script
    sh 'chmod +x health-check.sh && ./health-check.sh'

    // Load a template and fill in values
    def template = libraryResource('templates/k8s-deployment.yaml.template')
    def rendered = template
        .replace('{{IMAGE}}', config.image)
        .replace('{{REPLICAS}}', config.replicas.toString())
    writeFile file: 'deployment.yaml', text: rendered
    sh 'kubectl apply -f deployment.yaml'
}
```

---

## 🔄 Shared Library Step Examples

### `vars/deployToKubernetes.groovy`:
```groovy
def call(Map config = [:]) {
    def namespace  = config.namespace  ?: 'default'
    def deployment = config.deployment ?: error('deployment name required')
    def image      = config.image      ?: error('image required')
    def timeout    = config.timeout    ?: '120s'

    sh """
        kubectl set image deployment/${deployment} \
          app=${image} \
          -n ${namespace}
        kubectl rollout status deployment/${deployment} \
          -n ${namespace} \
          --timeout=${timeout}
    """
}
```

**Usage:**
```groovy
deployToKubernetes(
    namespace: 'production',
    deployment: 'my-web-app',
    image: "registry.company.com/my-web-app:${BUILD_NUMBER}",
    timeout: '180s'
)
```

### `vars/notifySlack.groovy`:
```groovy
def call(String status, String channel = '#deployments') {
    def color = status == 'SUCCESS' ? 'good' : 'danger'
    def emoji = status == 'SUCCESS' ? '✅' : '❌'
    slackSend(
        channel: channel,
        color: color,
        message: "${emoji} *${env.JOB_NAME}* #${env.BUILD_NUMBER}: ${status}\n${env.BUILD_URL}"
    )
}
```

**Usage:**
```groovy
post {
    success { notifySlack('SUCCESS') }
    failure { notifySlack('FAILURE', '#alerts') }
}
```

---

## 🎯 Key Takeaways

1. **Shared Libraries** eliminate copy-paste by centralizing pipeline logic in a Git repo
2. **`vars/`** files become callable pipeline steps — file name = step name
3. **`def call(Map config = [:])`** is the standard pattern for accepting named parameters
4. **`src/`** contains Groovy classes for complex, reusable logic
5. **Classes MUST implement `Serializable`** to be compatible with Jenkins' durability model
6. **Pass `this`** (pipeline context) to `src/` classes to access `sh`, `echo`, etc.
7. **`@Library('name@version') _`** loads the library — always pin to a tag in production
8. **`resources/`** holds non-Groovy files accessible via `libraryResource()`
9. **Register libraries** in `Manage Jenkins → Configure System → Global Pipeline Libraries`

---

*Shared libraries are what separate hobby Jenkins setups from enterprise-grade CI/CD platforms. They enforce consistency, reduce maintenance burden, and let platform teams govern pipeline standards centrally.*
