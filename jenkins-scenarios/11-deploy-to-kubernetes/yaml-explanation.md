# Jenkinsfile Explanation - Deploy to Kubernetes Scenario

This guide explains the Jenkinsfile patterns for deploying to Kubernetes, covering `kubectl set image`, `kubectl rollout status`, zero-downtime rolling updates, automatic rollback on failure, and health verification.

---

## 🚀 Kubernetes Deployment Strategy in Jenkinsfile

The core pattern for deploying a new image version to Kubernetes:

```groovy
stage('Deploy') {
    steps {
        sh """
            kubectl set image deployment/${DEPLOYMENT_NAME} \
              ${CONTAINER_NAME}=${REGISTRY}/${APP_NAME}:${BUILD_NUMBER} \
              -n ${NAMESPACE}
        """
        sh """
            kubectl rollout status deployment/${DEPLOYMENT_NAME} \
              -n ${NAMESPACE} \
              --timeout=120s
        """
    }
}
```

### Why `kubectl set image` instead of `kubectl apply`?

| Approach | Command | When to use |
|---|---|---|
| `set image` | `kubectl set image deployment/app app=image:tag` | Update just the container image (zero downtime) |
| `kubectl apply` | `kubectl apply -f deployment.yaml` | Apply full manifest changes |
| `kubectl patch` | `kubectl patch deployment/app -p '{"spec":...}'` | Surgical JSON patch |

**`kubectl set image`** is the standard CI/CD approach because:
- Only changes the image tag — doesn't accidentally change other fields
- Triggers a rolling update automatically
- Simple and auditable in CI/CD logs

**Full syntax:**
```bash
kubectl set image deployment/<deployment-name> \
  <container-name>=<registry>/<image>:<tag> \
  -n <namespace>
```

---

## 🔄 Kubernetes Rolling Update Strategy

The Deployment manifest controls how Kubernetes replaces pods during an image update:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-web-app
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1           # Allow up to 1 extra pod during update (3+1=4 max)
      maxUnavailable: 0     # Never take a pod down (always 3 available)
  selector:
    matchLabels:
      app: my-web-app
  template:
    metadata:
      labels:
        app: my-web-app
    spec:
      containers:
      - name: app
        image: registry.company.com/my-web-app:42
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

### `maxSurge` and `maxUnavailable` explained:

**`maxSurge: 1` (with 3 replicas):**
- Kubernetes can create up to 1 extra pod during the update
- Maximum pods at any time: 3 + 1 = 4
- Ensures new pods are running before old ones are terminated

**`maxUnavailable: 0`:**
- Zero pods can be taken offline during the update
- Always at least 3 pods serving traffic
- **Zero-downtime deployment**

**Rolling update sequence (3 replicas, maxSurge: 1, maxUnavailable: 0):**
```
Start: [v1][v1][v1]                    (3 pods, old version)
Step 1: [v1][v1][v1][v2]              (create new pod, now 4)
Step 2: [v1][v1][v2]                  (terminate one old pod, back to 3)
Step 3: [v1][v1][v2][v2]              (create another new pod, back to 4)
Step 4: [v1][v2][v2]                  (terminate another old pod)
Step 5: [v1][v2][v2][v2]              (create last new pod)
Step 6: [v2][v2][v2]                  (terminate last old pod)
Done:   [v2][v2][v2]                  (all new version, zero downtime)
```

**Alternative strategies:**

```yaml
# Recreate (causes downtime - all old pods terminated before new ones start)
strategy:
  type: Recreate

# Aggressive rolling (faster but brief reduction in capacity)
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 50%
    maxUnavailable: 25%
```

---

## ⏳ `kubectl rollout status` - The Critical Wait

```groovy
sh "kubectl rollout status deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE} --timeout=120s"
```

**What it does:** Blocks (waits) until the rollout is complete or times out. Returns:
- `exit code 0` → rollout succeeded, all pods healthy
- `exit code 1` → rollout failed or timed out

**Without this command:**
```
kubectl set image deployment/app ...   → EXIT 0 (command accepted)
Jenkins: "Deploy stage SUCCESS ✅"    ← WRONG: Pods might still be crashing!
```

**With this command:**
```
kubectl set image deployment/app ...   → triggers rolling update
kubectl rollout status ... --timeout=120s  → waits up to 120 seconds
  → Polls until: all pods running with new image + all readiness probes passing
  → If pods crash: "error: deployment exceeded its progress deadline" → EXIT 1
Jenkins: catches exit 1 → "Deploy stage FAILED ❌" → triggers rollback
```

**Options:**

```bash
# Basic wait (uses deployment's progressDeadlineSeconds from spec)
kubectl rollout status deployment/my-app -n production

# With explicit timeout (overrides deployment's progress deadline)
kubectl rollout status deployment/my-app -n production --timeout=120s

# Watch mode (stream progress to console)
kubectl rollout status deployment/my-app -n production -w

# Quiet mode (only print on change)
kubectl rollout status deployment/my-app -n production --timeout=120s 2>&1
```

**What Jenkins sees during a successful rollout:**
```
Waiting for deployment "my-app" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "my-app" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "my-app" rollout to finish: 1 old replicas are pending termination...
deployment "my-app" successfully rolled out
```

---

## ↩️ Automatic Rollback on Failure

```groovy
post {
    failure {
        sh "kubectl rollout undo deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}"
        echo "Rollback triggered - deployment reverted to previous version"
    }
}
```

**What `kubectl rollout undo` does:**
- Reverts the deployment to the **previous revision** (the last working version)
- Kubernetes keeps a history of deployment revisions (controlled by `revisionHistoryLimit`)
- Does NOT create a new deployment — rolls back to the exact previous state

**How it works:**
```
Before deploy:  Revision 5 (v1.0) ← current, Revision 4 (v0.9), Revision 3 (v0.8)
Deploy fails:   Revision 6 (v1.1) ← broken
Rollback runs:  kubectl rollout undo → Revision 6 removed, Revision 5 (v1.0) becomes current
After rollback: Revision 5 (v1.0) ← current
```

**Advanced rollback options:**

```bash
# Rollback to the previous revision (default)
kubectl rollout undo deployment/my-app -n production

# Rollback to a specific revision number
kubectl rollout undo deployment/my-app -n production --to-revision=3

# View revision history before rolling back
kubectl rollout history deployment/my-app -n production
```

**Rollback history output:**
```
REVISION  CHANGE-CAUSE
1         Initial deployment
2         Update to v1.0
3         Update to v1.1
4         Update to v1.2 ← current
```

**Control history size in Deployment spec:**
```yaml
spec:
  revisionHistoryLimit: 5    # Keep the last 5 revisions (default: 10)
```

---

## 🏥 Readiness and Liveness Probes

The deployment manifest includes probes that `kubectl rollout status` monitors:

```yaml
containers:
- name: app
  image: registry.company.com/my-web-app:42
  readinessProbe:
    httpGet:
      path: /health/ready       # HTTP GET to this endpoint
      port: 8080
    initialDelaySeconds: 10     # Wait 10s before first probe
    periodSeconds: 5            # Check every 5 seconds
    failureThreshold: 3         # Fail after 3 consecutive failures
    successThreshold: 1         # Pass after 1 success
  livenessProbe:
    httpGet:
      path: /health/live
      port: 8080
    initialDelaySeconds: 30
    periodSeconds: 10
    failureThreshold: 3
```

### Readiness vs Liveness:

| Probe | Purpose | On failure |
|---|---|---|
| `readinessProbe` | Is the pod ready to serve traffic? | Pod removed from Service endpoints (no traffic) |
| `livenessProbe` | Is the pod still alive? | Pod restarted by kubelet |

**For rolling updates:**
- `kubectl rollout status` waits until the **readiness probe** passes for the new pods
- A failing readiness probe causes the rollout to stall → timeout → `kubectl rollout status` exits 1 → Jenkins fails → rollback runs

**This is the safety net:**
```
New pod starts
→ Readiness probe fails (app not ready yet)
→ Pod stays out of Service rotation (no traffic)
→ After initialDelaySeconds: probes start
→ Probe succeeds: pod added to Service, old pod removed
→ All new pods ready: rollout complete ✅

OR:

New pod starts → repeatedly crashes (OOMKilled, config error)
→ Readiness probe never passes
→ Rolling update stalls (maxUnavailable: 0 means can't remove old pods)
→ After progressDeadlineSeconds (or --timeout): kubectl rollout status exits 1
→ Jenkins marks deploy FAILED → post{failure} runs rollback ✅
```

---

## 🔍 Kubernetes Deploy Health Check Pattern

```groovy
stage('Verify') {
    steps {
        script {
            // Wait for all pods to be running
            sh """
                kubectl wait pod \
                  -l app=${APP_NAME} \
                  -n ${NAMESPACE} \
                  --for=condition=Ready \
                  --timeout=120s
            """

            // Optional: run a smoke test against the service
            def podName = sh(
                script: "kubectl get pods -l app=${APP_NAME} -n ${NAMESPACE} -o name | head -1",
                returnStdout: true
            ).trim()

            sh """
                kubectl exec ${podName} -n ${NAMESPACE} -- \
                  curl -sf http://localhost:8080/health
            """
        }
    }
}
```

---

## 📊 Complete Deploy-to-Kubernetes Jenkinsfile

```groovy
pipeline {
    agent any

    environment {
        REGISTRY        = 'registry.company.com'
        APP_NAME        = 'my-web-app'
        CONTAINER_NAME  = 'app'
        DEPLOYMENT_NAME = 'my-web-app'
        NAMESPACE       = 'production'
        IMAGE_TAG       = "${BUILD_NUMBER}"
        FULL_IMAGE      = "${REGISTRY}/${APP_NAME}:${IMAGE_TAG}"
    }

    stages {
        stage('Build') {
            steps {
                sh "docker build -t ${FULL_IMAGE} ."
                withCredentials([usernamePassword(
                    credentialsId: 'registry-creds',
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh "docker login ${REGISTRY} -u ${REG_USER} -p ${REG_PASS}"
                    sh "docker push ${FULL_IMAGE}"
                }
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([file(credentialsId: 'k8s-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl set image deployment/${DEPLOYMENT_NAME} \
                          ${CONTAINER_NAME}=${FULL_IMAGE} \
                          -n ${NAMESPACE}
                    """
                    sh """
                        kubectl rollout status deployment/${DEPLOYMENT_NAME} \
                          -n ${NAMESPACE} \
                          --timeout=120s
                    """
                }
            }
        }

        stage('Verify') {
            steps {
                withCredentials([file(credentialsId: 'k8s-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        kubectl wait pod \
                          -l app=${APP_NAME} \
                          -n ${NAMESPACE} \
                          --for=condition=Ready \
                          --timeout=60s
                    """
                }
            }
        }
    }

    post {
        failure {
            withCredentials([file(credentialsId: 'k8s-kubeconfig', variable: 'KUBECONFIG')]) {
                sh "kubectl rollout undo deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}"
            }
            echo "Deployment failed. Rolled back to previous version."
        }
        always {
            sh "docker rmi ${FULL_IMAGE} || true"
            cleanWs()
        }
    }
}
```

---

## 🎯 Key Takeaways

1. **`kubectl set image`** updates only the container image — the safest way to deploy new versions
2. **`kubectl rollout status --timeout`** blocks until the rollout succeeds or fails — NEVER skip this
3. **`maxSurge: 1, maxUnavailable: 0`** = zero-downtime rolling update (always 3+ pods serving)
4. **`post { failure { kubectl rollout undo ... } }`** = automatic rollback when deploy fails
5. **`kubectl rollout undo --to-revision=N`** = rollback to a specific historical version
6. **Readiness probes** are the integration point between Kubernetes and `kubectl rollout status`
7. **Store kubeconfig as a Jenkins secret file** (`withCredentials([file(...)])`) for secure cluster access
8. **`kubectl wait --for=condition=Ready`** verifies all pods are healthy after the rollout

---

*The deploy-to-Kubernetes pattern (set image → rollout status → health check, with rollback on failure) is one of the most production-critical Jenkins patterns. These four steps form the foundation of safe, automated Kubernetes deployments.*
