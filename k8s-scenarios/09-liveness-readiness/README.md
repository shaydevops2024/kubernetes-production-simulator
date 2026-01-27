# Liveness and Readiness Probes Scenario

## Overview
Configure health checks to automatically detect and recover from application failures using liveness and readiness probes.

## What You'll Learn
- Difference between liveness and readiness probes
- Configuring HTTP health check endpoints
- Understanding probe timing parameters
- Automatic pod restart on liveness failure
- Service endpoint removal on readiness failure

## Prerequisites
- Basic Kubernetes knowledge
- Namespace: scenarios (created in step 1)

## Resources Created
- Namespace: scenarios
- Deployment: probes-demo (2 replicas with health probes)
- Service: probes-service

## Scenario Flow
1. Create namespace and deploy application with probes
2. Verify probes are working (check pod events)
3. Simulate liveness probe failure
4. Watch pod automatically restart
5. Simulate readiness probe failure
6. Observe pod removed from service endpoints
7. Verify traffic no longer routed to unhealthy pod

## Key Concepts
- **Liveness Probe:** Is the application alive? (restart if fails)
- **Readiness Probe:** Is the application ready for traffic? (remove from service if fails)
- **Startup Probe:** Has the application started? (for slow-starting apps)
- **HTTP Probes:** Check HTTP endpoint returns 200-399
- **Probe Parameters:** initialDelay, period, timeout, threshold

## Probe Configuration
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 3    # Wait before first check
  periodSeconds: 10         # Check every 10 seconds
  failureThreshold: 3       # Restart after 3 failures

readinessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3       # Remove from service after 3 failures
```

## Expected Outcomes
- Liveness failure triggers pod restart
- Readiness failure removes pod from service
- Service continues working with healthy pods only
- Understanding of probe behavior and use cases

## When to Use Each Probe
- **Liveness:** Detect deadlocks, infinite loops, hung processes
- **Readiness:** Detect temporary issues, initialization, dependencies
- **Startup:** Slow-starting legacy applications

## Best Practices
- Always configure both probes for production
- Use different endpoints if needed
- Set appropriate timeouts for your application
- Don't make probes too sensitive (avoid flapping)
- Include dependency checks in readiness only

## Cleanup
Run the cleanup commands to remove all resources.

## Time Required
Approximately 20 minutes

## Difficulty
Medium - Important for production reliability