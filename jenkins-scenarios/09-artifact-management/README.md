# Artifact Management

Manage build artifacts, publish test reports, and implement fingerprinting for full traceability across Jenkins pipelines.

## Learning Objectives
- Understand the different types of Jenkins artifacts and when to use each
- Use `archiveArtifacts` with glob patterns, exclusions, and fingerprinting
- Publish JUnit test results and HTML coverage reports
- Simulate creating versioned build artifacts and test reports
- Configure build retention policies to prevent disk exhaustion
- Implement artifact versioning strategies for deployment traceability

## Prerequisites
- Basic Jenkins Pipeline knowledge (Scenario 01)
- Familiarity with build tools (Maven, Gradle, npm)
- Namespace: jenkins-scenarios (created automatically in Step 4)

## Resources Created
- Namespace: jenkins-scenarios
- Pod: artifact-builder (simulates build artifact generation)
- Pod: report-generator (simulates JUnit XML and coverage report output)

## Scenario Flow
1. Understand artifact types - binaries, reports, logs, docs, configs
2. Review archiveArtifacts step with fingerprinting and glob patterns
3. Review junit and publishHTML steps for test result publishing
4. Simulate creating build artifacts in a Kubernetes pod
5. Simulate test report generation with JUnit XML and coverage metrics
6. Explore artifact retention policies and build discarder configuration
7. Deploy with artifact versioning and Artifactory integration
8. Verify resources and review summary of best practices
9. Clean up all scenario resources

## Key Concepts
- **archiveArtifacts:** Built-in step to preserve build outputs in Jenkins
- **Fingerprinting:** MD5 hashing for cross-job artifact tracking
- **JUnit Publishing:** Parse XML test results into trend dashboards
- **publishHTML:** Create browsable HTML report tabs on build pages
- **Build Discarder:** Retention policies to manage disk usage
- **Artifact Versioning:** Unique identifiers combining build number, commit SHA, and semantic version

## Expected Outcomes
- Ability to archive and retrieve build artifacts
- Understanding of test report publishing and trend tracking
- Knowledge of retention policies and disk management
- Familiarity with artifact versioning for production deployments

## Cleanup
Run the cleanup command (last step) to remove all pods from the jenkins-scenarios namespace.

## Time Required
Approximately 12 minutes

## Difficulty
Medium - Requires understanding of CI/CD artifact workflows
