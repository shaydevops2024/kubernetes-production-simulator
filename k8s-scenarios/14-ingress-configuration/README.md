# Ingress Configuration Scenario

## Overview
Configure Ingress resources for HTTP routing to expose multiple services through a single entry point with path-based or host-based routing.

## What You'll Learn
- Creating Ingress resources
- Path-based routing
- Host-based routing
- TLS/SSL termination
- Ingress annotations

## Prerequisites
- Ingress Controller installed (NGINX, Traefik, etc.)
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: ingress-demo (2 replicas)
- Service: ingress-demo-service
- Ingress: ingress-demo (HTTP routing rules)

## Scenario Flow
1. Create namespace
2. Deploy application and service
3. Create Ingress resource with routing rules
4. Verify Ingress resource created
5. Test access via Ingress hostname
6. Add path-based routing rules
7. Test different paths
8. View Ingress controller logs

## Key Concepts
- **Ingress:** L7 (HTTP/HTTPS) routing rules
- **Ingress Controller:** Implements the rules (NGINX, etc.)
- **Path-Based Routing:** Route by URL path (/api, /web)
- **Host-Based Routing:** Route by hostname (api.example.com)
- **TLS Termination:** HTTPS handling at ingress

## Ingress Structure
```yaml
spec:
  ingressClassName: nginx
  rules:
  - host: demo.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ingress-demo-service
            port:
              number: 80
```

## Routing Patterns
1. **Path-Based:**
   - /api → api-service
   - /web → web-service
   
2. **Host-Based:**
   - api.example.com → api-service
   - web.example.com → web-service

3. **Combined:**
   - api.example.com/v1 → api-v1-service
   - api.example.com/v2 → api-v2-service

## Expected Outcomes
- Single external IP/hostname for multiple services
- HTTP requests routed to correct backend service
- Understanding of L7 load balancing
- Knowledge of Ingress patterns

## Ingress vs Service
| Feature | Ingress | LoadBalancer Service |
|---------|---------|---------------------|
| Layer | L7 (HTTP) | L4 (TCP/UDP) |
| Routing | Path/Host | Port only |
| Cost | Single LB | One LB per service |
| SSL | Yes | No (pass-through) |

## Common Annotations
```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/rate-limit: "100"
```

## Best Practices
- Use TLS for production
- Set resource limits on Ingress Controller
- Use separate Ingress per namespace/app
- Configure timeouts appropriately
- Monitor Ingress Controller metrics

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 25 minutes

## Difficulty
Medium - Requires understanding of HTTP routing