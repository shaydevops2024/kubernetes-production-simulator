# Network Policies Scenario

## Overview
Implement network segmentation and security using Network Policies to control ingress and egress traffic between pods.

## What You'll Learn
- Creating Network Policies
- Controlling ingress traffic
- Using pod selectors for policy rules
- Testing network connectivity
- Implementing zero-trust networking

## Prerequisites
- CNI plugin with Network Policy support (Calico, Cilium, etc.)
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: backend-app (2 replicas with role: api)
- Service: backend-service
- NetworkPolicy: backend-policy (restricts access)

## Scenario Flow
1. Create namespace and deploy backend application
2. Verify pod-to-pod communication works (before policy)
3. Create Network Policy restricting ingress
4. Test that unrestricted pods cannot connect
5. Deploy pod with allowed label (role: frontend)
6. Verify allowed pod can connect
7. Understand policy enforcement

## Key Concepts
- **Network Policy:** Firewall rules for pods
- **Pod Selector:** Targets pods the policy applies to
- **Ingress Rules:** Control incoming traffic
- **Egress Rules:** Control outgoing traffic
- **Default Deny:** Best practice for security

## Network Policy Structure
```yaml
spec:
  podSelector:        # Which pods this applies to
    matchLabels:
      app: backend
  policyTypes:
  - Ingress           # Restrict incoming traffic
  ingress:
  - from:
    - podSelector:    # Allow from these pods
        matchLabels:
          role: frontend
```

## Expected Outcomes
- Backend pods only accept traffic from frontend pods
- Unauthorized pods blocked from accessing backend
- Understanding of Kubernetes network security
- Knowledge of zero-trust networking principles

## Security Best Practices
- Start with default deny for all traffic
- Explicitly allow only required connections
- Use namespace selectors for isolation
- Combine with RBAC for defense in depth
- Test policies thoroughly before production

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 25 minutes

## Difficulty
Medium - Requires understanding of networking and security