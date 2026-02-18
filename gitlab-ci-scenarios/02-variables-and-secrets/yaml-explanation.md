# GitLab CI YAML Explanation - Variables and Secrets

This guide explains how variables are declared, scoped, and secured in a GitLab CI `.gitlab-ci.yml` file. Variables are the primary mechanism for passing configuration and secrets into pipeline jobs.

---

## Top-Level variables Block

```yaml
variables:
  # Non-sensitive defaults — safe to commit
  APP_ENV: staging
  IMAGE_TAG: latest
  LOG_LEVEL: info
  REGISTRY: registry.gitlab.com/mygroup/myapp

  # Sensitive defaults (override in GitLab UI with real values)
  DATABASE_URL: sqlite:///test.db
  API_KEY: "placeholder-override-in-ui"
```

### Why two types of variables here?

Variables in `.gitlab-ci.yml` are **committed to Git** — visible to anyone with repo access. Use this block for:
- Non-sensitive configuration (URLs, feature flags, log levels)
- Safe placeholder values that get overridden by real secrets defined in the GitLab UI

Never put real passwords, tokens, or API keys in this file.

---

## Job-Level variables

```yaml
build-image:
  stage: build
  variables:
    DOCKERFILE: Dockerfile.prod
    BUILD_CONTEXT: ./app
    DOCKER_BUILDKIT: "1"
  script:
    - docker build -f $DOCKERFILE $BUILD_CONTEXT -t $REGISTRY:$CI_COMMIT_SHA
```

### Job-level vs top-level variables

Job-level `variables` are **scoped to that job only**. They merge with top-level variables — if the same key exists at both levels, the job-level value wins. Use job-level variables when a setting only makes sense for one specific job (like a Dockerfile path for a build job).

---

## Predefined CI Variables

GitLab automatically injects these into every job — no configuration needed:

```yaml
tag-image:
  stage: build
  script:
    # Commit info
    - echo "Full SHA:  $CI_COMMIT_SHA"          # e7f3a1b2c...  (40 chars)
    - echo "Short SHA: $CI_COMMIT_SHORT_SHA"    # e7f3a1b2   (8 chars)
    - echo "Branch:    $CI_COMMIT_BRANCH"       # main, feature/login
    - echo "Tag:       $CI_COMMIT_TAG"          # v1.2.3  (null for branches)

    # Pipeline info
    - echo "Pipeline:  $CI_PIPELINE_ID"         # 12345
    - echo "Source:    $CI_PIPELINE_SOURCE"     # push, merge_request_event, schedule

    # Job info
    - echo "Job ID:    $CI_JOB_ID"              # 67890
    - echo "Job name:  $CI_JOB_NAME"            # tag-image

    # Registry shortcut
    - echo "Image:     $CI_REGISTRY_IMAGE"      # registry.gitlab.com/group/project
    - docker tag myapp $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

### $CI_COMMIT_SHA — the most important predefined variable

Used to tag Docker images with the exact commit that built them. This gives you full traceability: if a production incident occurs, you can check the running image tag and find the exact commit in Git.

### $CI_PIPELINE_SOURCE

Controls job behavior based on how the pipeline was triggered:
- `push` — someone pushed a commit
- `merge_request_event` — a merge request was opened/updated
- `schedule` — a scheduled pipeline
- `api` — triggered via the API

---

## Environment-Scoped Variables in YAML

```yaml
deploy-staging:
  stage: deploy
  environment:
    name: staging          # Activates "staging" scoped variables
  script:
    - echo $DATABASE_URL   # Gets staging value from GitLab UI

deploy-production:
  stage: deploy
  environment:
    name: production       # Activates "production" scoped variables
  script:
    - echo $DATABASE_URL   # Gets production value from GitLab UI
```

### How scoping works

In **GitLab UI > Settings > CI/CD > Variables**, you define the same key twice with different environment scopes:

| Key | Value | Scope |
|-----|-------|-------|
| `DATABASE_URL` | `postgres://staging-db:5432/app` | `staging` |
| `DATABASE_URL` | `postgres://prod-db:5432/app` | `production` |

The `environment.name` in the job determines which value the job receives. The same `.gitlab-ci.yml` code works for all environments — no `if/else` branches needed.

---

## Variable Precedence (highest → lowest)

```yaml
# These levels override each other in this order:
# 1. Trigger variables        (from API/webhook)
# 2. Pipeline-level variables (from "Run Pipeline" UI)
# 3. Project-level variables  (Settings > CI/CD > Variables)
# 4. Group-level variables    (group-wide secrets)
# 5. Instance-level variables (GitLab admin-level)
# 6. .gitlab-ci.yml variables (this file — lowest priority)
```

This is why you can safely commit placeholder values in `.gitlab-ci.yml` and override them in the UI — the UI variables always win.

---

## Protected and Masked Variables (UI-only, YAML context)

These properties don't exist in `.gitlab-ci.yml` — they're configured in the GitLab UI. But understanding them is critical for how YAML jobs interact with secrets:

```yaml
deploy-production:
  stage: deploy
  rules:
    # This job only runs on protected branches
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    # $PROD_DB_PASSWORD is a Protected + Masked variable
    # It's only injected when running on a protected branch
    # In job logs it appears as [MASKED], not the real value
    - kubectl create secret generic db-creds \
        --from-literal=password=$PROD_DB_PASSWORD
```

### Protected variables

Only injected into jobs running on **protected branches or tags**. If someone creates a feature branch and pushes, their pipeline jobs do NOT receive protected variables. This prevents fork-based attacks where a contributor creates a malicious MR to exfiltrate secrets.

### Masked variables

The value is replaced with `[MASKED]` in job logs. If your script accidentally prints the variable (via `set -x` or `echo $PROD_DB_PASSWORD`), the log shows `[MASKED]`. Requirements: at least 8 characters, no newlines, Base64-safe characters.

---

## File-Type Variables in YAML

```yaml
deploy:
  stage: deploy
  script:
    # $KUBECONFIG is a "File" type variable in GitLab UI
    # GitLab writes the variable's VALUE to a temp file
    # The environment variable $KUBECONFIG holds the FILE PATH
    - kubectl --kubeconfig $KUBECONFIG get pods
    - helm --kubeconfig $KUBECONFIG upgrade myapp ./chart
```

File variables are essential for configs that expect a file path rather than a string value (kubeconfig, TLS certificates, service account JSON keys). GitLab creates a temporary file per job and cleans it up afterward.

---

## dotenv Artifact — Passing Variables Between Jobs

```yaml
build:
  stage: build
  script:
    - docker build -t myapp:$CI_COMMIT_SHA .
    - echo "IMAGE_TAG=$CI_COMMIT_SHA" >> build.env
    - echo "BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> build.env
  artifacts:
    reports:
      dotenv: build.env    # Special artifact type — exports as variables

deploy:
  stage: deploy
  needs: [build]
  script:
    # $IMAGE_TAG and $BUILD_TIME are available here from the artifact
    - kubectl set image deployment/myapp app=myapp:$IMAGE_TAG
```

### reports: dotenv

The `dotenv` artifact type reads a `KEY=VALUE` file and injects those values as **CI variables** in downstream jobs. This is the cleanest way to pass computed values (like a built image tag or version number) from one job to the next.

---

## Key Takeaways

- **Top-level `variables`**: Non-sensitive defaults; safe to commit — will be overridden by UI variables
- **Predefined variables**: `$CI_COMMIT_SHA`, `$CI_PIPELINE_SOURCE`, `$CI_REGISTRY_IMAGE` — automatically injected, always available
- **Environment scoping**: Define the same key twice in the UI with different scopes; `environment.name` in the job selects which value it gets
- **Protected variables**: Only injected on protected branches — use for production secrets
- **Masked variables**: Replace value with `[MASKED]` in logs — prevent accidental secret exposure
- **File variables**: For configs that require a file path (kubeconfig, certs)
- **dotenv artifacts**: The right way to pass computed variables between pipeline stages
