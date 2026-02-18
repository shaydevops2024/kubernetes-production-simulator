# GitLab CI YAML Explanation - Production Release Pipeline

This guide explains the Kubernetes manifests and GitLab CI pipeline patterns for a production release pipeline — covering canary deployments, stable deployments, the traffic split between them, and the GitLab release management workflow.

---

## The Stable Deployment (stable-deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-demo
  namespace: gitlab-ci-scenarios
  labels:
    app: release-demo
    version: v1.0.0
    scenario: release-pipeline
spec:
  replicas: 3
  selector:
    matchLabels:
      app: release-demo
      track: stable             # Selector includes track label
  template:
    metadata:
      labels:
        app: release-demo
        track: stable           # Stable pods have this label
        version: v1.0.0
        scenario: release-pipeline
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          env:
            - name: VERSION
              value: "v1.0.0"
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
  name: release-demo
  namespace: gitlab-ci-scenarios
  labels:
    app: release-demo
spec:
  selector:
    app: release-demo           # Selects BOTH stable and canary pods
  ports:
    - port: 80
      targetPort: 80
```

### selector: app: release-demo (Service)

```yaml
selector:
  app: release-demo
```

The Service selects **all pods** with `app: release-demo` — both stable and canary. This is the traffic split mechanism: by having 3 stable pods and 1 canary pod, ~25% of requests go to canary. No Ingress rules or load balancer config needed for basic canary — the ratio of pods controls the ratio of traffic.

### track: stable label

```yaml
labels:
  track: stable
```

The `track` label differentiates stable from canary pods. The Deployment's `selector.matchLabels` includes `track: stable`, so this Deployment only manages stable pods. The canary Deployment has `track: canary` and manages only canary pods. Without the `track` label in the selector, both Deployments would fight over the same pods.

### env.VERSION

```yaml
env:
  - name: VERSION
    value: "v1.0.0"
```

An environment variable injected into the container. In a real app, this would be read and returned in health/info endpoints. This allows you to verify which version is running:
```bash
curl http://service/version  # Returns {"version": "v1.0.0"}
```

---

## The Canary Deployment (canary-deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-demo-canary
  namespace: gitlab-ci-scenarios
  labels:
    app: release-demo
    version: v1.1.0
    track: canary
    scenario: release-pipeline
spec:
  replicas: 1                   # 1 canary vs 3 stable = 25% canary traffic
  selector:
    matchLabels:
      app: release-demo
      track: canary             # Only manages canary pods
  template:
    metadata:
      labels:
        app: release-demo
        track: canary
        version: v1.1.0
        scenario: release-pipeline
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          env:
            - name: VERSION
              value: "v1.1.0"
            - name: CANARY
              value: "true"     # Flag to identify canary requests in logs
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
```

### replicas: 1 (canary) vs replicas: 3 (stable)

The traffic split is determined by the pod count ratio:
- 3 stable + 1 canary = **25% canary traffic**
- 3 stable + 3 canary = **50% canary traffic**
- 0 stable + 3 canary = **100% canary (full rollout)**

To promote the canary to full production: scale canary to 3, scale stable to 0, then update stable's image to v1.1.0 and scale back to 3.

### CANARY: "true" env var

```yaml
env:
  - name: CANARY
    value: "true"
```

Canary pods identify themselves. Application code can log this flag, letting you filter metrics/logs by canary vs stable. In monitoring tools (Prometheus, Grafana), you'd create separate dashboards for `track=canary` pods to compare error rates and latency against stable pods.

### No readinessProbe in this manifest

This scenario's YAML uses a simple nginx image. In production, every deployment would have a `readinessProbe` — the canary especially needs one so traffic only reaches it after it's healthy:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 80
  initialDelaySeconds: 10
  failureThreshold: 3
```

---

## GitLab CI — Production Release Pipeline

```yaml
stages:
  - build
  - deploy-canary
  - monitor-canary
  - promote-or-rollback
  - deploy-stable
  - release

variables:
  STABLE_REPLICAS: "3"
  CANARY_REPLICAS: "1"
  K8S_NAMESPACE: gitlab-ci-scenarios

build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:canary
    - docker push $CI_REGISTRY_IMAGE:canary
  rules:
    - if: $CI_COMMIT_TAG                      # Only on version tags

deploy-canary:
  stage: deploy-canary
  image: bitnami/kubectl:latest
  script:
    - kubectl apply -f canary-deployment.yaml
    - kubectl set image deployment/release-demo-canary
        app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        -n $K8S_NAMESPACE
    - kubectl rollout status deployment/release-demo-canary
        -n $K8S_NAMESPACE --timeout=120s
  environment:
    name: production/canary
    url: https://app.example.com
  rules:
    - if: $CI_COMMIT_TAG
```

### rules: if: $CI_COMMIT_TAG

```yaml
rules:
  - if: $CI_COMMIT_TAG
```

Release pipelines typically only run on **Git tags** (e.g., `v1.1.0`). Tags represent intentional releases — unlike branch pushes, which happen continuously. `$CI_COMMIT_TAG` is non-empty only when the pipeline was triggered by a tag push.

---

## Canary Monitoring Stage

```yaml
monitor-canary:
  stage: monitor-canary
  image: curlimages/curl:latest
  script:
    - echo "Monitoring canary for 5 minutes..."
    - |
      for i in $(seq 1 10); do
        sleep 30
        CANARY_ERRORS=$(curl -s http://prometheus:9090/api/v1/query \
          --data-urlencode 'query=rate(http_requests_total{track="canary",status=~"5.."}[1m])' \
          | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['result'][0]['value'][1])")

        echo "Canary error rate: $CANARY_ERRORS"

        if (( $(echo "$CANARY_ERRORS > 0.01" | bc -l) )); then
          echo "❌ Canary error rate too high: $CANARY_ERRORS > 1%"
          exit 1
        fi
      done
    - echo "✅ Canary healthy after 5 minutes"
```

This job **blocks the pipeline** while monitoring canary metrics. If error rates spike during the monitoring window, the job fails — preventing promotion and triggering rollback. This is automated canary analysis.

---

## Promote or Rollback Gate

```yaml
promote-canary:
  stage: promote-or-rollback
  image: bitnami/kubectl:latest
  when: manual                  # Human decision after reviewing canary metrics
  script:
    - echo "Promoting canary to stable..."
    # Scale canary to full traffic
    - kubectl scale deployment/release-demo-canary --replicas=$STABLE_REPLICAS -n $K8S_NAMESPACE
    # Scale down stable
    - kubectl scale deployment/release-demo --replicas=0 -n $K8S_NAMESPACE

rollback-canary:
  stage: promote-or-rollback
  image: bitnami/kubectl:latest
  when: manual
  allow_failure: true
  script:
    - echo "Rolling back canary..."
    - kubectl delete deployment release-demo-canary -n $K8S_NAMESPACE --ignore-not-found
    - kubectl scale deployment/release-demo --replicas=$STABLE_REPLICAS -n $K8S_NAMESPACE
```

Two manual jobs side by side: **promote** (full rollout) or **rollback** (remove canary, restore stable). Both are `when: manual` — a human decides based on canary metrics and business signals. Neither runs automatically.

---

## GitLab Release (release: keyword)

```yaml
create-release:
  stage: release
  image: registry.gitlab.com/gitlab-org/release-cli:latest
  needs: [deploy-stable]
  rules:
    - if: $CI_COMMIT_TAG
  release:
    tag_name: $CI_COMMIT_TAG              # e.g., v1.1.0
    name: "Release $CI_COMMIT_TAG"
    description: './CHANGELOG.md'          # Release notes from file
    assets:
      links:
        - name: "Docker Image"
          url: "https://registry.gitlab.com/mygroup/myapp/container_registry"
        - name: "Kubernetes Manifests"
          url: "$CI_PROJECT_URL/-/tree/$CI_COMMIT_TAG/k8s/"
```

### release: keyword

The `release:` block creates a **GitLab Release** — a tagged snapshot with release notes, linked assets, and download links. This appears in Project > Releases and can be referenced in changelogs, Slack notifications, and deployment tracking.

### release.description: './CHANGELOG.md'

Reads the release notes from a file in the repository. Keep a `CHANGELOG.md` updated per release — the release pipeline reads it automatically, creating well-documented releases without manual editing.

---

## Traffic Split Summary

| Pods | Canary % | Use case |
|------|----------|----------|
| stable=3, canary=1 | 25% | Initial canary — small exposure |
| stable=2, canary=2 | 50% | Expanded canary — growing confidence |
| stable=1, canary=3 | 75% | Near-full canary — final validation |
| stable=0, canary=4 | 100% | Full promotion (rename canary→stable) |

---

## Key Takeaways

- **`track: stable` / `track: canary` labels**: Differentiates which Deployment manages which pods while sharing the same Service selector
- **`selector: app: release-demo`** (Service): Routes to ALL pods (stable + canary) — pod count ratio = traffic split
- **Replicas ratio**: 3 stable + 1 canary = 25% canary traffic, no Ingress changes needed
- **`rules: if: $CI_COMMIT_TAG`**: Release pipelines trigger on version tags, not branch pushes
- **`CANARY: "true"` env var**: Flag canary pods for metric/log filtering in monitoring tools
- **Monitor-then-gate pattern**: Automated metric check → manual promote/rollback decision
- **`release:` keyword**: Create GitLab Releases with changelogs and asset links as the final pipeline step
- **Two manual jobs** (promote + rollback): Explicit human choices — never automatic promotion to full production
