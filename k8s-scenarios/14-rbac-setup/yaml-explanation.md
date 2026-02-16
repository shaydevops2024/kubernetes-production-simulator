# YAML Files Explanation - RBAC Setup Scenario

This scenario uses four Kubernetes configuration files to demonstrate Role-Based Access Control (RBAC) for fine-grained permission management.

---

## ServiceAccount Configuration (serviceaccount.yaml)

### apiVersion: v1
**What it is:** Specifies which version of the Kubernetes API to use for this resource.

**Why v1:** ServiceAccounts are part of the core Kubernetes API. The "v1" indicates this is a stable, production-ready version.

**Options:**
- `v1` - Stable API for ServiceAccounts (always use this)
- Older beta versions are deprecated and no longer supported

---

## kind: ServiceAccount
**What it is:** Defines the type of Kubernetes resource being created.

**Why ServiceAccount:** ServiceAccounts provide an identity for processes running in pods to authenticate with the Kubernetes API server.

**Key Use Cases:**
- **Pod Identity:** Give pods a specific identity instead of using the default ServiceAccount
- **API Authentication:** Allow pods to make authenticated requests to the Kubernetes API
- **Permission Scoping:** Assign specific permissions to different applications
- **Service-to-Service Auth:** Enable secure communication between microservices

**Alternatives:**
- `User Account` - For human users (managed externally, not in Kubernetes)
- Default ServiceAccount - Automatically created in each namespace (has minimal permissions)

---

## metadata.name: rbac-demo-sa
**Purpose:** The unique identifier for this ServiceAccount within its namespace.

**Naming Best Practices:**
- Use lowercase alphanumeric characters and hyphens only
- Make it descriptive of the application or purpose (e.g., `api-service-sa`, `db-backup-sa`)
- Suffix with `-sa` to clearly identify it as a ServiceAccount
- Max 253 characters

**How it's referenced:**
- In pod specs: `serviceAccountName: rbac-demo-sa`
- In RBAC bindings: `system:serviceaccount:scenarios:rbac-demo-sa`

---

## metadata.namespace: scenarios
**Purpose:** Specifies which namespace the ServiceAccount belongs to.

**Why Namespaces Matter:**
- **Isolation:** ServiceAccounts are namespace-scoped resources
- **Organization:** Group related resources together
- **Access Control:** Namespace-level RBAC policies
- **Multi-tenancy:** Separate different teams or environments

**Important Notes:**
- ServiceAccounts can only be used by pods in the same namespace
- To reference a ServiceAccount: `system:serviceaccount:<namespace>:<name>`
- Cross-namespace access requires ClusterRole/ClusterRoleBinding

---

## Role Configuration (role.yaml)

### apiVersion: rbac.authorization.k8s.io/v1
**What it is:** The API version for RBAC resources.

**Why rbac.authorization.k8s.io/v1:** RBAC resources belong to a specialized API group. The `v1` version has been stable since Kubernetes 1.8.

**Options:**
- `rbac.authorization.k8s.io/v1` - Stable, production-ready (always use this)
- `rbac.authorization.k8s.io/v1beta1` - Deprecated, removed in Kubernetes 1.22+

---

## kind: Role
**What it is:** Defines a set of permissions within a specific namespace.

**Why Use Roles:**
- **Namespace-Scoped:** Permissions apply only within one namespace
- **Least Privilege:** Grant only the permissions needed for a specific task
- **Reusable:** Can be bound to multiple ServiceAccounts or users
- **Auditable:** Clear definition of what actions are allowed

**Role vs ClusterRole:**
| Feature | Role | ClusterRole |
|---------|------|-------------|
| Scope | Single namespace | Cluster-wide |
| Resources | Namespace resources only | Cluster + namespace resources |
| Use Case | App permissions | Admin tasks, cluster resources |
| Binding | RoleBinding | ClusterRoleBinding or RoleBinding |

**When to use Role:**
- Application needs permissions within its namespace only
- Following principle of least privilege
- Multi-tenant environments where teams should be isolated

**When to use ClusterRole:**
- Need access to cluster-scoped resources (nodes, namespaces, PVs)
- Admin or operator tasks
- Cross-namespace access required

---

## metadata.name: rbac-demo-role
**Purpose:** Unique name for this Role within the namespace.

**Naming Best Practices:**
- Describe the permissions or purpose: `pod-reader`, `deployment-manager`, `secrets-admin`
- Use suffixes like `-role` or `-viewer`/`-editor`/`-admin` to indicate permission level
- Keep it descriptive but concise

---

## spec.rules
**Purpose:** Defines the permissions this Role grants.

**Structure:** A list of rules, each specifying allowed operations on resources.

---

## Rule 1: Pod and Service Permissions

### apiGroups: [""]
**What it is:** Specifies which Kubernetes API group the resources belong to.

**Why empty string "":** Core resources (pods, services, configmaps, secrets, etc.) belong to the "core" API group, represented by an empty string.

**Common API Groups:**
- `""` (empty) - Core resources: pods, services, configmaps, secrets, persistentvolumeclaims
- `apps` - Deployments, StatefulSets, DaemonSets, ReplicaSets
- `batch` - Jobs, CronJobs
- `networking.k8s.io` - NetworkPolicies, Ingresses
- `rbac.authorization.k8s.io` - Roles, RoleBindings
- `*` - All API groups (avoid in production!)

**How to find API group:**
```bash
kubectl api-resources  # Lists all resources with their API groups
```

---

### resources: ["pods", "services"]
**What it is:** Specifies which resource types this rule applies to.

**Resource Types Explained:**
- **pods:** Individual container instances
- **services:** Network endpoints for accessing pods
- **deployments:** Declarative pod management
- **configmaps:** Configuration data
- **secrets:** Sensitive data
- **persistentvolumeclaims:** Storage requests

**Common Resource Patterns:**
- `["pods"]` - Only pods
- `["pods", "pods/log"]` - Pods and pod logs (subresources)
- `["*"]` - All resources in the API group (dangerous, avoid!)

**Subresources:**
- `pods/log` - Pod logs
- `pods/exec` - Execute commands in pods
- `pods/portforward` - Port forwarding
- `deployments/scale` - Scaling deployments

---

### verbs: ["get", "list", "watch"]
**What it is:** Specifies which actions can be performed on the resources.

**All Available Verbs:**

| Verb | Description | Example Use Case |
|------|-------------|------------------|
| **get** | Retrieve a single resource | `kubectl get pod my-pod` |
| **list** | List all resources of a type | `kubectl get pods` |
| **watch** | Watch for changes to resources | Real-time monitoring, controllers |
| **create** | Create new resources | `kubectl create -f deployment.yaml` |
| **update** | Update existing resources | `kubectl apply -f updated-config.yaml` |
| **patch** | Partially update resources | `kubectl patch pod my-pod -p '...'` |
| **delete** | Delete resources | `kubectl delete pod my-pod` |
| **deletecollection** | Delete multiple resources | `kubectl delete pods --all` |

**Permission Levels (Common Patterns):**

**Read-Only (Viewer):**
```yaml
verbs: ["get", "list", "watch"]
```
- Can view resources but not modify them
- Good for monitoring, debugging, read-only dashboards
- Lowest risk, least privilege

**Editor:**
```yaml
verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```
- Can view and modify resources
- Suitable for application deployments
- Moderate risk, requires trust

**Admin:**
```yaml
verbs: ["*"]
```
- All permissions including delete collections
- Use sparingly, only for admin roles
- High risk, maximum privilege

**This scenario uses:** `["get", "list", "watch"]` for **read-only access** - following the principle of least privilege.

---

## Rule 2: Deployment Permissions

### apiGroups: ["apps"]
**What it is:** The "apps" API group containing Deployment, StatefulSet, DaemonSet, and ReplicaSet resources.

**Why separate rule:** Different API groups require separate rules in RBAC.

---

### resources: ["deployments"]
**What it is:** Grants permissions only for Deployment resources.

**Why deployments:** Allows the ServiceAccount to view deployment information, useful for self-introspection or monitoring.

**Common "apps" resources:**
- `deployments` - Declarative pod management
- `statefulsets` - Stateful applications
- `daemonsets` - One pod per node
- `replicasets` - Pod replica management (usually managed by Deployments)

---

### verbs: ["get", "list"]
**What it is:** Read-only permissions for deployments.

**Why only get/list:** The ServiceAccount only needs to view deployments, not modify them. No "watch" here, but could be added if needed for real-time updates.

---

## RoleBinding Configuration (rolebinding.yaml)

### apiVersion: rbac.authorization.k8s.io/v1
**What it is:** API version for RBAC binding resources.

---

## kind: RoleBinding
**What it is:** Connects a Role to subjects (users, groups, or ServiceAccounts).

**Why RoleBinding:** Without a binding, the Role has no effect. RoleBinding activates the permissions.

**How it works:**
```
ServiceAccount (rbac-demo-sa)
       ↓
RoleBinding (rbac-demo-binding)
       ↓
Role (rbac-demo-role)
       ↓
Permissions (get, list, watch on pods/services/deployments)
```

**RoleBinding vs ClusterRoleBinding:**
| Feature | RoleBinding | ClusterRoleBinding |
|---------|-------------|-------------------|
| Scope | Single namespace | Cluster-wide |
| Can bind | Role or ClusterRole | ClusterRole only |
| Grants access to | Namespace resources | Cluster + all namespace resources |

**Important:** A RoleBinding can reference a ClusterRole to grant namespace-scoped access to cluster-defined roles.

---

## metadata.name: rbac-demo-binding
**Purpose:** Unique identifier for this binding within the namespace.

**Naming Best Practices:**
- Combine subject + role: `sa-name-role-name-binding`
- Or descriptive: `app-viewer-binding`, `deployer-editor-binding`
- Suffix with `-binding` for clarity

---

## spec.subjects
**Purpose:** Specifies WHO receives the permissions (users, groups, or ServiceAccounts).

**Structure:** A list of subjects to bind the Role to.

---

### subjects[0].kind: ServiceAccount
**What it is:** The type of subject receiving permissions.

**Subject Types:**

| Kind | Description | Example |
|------|-------------|---------|
| **ServiceAccount** | Pod identity | `serviceaccount:scenarios:rbac-demo-sa` |
| **User** | Human user (external auth) | `user:alice@example.com` |
| **Group** | Group of users | `group:developers` |

**When to use:**
- `ServiceAccount` - For applications, pods, automated processes (most common in production)
- `User` - For individual developers, admins (authenticated via OIDC, certificates, etc.)
- `Group` - For teams or departments (requires external auth provider)

---

### subjects[0].name: rbac-demo-sa
**What it is:** The exact name of the ServiceAccount to grant permissions to.

**Must Match:** The ServiceAccount name in serviceaccount.yaml

**Important:** ServiceAccounts are namespace-scoped, so you must also specify the namespace.

---

### subjects[0].namespace: scenarios
**What it is:** The namespace where the ServiceAccount exists.

**Why Required:** ServiceAccounts are namespace-scoped, so you must specify which namespace the ServiceAccount belongs to.

**Cross-Namespace Access:**
- RoleBinding grants permissions in its own namespace
- But can bind to a ServiceAccount from another namespace? **NO**
- ServiceAccount and RoleBinding must be in the same namespace (or use ClusterRoleBinding)

---

## spec.roleRef
**Purpose:** Specifies WHICH Role to grant (the permissions to activate).

**Immutable:** Once created, roleRef cannot be changed. You must delete and recreate the binding to change the role.

---

### roleRef.kind: Role
**What it is:** Type of role to reference.

**Options:**
- `Role` - Namespace-scoped role
- `ClusterRole` - Cluster-scoped role

**Pattern: RoleBinding + ClusterRole**
You can bind a ClusterRole with a RoleBinding to grant namespace-scoped access to cluster-defined roles:
```yaml
roleRef:
  kind: ClusterRole
  name: view  # Built-in ClusterRole
  apiGroup: rbac.authorization.k8s.io
```
This grants read-only access to resources in the namespace, using the predefined `view` ClusterRole.

---

### roleRef.name: rbac-demo-role
**What it is:** The exact name of the Role to bind.

**Must Match:** The Role name in role.yaml

**Immutable:** Cannot be changed after creation. To change the role, delete and recreate the RoleBinding.

---

### roleRef.apiGroup: rbac.authorization.k8s.io
**What it is:** The API group for the Role resource.

**Why required:** Roles belong to the RBAC API group, so this must always be `rbac.authorization.k8s.io` for Role or ClusterRole references.

---

## Deployment Configuration (deployment.yaml)

### apiVersion: apps/v1
**What it is:** API version for Deployment resources.

**Why apps/v1:** Deployments belong to the "apps" API group. This is the stable version since Kubernetes 1.9.

---

## kind: Deployment
**What it is:** Manages the lifecycle of replicated pods.

**Why Deployment for RBAC testing:**
- Creates a pod that uses the ServiceAccount
- Demonstrates how pods authenticate with the Kubernetes API
- Allows us to test permissions from inside the pod

---

## metadata.name: rbac-demo-app
**Purpose:** Name of the deployment.

**Why important:** This name is used to reference the deployment in kubectl commands:
```bash
kubectl exec -it deployment/rbac-demo-app -- /bin/sh
```

---

## metadata.labels
**Purpose:** Key-value pairs for organizing and selecting resources.

**Labels in this deployment:**
```yaml
labels:
  app: rbac-demo
```

**Why labels matter:**
- **Selection:** Services and selectors use labels to find pods
- **Organization:** Group related resources
- **Filtering:** `kubectl get pods -l app=rbac-demo`

---

## spec.replicas: 1
**Purpose:** Number of pod copies to run.

**Why 1 replica:** For RBAC testing, we only need one pod to exec into and test permissions.

**Production Considerations:**
- `1` - Development, testing, or single-instance apps
- `2+` - High availability, load distribution
- `3+` - Recommended for critical production services (allows one pod to fail while maintaining quorum)

---

## spec.selector.matchLabels
**Purpose:** Determines which pods belong to this Deployment.

**Must match:** The labels in `spec.template.metadata.labels`

**How it works:** The Deployment manages all pods with matching labels. If labels don't match, the Deployment won't control the pods.

---

## spec.template
**Purpose:** Template for creating pods.

**Structure:** Contains metadata (labels) and spec (what runs in the pod).

---

## spec.template.spec.serviceAccountName: rbac-demo-sa
**Purpose:** Specifies which ServiceAccount the pod should use.

**Why critical for RBAC:** This is how the pod gets its identity and permissions!

**How it works:**
1. Pod starts with `serviceAccountName: rbac-demo-sa`
2. Kubernetes mounts the ServiceAccount token into the pod at `/var/run/secrets/kubernetes.io/serviceaccount/token`
3. When the pod makes API requests, it uses this token for authentication
4. The API server checks the Role permissions via the RoleBinding
5. Access is granted or denied based on RBAC rules

**Default Behavior:**
- If not specified, the pod uses the `default` ServiceAccount in the namespace
- The `default` ServiceAccount has minimal permissions (usually none)

**Security Best Practice:** Always use specific ServiceAccounts for applications that need API access. Never grant extra permissions to the `default` ServiceAccount.

---

## spec.template.spec.containers
**Purpose:** Defines what runs inside the pod.

---

### containers[0].name: kubectl
**Purpose:** Name of the container within the pod.

**Why "kubectl":** Descriptive name indicating this container has kubectl installed for testing.

---

### containers[0].image: bitnami/kubectl:latest
**Purpose:** Container image to run.

**Why this image:**
- **bitnami/kubectl:** Official kubectl client in a container
- **Minimal:** Lightweight image with just kubectl and shell
- **Testing:** Perfect for testing Kubernetes API access from inside a pod

**Image Tag Best Practices:**
- ✅ `bitnami/kubectl:1.28` - Specific version (recommended for production)
- ⚠️ `bitnami/kubectl:latest` - Acceptable for testing/demos
- ❌ `kubectl` - Ambiguous, may pull from untrusted registry

**Alternative images for RBAC testing:**
- `alpine/k8s:1.28.0` - Alpine-based with kubectl
- `busybox` - Minimal shell, no kubectl (test API with curl)

---

### containers[0].command: ["sleep", "3600"]
**Purpose:** Keeps the container running so we can exec into it.

**Why sleep:**
- Default command for kubectl image would exit immediately
- `sleep 3600` keeps the container alive for 1 hour
- Allows us to exec into the pod and run kubectl commands

**Alternatives:**
```yaml
command: ["sleep", "infinity"]  # Keep running forever
command: ["sh", "-c", "while true; do sleep 30; done"]  # Loop
command: ["tail", "-f", "/dev/null"]  # Another way to keep running
```

**Production Note:** In real applications, this would be your actual application command (e.g., `python app.py`, `./server`, etc.)

---

## How These Files Work Together

### 1. ServiceAccount Provides Identity
- **Created:** `rbac-demo-sa` ServiceAccount in `scenarios` namespace
- **Purpose:** Provides identity for pods
- **Token:** Automatically created and mounted into pods using this ServiceAccount

### 2. Role Defines Permissions
- **Created:** `rbac-demo-role` Role in `scenarios` namespace
- **Permissions:**
  - **Pods:** get, list, watch
  - **Services:** get, list, watch
  - **Deployments:** get, list
- **Scope:** Only within `scenarios` namespace

### 3. RoleBinding Grants Permissions
- **Created:** `rbac-demo-binding` RoleBinding in `scenarios` namespace
- **Connects:** `rbac-demo-sa` ServiceAccount → `rbac-demo-role` Role
- **Effect:** Pods using `rbac-demo-sa` can now perform the allowed operations

### 4. Deployment Uses ServiceAccount
- **Created:** `rbac-demo-app` Deployment with 1 replica
- **ServiceAccount:** Uses `rbac-demo-sa`
- **Container:** Runs `bitnami/kubectl` image with sleep command
- **Purpose:** Allows exec into pod to test RBAC permissions

### 5. Testing Flow
```
1. Exec into pod:
   kubectl exec -it deployment/rbac-demo-app -- /bin/sh

2. Inside pod, test allowed action:
   kubectl get pods -n scenarios
   ✅ Success! (allowed by Role)

3. Inside pod, test denied action:
   kubectl create pod test --image=nginx
   ❌ Forbidden! (not allowed by Role)
```

### 6. Permission Flow
```
kubectl command in pod
       ↓
Uses ServiceAccount token (/var/run/secrets/kubernetes.io/serviceaccount/token)
       ↓
Kubernetes API authenticates: "This is rbac-demo-sa"
       ↓
Checks RoleBinding: rbac-demo-binding
       ↓
Finds Role: rbac-demo-role
       ↓
Evaluates rules: Does this action match the allowed verbs/resources?
       ↓
✅ Allow (if matches) or ❌ Deny (if doesn't match)
```

---

## RBAC Best Practices

### Principle of Least Privilege
✅ **DO:**
- Grant only the minimum permissions needed
- Use specific resource names when possible
- Prefer `get`, `list`, `watch` over `create`, `delete`
- Use namespace-scoped Roles instead of ClusterRoles when possible

❌ **DON'T:**
- Grant `verbs: ["*"]` (all permissions)
- Use `resources: ["*"]` (all resources)
- Grant permissions to the `default` ServiceAccount
- Use ClusterRole when a Role is sufficient

### ServiceAccount Management
✅ **DO:**
- Create dedicated ServiceAccounts for each application
- Use descriptive names that indicate purpose
- Document what permissions each ServiceAccount needs
- Regularly audit ServiceAccount permissions

❌ **DON'T:**
- Reuse ServiceAccounts across different applications
- Grant broad permissions "just in case"
- Use the `default` ServiceAccount for applications
- Create ServiceAccounts without corresponding Roles

### Role Design
✅ **DO:**
- Create granular Roles for specific tasks
- Separate read-only from write permissions
- Use subresources (e.g., `pods/log`, `pods/exec`) when you need fine-grained control
- Name Roles descriptively: `pod-viewer`, `deployment-editor`, `secret-admin`

❌ **DON'T:**
- Create one "god" Role with all permissions
- Mix unrelated permissions in one Role
- Use wildcards unless absolutely necessary
- Grant admin permissions by default

### Security Considerations

**Token Security:**
- ServiceAccount tokens are sensitive credentials
- Tokens are automatically mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`
- Limit container access to the filesystem to protect tokens
- Consider using short-lived tokens (TokenRequest API) for enhanced security

**Audit and Monitoring:**
- Enable Kubernetes audit logging to track API access
- Monitor for failed authorization attempts
- Regularly review RoleBindings to ensure they're still needed
- Use tools like `kubectl auth can-i` to verify permissions

**Common Security Issues:**
- **Over-permissioned default ServiceAccount:** Never grant permissions to `default`
- **Wildcard permissions:** Avoid `*` in verbs, resources, or apiGroups
- **Cluster-wide access:** Use Roles instead of ClusterRoles when possible
- **Long-lived tokens:** Consider rotating or using short-lived tokens

---

## Troubleshooting RBAC

### Permission Denied Errors

**Error:** `pods is forbidden: User "system:serviceaccount:scenarios:rbac-demo-sa" cannot list resource "pods" in API group "" in the namespace "scenarios"`

**Diagnosis:**
1. Check if RoleBinding exists: `kubectl get rolebinding -n scenarios`
2. Verify ServiceAccount exists: `kubectl get sa -n scenarios`
3. Check Role permissions: `kubectl get role rbac-demo-role -n scenarios -o yaml`
4. Test permissions: `kubectl auth can-i list pods --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios`

**Common Causes:**
- RoleBinding doesn't exist or doesn't reference the correct Role/ServiceAccount
- Role doesn't include the required verb/resource
- Namespace mismatch between resources
- ServiceAccount doesn't exist

### Cannot Create Resources

**Error:** `pods is forbidden: User cannot create resource "pods"`

**Why:** The Role only has `get`, `list`, `watch` verbs, not `create`.

**Solution:** If creation is needed, add `create` verb to the Role:
```yaml
verbs: ["get", "list", "watch", "create"]
```

### Testing Permissions

**From outside the pod:**
```bash
kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<namespace>:<sa-name> -n <namespace>

# Examples:
kubectl auth can-i list pods --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios
kubectl auth can-i create pods --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios
kubectl auth can-i delete services --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios
```

**From inside the pod:**
```bash
# Exec into pod
kubectl exec -it deployment/rbac-demo-app -- /bin/sh

# Test allowed action
kubectl get pods -n scenarios  # Should work

# Test denied action
kubectl delete pod some-pod -n scenarios  # Should fail
```

---

## Advanced RBAC Patterns

### Pattern 1: Read-Only Application
**Use Case:** Monitoring, dashboards, log viewers

```yaml
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets"]
  verbs: ["get", "list", "watch"]
```

### Pattern 2: CI/CD Deployer
**Use Case:** Automated deployments from CI/CD pipeline

```yaml
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["services", "configmaps"]
  verbs: ["get", "list", "create", "update", "patch"]
```

### Pattern 3: Namespace Admin
**Use Case:** Full control within a namespace

```yaml
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

**Better approach:** Use built-in `admin` ClusterRole:
```yaml
roleRef:
  kind: ClusterRole
  name: admin
  apiGroup: rbac.authorization.k8s.io
```

### Pattern 4: Pod Execution Rights
**Use Case:** Application needs to exec into other pods (debugging, sidecar)

```yaml
rules:
- apiGroups: [""]
  resources: ["pods", "pods/exec"]
  verbs: ["get", "list", "create"]
```

---

## Built-in ClusterRoles

Kubernetes provides predefined ClusterRoles for common use cases:

| ClusterRole | Permissions | Use Case |
|-------------|-------------|----------|
| **view** | Read-only access to most resources | Developers, dashboards |
| **edit** | Read-write access to most resources | Application deployment |
| **admin** | Full access within namespace | Namespace administrators |
| **cluster-admin** | Full cluster access | Cluster administrators (use sparingly!) |

**Usage example:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developer-view
  namespace: dev
subjects:
- kind: ServiceAccount
  name: dev-app-sa
  namespace: dev
roleRef:
  kind: ClusterRole  # ← Using ClusterRole
  name: view         # ← Built-in "view" role
  apiGroup: rbac.authorization.k8s.io
```

---

## Further Learning

### Experiment With:
1. **Add more permissions:** Try adding `create` verb and test pod creation
2. **Deny by default:** Remove a permission and see the error
3. **Multiple ServiceAccounts:** Create two SAs with different permissions
4. **ClusterRole:** Convert the Role to ClusterRole and test cluster-wide access
5. **Subresources:** Add `pods/log` to access logs, `pods/exec` for exec permissions

### Related Concepts:
- **PodSecurityPolicies (PSP):** Control security context (deprecated in K8s 1.25, replaced by Pod Security Standards)
- **Pod Security Standards (PSS):** Enforce security policies at namespace level
- **Network Policies:** Control pod-to-pod communication
- **Admission Controllers:** Validate/mutate requests before they're persisted
- **OPA (Open Policy Agent):** Advanced policy enforcement

### Next Steps:
- Try creating a ClusterRole and ClusterRoleBinding
- Explore aggregated ClusterRoles (combining multiple roles)
- Implement RBAC for a multi-tenant cluster
- Learn about certificate-based authentication for users
- Integrate RBAC with external identity providers (OIDC, LDAP)

---

## Quick Reference

### Useful Commands

```bash
# View all RBAC resources
kubectl get sa,role,rolebinding -n scenarios

# Describe a ServiceAccount (shows tokens)
kubectl describe sa rbac-demo-sa -n scenarios

# View Role permissions in YAML
kubectl get role rbac-demo-role -n scenarios -o yaml

# View RoleBinding details
kubectl get rolebinding rbac-demo-binding -n scenarios -o yaml

# Test permissions from outside pod
kubectl auth can-i list pods --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios

# View all permissions for a ServiceAccount
kubectl auth can-i --list --as=system:serviceaccount:scenarios:rbac-demo-sa -n scenarios

# Exec into pod to test from inside
kubectl exec -it deployment/rbac-demo-app -n scenarios -- /bin/sh

# Inside pod: check mounted ServiceAccount token
cat /var/run/secrets/kubernetes.io/serviceaccount/token

# Inside pod: test API access
kubectl get pods -n scenarios
kubectl get services -n scenarios
kubectl create pod test --image=nginx  # Should fail
```

### Common RBAC Verbs Cheat Sheet

| Verb | kubectl Command Example |
|------|------------------------|
| `get` | `kubectl get pod my-pod` |
| `list` | `kubectl get pods` |
| `watch` | `kubectl get pods --watch` |
| `create` | `kubectl create -f pod.yaml` |
| `update` | `kubectl replace -f pod.yaml` |
| `patch` | `kubectl patch pod my-pod -p '{...}'` |
| `delete` | `kubectl delete pod my-pod` |
| `deletecollection` | `kubectl delete pods --all` |

### Common Resources by API Group

**Core (`""`)**
- pods, services, configmaps, secrets, persistentvolumeclaims, namespaces, nodes, events

**apps**
- deployments, statefulsets, daemonsets, replicasets

**batch**
- jobs, cronjobs

**networking.k8s.io**
- networkpolicies, ingresses

**rbac.authorization.k8s.io**
- roles, rolebindings, clusterroles, clusterrolebindings

---

## Summary

This scenario demonstrates the fundamental components of Kubernetes RBAC:

1. **ServiceAccount:** Provides identity for pods
2. **Role:** Defines what actions are allowed on which resources
3. **RoleBinding:** Connects ServiceAccounts to Roles
4. **Deployment:** Uses the ServiceAccount to authenticate with the API server

By combining these resources, you can implement fine-grained access control that follows the principle of least privilege, ensuring that applications and users only have the permissions they absolutely need.

**Key Takeaways:**
- Always create dedicated ServiceAccounts for applications
- Use Roles to define granular permissions
- RoleBindings activate the permissions
- Test permissions using `kubectl auth can-i`
- Follow the principle of least privilege
- Prefer namespace-scoped Roles over cluster-wide ClusterRoles when possible
