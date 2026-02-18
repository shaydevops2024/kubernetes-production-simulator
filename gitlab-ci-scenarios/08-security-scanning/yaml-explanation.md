# GitLab CI YAML Explanation - Security Scanning

This guide explains the GitLab CI YAML configuration for security scanning — SAST, container scanning, dependency scanning, and secret detection. It covers the `include: template:` pattern, security report artifacts, and how to configure scans without writing scanner code yourself.

---

## GitLab Security Templates — include: template:

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml
  - template: Security/DAST.gitlab-ci.yml
```

### What include: template: does

GitLab maintains pre-built CI templates for security scanning. `include: template:` pulls these in and adds their job definitions to your pipeline automatically. You get the entire scanning pipeline without writing any scanner code — the template defines which tools to use, how to run them, and what report format to produce.

These templates live in GitLab's own repository and are updated with each GitLab release.

### Which templates are available

| Template | Scans for |
|----------|-----------|
| `Security/SAST.gitlab-ci.yml` | Source code vulnerabilities (static analysis) |
| `Security/Secret-Detection.gitlab-ci.yml` | Hardcoded secrets, API keys, passwords in code |
| `Security/Dependency-Scanning.gitlab-ci.yml` | Known CVEs in packages (npm, pip, bundler) |
| `Security/Container-Scanning.gitlab-ci.yml` | CVEs in Docker image layers |
| `Security/DAST.gitlab-ci.yml` | Running app vulnerabilities (dynamic analysis) |
| `Security/License-Scanning.gitlab-ci.yml` | Open source license compliance |

---

## SAST Configuration

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml

variables:
  SAST_EXCLUDED_PATHS: "tests/, vendor/, node_modules/"
  SAST_EXCLUDED_ANALYZERS: "gosec, flawfinder"   # Skip analyzers not relevant to your stack
  SAST_ANALYZER_IMAGE_TAG: "4"                   # Pin analyzer version
  SECURE_LOG_LEVEL: "info"

# Override the included template's job behavior
semgrep-sast:
  variables:
    SAST_SCANNER_ALLOWED_CLI_OPTS: "--metrics=off"
```

### SAST_EXCLUDED_PATHS

```yaml
SAST_EXCLUDED_PATHS: "tests/, vendor/, node_modules/"
```

Exclude directories that generate false positives or aren't your code. Test files often contain intentionally vulnerable patterns (for testing security checks). Vendor/node_modules is third-party code — covered by Dependency Scanning instead.

### How SAST works

GitLab auto-detects your language and runs the appropriate analyzer:
- Python → `bandit`
- JavaScript/TypeScript → `semgrep` or `eslint-sast`
- Go → `gosec`
- Java → `spotbugs`
- Ruby → `brakeman`

The analyzers run as separate jobs, all in parallel, in the `test` stage.

---

## Container Scanning

```yaml
include:
  - template: Security/Container-Scanning.gitlab-ci.yml

container_scanning:
  variables:
    CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA    # Image to scan
    CS_SEVERITY_THRESHOLD: HIGH                    # Report HIGH and CRITICAL only
    CS_DISABLE_DEPENDENCY_LIST: "true"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"              # Only scan on main branch
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### CS_IMAGE

```yaml
CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

The Docker image to scan. This must be the image you just built in the `build` stage — same commit SHA, same registry path. GitLab pulls this image and uses Trivy (or Grype) to scan all layers for known CVEs.

### CS_SEVERITY_THRESHOLD

Filters findings by severity. Setting `HIGH` means only HIGH and CRITICAL vulnerabilities appear in the report. LOW and MEDIUM are still scanned but not reported. Start strict in established projects; in new projects, consider reporting everything to understand your baseline.

---

## Dependency Scanning

```yaml
include:
  - template: Security/Dependency-Scanning.gitlab-ci.yml

variables:
  DS_EXCLUDED_PATHS: "spec, test, tests, tmp"
  DS_MAX_DEPTH: 2                        # How deep to scan nested packages
  GEMNASIUM_DB_REMOTE_URL: ""            # Use bundled DB for air-gapped environments
```

### How Dependency Scanning works

GitLab auto-detects your package files (`package.json`, `requirements.txt`, `Gemfile.lock`, `pom.xml`, etc.) and checks each dependency version against the GitLab Advisory Database (based on NVD and other sources). Results appear in the MR Security widget.

---

## Secret Detection

```yaml
include:
  - template: Security/Secret-Detection.gitlab-ci.yml

variables:
  SECRET_DETECTION_EXCLUDED_PATHS: "tests/"
  SECRET_DETECTION_HISTORIC_SCAN: "false"   # Scan only new commits (set true for initial scan)
```

### SECRET_DETECTION_HISTORIC_SCAN

```yaml
SECRET_DETECTION_HISTORIC_SCAN: "false"
```

By default, secret detection scans only the current commit diff. Set to `"true"` for a one-time full history scan — useful when you first add secret detection to an existing repo. Running full history scans on every commit would be too slow.

---

## Security Artifacts — The reports Block

All security templates produce standardized report artifacts:

```yaml
# What the templates produce (you don't write this — it's in the template):
artifacts:
  reports:
    sast: gl-sast-report.json
    secret_detection: gl-secret-detection-report.json
    dependency_scanning: gl-dependency-scanning-report.json
    container_scanning: gl-container-scanning-report.json
    dast: gl-dast-report.json
```

### reports: sast (and others)

These are **special artifact types** that GitLab understands. When these reports are present, GitLab:
- Shows a **Security widget** in the merge request with found vulnerabilities
- Tracks vulnerability status in the **Security Dashboard**
- Lets you mark findings as "dismissed" or "confirmed" in the UI
- Blocks MR approval if policies require zero CRITICAL findings

The report format is standardized JSON — you can parse it with your own tools or integrate with third-party SIEM systems.

---

## Custom Trivy Scan (without GitLab template)

```yaml
trivy-scan:
  stage: security
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  variables:
    SEVERITY: "HIGH,CRITICAL"
    TRIVY_EXIT_CODE: "1"           # Fail the job on findings
    TRIVY_NO_PROGRESS: "true"
  script:
    - trivy image
        --severity $SEVERITY
        --exit-code $TRIVY_EXIT_CODE
        --format json
        --output gl-container-scanning-report.json
        $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  artifacts:
    when: always
    reports:
      container_scanning: gl-container-scanning-report.json
    paths:
      - gl-container-scanning-report.json
    expire_in: 1 week
  allow_failure: true            # Reporting mode: findings don't block pipeline
```

### allow_failure: true vs TRIVY_EXIT_CODE

Two ways to handle scan findings:
- **`allow_failure: true`**: Job can have findings and fail, but pipeline continues (reporting mode)
- **`TRIVY_EXIT_CODE: "0"`**: Trivy never fails regardless of findings (pure reporting)
- **`TRIVY_EXIT_CODE: "1"` + `allow_failure: false`**: Pipeline blocks on any HIGH/CRITICAL (blocking mode)

Start with `allow_failure: true` to understand your current vulnerability landscape. Move to blocking mode once your team has a process for addressing findings.

---

## Full Security Pipeline

```yaml
stages:
  - build
  - test
  - security
  - deploy

include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml

# Override template jobs to only run on main + MRs
.security-rules: &security-rules
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

# Apply the rules to all scanning jobs
sast:
  <<: *security-rules

secret_detection:
  <<: *security-rules

dependency_scanning:
  <<: *security-rules

container_scanning:
  <<: *security-rules
  needs: [build-image]          # Can't scan before the image exists
```

### YAML anchors (&) and aliases (*)

```yaml
.security-rules: &security-rules   # Define the anchor
  rules:
    - if: ...

sast:
  <<: *security-rules              # Merge the anchor's content
```

YAML anchors (`&name`) and aliases (`*name`) let you define a block once and reuse it. `<<:` (merge key) merges the referenced block's keys into the current mapping — it's YAML's version of inheritance. This avoids repeating the same `rules:` block across every security job.

---

## Key Takeaways

- **`include: template: Security/*`**: Pulls in GitLab-maintained scanning jobs — no scanner code needed
- **`artifacts.reports.sast`** (and others): Standardized JSON that GitLab parses into the Security Dashboard and MR widget
- **`allow_failure: true`**: Start in reporting mode; move to blocking mode once you address baseline findings
- **`CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA`**: Always scan the image you just built — same commit, same tag
- **`SECRET_DETECTION_HISTORIC_SCAN: "true"`**: Run once on initial setup to find secrets in Git history
- **YAML anchors (`&`) and aliases (`*`)**: DRY pattern for repeating `rules:` across multiple security jobs
- **`needs: [build-image]`**: Container scanning must wait for the build job — use `needs:` to create the dependency
