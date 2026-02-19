# Jenkinsfile Explanation - Docker Build and Push Scenario

This guide explains the Jenkinsfile patterns for building Docker images, tagging strategies, pushing to registries, multi-stage Dockerfiles, and different Docker-in-Jenkins execution strategies.

---

## 🐳 Dockerfile Structure in CI/CD

Before looking at the Jenkinsfile, let's understand the Dockerfile being built.

### Multi-stage Dockerfile (best practice):

```dockerfile
# Stage 1: Builder - has all build tools
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Stage 2: Production image - only runtime artifacts
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Why multi-stage?**
- Builder image has npm, compilers, dev dependencies → large (~800MB)
- Production image only has the compiled output + nginx → small (~25MB)
- Security: build tools and source code don't ship to production
- Jenkins builds the full Dockerfile, but only the final stage is pushed

---

## 🏗️ Docker Build Step

```groovy
stage('Docker Build') {
    steps {
        sh """
            docker build \
              --tag ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} \
              --tag ${REGISTRY}/${APP_NAME}:latest \
              --label "build.number=${BUILD_NUMBER}" \
              --label "build.url=${BUILD_URL}" \
              --label "git.commit=${GIT_COMMIT}" \
              --file Dockerfile \
              .
        """
    }
}
```

### `docker build` flags:

| Flag | Description |
|---|---|
| `--tag` / `-t` | Image name and tag. Use multiple `-t` flags for multiple tags |
| `--label` | Add metadata to the image (inspectable later) |
| `--file` / `-f` | Specify a Dockerfile path (default: `./Dockerfile`) |
| `--build-arg` | Pass build arguments to the Dockerfile |
| `--no-cache` | Don't use the Docker build cache |
| `--platform` | Build for a specific OS/arch (e.g., `linux/amd64`) |
| `.` | Build context: the directory Docker sends to the daemon |

### Build args for CI metadata:
```groovy
sh """
    docker build \
      --build-arg APP_VERSION=${BUILD_NUMBER} \
      --build-arg GIT_SHA=${GIT_COMMIT[0..7]} \
      -t ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} \
      .
"""
```

In the Dockerfile:
```dockerfile
ARG APP_VERSION
ARG GIT_SHA
ENV APP_VERSION=${APP_VERSION}
LABEL git.sha=${GIT_SHA}
```

---

## 🏷️ Image Tagging Strategy

```groovy
environment {
    REGISTRY   = 'registry.company.com'
    APP_NAME   = 'my-web-app'
    IMAGE_TAG  = "${BUILD_NUMBER}"    // Unique per build
}
```

### Why `BUILD_NUMBER` as the tag?

| Tag strategy | Example | Pros | Cons |
|---|---|---|---|
| `BUILD_NUMBER` | `app:42` | Unique, traceable to CI build | Not human-readable |
| `GIT_COMMIT` | `app:abc1234` | Traceable to exact commit | Long, not sequential |
| `latest` | `app:latest` | Convenient | Not reproducible — changes meaning |
| Semantic version | `app:v1.2.3` | Human-readable, meaningful | Requires version management |
| Branch + build | `app:main-42` | Branch context | Longer tag |
| Date + build | `app:20240115-42` | Human-readable date | Not always useful |

**Best practice for production:** Tag with both `BUILD_NUMBER` (for traceability) AND the semantic version:
```groovy
sh "docker build -t ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} -t ${REGISTRY}/${APP_NAME}:${APP_VERSION} ."
```

**Why never use `latest` alone in CI?**
- `latest` is mutable — `docker pull my-app:latest` today may give a different image than tomorrow
- Makes rollbacks impossible (which `latest` was the good one?)
- Pin `latest` as an additional convenience tag, never as the primary tag

---

## 🔐 Docker Registry Login

```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-registry-creds',
    usernameVariable: 'REGISTRY_USER',
    passwordVariable: 'REGISTRY_PASS'
)]) {
    sh "docker login ${REGISTRY} -u ${REGISTRY_USER} -p ${REGISTRY_PASS}"
    sh "docker push ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER}"
}
```

**Why `withCredentials` for Docker login?**
- `docker login` writes credentials to `~/.docker/config.json` on the Jenkins agent
- `withCredentials` ensures the password never appears in the console log (masked as `****`)
- The block's scope prevents the variable from leaking to other steps

**Alternative: `--password-stdin` (more secure):**
```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-registry-creds',
    usernameVariable: 'REGISTRY_USER',
    passwordVariable: 'REGISTRY_PASS'
)]) {
    sh "echo ${REGISTRY_PASS} | docker login ${REGISTRY} -u ${REGISTRY_USER} --password-stdin"
}
```
`--password-stdin` reads the password from stdin instead of a command-line argument, preventing it from appearing in process lists (`ps aux`).

---

## 🚀 Docker Push

```groovy
sh "docker push ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER}"
sh "docker push ${REGISTRY}/${APP_NAME}:latest"   // Optional: also push latest tag
```

**Push multiple tags at once:**
```groovy
sh """
    docker push ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER}
    docker push ${REGISTRY}/${APP_NAME}:latest
"""
```

**Or use a loop:**
```groovy
script {
    def tags = [BUILD_NUMBER, 'latest', GIT_COMMIT[0..7]]
    tags.each { tag ->
        sh "docker push ${REGISTRY}/${APP_NAME}:${tag}"
    }
}
```

---

## 🧹 Post-Build Cleanup

```groovy
post {
    always {
        sh "docker rmi ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} || true"
        sh "docker rmi ${REGISTRY}/${APP_NAME}:latest || true"
        cleanWs()
    }
}
```

**Why clean up Docker images?**
- Jenkins agents have limited disk space
- Docker images can be hundreds of MB each
- Multiple builds per day × multiple agents = disk full quickly
- `|| true` prevents the cleanup command from failing the build if the image doesn't exist

**More aggressive cleanup:**
```groovy
sh "docker system prune -f"          // Remove stopped containers, unused images
sh "docker image prune -f"           // Remove dangling (untagged) images
sh "docker image prune -a -f"        // Remove ALL unused images (aggressive)
```

---

## 🔄 Docker Build Strategies in Jenkins

There are three main ways to build Docker images in a Jenkins pipeline:

### Strategy 1: Docker socket (DooD - Docker Outside of Docker)

```groovy
agent {
    docker {
        image 'docker:24-dind'
        args '-v /var/run/docker.sock:/var/run/docker.sock'
    }
}
```

**How it works:** Mounts the host's Docker socket into the container, so `docker build` inside the container actually runs on the host's Docker daemon.

| Pros | Cons |
|---|---|
| Fast (uses host cache) | Security risk (full Docker access = root on host) |
| Simple setup | Container escapes are possible |
| Shares image cache across builds | Not suitable for multi-tenant environments |

### Strategy 2: Docker-in-Docker (DinD)

```groovy
agent {
    kubernetes {
        yaml '''
        spec:
          containers:
          - name: dind
            image: docker:24-dind
            securityContext:
              privileged: true    ← Requires privileged mode
        '''
    }
}
```

**How it works:** Runs a complete Docker daemon inside a container. The Jenkins agent communicates with this inner daemon.

| Pros | Cons |
|---|---|
| Isolated from host Docker | Requires privileged containers |
| Better security than DooD | Slower (no shared cache) |
| Standard in Kubernetes environments | Complex setup |

### Strategy 3: Kaniko (no Docker daemon)

```groovy
agent {
    kubernetes {
        yaml '''
        spec:
          containers:
          - name: kaniko
            image: gcr.io/kaniko-project/executor:latest
            command: ['/busybox/sh', '-c', 'cat']
            tty: true
        '''
    }
}

steps {
    container('kaniko') {
        sh """
            /kaniko/executor \
              --context . \
              --dockerfile Dockerfile \
              --destination ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} \
              --destination ${REGISTRY}/${APP_NAME}:latest
        """
    }
}
```

**How it works:** Builds Docker images in userspace without a Docker daemon, by directly manipulating container filesystem layers.

| Pros | Cons |
|---|---|
| No Docker daemon needed | No build cache by default (can be configured) |
| No privileged containers | Slower than Docker build |
| Cloud-native, Kubernetes-friendly | Different syntax for advanced Dockerfile features |
| Recommended for Kubernetes CI/CD | Less mature tooling |

**For this scenario:** We use the DooD approach (simplest for learning).

---

## 🔒 Docker Image Labels as Metadata

Labels bake metadata into images, making them traceable after deployment:

```dockerfile
LABEL maintainer="platform-team@company.com"
LABEL version="${APP_VERSION}"
LABEL build.number="${BUILD_NUMBER}"
```

Or set during `docker build`:
```groovy
sh """
    docker build \
      --label "maintainer=platform-team@company.com" \
      --label "build.number=${BUILD_NUMBER}" \
      --label "build.url=${BUILD_URL}" \
      --label "git.commit=${GIT_COMMIT}" \
      --label "git.branch=${BRANCH_NAME}" \
      -t ${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} \
      .
"""
```

**Inspect labels:**
```bash
docker inspect my-app:42 | jq '.[0].Config.Labels'
```

Output:
```json
{
    "build.number": "42",
    "build.url": "https://jenkins.company.com/job/my-app/42/",
    "git.commit": "abc1234",
    "git.branch": "main"
}
```

---

## 📊 Complete Docker Pipeline Example

```groovy
pipeline {
    agent any

    environment {
        REGISTRY    = 'registry.company.com'
        APP_NAME    = 'my-web-app'
        BUILD_TAG   = "${BUILD_NUMBER}"
        FULL_IMAGE  = "${REGISTRY}/${APP_NAME}:${BUILD_TAG}"
    }

    stages {
        stage('Build') {
            steps {
                sh """
                    docker build \
                      --tag ${FULL_IMAGE} \
                      --tag ${REGISTRY}/${APP_NAME}:latest \
                      --label build.number=${BUILD_NUMBER} \
                      --label git.commit=${GIT_COMMIT} \
                      .
                """
            }
        }

        stage('Test Image') {
            steps {
                sh """
                    docker run --rm \
                      -e NODE_ENV=test \
                      ${FULL_IMAGE} \
                      npm test
                """
            }
        }

        stage('Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'docker-registry-creds',
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh "echo ${REG_PASS} | docker login ${REGISTRY} -u ${REG_USER} --password-stdin"
                    sh "docker push ${FULL_IMAGE}"
                    sh "docker push ${REGISTRY}/${APP_NAME}:latest"
                }
            }
        }
    }

    post {
        always {
            sh "docker rmi ${FULL_IMAGE} || true"
            sh "docker rmi ${REGISTRY}/${APP_NAME}:latest || true"
            cleanWs()
        }
    }
}
```

---

## 🎯 Key Takeaways

1. **Multi-stage Dockerfiles** produce small production images by separating build and runtime stages
2. **`BUILD_NUMBER` as the image tag** ensures each build produces a unique, traceable image
3. **Never use `:latest` as the only tag** — it's mutable and makes rollbacks impossible
4. **`withCredentials` for `docker login`** masks the password in Jenkins console logs
5. **`--password-stdin`** is more secure than passing `-p ${PASS}` on the command line
6. **`docker rmi` in `post { always }`** prevents disk exhaustion on Jenkins agents
7. **Three Docker strategies:** DooD (simple, less secure), DinD (isolated, privileged), Kaniko (daemonless, Kubernetes-native)
8. **Image labels** bake build metadata into the image for traceability after deployment

---

*Docker image management in CI/CD is about reproducibility (unique tags), security (credential handling), efficiency (cleanup), and traceability (labels). Get these right and your image pipeline will be reliable at scale.*
