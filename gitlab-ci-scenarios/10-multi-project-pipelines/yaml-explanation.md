# GitLab CI YAML Explanation - Multi-Project Pipelines

This guide explains the `orchestrator-pipeline.yml` — a central deployment orchestrator triggered by multiple service repositories. It covers multi-project pipeline triggers, upstream/downstream relationships, manual gates, and the `needs:` keyword.

---

## The orchestrator-pipeline.yml

```yaml
# orchestrator-pipeline.yml - Deployment Orchestrator
# Lives in: mygroup/deploy-orchestrator
# Triggered by service repos after successful builds
```

This pipeline lives in a **dedicated orchestrator project** — not in the application repos. Multiple application repos trigger it (via API or `trigger:`) when their builds succeed, passing service-specific variables. The orchestrator handles the full deployment flow: validate → staging → smoke test → approve → production.

---

## Stages

```yaml
stages:
  - validate
  - deploy-staging
  - test-staging
  - approve
  - deploy-production
```

Five stages implement a complete promotion workflow. Each is a gate — a failure stops the pipeline before it reaches production. The `approve` stage contains a manual job, creating a human gate between staging and production.

---

## Stage 1: validate-trigger

```yaml
validate-trigger:
  stage: validate
  script:
    - echo "Triggered by $TRIGGERED_BY"
    - echo "Deploying $SERVICE_NAME with image $IMAGE_REPO:$IMAGE_TAG"
    - |
      if [ -z "$SERVICE_NAME" ] || [ -z "$IMAGE_TAG" ]; then
        echo "ERROR: Missing required variables SERVICE_NAME or IMAGE_TAG"
        exit 1
      fi
    - echo "Validation passed"
```

### Validating upstream variables

Variables `$SERVICE_NAME` and `$IMAGE_TAG` come from the triggering pipeline. This validation job checks they're present before any deployment work begins. It's a **fast-fail gate** — if the trigger sent incomplete data, the pipeline fails in seconds instead of halfway through a production deployment.

### $TRIGGERED_BY

A custom variable the upstream pipeline sets to identify itself:
```yaml
# In the service repo's .gitlab-ci.yml:
trigger-deploy:
  trigger:
    project: mygroup/deploy-orchestrator
    strategy: depend
  variables:
    SERVICE_NAME: api-service
    IMAGE_TAG: $CI_COMMIT_SHA
    IMAGE_REPO: $CI_REGISTRY_IMAGE
    TRIGGERED_BY: "$CI_PROJECT_NAME pipeline #$CI_PIPELINE_ID"
```

---

## Stage 2: deploy-staging

```yaml
deploy-staging:
  stage: deploy-staging
  image: alpine/helm:3.14
  script:
    - echo "Deploying $SERVICE_NAME to staging"
    - helm upgrade --install $SERVICE_NAME charts/$SERVICE_NAME
        --namespace staging
        --set image.repository=$IMAGE_REPO
        --set image.tag=$IMAGE_TAG
        --atomic
        --timeout 5m
  environment:
    name: staging/$SERVICE_NAME
    url: https://$SERVICE_NAME.staging.example.com
```

### image: alpine/helm:3.14

The Helm CLI image. Unlike `bitnami/kubectl`, this image includes both Helm and kubectl. `3.14` is a pinned version — critical for reproducibility. Unpinned (`latest`) could break your pipeline after a Helm release with breaking changes.

### helm upgrade --install

```yaml
- helm upgrade --install $SERVICE_NAME charts/$SERVICE_NAME
    --namespace staging
    --set image.repository=$IMAGE_REPO
    --set image.tag=$IMAGE_TAG
    --atomic
    --timeout 5m
```

`--install`: Creates the release if it doesn't exist; upgrades if it does. This idempotent pattern means the same command works for the first deployment and all subsequent updates.

`--set image.repository` and `--set image.tag`: Inject the specific image from the triggering pipeline. `$IMAGE_REPO:$IMAGE_TAG` refers to the exact build that triggered this orchestrator.

`--atomic`: If the upgrade fails, automatically rolls back to the previous release. Combined with `--timeout 5m`, if Kubernetes can't get pods healthy within 5 minutes, Helm rolls back and the job fails.

### environment.name: staging/$SERVICE_NAME

```yaml
environment:
  name: staging/$SERVICE_NAME
  url: https://$SERVICE_NAME.staging.example.com
```

Dynamic environment name creates a separate GitLab environment per service (e.g., `staging/api-service`, `staging/worker`). Each has its own deployment history in the GitLab Environments UI. The `url` makes the review link clickable in the pipeline UI.

---

## Stage 3: smoke-test

```yaml
smoke-test:
  stage: test-staging
  image: curlimages/curl:latest
  script:
    - echo "Running smoke tests for $SERVICE_NAME on staging"
    - curl -f https://$SERVICE_NAME.staging.example.com/health
    - curl -f https://$SERVICE_NAME.staging.example.com/api/status
```

### curl -f

The `-f` flag makes `curl` exit with code 22 if the HTTP response is 4xx or 5xx. Without `-f`, `curl` exits 0 on any HTTP response (including 500 errors). This turns a 500-response staging health check into a CI failure, triggering the `--atomic` Helm rollback in the previous stage.

### Testing before approval

The smoke test runs **between staging deployment and the approval gate**. If staging is unhealthy, you never reach the manual approval step — the pipeline fails before giving anyone the option to promote to production. This is a critical safety gate.

---

## Stage 4: approve-production (Manual Gate)

```yaml
approve-production:
  stage: approve
  script:
    - echo "Production deployment approved for $SERVICE_NAME:$IMAGE_TAG"
  when: manual
  allow_failure: false
```

### when: manual

This job appears in the GitLab pipeline UI as a paused job with a "play" button. The pipeline **stops at this job** until someone clicks play. This is the human approval gate between staging and production.

### allow_failure: false

**Critical**: This makes the manual approval a hard gate. If the job is skipped (not run) or no one clicks play, the pipeline cannot proceed past this stage. With `allow_failure: true` (the default for `when: manual`), the pipeline would continue even if the approval job is never triggered.

Together, `when: manual` + `allow_failure: false` = **blocking manual gate** — nothing in later stages runs until a human explicitly approves.

---

## Stage 5: deploy-production

```yaml
deploy-production:
  stage: deploy-production
  image: alpine/helm:3.14
  script:
    - echo "Deploying $SERVICE_NAME to production"
    - helm upgrade --install $SERVICE_NAME charts/$SERVICE_NAME
        --namespace production
        --set image.repository=$IMAGE_REPO
        --set image.tag=$IMAGE_TAG
        --atomic
        --timeout 10m
  environment:
    name: production/$SERVICE_NAME
    url: https://$SERVICE_NAME.example.com
  needs: [approve-production]
```

### needs: [approve-production]

```yaml
needs: [approve-production]
```

`needs:` creates an explicit dependency. The production deploy job can only run after `approve-production` completes successfully. Without `needs:`, jobs in the same stage run in parallel or based only on stage order.

In this case, `needs:` is redundant (the `approve` stage must complete before `deploy-production` stage starts), but it's included as a clear, explicit signal: "this job requires prior approval." It also enables DAG execution — the job can start as soon as `approve-production` finishes, without waiting for other jobs in the `approve` stage.

### --timeout 10m (vs 5m for staging)

Production gets a longer timeout. Production environments may have more replicas (longer rollout time), more strict health checks, and slower readiness probes. Giving production extra time reduces false failures from legitimate slow startups.

---

## How the Multi-Project Trigger Works

```yaml
# In service repo (.gitlab-ci.yml):
trigger-orchestrator:
  stage: trigger
  trigger:
    project: mygroup/deploy-orchestrator   # The orchestrator project
    branch: main                           # Which branch to use
    strategy: depend                       # Wait for orchestrator to complete
  variables:
    SERVICE_NAME: $CI_PROJECT_NAME
    IMAGE_TAG: $CI_COMMIT_SHA
    IMAGE_REPO: $CI_REGISTRY_IMAGE
    TRIGGERED_BY: "$CI_PROJECT_NAME #$CI_PIPELINE_ID"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### trigger: project:

Triggers a pipeline in a **different GitLab project**. The triggering project must have permission to trigger pipelines in the target project (via a trigger token or through group membership).

### strategy: depend (on the upstream)

The service repo's pipeline waits for the orchestrator pipeline to complete and mirrors its status. If the orchestrator fails (staging unhealthy, approval denied, production deployment failed), the service repo pipeline fails too. This creates end-to-end traceability.

---

## Key Takeaways

- **Orchestrator pattern**: A dedicated deployment project triggered by many service repos — separates build from deploy concerns
- **`trigger: project:`**: Triggers a pipeline in another GitLab project, passing variables from the current context
- **`strategy: depend`**: Upstream waits for downstream — required to propagate failures back to the service repo
- **`when: manual` + `allow_failure: false`**: Hard blocking gate — pipeline cannot proceed until someone approves
- **`helm upgrade --install --atomic`**: Idempotent deploy + automatic rollback on failure in one command
- **Dynamic environment names** (`staging/$SERVICE_NAME`): Each service gets its own environment history in the GitLab UI
- **`needs: [approve-production]`**: Explicit dependency on approval — makes the intent clear even if stages enforce the same order
- **Smoke tests before approval**: Verify staging before giving anyone the option to promote to production
