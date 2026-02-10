# Webhook Triggers

Configure GitHub and GitLab webhooks, SCM polling, and the Generic Webhook Trigger plugin to automatically start Jenkins builds on code changes.

## Learning Objectives
- Understand the differences between push-based webhooks, pull-based SCM polling, and scheduled triggers
- Configure GitHub webhook integration with HMAC secret verification
- Parse and understand GitHub webhook JSON payloads
- Set up SCM polling as a fallback using Jenkins cron syntax with the H hash symbol
- Use the Generic Webhook Trigger plugin for custom integrations with any HTTP source
- Simulate a complete webhook-triggered CI/CD pipeline execution

## Prerequisites
- Basic Jenkins Pipeline knowledge (Scenario 01)
- Understanding of Git and GitHub/GitLab workflows
- Namespace: jenkins-scenarios (created automatically in Step 6)

## Resources Created
- Namespace: jenkins-scenarios
- Pod: webhook-receiver (simulates receiving and processing a GitHub webhook)
- Pod: webhook-demo (represents a deployment triggered by a webhook)

## Scenario Flow
1. Understand trigger types - webhooks, SCM polling, scheduled, manual
2. Review webhook configuration for GitHub integration
3. Examine a GitHub push webhook JSON payload structure
4. Configure SCM polling as a fallback with cron syntax
5. Explore the Generic Webhook Trigger plugin for custom sources
6. Simulate a complete webhook-triggered build pipeline
7. Deploy a pod with traceability labels from webhook metadata
8. Verify resources and review summary with security checklist
9. Clean up all scenario resources

## Key Concepts
- **Webhook (Push-based):** SCM server notifies Jenkins instantly on push/PR events
- **SCM Polling (Pull-based):** Jenkins periodically checks the repository for changes
- **H Symbol:** Hash-based cron offset to distribute polling load across Jenkins
- **Generic Webhook Trigger:** Accept webhooks from any HTTP source with JSONPath extraction
- **HMAC Verification:** Shared secret to validate webhook authenticity
- **Trigger Token:** Unique identifier to route generic webhooks to the correct job

## Expected Outcomes
- Ability to configure webhook triggers for GitHub and GitLab
- Understanding of SCM polling as a reliable fallback mechanism
- Knowledge of the Generic Webhook Trigger plugin for custom integrations
- Awareness of webhook security best practices

## Cleanup
Run the cleanup command (last step) to remove all pods from the jenkins-scenarios namespace.

## Time Required
Approximately 15 minutes

## Difficulty
Medium - Requires understanding of webhooks and SCM integration
