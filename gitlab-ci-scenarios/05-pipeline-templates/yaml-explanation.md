# GitLab CI YAML Explanation - Pipeline Templates

This guide explains the `pipeline-library.yml` shared template file used in this scenario. Templates eliminate copy-paste across projects by defining reusable job definitions that other pipelines can `extend` or `include`.

---

## The pipeline-library.yml

```yaml
# pipeline-library.yml - Shared Pipeline Library
# Lives in a separate GitLab project: platform-team/ci-templates
```

This file lives in a **dedicated "templates" project** (e.g., `platform-team/ci-templates`). Individual project pipelines include it via the `include:` keyword. The platform team owns the templates; application teams consume them.

---

## Dot-Jobs (Hidden Jobs) — The Template Pattern

Jobs whose names start with `.` are **hidden** — GitLab ignores them and does not run them. They exist purely as templates to be inherited via `extends`.

```yaml
# This job NEVER runs on its own
.docker-build:
  image:
    name: gcr.io/kaniko-project/executor:v1.14.0-debug
    entrypoint: [""]
  variables:
    DOCKERFILE: Dockerfile
    BUILD_CONTEXT: "."
    KANIKO_CACHE: "true"
  script:
    - mkdir -p /kaniko/.docker
    - >-
      echo "{\"auths\":{\"$CI_REGISTRY\":{\"auth\":\"$(echo -n
      $CI_REGISTRY_USER:$CI_REGISTRY_PASSWORD | base64)\"}}}"
      > /kaniko/.docker/config.json
    - >-
      /kaniko/executor
      --context $CI_PROJECT_DIR/$BUILD_CONTEXT
      --dockerfile $CI_PROJECT_DIR/$DOCKERFILE
      --destination $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      --cache=$KANIKO_CACHE
      --cache-repo=$CI_REGISTRY_IMAGE/cache
```

### image.name + image.entrypoint

```yaml
image:
  name: gcr.io/kaniko-project/executor:v1.14.0-debug
  entrypoint: [""]
```

The `image:` block can be a string (simple) or an object (advanced). `entrypoint: [""]` overrides the image's built-in entrypoint so you can run shell commands before invoking the Kaniko executor. Without this, Kaniko's executor would start immediately on container start, preventing any setup.

### variables in the template

```yaml
variables:
  DOCKERFILE: Dockerfile          # Default — override per-project
  BUILD_CONTEXT: "."              # Default — override per-project
  KANIKO_CACHE: "true"
```

Template variables define **overridable defaults**. Consumer jobs set these variables to customize behavior without changing the template itself:

```yaml
# In your project's .gitlab-ci.yml
build-api:
  extends: .docker-build
  variables:
    DOCKERFILE: api/Dockerfile    # Override the default
    BUILD_CONTEXT: api/
```

### YAML block scalar (>-)

```yaml
- >-
  /kaniko/executor
  --context $CI_PROJECT_DIR/$BUILD_CONTEXT
  --dockerfile $CI_PROJECT_DIR/$DOCKERFILE
  --destination $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

`>-` is YAML's **folded block scalar** with strip chomping. It folds newlines into spaces (so the multi-line YAML becomes a single command) and strips the trailing newline. This lets you write long commands readably across multiple lines without shell line continuations (`\`).

---

## The .k8s-deploy Template

```yaml
.k8s-deploy:
  image: bitnami/kubectl:latest
  variables:
    REPLICAS: "2"
    TIMEOUT: "120s"
  before_script:
    - echo "Deploying to $KUBE_NAMESPACE"
  script:
    - kubectl set image deployment/$CI_PROJECT_NAME
        app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        -n $KUBE_NAMESPACE
    - kubectl scale deployment/$CI_PROJECT_NAME
        --replicas=$REPLICAS -n $KUBE_NAMESPACE
    - kubectl rollout status deployment/$CI_PROJECT_NAME
        -n $KUBE_NAMESPACE --timeout=$TIMEOUT
  retry:
    max: 2
    when:
      - runner_system_failure
```

### retry

```yaml
retry:
  max: 2                          # Retry up to 2 times (3 total attempts)
  when:
    - runner_system_failure       # Only retry on infrastructure failures
    - stuck_or_timeout_failure    # Not on script failures (don't retry broken code)
```

`retry.when` is critical — without it, GitLab retries on ALL failures including script failures. You want to retry flaky infrastructure (runner crashed, network blip) but NOT retry broken application code. Common `when` values:
- `runner_system_failure` — runner crashed or couldn't start the job
- `stuck_or_timeout_failure` — job got stuck
- `api_failure` — GitLab API error

### $KUBE_NAMESPACE

This variable is **not predefined** by GitLab — it must be provided by the consuming job or as a project/group variable. This is how the template stays environment-agnostic: the template defines the pattern, the consumer provides the environment specifics.

### kubectl rollout status

```yaml
- kubectl rollout status deployment/$CI_PROJECT_NAME
    -n $KUBE_NAMESPACE --timeout=$TIMEOUT
```

This command **blocks** until the rollout finishes or times out. It's what makes CI deployments reliable — without it, the job would exit immediately after `kubectl set image`, and you'd have no idea if pods actually came up healthy.

---

## The .security-scan Template

```yaml
.security-scan:
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  variables:
    SEVERITY: "HIGH,CRITICAL"
    EXIT_CODE: "0"
  script:
    - trivy image
        --severity $SEVERITY
        --exit-code $EXIT_CODE
        --format json
        --output trivy-report.json
        $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  artifacts:
    paths:
      - trivy-report.json
    expire_in: 1 week
  allow_failure: true
```

### allow_failure: true

The job can fail without failing the entire pipeline. In the security template, this means a vulnerability scan finding HIGH/CRITICAL issues won't block your deployment. In production, you'd evolve this: start with `allow_failure: true` (reporting mode), then set `EXIT_CODE: "1"` and `allow_failure: false` once your team has addressed the existing findings (blocking mode).

### SEVERITY: "HIGH,CRITICAL"

Trivy's severity filter — only report findings at HIGH or CRITICAL level. Including LOW and MEDIUM in CI tends to generate noise and gets ignored. Start strict (only CRITICAL), expand as your team matures.

---

## How Consumer Pipelines Use Templates

```yaml
# In your project's .gitlab-ci.yml

include:
  - project: platform-team/ci-templates
    ref: main
    file: pipeline-library.yml
  # Can also include GitLab-provided templates:
  - template: Security/SAST.gitlab-ci.yml

stages:
  - build
  - security
  - deploy-staging
  - deploy-production

# Override with project-specific values
build-image:
  extends: .docker-build
  stage: build
  variables:
    DOCKERFILE: Dockerfile.prod   # Override template default

# Use security scan as-is
scan-image:
  extends: .security-scan
  stage: security

# Staging deploy
deploy-staging:
  extends: .k8s-deploy
  stage: deploy-staging
  variables:
    KUBE_NAMESPACE: staging
    REPLICAS: "2"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# Production deploy with more replicas
deploy-production:
  extends: .k8s-deploy
  stage: deploy-production
  variables:
    KUBE_NAMESPACE: production
    REPLICAS: "5"
    TIMEOUT: "300s"
  environment:
    name: production
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### include

```yaml
include:
  - project: platform-team/ci-templates   # Another GitLab project
    ref: main                              # Which branch/tag
    file: pipeline-library.yml            # Which file

  - template: Security/SAST.gitlab-ci.yml  # GitLab built-in template

  - local: .ci/custom-jobs.yml            # File in same repo

  - remote: https://example.com/ci.yml    # External URL
```

Four `include` types. `project:` is the most powerful — it references another repo in your GitLab instance, enabling true centralized template management with version pinning via `ref:`.

### extends — Deep Merge

When a job `extends` a template, GitLab **deep-merges** the configurations. Lists (like `script`) are completely replaced by the consumer. Scalar values (like `image`, `when`) are overridden. This means a consumer can add to `variables` without replacing all template variables.

---

## Key Takeaways

- **Dot-jobs (`.name`)**: Hidden — never run directly. Exist only as templates for `extends`
- **`extends`**: Deep-merges the template into the consumer job — override only what you need
- **`image.entrypoint: [""]`**: Required to override image entrypoints (Kaniko, custom executors)
- **Template variables with defaults**: Set sensible defaults in the template; consumers override per-project
- **`retry.when`**: Retry on infrastructure failures only — never on script failures
- **`allow_failure: true`**: Non-blocking jobs (security scans in reporting mode)
- **`include: project:`**: The right way to share templates across projects — version-pinned, centrally managed
- **`>-` YAML scalar**: Write long commands across multiple lines without shell line continuations
