# Credentials and Secrets Management

Learn how Jenkins securely stores and injects credentials into pipelines using the Credential Store and withCredentials() blocks.

## Learning Objectives
- Understand Jenkins credential types (Username/Password, Secret Text, SSH Key, Certificate)
- Use withCredentials() to inject secrets into pipeline steps
- Integrate Jenkins credentials with Kubernetes secrets
- Follow secret management best practices

## Prerequisites
- Completed Scenario 01 (First Pipeline)
- Basic understanding of environment variables

## Resources Created
- Kubernetes namespace: jenkins-scenarios
- Kubernetes secret: db-credentials
- Sample deployment using secret environment variables

## Cleanup
Run the final cleanup command to remove all created resources.
