# GitLab CI YAML Explanation - Compliance & Governance

This guide explains the GitLab CI YAML patterns for compliance pipelines — separation of duties, required approvals, audit trails, policy enforcement, and compliance frameworks. These patterns prevent unauthorized changes from reaching production.

---

## Compliance Pipeline Framework

GitLab's **Compliance Pipeline** feature lets admins inject jobs into every pipeline in a group, regardless of what the project's `.gitlab-ci.yml` contains. This is configured in the Group settings and references a compliance pipeline configuration file.

```yaml
# compliance-pipeline.yml — Lives in: mygroup/compliance-configs
# Injected by GitLab into every pipeline in the group automatically

stages:
  - pre-compliance    # Runs BEFORE the project's stages
  - [project-stages]  # Placeholder — the project's own stages run here
  - post-compliance   # Runs AFTER the project's stages

# These jobs always run, regardless of project config
verify-approvals:
  stage: pre-compliance
  image: alpine/git:latest
  script:
    - echo "Verifying required approvals for $CI_PROJECT_NAME"
    - |
      if [ "$CI_COMMIT_BRANCH" == "main" ]; then
        echo "Production branch — checking MR approval requirements"
        # In real implementation: call GitLab API to verify MR approval status
        echo "Approval verification passed"
      fi

generate-audit-log:
  stage: post-compliance
  when: always
  script:
    - echo "Pipeline $CI_PIPELINE_ID completed for $CI_PROJECT_NAME"
    - echo "Commit: $CI_COMMIT_SHA by $GITLAB_USER_LOGIN"
    - echo "Branch: $CI_COMMIT_BRANCH"
  artifacts:
    reports:
      dotenv: audit-event.env
```

### why: always (on audit job)

```yaml
generate-audit-log:
  when: always
```

The audit log job runs **regardless of pipeline success or failure**. This is critical for compliance — you need to record what happened even when deployments fail, tests fail, or the pipeline is cancelled. `when: always` ensures the audit trail is never skipped.

---

## Required Approvals in YAML

GitLab enforces approval rules at the merge request level (configured in the UI), but you can add a pipeline-level check:

```yaml
check-required-approvals:
  stage: pre-compliance
  image: curlimages/curl:latest
  variables:
    MIN_APPROVALS: "2"
  script:
    - |
      MR_IID=$CI_MERGE_REQUEST_IID
      PROJECT_ID=$CI_PROJECT_ID

      # Call GitLab API to check approval status
      APPROVALS=$(curl -s --header "PRIVATE-TOKEN: $COMPLIANCE_BOT_TOKEN" \
        "$CI_API_V4_URL/projects/$PROJECT_ID/merge_requests/$MR_IID/approvals")

      APPROVAL_COUNT=$(echo $APPROVALS | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['approved_by'].__len__())")

      if [ "$APPROVAL_COUNT" -lt "$MIN_APPROVALS" ]; then
        echo "ERROR: $APPROVAL_COUNT approvals found, $MIN_APPROVALS required"
        exit 1
      fi
      echo "✅ Required approvals satisfied: $APPROVAL_COUNT/$MIN_APPROVALS"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      if: $CI_MERGE_REQUEST_TARGET_BRANCH_NAME == "main"
```

### $COMPLIANCE_BOT_TOKEN

A dedicated service account token stored as a **protected, masked project/group variable**. Never use your personal token in CI pipelines — service account tokens have minimal permissions and can be rotated without affecting human users.

### $CI_API_V4_URL

Predefined GitLab variable pointing to the current instance's API endpoint. Automatically correct for self-hosted and GitLab.com instances. Always use this instead of hardcoding `https://gitlab.com/api/v4`.

---

## Protected Environments in YAML

Protected environments enforce who can deploy and require approvals before jobs targeting that environment can run.

```yaml
deploy-production:
  stage: deploy
  environment:
    name: production          # Must match a protected environment in GitLab UI
    url: https://app.example.com
  script:
    - helm upgrade --install myapp ./chart --namespace production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual            # Requires manual action in pipeline UI
```

In the GitLab UI (Settings > CI/CD > Protected environments), you configure:
- Which roles can deploy to this environment (e.g., only Maintainers)
- How many approvals are required before the deployment job can start
- Which users/groups can approve

When the job reaches the `manual` gate, GitLab presents an approval UI to the configured approvers. The job doesn't start until the required number of approvals is collected. This approval is separate from MR approvals — it's a deployment-time gate.

---

## Separation of Duties — Who Can Deploy

```yaml
# The CI pipeline itself enforces who can push to protected branches
# via branch protection (GitLab UI), not just YAML

# In the pipeline, enforce separation:
deploy-production:
  stage: deploy
  environment:
    name: production
  script:
    - |
      # Verify the commit was merged (not a direct push to main)
      if [ "$CI_PIPELINE_SOURCE" != "push" ] && \
         [ "$CI_COMMIT_AUTHOR" == "$GITLAB_USER_LOGIN" ]; then
        echo "Direct push by author — must go through MR process"
        exit 1
      fi
    - helm upgrade --install myapp ./chart --namespace production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### $GITLAB_USER_LOGIN

The GitLab username of the person who triggered the pipeline. Combined with `$CI_COMMIT_AUTHOR`, you can verify that the pipeline was triggered by someone other than the code author (four-eyes principle).

---

## Policy Enforcement Jobs

```yaml
enforce-image-policy:
  stage: pre-compliance
  image: alpine:latest
  script:
    - |
      # Only allow images from approved registries
      APPROVED_REGISTRIES="registry.gitlab.com/mygroup gcr.io/company-images"

      # Scan all Dockerfiles for FROM instructions
      IMAGES=$(grep -r "^FROM" --include="Dockerfile*" . | awk '{print $2}' | grep -v "AS")

      for IMAGE in $IMAGES; do
        REGISTRY=$(echo $IMAGE | cut -d/ -f1)
        APPROVED=false
        for APPROVED_REG in $APPROVED_REGISTRIES; do
          if echo "$IMAGE" | grep -q "^$APPROVED_REG"; then
            APPROVED=true
            break
          fi
        done
        if [ "$APPROVED" = "false" ]; then
          echo "❌ Unapproved base image: $IMAGE"
          echo "Only images from: $APPROVED_REGISTRIES"
          exit 1
        fi
      done
      echo "✅ All base images from approved registries"

enforce-no-privileged:
  stage: pre-compliance
  image: python:3.11-slim
  script:
    - pip install pyyaml -q
    - |
      python3 << 'EOF'
      import yaml, os, sys

      violations = []
      for root, dirs, files in os.walk('k8s/'):
        for f in files:
          if f.endswith('.yaml') or f.endswith('.yml'):
            path = os.path.join(root, f)
            with open(path) as fh:
              docs = yaml.safe_load_all(fh)
              for doc in docs:
                if doc and 'spec' in doc:
                  containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                  for c in containers:
                    sc = c.get('securityContext', {})
                    if sc.get('privileged'):
                      violations.append(f"{path}: container '{c['name']}' is privileged")

      if violations:
        print("❌ Privileged containers found:")
        for v in violations:
          print(f"  {v}")
        sys.exit(1)
      print("✅ No privileged containers found")
      EOF
```

### Policy jobs as compliance gates

These jobs run before any deployment and fail the pipeline if policies are violated. By putting them in `pre-compliance` (a stage that runs first), you prevent any deployment work from happening with non-compliant configurations.

---

## Audit Trail Artifacts

```yaml
generate-audit-trail:
  stage: post-compliance
  image: alpine:latest
  when: always                      # Run even if pipeline failed
  script:
    - |
      cat > pipeline-audit.json << EOF
      {
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "pipeline_id": "$CI_PIPELINE_ID",
        "project": "$CI_PROJECT_PATH",
        "branch": "$CI_COMMIT_BRANCH",
        "commit_sha": "$CI_COMMIT_SHA",
        "commit_author": "$CI_COMMIT_AUTHOR",
        "triggered_by": "$GITLAB_USER_LOGIN",
        "pipeline_status": "$CI_JOB_STATUS",
        "environment": "${DEPLOY_ENV:-none}"
      }
      EOF
      echo "Audit record:"
      cat pipeline-audit.json
  artifacts:
    paths:
      - pipeline-audit.json
    expire_in: 1 year               # Keep audit logs for compliance retention
```

### expire_in: 1 year

Audit artifacts must be retained longer than regular build artifacts. Set the expiry to match your compliance retention requirements (SOC 2, ISO 27001, etc. typically require 1 year minimum). In regulated industries, use `expire_in: never` and implement external archival.

---

## Compliance Pipeline include (Group-Level)

In the GitLab UI (Group > Settings > CI/CD > Compliance pipeline configuration), you specify:

```
mygroup/compliance-configs:main:compliance-pipeline.yml
```

GitLab then **injects** the jobs from `compliance-pipeline.yml` into every pipeline in the group. Project teams cannot remove or override compliance jobs — they're enforced at the group level.

```yaml
# What the injected compliance pipeline YAML looks like at runtime:
# (project's .gitlab-ci.yml stages + compliance stages merged)
stages:
  - pre-compliance          # From compliance pipeline
  - build                   # From project's .gitlab-ci.yml
  - test                    # From project's .gitlab-ci.yml
  - deploy                  # From project's .gitlab-ci.yml
  - post-compliance         # From compliance pipeline
```

---

## Key Takeaways

- **Compliance Pipeline**: Group admins inject mandatory jobs into every pipeline — projects cannot override them
- **`when: always`** on audit jobs: Capture audit events even when pipelines fail
- **Protected environments**: Deployment-time approval gates, separate from MR approvals — configured in GitLab UI
- **`$CI_API_V4_URL`**: Always use this predefined variable for GitLab API calls — works on all instances
- **`$GITLAB_USER_LOGIN`**: Track who triggered the pipeline for four-eyes principle enforcement
- **Policy enforcement jobs**: Scan Dockerfiles and K8s manifests for policy violations before any deployment
- **`expire_in: 1 year`**: Audit artifacts need longer retention than build artifacts
- **`$COMPLIANCE_BOT_TOKEN`**: Use a dedicated service account — never a personal token in CI
