# GitLab CI YAML Explanation - Kubernetes Deployments

This guide explains the Kubernetes `deployment.yaml` used in this scenario and the GitLab CI pipeline patterns for deploying to Kubernetes — covering KUBECONFIG setup, rolling updates, readiness gates, and rollback.

---

## The Kubernetes Deployment (deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: k8s-deploy-demo
  namespace: gitlab-ci-scenarios
  labels:
    app: k8s-deploy-demo
    scenario: "07-kubernetes-deployments"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: k8s-deploy-demo
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: k8s-deploy-demo
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
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
  name: k8s-deploy-demo
  namespace: gitlab-ci-scenarios
spec:
  selector:
    app: k8s-deploy-demo
  ports:
    - port: 80
      targetPort: 80
```

---

## Field-by-Field Breakdown

### spec.strategy — RollingUpdate

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

Controls how Kubernetes replaces old pods with new ones during a deployment.

**`maxSurge: 1`** — Kubernetes can create 1 extra pod above the desired replica count during the rollout. With `replicas: 3`, up to 4 pods can exist simultaneously during the update.

**`maxUnavailable: 0`** — Zero old pods are killed before a new pod is `Ready`. This is the **zero-downtime** configuration: new pods must pass their readiness probe before any old pods are terminated. Traffic is always served by at least 3 healthy pods.

**Production guidance**:
- `maxUnavailable: 0, maxSurge: 1` — Zero downtime, slightly slower rollout
- `maxUnavailable: 1, maxSurge: 0` — No extra pods (resource-constrained), brief reduction in capacity
- `maxUnavailable: 25%, maxSurge: 25%` — Balanced approach for large deployments

### spec.template.spec.containers.readinessProbe

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Critical for CI/CD**: The readiness probe is what makes `maxUnavailable: 0` actually work. Kubernetes only sends traffic to pods that pass their readiness probe. During a rollout, a new pod must respond with HTTP 200 on `GET /` before the Service routes traffic to it.

**`initialDelaySeconds: 5`** — Wait 5 seconds after the container starts before the first probe. Prevents premature failures during app startup.

**`periodSeconds: 5`** — Check every 5 seconds. A faster period means quicker detection of readiness (and quicker rollouts), but more probe traffic.

**Why this matters for CI**: Without a readiness probe, Kubernetes marks pods Ready immediately after the container starts — before your app has finished initializing. This causes 502 errors during deployments as traffic hits pods that aren't ready yet.

### replicas: 3

Three pods for high availability across nodes. In a CI/CD context, this also means rolling updates only affect 1 pod at a time (with the settings above), so the service stays available throughout the deployment.

---

## GitLab CI — Deploying to Kubernetes

```yaml
stages:
  - build
  - deploy
  - verify
  - rollback

variables:
  K8S_NAMESPACE: gitlab-ci-scenarios
  DEPLOYMENT_NAME: k8s-deploy-demo

deploy-to-cluster:
  stage: deploy
  image: bitnami/kubectl:latest
  before_script:
    # $KUBECONFIG is a "File" type variable set in GitLab UI
    # It contains the full kubeconfig YAML — written to a temp file by GitLab Runner
    - kubectl cluster-info
  script:
    # Update image tag — triggers rolling update
    - kubectl set image deployment/$DEPLOYMENT_NAME
        app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        -n $K8S_NAMESPACE

    # Block until rollout completes (or timeout)
    - kubectl rollout status deployment/$DEPLOYMENT_NAME
        -n $K8S_NAMESPACE
        --timeout=120s
  environment:
    name: production
    url: https://app.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### KUBECONFIG as a File Variable

The `$KUBECONFIG` variable must be configured in **GitLab UI > Settings > CI/CD > Variables**:
- **Type**: File (not String)
- **Value**: Your kubeconfig file contents
- **Protected**: Yes (production clusters only)
- **Masked**: No (file type variables can't be masked)

When the job starts, GitLab Runner writes the kubeconfig content to a temporary file and sets `$KUBECONFIG` to that file path. `kubectl` automatically reads this path.

### kubectl set image

```yaml
- kubectl set image deployment/$DEPLOYMENT_NAME
    app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    -n $K8S_NAMESPACE
```

Updates the container image tag in the Deployment spec. Kubernetes detects the spec change and starts a rolling update. The image tag `$CI_COMMIT_SHA` is the exact Git commit SHA — every deployment is traceable back to a specific commit.

### kubectl rollout status

```yaml
- kubectl rollout status deployment/$DEPLOYMENT_NAME
    -n $K8S_NAMESPACE --timeout=120s
```

**This command makes the CI job wait for the rollout.** Without it, the CI job exits immediately after `kubectl set image`, and the pipeline shows "success" even if pods are crash-looping. With `rollout status`, the job only exits 0 if all pods are Running and Ready within the timeout. If the rollout fails (image pull error, crash loop), the job fails, and you can trigger a rollback.

---

## Helm-Based Deployment Pattern

```yaml
deploy-helm:
  stage: deploy
  image: alpine/helm:3.14
  script:
    - helm upgrade --install $DEPLOYMENT_NAME ./chart
        --namespace $K8S_NAMESPACE
        --set image.repository=$CI_REGISTRY_IMAGE
        --set image.tag=$CI_COMMIT_SHA
        --set replicaCount=3
        --atomic                  # Roll back automatically on failure
        --timeout 5m              # Maximum wait time
        --wait                    # Wait for all resources to be ready
  environment:
    name: production
```

### --atomic

If the Helm upgrade fails (any resource fails to become Ready), Helm automatically rolls back to the previous release. This gives you automatic rollback without writing a separate rollback job.

### --wait

Helm waits for all pods, services, and other resources to reach Ready state before the command exits. Combined with `--atomic`, this means: "deploy the new version, wait for it to be healthy, and if it's not, roll back automatically."

---

## Manual Rollback Job

```yaml
rollback:
  stage: rollback
  image: bitnami/kubectl:latest
  when: manual                    # Only runs when manually triggered
  allow_failure: true
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    - kubectl rollout undo deployment/$DEPLOYMENT_NAME -n $K8S_NAMESPACE
    - kubectl rollout status deployment/$DEPLOYMENT_NAME -n $K8S_NAMESPACE --timeout=120s
```

### when: manual

The rollback job only runs when explicitly triggered by a user in the GitLab UI. It appears in the pipeline as a paused job with a "play" button. This gives you a one-click rollback without re-running the entire pipeline.

---

## Deployment Verification Job

```yaml
verify-deployment:
  stage: verify
  image: curlimages/curl:latest
  needs: [deploy-to-cluster]
  script:
    - sleep 10  # Brief stabilization wait
    - curl -f http://k8s-deploy-demo.$K8S_NAMESPACE.svc.cluster.local/health
    - echo "Deployment verified — service is responding"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

Post-deployment verification hits the actual service endpoint. If it fails, the pipeline fails, and engineers know the deployment is unhealthy despite `rollout status` passing. Use `needs:` to run this immediately after the deploy job without waiting for the full stage to complete.

---

## Key Takeaways

- **`maxUnavailable: 0`**: Zero-downtime rollout — new pods must be Ready before old ones are killed
- **`readinessProbe`**: What makes zero-downtime work — pods only receive traffic after this passes
- **`kubectl rollout status --timeout`**: Makes the CI job wait and fail if the rollout fails — critical for detecting broken deployments in CI
- **`KUBECONFIG` as File variable**: The correct way to pass cluster credentials to CI jobs
- **`kubectl set image ... $CI_COMMIT_SHA`**: Traceable deployments — every image tag links to a specific commit
- **`helm --atomic`**: Automatic rollback on deployment failure — no separate rollback job needed
- **`when: manual`** rollback job: One-click emergency rollback available in every pipeline run
