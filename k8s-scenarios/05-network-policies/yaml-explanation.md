# YAML Files Explanation - Network Policies Scenario

This guide explains each YAML file in detail, breaking down every field and providing context for why and how to write them.

---

## 🔒 network-policy.yaml

### What is a Network Policy?
A NetworkPolicy is a Kubernetes resource that controls network traffic between pods at the IP address or port level. It acts as a firewall, implementing network segmentation and zero-trust security within your cluster.

### YAML Structure Breakdown:

```yaml
apiVersion: networking.k8s.io/v1
```
**What it is:** The API version for NetworkPolicy resources
**Options:** `networking.k8s.io/v1` is the current stable version
**Why:** NetworkPolicies are part of the `networking.k8s.io` API group

```yaml
kind: NetworkPolicy
```
**What it is:** Declares this is a NetworkPolicy resource
**Purpose:** Define firewall rules for pod-to-pod communication

```yaml
metadata:
  name: netpol-demo-policy
  namespace: scenarios
```
**What it is:** NetworkPolicy metadata
- `name`: Unique name for this policy
- `namespace`: Must be in the same namespace as the pods it protects

**Important:** NetworkPolicies are **namespace-scoped** - they only affect pods in their namespace

```yaml
spec:
  podSelector:
    matchLabels:
      app: netpol-demo
      role: backend
```
**What it is:** Selects which pods this policy applies to
**Critical:** This defines the **target pods** that will have restricted traffic

**How it works:**
- Finds all pods with BOTH labels: `app: netpol-demo` AND `role: backend`
- Only those pods will have the ingress/egress rules applied
- Other pods in the namespace are unaffected

**Options:**
```yaml
# Option 1: Select specific pods (used here)
podSelector:
  matchLabels:
    app: netpol-demo
    role: backend

# Option 2: Select ALL pods in namespace
podSelector: {}

# Option 3: Complex selection
podSelector:
  matchExpressions:
  - key: app
    operator: In
    values: [netpol-demo, other-app]
```

**⚠️ Empty podSelector `{}` means ALL pods in namespace!**

```yaml
  policyTypes:
  - Ingress
```
**What it is:** Types of traffic this policy controls

**Options:**
1. **Ingress** (used here): Controls **incoming** traffic to selected pods
2. **Egress**: Controls **outgoing** traffic from selected pods
3. **Both**: Control both directions
   ```yaml
   policyTypes:
   - Ingress
   - Egress
   ```

**Default Behavior (CRITICAL!):**
- Once a NetworkPolicy is applied with `Ingress`, ALL ingress traffic is **denied by default**
- Only explicitly allowed connections work
- This is **zero-trust networking** - deny all, allow specific

```yaml
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: backend
    ports:
    - protocol: TCP
      port: 80
```
**What it is:** Ingress rules - defines WHO can connect and on WHICH ports

### Breaking down the ingress rules:

**`ingress:`** - List of allowed incoming traffic rules

**`- from:`** - Source selector (who can connect)

**`- podSelector:`** - Select pods by labels
```yaml
matchLabels:
  role: backend
```
**Meaning:** Only pods with `role: backend` label can connect

**Alternative source selectors:**
```yaml
# Option 1: Pods in same namespace (used here)
- from:
  - podSelector:
      matchLabels:
        role: backend

# Option 2: Pods from specific namespace
- from:
  - namespaceSelector:
      matchLabels:
        environment: production

# Option 3: Pods from namespace AND with label
- from:
  - namespaceSelector:
      matchLabels:
        environment: production
    podSelector:
      matchLabels:
        role: frontend

# Option 4: Specific IP blocks (external sources)
- from:
  - ipBlock:
      cidr: 172.17.0.0/16
      except:
      - 172.17.1.0/24

# Option 5: Multiple sources (OR logic)
- from:
  - podSelector:
      matchLabels:
        role: frontend
  - podSelector:
      matchLabels:
        role: backend
```

**`ports:`** - Which ports are allowed
```yaml
- protocol: TCP
  port: 80
```
**Meaning:** Allow TCP traffic on port 80 only

**Port options:**
```yaml
# Option 1: Single port (used here)
ports:
- protocol: TCP
  port: 80

# Option 2: Multiple ports
ports:
- protocol: TCP
  port: 80
- protocol: TCP
  port: 443

# Option 3: Named ports
ports:
- protocol: TCP
  port: http  # References containerPort name

# Option 4: UDP protocol
ports:
- protocol: UDP
  port: 53
```

---

## 🚀 deployment.yaml

### YAML Structure Breakdown:

```yaml
apiVersion: apps/v1
kind: Deployment
```
**What it is:** Standard Deployment resource
**Purpose:** Manages the backend application pods

```yaml
metadata:
  name: netpol-demo-app
  namespace: scenarios
  labels:
    app: netpol-demo
    scenario: "06"
```
**What it is:** Deployment metadata
- `name`: Unique name for the deployment
- `namespace`: Must match NetworkPolicy namespace
- `labels`: Organize and identify the deployment

```yaml
spec:
  replicas: 2
```
**What it is:** Number of pod replicas
**Why 2?** High availability - if one pod fails, the other continues serving traffic

```yaml
  selector:
    matchLabels:
      app: netpol-demo
      role: backend
```
**What it is:** How Deployment finds its pods
**Critical:** Must match `template.metadata.labels` exactly

```yaml
  template:
    metadata:
      labels:
        app: netpol-demo
        role: backend
```
**What it is:** Pod template labels
**CRITICAL for NetworkPolicy:**
- `app: netpol-demo` - Matches NetworkPolicy podSelector (policy applies to these pods)
- `role: backend` - Matches NetworkPolicy podSelector AND ingress from selector

**How labels work with NetworkPolicy:**
```
NetworkPolicy podSelector:     app=netpol-demo, role=backend  ← Applies to these pods
Pod labels:                    app=netpol-demo, role=backend  ← These pods are protected
NetworkPolicy ingress from:    role=backend                   ← These pods can connect
```

**In this scenario:**
- Pods with `app: netpol-demo` AND `role: backend` are **protected** by the policy
- Only pods with `role: backend` can **connect** to them
- Since the pods themselves have `role: backend`, they can connect to each other

```yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
        ports:
        - containerPort: 80
```
**What it is:** Container specification
- `name`: Container name
- `image`: Nginx web server (lightweight Alpine version)
- `containerPort: 80`: HTTP port

**Why nginx?**
- Simple HTTP server for testing connectivity
- Returns HTTP 200 response when accessible
- Easy to test with wget/curl

---

## 🌐 service.yaml

### YAML Structure Breakdown:

```yaml
apiVersion: v1
kind: Service
```
**What it is:** Service resource to expose pods
**Purpose:** Provides stable DNS name and load balancing

```yaml
metadata:
  name: netpol-demo-service
  namespace: scenarios
```
**What it is:** Service metadata
- `name`: DNS name (`netpol-demo-service.scenarios.svc.cluster.local`)
- `namespace`: Must match pods

```yaml
spec:
  selector:
    app: netpol-demo
```
**What it is:** Selects which pods to route traffic to
**Note:** Only uses `app: netpol-demo`, not `role: backend`

**Why not include `role: backend`?**
- Service selector is about **routing traffic**, not security
- NetworkPolicy handles security (which pods can access)
- Service just needs to find the backend pods to route traffic to

**Traffic flow:**
```
Client pod → Service (netpol-demo-service) → Backend pods
                ↓
         NetworkPolicy checks:
         - Is client pod allowed? (has role: backend label?)
         - If YES → Allow connection
         - If NO → Block connection
```

```yaml
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
```
**What it is:** Port mapping
- `port: 80`: Service listens on port 80
- `targetPort: 80`: Forwards to pod port 80
- `protocol: TCP`: TCP protocol

---

## 🔐 How Everything Works Together

### Complete Flow - Setup:

1. **Apply deployment.yaml:**
   - Creates 2 pods with labels: `app: netpol-demo`, `role: backend`
   - Pods run nginx on port 80
   - Pods can freely communicate (no policy yet)

2. **Apply service.yaml:**
   - Creates Service `netpol-demo-service`
   - Service selects pods with `app: netpol-demo`
   - DNS entry created: `netpol-demo-service` → ClusterIP
   - Any pod can access the service (no restrictions yet)

3. **Apply network-policy.yaml:**
   - NetworkPolicy targets pods with `app: netpol-demo` AND `role: backend`
   - **Default deny** for ingress traffic to those pods
   - **Only allow** ingress from pods with `role: backend`
   - Now only backend pods can access each other!

### Complete Flow - Testing:

**Test 1: Unlabeled pod (should be blocked)**
```bash
kubectl run test-unauthorized --rm -i --tty --image=busybox:1.28 -n scenarios \
  -- wget -qO- --timeout=2 http://netpol-demo-service
```
**What happens:**
1. Pod created with NO `role` label
2. Pod tries to connect to Service
3. Service routes to backend pods
4. **NetworkPolicy blocks** - pod lacks `role: backend` label
5. Connection times out → BLOCKED ✅

**Test 2: Backend-labeled pod (should succeed)**
```bash
kubectl run test-authorized --rm -i --tty --labels=role=backend --image=busybox:1.28 -n scenarios \
  -- wget -qO- --timeout=2 http://netpol-demo-service
```
**What happens:**
1. Pod created WITH `role: backend` label
2. Pod tries to connect to Service
3. Service routes to backend pods
4. **NetworkPolicy allows** - pod has `role: backend` label ✅
5. Connection succeeds → HTTP 200 response

---

## 🎯 Best Practices & Production Recommendations

### 1. Start with Default Deny
✅ **Recommended approach:**
```yaml
# Step 1: Deny all traffic to your pods
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}  # All pods in namespace
  policyTypes:
  - Ingress
  # No ingress rules = deny all

# Step 2: Add specific allow rules
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
spec:
  podSelector:
    matchLabels:
      role: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
```

**Why?**
- Secure by default
- Explicit allow rules are easier to audit
- Prevents accidental exposure

### 2. Use Meaningful Labels
✅ **Good labels:**
```yaml
labels:
  app: payment-service
  role: backend
  tier: api
  environment: production
```

❌ **Bad labels:**
```yaml
labels:
  name: pod1
  version: v2
```

**Why meaningful labels?**
- Clear intent in NetworkPolicy rules
- Easy to understand security boundaries
- Self-documenting

### 3. Namespace Isolation
✅ **Isolate environments with namespaces:**
```yaml
# Production namespace policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-from-other-namespaces
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector: {}  # Only from same namespace
```

**Benefits:**
- Production isolated from dev/test
- Prevents cross-environment data leaks
- Clear security boundaries

### 4. Egress Policies for Data Exfiltration Prevention
✅ **Control outbound traffic:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-egress
spec:
  podSelector:
    matchLabels:
      role: backend
  policyTypes:
  - Egress
  egress:
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # Allow to database
  - to:
    - podSelector:
        matchLabels:
          role: database
    ports:
    - protocol: TCP
      port: 5432
  # Block everything else!
```

**Why?**
- Prevents compromised pods from exfiltrating data
- Limits blast radius of security incidents
- Enforces intended communication patterns

### 5. Common Patterns

**Pattern 1: Three-tier application**
```yaml
# Allow: Frontend → Backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-allow-from-frontend
spec:
  podSelector:
    matchLabels:
      tier: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: frontend

---
# Allow: Backend → Database
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-allow-from-backend
spec:
  podSelector:
    matchLabels:
      tier: database
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: backend
    ports:
    - protocol: TCP
      port: 5432
```

**Pattern 2: Allow from Ingress Controller**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress
spec:
  podSelector:
    matchLabels:
      expose: external
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 80
```

**Pattern 3: Allow external IPs**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external-api
spec:
  podSelector:
    matchLabels:
      role: api-gateway
  ingress:
  - from:
    - ipBlock:
        cidr: 203.0.113.0/24  # Office IP range
    ports:
    - protocol: TCP
      port: 443
```

### 6. Testing NetworkPolicies

✅ **Before production:**
```bash
# 1. Deploy policy in test namespace first
kubectl apply -f network-policy.yaml -n test

# 2. Test expected connections work
kubectl run test-allowed -n test --labels=role=frontend \
  --image=busybox -- wget -qO- backend-service

# 3. Test blocked connections fail
kubectl run test-blocked -n test \
  --image=busybox -- wget -qO- backend-service

# 4. Check logs for unexpected blocks
kubectl logs -n kube-system -l k8s-app=calico-node | grep denied

# 5. Monitor metrics
kubectl get networkpolicy -n test -w
```

### 7. CNI Plugin Requirements

⚠️ **NetworkPolicies require CNI plugin support!**

**Supported CNI plugins:**
- ✅ Calico (most popular)
- ✅ Cilium (eBPF-based, advanced features)
- ✅ Weave Net
- ✅ Antrea
- ❌ Flannel (does NOT support NetworkPolicies)
- ❌ Default Kind/Minikube CNI (usually doesn't support)

**Check CNI support:**
```bash
# Check CNI plugin
kubectl get pods -n kube-system | grep -E 'calico|cilium|weave'

# Test NetworkPolicy support
kubectl apply -f test-policy.yaml
kubectl describe networkpolicy test-policy
# Should show policy details, not errors
```

**Installing Calico on Kind:**
```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/calico.yaml
```

### 8. Debugging NetworkPolicies

**Issue 1: Policy not blocking traffic**
```bash
# Check policy is applied
kubectl get networkpolicy -n scenarios
kubectl describe networkpolicy netpol-demo-policy -n scenarios

# Check pod labels match
kubectl get pods -n scenarios --show-labels

# Check CNI plugin is installed
kubectl get pods -n kube-system | grep calico
```

**Issue 2: Policy blocking too much**
```bash
# Check all policies affecting pods
kubectl get networkpolicy -n scenarios -o yaml

# Describe specific policy
kubectl describe networkpolicy <policy-name> -n scenarios

# Check for conflicting policies
kubectl get networkpolicy --all-namespaces
```

**Issue 3: DNS not working**
```bash
# NetworkPolicies often block DNS - add egress rule:
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
```

### 9. Monitoring & Auditing

✅ **Monitor NetworkPolicy effectiveness:**
```bash
# Calico logs (if using Calico)
kubectl logs -n kube-system -l k8s-app=calico-node --tail=100 | grep denied

# Cilium logs (if using Cilium)
kubectl logs -n kube-system -l k8s-app=cilium | grep DENIED

# Check policy status
kubectl get networkpolicy --all-namespaces

# Audit which pods are protected
kubectl get pods --all-namespaces -o json | \
  jq -r '.items[] | select(.metadata.labels != null) |
    "\(.metadata.namespace)/\(.metadata.name): \(.metadata.labels)"'
```

**Prometheus metrics (Cilium):**
- `cilium_policy_enforcement_duration_seconds`
- `cilium_policy_l3_l4_ingress_denied_total`
- `cilium_policy_l3_l4_egress_denied_total`

### 10. Advanced Features

**Time-based policies (using labels + automation):**
```yaml
# Add label: maintenance-window=true during maintenance
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: maintenance-access
spec:
  podSelector:
    matchLabels:
      app: database
      maintenance-window: "true"  # Only active during maintenance
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: admin
```

**Multi-cluster policies (Cilium):**
```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: multi-cluster
spec:
  endpointSelector:
    matchLabels:
      app: global-service
  ingress:
  - fromEndpoints:
    - matchLabels:
        io.cilium.k8s.policy.cluster: cluster-1
```

---

## 🔍 Common Issues & Solutions

**Issue:** Pods can't communicate after applying NetworkPolicy
**Solution:** Add explicit allow rules for all required communication

**Issue:** DNS lookups failing
**Solution:** Add egress rule allowing DNS (UDP port 53 to kube-system)

**Issue:** NetworkPolicy seems to have no effect
**Solution:** Check CNI plugin supports NetworkPolicies (Calico, Cilium, etc.)

**Issue:** Can't connect to pods from outside cluster
**Solution:** NetworkPolicies don't affect external load balancers - check Service type

**Issue:** Policy applies to wrong pods
**Solution:** Check podSelector labels match pod labels exactly

---

## 🎓 Key Takeaways

1. **NetworkPolicies are deny-by-default** - Once applied, all traffic is blocked unless explicitly allowed
2. **Labels are critical** - podSelector and ingress/egress rules all use labels
3. **CNI plugin required** - Not all CNI plugins support NetworkPolicies (Calico, Cilium work)
4. **Namespace-scoped** - Policies only affect pods in their namespace
5. **Zero-trust networking** - Explicitly allow only required connections
6. **Test thoroughly** - Broken NetworkPolicies can break applications
7. **Combine with RBAC** - Defense in depth - network + API access control
8. **Start simple** - Begin with ingress, add egress when needed

---

## 📚 Further Reading

- **Kubernetes NetworkPolicy documentation:** https://kubernetes.io/docs/concepts/services-networking/network-policies/
- **Calico NetworkPolicy:** https://docs.tigera.io/calico/latest/network-policy/
- **Cilium NetworkPolicy:** https://docs.cilium.io/en/stable/security/policy/
- **NetworkPolicy recipes:** https://github.com/ahmetb/kubernetes-network-policy-recipes

---

*This explanation provides comprehensive insights into Kubernetes NetworkPolicies. Master these concepts to implement zero-trust networking and secure pod-to-pod communication in your clusters!*
