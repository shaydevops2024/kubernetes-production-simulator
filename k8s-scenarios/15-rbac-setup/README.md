# RBAC Setup Scenario

## Overview
Configure Role-Based Access Control (RBAC) to manage permissions with ServiceAccounts, Roles, and RoleBindings for fine-grained access control.

## What You'll Learn
- Creating ServiceAccounts
- Defining Roles with specific permissions
- Creating RoleBindings to grant permissions
- Testing permissions with kubectl auth can-i
- Using ServiceAccounts in pods

## Prerequisites
- Understanding of Kubernetes API resources
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- ServiceAccount: demo-sa
- Role: demo-role (permissions for pods, services, deployments)
- RoleBinding: demo-binding (binds role to service account)
- Deployment: rbac-test-pod (uses the service account)

## Scenario Flow
1. Create namespace
2. Create ServiceAccount
3. Define Role with specific permissions
4. Create RoleBinding linking SA and Role
5. Test permissions with kubectl auth can-i
6. Deploy pod using the ServiceAccount
7. Exec into pod and test API access
8. Verify permissions work as expected

## Key Concepts
- **ServiceAccount:** Identity for pods
- **Role:** Set of permissions (namespace-scoped)
- **ClusterRole:** Set of permissions (cluster-scoped)
- **RoleBinding:** Grants Role to subjects (namespace-scoped)
- **ClusterRoleBinding:** Grants ClusterRole (cluster-scoped)

## RBAC Structure
```yaml
ServiceAccount (demo-sa)
    ↓ granted by
RoleBinding (demo-binding)
    ↓ references
Role (demo-role)
    ↓ has permissions
API Resources (pods, services, deployments)
```

## Role Definition
```yaml
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list"]
```

### RBAC Verbs
- **get:** Read single resource
- **list:** List resources
- **watch:** Watch for changes
- **create:** Create new resource
- **update:** Update existing resource
- **patch:** Partial update
- **delete:** Delete resource
- **deletecollection:** Delete multiple

## Expected Outcomes
- ServiceAccount can list pods and services
- ServiceAccount cannot create or delete resources
- Understanding of least-privilege principle
- Knowledge of RBAC authorization

## Testing Permissions
```bash
# Test as service account
kubectl auth can-i list pods --as=system:serviceaccount:scenarios:demo-sa -n scenarios

# From inside pod
kubectl get pods  # Should work
kubectl delete pod test  # Should fail
```

## Role vs ClusterRole
| Scope | Role | ClusterRole |
|-------|------|-------------|
| Namespace | Yes | No |
| Resources | Namespace resources | Cluster + namespace |
| Binding | RoleBinding | ClusterRoleBinding |
| Use Case | App permissions | Admin, cluster resources |

## Security Best Practices
- **Least Privilege:** Grant minimum necessary permissions
- **Separate Accounts:** One ServiceAccount per application
- **Avoid Wildcards:** Be specific with resources and verbs
- **Regular Audit:** Review and revoke unnecessary permissions
- **Use Roles over ClusterRoles:** Limit to namespace when possible

## Common Patterns
1. **Read-Only Access:** get, list, watch only
2. **App Deployment:** create, update, delete for deployments
3. **Service Management:** CRUD on services
4. **Cluster Admin:** All permissions (*) - avoid in production

## Troubleshooting
- **403 Forbidden:** Missing permissions, check Role
- **401 Unauthorized:** Invalid ServiceAccount token
- **Cannot find resource:** Wrong API group or resource name

## Cleanup
Run the cleanup commands to remove all RBAC resources.

## Time Required
Approximately 30 minutes

## Difficulty
Hard - Requires understanding of Kubernetes security model