# GitLab CI YAML Explanation - Caching and Artifacts

This guide explains the `cache:` and `artifacts:` YAML blocks in GitLab CI — two distinct mechanisms for persisting and sharing data across jobs and pipelines.

---

## cache vs artifacts — The Core Distinction

| | `cache` | `artifacts` |
|---|---|---|
| Purpose | Speed up jobs (skip re-downloading deps) | Pass files **between jobs** in the same pipeline |
| Scope | Shared across pipeline runs | Scoped to one pipeline run |
| Guarantee | Best-effort (may be missing) | Guaranteed available to downstream jobs |
| Storage | Runner cache (S3, local fs) | GitLab server |
| Use case | `node_modules`, `.pip-cache`, Maven cache | Built binaries, test reports, compiled assets |

---

## The cache Block

```yaml
install-deps:
  stage: setup
  image: node:18
  cache:
    key:
      files:
        - package-lock.json       # Cache key based on this file's hash
    paths:
      - node_modules/             # What to cache
    policy: pull-push             # Download existing cache, upload updated cache
  script:
    - npm ci
```

### cache.key

The cache key determines **which cache entry to use**. GitLab stores cache entries per key — different keys are different caches.

```yaml
# Simple string key — shared across all branches
cache:
  key: my-cache

# Branch-specific key — each branch gets its own cache
cache:
  key: $CI_COMMIT_REF_SLUG

# File-content-based key — invalidates when file changes
cache:
  key:
    files:
      - package-lock.json         # Hash of this file becomes the key
      - Gemfile.lock              # Can include multiple files

# Prefix + file hash — namespaced by branch
cache:
  key:
    prefix: $CI_COMMIT_REF_SLUG
    files:
      - package-lock.json
```

**`key.files`** is the most useful pattern: the cache is only invalidated when `package-lock.json` changes (meaning new dependencies were added or updated). If only application code changes, the existing `node_modules` cache is reused, saving the `npm ci` download time.

### cache.paths

```yaml
cache:
  paths:
    - node_modules/
    - .npm/
    - vendor/
    - ~/.cache/pip/
```

Directories (relative to the project root) to save. These are tar'd up and uploaded after the job (for `pull-push` policy). Be specific — don't cache the entire working directory.

### cache.policy

```yaml
# pull-push (default): Download existing cache, upload updated cache
cache:
  policy: pull-push

# pull: Only download, never upload (read-only consumer)
cache:
  policy: pull

# push: Only upload, never download (cache creator)
cache:
  policy: push
```

Use `policy: pull` in test jobs that consume dependencies but don't change them — this skips the upload at the end, speeding up the job. Use `policy: pull-push` only in the job that actually installs/updates dependencies.

### cache.when

```yaml
cache:
  when: on_success    # Default: only cache if job succeeded
  when: on_failure    # Cache even if job failed (useful for debug artifacts)
  when: always        # Always cache, regardless of job result
```

---

## The artifacts Block

```yaml
unit-tests:
  stage: test
  script:
    - pytest tests/ --junitxml=report.xml --cov=src --cov-report=xml
  artifacts:
    when: always                  # Save artifacts even if tests fail
    expire_in: 1 week
    paths:
      - report.xml
      - coverage.xml
    reports:
      junit: report.xml           # GitLab parses this for test results UI
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

### artifacts.paths

Raw files/directories to save. These become downloadable from the GitLab UI and are passed to jobs in later stages via `dependencies` or `needs`.

```yaml
build:
  artifacts:
    paths:
      - dist/                     # Built frontend assets
      - .build-tag                # File containing image tag
      - target/*.jar              # Compiled JAR

deploy:
  script:
    - TAG=$(cat .build-tag)       # Read the artifact from build stage
    - kubectl set image deployment/myapp app=myapp:$TAG
```

### artifacts.reports

Special artifact types that GitLab understands and integrates into the UI:

```yaml
artifacts:
  reports:
    junit: report.xml             # Shows test results in MR widget
    coverage_report:
      coverage_format: cobertura
      path: coverage.xml          # Shows coverage % in MR widget
    sast: gl-sast-report.json     # Security tab in GitLab UI
    container_scanning: gl-container-scanning-report.json
    dependency_scanning: gl-dependency-scanning-report.json
    dotenv: build.env             # Exports KEY=VALUE as pipeline variables
```

`junit` is the most commonly used — GitLab parses the JUnit XML and displays pass/fail counts directly on the merge request.

### artifacts.when

```yaml
artifacts:
  when: on_success    # Default: only save if job succeeded
  when: on_failure    # Only save if job failed (useful for error logs)
  when: always        # Always save (test reports — you want them even on failure)
```

For test reports, always use `when: always` — you need the test results most when tests fail.

### artifacts.expire_in

```yaml
artifacts:
  expire_in: 1 week       # Relative time
  expire_in: 30 days
  expire_in: 1 year
  expire_in: never        # Keep forever (use sparingly)
```

Artifacts consume GitLab storage. Set reasonable expiry. For release artifacts (compiled binaries for a specific version), use `never` or a long duration. For test reports, 1-4 weeks is typical.

---

## Controlling Artifact Downloads with dependencies

```yaml
build-frontend:
  stage: build
  artifacts:
    paths:
      - dist/                     # Frontend assets

build-backend:
  stage: build
  artifacts:
    paths:
      - target/app.jar            # Backend JAR

deploy:
  stage: deploy
  dependencies:
    - build-frontend              # Only download frontend artifacts
    # (build-backend artifacts NOT downloaded)
  script:
    - aws s3 sync dist/ s3://my-bucket/
```

By default, a job downloads **all artifacts from all previous stages**. `dependencies` limits which job artifacts to download — essential in large pipelines where downloading everything would be slow.

To download **no artifacts at all**:
```yaml
smoke-test:
  dependencies: []                # Explicitly download nothing
```

---

## needs + artifacts for DAG Pipelines

```yaml
test:
  stage: test
  needs:
    - job: build
      artifacts: true             # Download build artifacts (default true)
  script:
    - ./run-tests dist/app        # Use build output immediately
```

`needs` creates a **Directed Acyclic Graph (DAG)** — the `test` job starts as soon as `build` completes, without waiting for other jobs in the `build` stage to finish. `artifacts: true` (the default) means the test job downloads the build job's artifacts.

---

## Practical Pattern: Full Pipeline Cache + Artifacts

```yaml
stages:
  - setup
  - test
  - build
  - deploy

install:
  stage: setup
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]
    policy: pull-push             # Creates the cache
  script:
    - npm ci

test:
  stage: test
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]
    policy: pull                  # Read-only — don't re-upload
  script:
    - npm test -- --coverage
  artifacts:
    when: always
    reports:
      junit: test-results.xml
    paths:
      - coverage/
    expire_in: 2 weeks

build:
  stage: build
  cache:
    key:
      files: [package-lock.json]
    paths: [node_modules/]
    policy: pull
  script:
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 month

deploy:
  stage: deploy
  dependencies:
    - build                       # Only need build output, not coverage
  script:
    - aws s3 sync dist/ s3://my-bucket/
```

---

## Key Takeaways

- **`cache`**: Speed optimization — skip re-downloading dependencies. Best-effort, not guaranteed
- **`artifacts`**: Data transfer — pass files between jobs. Guaranteed available to downstream jobs
- **`cache.key.files`**: Invalidate cache only when `package-lock.json` or `Gemfile.lock` changes
- **`cache.policy: pull`**: Consumer jobs shouldn't re-upload the cache — saves time
- **`artifacts.when: always`**: Required for test reports — you need them most when tests fail
- **`artifacts.reports.junit`**: GitLab parses this and shows test results in the MR widget
- **`dependencies: []`**: Download no artifacts (explicit opt-out of all artifacts)
- **`dotenv` report**: The right way to pass computed variables (image tags, version numbers) between jobs
