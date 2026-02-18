# GitLab CI YAML Explanation - Merge Request Pipelines

This guide explains the YAML configurations for GitLab CI merge request (MR) pipelines, including the `rules:` block for MR-specific job control, dynamic `environment:` names for review apps, and the `review-app.yaml` Kubernetes deployment.

---

## MR Pipeline Rules — The rules Block

```yaml
unit-tests:
  stage: test
  image: python:3.11
  script:
    - pytest tests/ -v
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"   # Run in MR pipelines
    - if: $CI_COMMIT_BRANCH == "main"                    # Run on main branch too
```

### rules evaluation

`rules` evaluates conditions **top to bottom** and runs the job on the first match. If no condition matches, the job is excluded from the pipeline. Each rule can set:

```yaml
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    when: always                  # Run this job (default)
  - if: $CI_COMMIT_BRANCH == "main"
    when: always
  - when: never                   # Catch-all: exclude from everything else
```

### $CI_PIPELINE_SOURCE values

| Value | When |
|-------|------|
| `push` | Direct push to a branch |
| `merge_request_event` | MR opened, updated, or commit pushed to MR source branch |
| `schedule` | Scheduled pipeline |
| `api` | Triggered via API |
| `trigger` | Multi-project pipeline trigger |
| `web` | Manually run from GitLab UI |

### Avoiding duplicate pipelines

When you push to a branch that has an open MR, GitLab may run **two pipelines**: a branch pipeline and an MR pipeline. Use `workflow:rules` to suppress duplicates:

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"  # Run MR pipeline
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS  # Skip branch pipeline when MR exists
      when: never
    - if: $CI_COMMIT_BRANCH                             # Run branch pipeline (no open MR)
```

This is the standard pattern for projects using MR pipelines.

---

## MR-Only Jobs

```yaml
lint-mr-title:
  stage: lint
  image: alpine:latest
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"   # MR pipelines only
  script:
    - echo "MR title: $CI_MERGE_REQUEST_TITLE"
    - echo "MR IID:   $CI_MERGE_REQUEST_IID"
    - |
      if echo "$CI_MERGE_REQUEST_TITLE" | grep -qE "^(feat|fix|chore|docs):"; then
        echo "✅ MR title follows conventional commit format"
      else
        echo "❌ MR title must start with feat|fix|chore|docs"
        exit 1
      fi
```

### $CI_MERGE_REQUEST_* variables

These variables are **only available in MR pipelines**. On regular branch pipelines, they are empty:

- `$CI_MERGE_REQUEST_IID` — MR number (e.g., `42`)
- `$CI_MERGE_REQUEST_TITLE` — MR title text
- `$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME` — source branch (e.g., `feature/login`)
- `$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` — target branch (e.g., `main`)
- `$CI_MERGE_REQUEST_LABELS` — comma-separated MR labels
- `$CI_MERGE_REQUEST_DIFF_BASE_SHA` — commit SHA of the merge base

---

## Review Apps — Dynamic Environment Deployment

```yaml
deploy-review:
  stage: deploy
  image: bitnami/kubectl:latest
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  environment:
    name: review/$CI_MERGE_REQUEST_IID          # Unique per MR: review/42, review/43
    url: http://review-$CI_MERGE_REQUEST_IID.example.com
    on_stop: stop-review                        # Job to run when environment is stopped
    auto_stop_in: 1 week                        # Auto-stop after 1 week
  script:
    - kubectl create namespace review-$CI_MERGE_REQUEST_IID --dry-run=client -o yaml | kubectl apply -f -
    - sed "s/merge-request: \"42\"/merge-request: \"$CI_MERGE_REQUEST_IID\"/g" review-app.yaml | kubectl apply -f -
  variables:
    REVIEW_NS: review-$CI_MERGE_REQUEST_IID

stop-review:
  stage: deploy
  image: bitnami/kubectl:latest
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: manual                              # Only run manually or on MR close
  environment:
    name: review/$CI_MERGE_REQUEST_IID
    action: stop                               # This is the stop job
  script:
    - kubectl delete namespace review-$CI_MERGE_REQUEST_IID --ignore-not-found
```

### environment.name with dynamic value

```yaml
environment:
  name: review/$CI_MERGE_REQUEST_IID
```

Each MR gets its own named environment (e.g., `review/42`). GitLab tracks these environments in **Operations > Environments**, showing deployment status, links to the review app, and deployment history. Using `$CI_MERGE_REQUEST_IID` ensures each MR is isolated.

### environment.on_stop

```yaml
environment:
  on_stop: stop-review
```

Links to the job that should run when this environment is "stopped". GitLab calls this job when:
- You manually click "Stop" in the Environments UI
- The MR is merged or closed
- `auto_stop_in` duration expires

The stop job must have `action: stop` in its `environment` block.

### environment.auto_stop_in

```yaml
auto_stop_in: 1 week
```

Automatically stops the review app environment after this duration. This triggers the `on_stop` job, which deletes the Kubernetes namespace. Essential for cost control — review apps get automatically cleaned up after the review period.

---

## The review-app.yaml Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-app
  namespace: gitlab-ci-scenarios
  labels:
    app: review-app
    scenario: "06-merge-request-pipelines"
    merge-request: "42"           # In real CI, replaced with $CI_MERGE_REQUEST_IID
spec:
  replicas: 1                     # Minimal — review apps don't need HA
  selector:
    matchLabels:
      app: review-app
  template:
    metadata:
      labels:
        app: review-app
        merge-request: "42"       # Label on pods — used for filtering
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m            # Minimal resources for a review app
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
```

### merge-request label

```yaml
labels:
  merge-request: "42"
```

This custom label tracks which MR this deployment belongs to. In a real pipeline, you'd inject `$CI_MERGE_REQUEST_IID` here (e.g., via `sed` or `envsubst`). This lets you find all resources for a given MR:

```bash
kubectl get all -l merge-request=42 -n review-42
```

### replicas: 1

Review apps are temporary and used by one reviewer at a time. Using 1 replica conserves cluster resources. In production namespaces, you'd use 2+ for availability.

### Small resource requests

```yaml
resources:
  requests:
    cpu: 25m
    memory: 32Mi
```

Review apps should be as light as possible — you might have dozens open simultaneously (one per active MR). Minimal resource requests let the cluster schedule many review apps on available nodes.

---

## MR Pipeline Job Flow

```
Push to feature branch → MR opened
       ↓
  MR Pipeline triggers
       ↓
  [lint] → [test] → [build] → [deploy-review]
                                     ↓
                              review/42 environment created
                              http://review-42.example.com
                                     ↓
                         Reviewer approves MR → Merge to main
                                     ↓
                              stop-review triggered
                              review-42 namespace deleted
```

---

## Key Takeaways

- **`$CI_PIPELINE_SOURCE == "merge_request_event"`**: The correct condition for MR-only jobs
- **`workflow:rules`**: Prevent duplicate pipelines when both a branch pipeline and MR pipeline would run
- **`$CI_MERGE_REQUEST_IID`**: The MR number — use it to create unique environment names (`review/42`)
- **`environment.on_stop`**: Links to the cleanup job — called automatically on MR merge/close
- **`environment.auto_stop_in`**: Automatically clean up review apps after the review period
- **`action: stop`**: Required on the stop job to tell GitLab it terminates the environment
- **`replicas: 1` + tiny resources**: Review apps are temporary — don't over-provision them
- **`merge-request` label**: Track which MR owns which Kubernetes resources
