# GitLab CI YAML Explanation - Pipeline Fundamentals

This guide explains the YAML files used in this scenario: the `.gitlab-ci.yml` pipeline structure and the Kubernetes `deployment.yaml` that the pipeline deploys.

---

## The .gitlab-ci.yml — Pipeline Definition

The `.gitlab-ci.yml` file is the single source of truth for your CI/CD pipeline. It lives at the repository root and GitLab reads it automatically on every push.

```yaml
stages:
  - lint
  - test
  - build
  - deploy

variables:
  IMAGE_NAME: myapp
  REGISTRY: registry.gitlab.com/mygroup/myapp

lint-yaml:
  stage: lint
  image: python:3.11-slim
  script:
    - pip install yamllint
    - yamllint .gitlab-ci.yml

unit-tests:
  stage: test
  image: python:3.11
  before_script:
    - pip install -r requirements.txt
  script:
    - pytest tests/ -v
  artifacts:
    paths:
      - coverage/
    expire_in: 1 week

build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $REGISTRY:$CI_COMMIT_SHA .
    - docker push $REGISTRY:$CI_COMMIT_SHA

deploy-staging:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl apply -f deployment.yaml
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

---

## Field-by-Field Breakdown

### stages

```yaml
stages:
  - lint
  - test
  - build
  - deploy
```

Defines the **ordered list of stages**. Stages run top-to-bottom. All jobs within the same stage run in parallel. If any job in a stage fails, the pipeline stops — jobs in later stages never run. This creates quality gates: linting failures stop tests from running, which saves CI minutes.

### variables (top-level)

```yaml
variables:
  IMAGE_NAME: myapp
  REGISTRY: registry.gitlab.com/mygroup/myapp
```

Top-level `variables` are available to **every job** in the pipeline. Use them for non-sensitive configuration. Secrets should never go here — they get committed to Git. Use the GitLab UI (Settings > CI/CD > Variables) for anything sensitive.

### image

```yaml
image: python:3.11
```

The Docker image that runs the job. GitLab Runner pulls this image and executes all scripts inside a container. Every job can use a different image, letting you run your tests in Python, your build in Docker, and your deploy in a kubectl image — all in the same pipeline.

### stage

```yaml
stage: test
```

Assigns the job to a stage. Jobs without a `stage` field default to the `test` stage. The job runs when its stage's turn comes in the execution order.

### before_script

```yaml
before_script:
  - pip install -r requirements.txt
```

Commands that run **before** the main `script`. Used for setup: installing dependencies, logging in to registries, configuring tools. If `before_script` fails, the job fails and `script` never runs.

### script

```yaml
script:
  - pytest tests/ -v
```

The **required** field. These are the shell commands GitLab executes. If any command exits with a non-zero code, the job fails. Commands run sequentially within `script`.

### services

```yaml
services:
  - docker:24-dind
```

Sidecar containers that run alongside the job. `docker:24-dind` (Docker-in-Docker) starts a Docker daemon so you can run `docker build` and `docker push` inside the job. The job container can reach services via their image name as a hostname.

### artifacts

```yaml
artifacts:
  paths:
    - coverage/
  expire_in: 1 week
```

Files saved after the job completes and made available to later stages. `paths` lists directories or files to save. `expire_in` controls automatic cleanup — after the expiry, GitLab deletes the artifact. Without this, artifacts accumulate and consume storage.

### rules

```yaml
rules:
  - if: $CI_COMMIT_BRANCH == "main"
```

Controls **when a job runs**. This replaces the older `only/except` syntax. `rules` evaluates conditions top-to-bottom and runs the job on the first match. Here, `deploy-staging` only runs on pushes to the `main` branch — not on feature branches or merge requests.

---

## The Kubernetes Deployment (deployment.yaml)

This file represents what the CI pipeline deploys to the cluster at the end of the pipeline.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pipeline-demo
  namespace: gitlab-ci-scenarios
  labels:
    app: pipeline-demo
    scenario: "01-pipeline-fundamentals"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pipeline-demo
  template:
    metadata:
      labels:
        app: pipeline-demo
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: pipeline-demo
  namespace: gitlab-ci-scenarios
spec:
  selector:
    app: pipeline-demo
  ports:
    - port: 80
      targetPort: 80
```

### metadata.labels (scenario label)

```yaml
labels:
  app: pipeline-demo
  scenario: "01-pipeline-fundamentals"
```

The `scenario` label is custom metadata for this learning environment. In production, you'd add labels like `version: v1.2.3` or `commit: abc1234` to trace exactly which code is running. CI pipelines often inject `$CI_COMMIT_SHA` here via `kubectl set image` or Helm `--set`.

### replicas: 2

Two pods for basic availability. In a real pipeline, this value would typically come from a pipeline variable or environment-specific values file rather than being hardcoded.

### resources.requests vs limits

- `requests` (cpu: 50m, memory: 64Mi): The scheduler guarantees this capacity to the pod
- `limits` (cpu: 100m, memory: 128Mi): The hard ceiling — the container is throttled (CPU) or OOM-killed (memory) if exceeded

**50m CPU** = 5% of one CPU core. **64Mi** = 64 mebibytes.

### Service (ClusterIP)

The Service without a `type` field defaults to `ClusterIP` — internal cluster access only. The `selector: app: pipeline-demo` connects it to pods with that label. In a full pipeline, this gets exposed via an Ingress or LoadBalancer as a post-deploy step.

---

## Pipeline → Cluster Connection

```
Git push
  → GitLab detects .gitlab-ci.yml
  → Runs: lint → test → build → deploy
  → deploy-staging job runs:
      kubectl apply -f deployment.yaml
  → Kubernetes creates/updates the Deployment
  → Pods come up running the new image
```

This is the core CI/CD loop. The `.gitlab-ci.yml` orchestrates the automation; `deployment.yaml` defines the desired cluster state.

---

## Key Takeaways

- **`stages`** define the order and create quality gates — a stage failure stops the pipeline
- **Jobs within a stage run in parallel** — put independent checks (YAML lint + Dockerfile lint) in the same stage
- **`image`** per job means each job runs in the right container — no tool conflicts
- **`artifacts`** pass build outputs (image tags, test reports) between stages
- **`rules`** replace `only/except` — use `if: $CI_COMMIT_BRANCH == "main"` to protect deploy jobs
- **`deployment.yaml`** is what the pipeline actually deploys — labels tie the running pod back to the pipeline that created it
