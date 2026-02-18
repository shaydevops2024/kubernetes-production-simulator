# GitLab CI YAML Explanation - Dynamic Child Pipelines

This guide explains the YAML patterns for dynamic child pipelines in GitLab CI — where a parent pipeline generates a child pipeline's YAML at runtime, enabling matrix deployments, monorepo CI, and data-driven pipeline generation.

---

## The Parent Pipeline — trigger: include: artifact:

```yaml
# Parent pipeline (.gitlab-ci.yml)
stages:
  - generate
  - trigger

generate-pipeline:
  stage: generate
  image: python:3.11-slim
  script:
    - python generate-pipeline.sh   # Outputs a .gitlab-ci.yml to a file
  artifacts:
    paths:
      - generated-pipeline.yml      # The generated YAML
    expire_in: 1 hour

trigger-child:
  stage: trigger
  trigger:
    include:
      - artifact: generated-pipeline.yml    # Use the generated file
        job: generate-pipeline              # From this job's artifacts
    strategy: depend                         # Parent waits for child to complete
```

### trigger:

```yaml
trigger:
  include:
    - artifact: generated-pipeline.yml
      job: generate-pipeline
```

`trigger:` creates a **child pipeline** — a separate, independent pipeline that runs under the parent. Unlike regular stages, child pipelines can have their own stages, jobs, and rules. They appear as a nested pipeline in the GitLab UI.

`include.artifact` and `include.job` tell GitLab to read the child pipeline's YAML from the specified job's artifact. This is the dynamic part: the YAML that defines the child pipeline was **generated at runtime**, not committed to the repository.

### strategy: depend

```yaml
strategy: depend
```

By default, the parent pipeline continues (and may complete) without waiting for child pipelines to finish. `strategy: depend` makes the parent **wait for the child** to complete and mirrors the child's final status — if the child fails, the parent fails. Without this, the parent always succeeds even if the child fails.

---

## The Generator Script — What It Produces

```bash
#!/bin/bash
# generate-pipeline.sh
# Generates a child pipeline YAML based on runtime data

SERVICES=$(git diff --name-only HEAD~1 HEAD | grep "^services/" | cut -d/ -f2 | sort -u)

cat > generated-pipeline.yml << 'EOF'
stages:
  - build
  - deploy

EOF

for SERVICE in $SERVICES; do
  cat >> generated-pipeline.yml << EOF
build-${SERVICE}:
  stage: build
  script:
    - echo "Building ${SERVICE}"
    - docker build -t myapp/${SERVICE}:\$CI_COMMIT_SHA services/${SERVICE}/

deploy-${SERVICE}:
  stage: deploy
  script:
    - kubectl set image deployment/${SERVICE} app=myapp/${SERVICE}:\$CI_COMMIT_SHA
  needs: [build-${SERVICE}]
EOF
done
```

### What the generator produces

For a change to `services/api/` and `services/worker/`, the generator outputs:

```yaml
stages:
  - build
  - deploy

build-api:
  stage: build
  script:
    - echo "Building api"
    - docker build -t myapp/api:$CI_COMMIT_SHA services/api/

build-worker:
  stage: build
  script:
    - echo "Building worker"
    - docker build -t myapp/worker:$CI_COMMIT_SHA services/worker/

deploy-api:
  stage: deploy
  needs: [build-api]
  script:
    - kubectl set image deployment/api app=myapp/api:$CI_COMMIT_SHA

deploy-worker:
  stage: deploy
  needs: [build-worker]
  script:
    - kubectl set image deployment/worker app=myapp/worker:$CI_COMMIT_SHA
```

The child pipeline YAML is valid GitLab CI YAML — it just happens to be generated programmatically rather than written by hand. Any valid `.gitlab-ci.yml` syntax works here.

---

## Static Child Pipelines (Non-dynamic Reference)

```yaml
# Parent: trigger a child pipeline from a committed file
trigger-child-static:
  trigger:
    include:
      - local: .ci/child-pipeline.yml   # Committed YAML file
    strategy: depend

# Or from another project's file
trigger-child-project:
  trigger:
    include:
      - project: mygroup/deploy-templates
        ref: main
        file: kubernetes-deploy.yml
    strategy: depend
```

### local vs artifact

| | `local:` | `artifact:` |
|---|---|---|
| Source | Committed file in same repo | Generated file from a job |
| Changes require | Git commit | Pipeline run |
| Use case | Stable sub-pipeline structure | Dynamic, runtime-computed pipelines |

---

## Passing Variables to Child Pipelines

```yaml
trigger-child:
  stage: trigger
  variables:
    DEPLOY_ENV: staging
    IMAGE_TAG: $CI_COMMIT_SHA
    SERVICE_NAME: api
  trigger:
    include:
      - artifact: generated-pipeline.yml
        job: generate-pipeline
    strategy: depend
```

Variables defined on the `trigger:` job are passed to the child pipeline. The child pipeline's jobs can access `$DEPLOY_ENV`, `$IMAGE_TAG`, and `$SERVICE_NAME` as if they were defined in the child's own `variables:` block.

---

## Matrix Child Pipelines — Parallel Deployments

```yaml
# Parent pipeline
stages:
  - deploy

.deploy-matrix: &deploy-matrix
  trigger:
    include:
      - local: .ci/deploy-child.yml
    strategy: depend

deploy-staging:
  <<: *deploy-matrix
  variables:
    ENVIRONMENT: staging
    REPLICAS: "2"
    KUBE_NAMESPACE: app-staging

deploy-production:
  <<: *deploy-matrix
  when: manual
  variables:
    ENVIRONMENT: production
    REPLICAS: "5"
    KUBE_NAMESPACE: app-production
```

```yaml
# .ci/deploy-child.yml (the child template)
deploy:
  image: alpine/helm:3.14
  script:
    - helm upgrade --install myapp ./chart
        --namespace $KUBE_NAMESPACE
        --set replicas=$REPLICAS
        --atomic
  environment:
    name: $ENVIRONMENT
```

Each `trigger:` job runs the same child pipeline template, but with different variables. This creates isolated child pipelines for staging and production, both running the same deployment logic. The parent shows both pipelines with their individual status.

---

## Monorepo Pattern — Only Build Changed Services

```yaml
# Parent pipeline
stages:
  - detect-changes
  - trigger

detect-changes:
  stage: detect-changes
  script:
    - |
      # Detect which services changed
      git diff --name-only $CI_COMMIT_BEFORE_SHA $CI_COMMIT_SHA > changed-files.txt

      # Generate pipeline for changed services only
      python scripts/generate-pipeline.py changed-files.txt > generated.yml

      echo "Generated pipeline:"
      cat generated.yml
  artifacts:
    paths:
      - generated.yml
      - changed-files.txt
    expire_in: 1 hour

run-dynamic-pipeline:
  stage: trigger
  trigger:
    include:
      - artifact: generated.yml
        job: detect-changes
    strategy: depend
  rules:
    - exists:
        - generated.yml           # Only trigger if a pipeline was generated
```

### rules.exists

```yaml
rules:
  - exists:
    - generated.yml
```

Only runs the trigger job if `generated.yml` exists. If the generator script finds no changed services, it might produce an empty file or not create the file at all. `exists:` prevents triggering an empty child pipeline.

---

## Child Pipeline YAML Requirements

The generated/child YAML must be valid GitLab CI syntax:

```yaml
# Valid child pipeline YAML
stages:
  - build
  - test
  - deploy

# Jobs must have at minimum: stage + script (or trigger)
my-job:
  stage: build
  image: alpine:latest
  script:
    - echo "Hello from child pipeline"
```

**Constraints on child pipelines**:
- Cannot `include: template:` (GitLab security restriction on dynamically generated pipelines)
- Cannot reference parent pipeline's artifacts (they're separate pipeline contexts)
- Variables must be explicitly passed via the `variables:` block on the trigger job
- Child pipelines have their own pipeline ID visible in the GitLab UI under the parent

---

## Key Takeaways

- **`trigger: include: artifact:`**: Run a child pipeline whose YAML was generated at runtime by a previous job
- **`strategy: depend`**: Parent waits for child — without this, parent succeeds even if child fails
- **Generator script**: Produces valid `.gitlab-ci.yml` YAML dynamically based on runtime data (changed files, API calls, config)
- **Variables on trigger job**: Pass data from the parent context to the child pipeline
- **Matrix pattern**: Same child template, multiple trigger jobs with different `variables:` = parallel isolated pipelines
- **Monorepo use case**: Generate build/deploy jobs only for services that actually changed — skip unchanged services
- **`rules.exists:`**: Conditionally skip the trigger job if the generator produced nothing
