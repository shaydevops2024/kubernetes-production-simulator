# GitLab CI YAML Explanation - Docker Build & Registry

This guide explains the YAML configuration for building Docker images in GitLab CI and pushing them to the GitLab Container Registry. It covers the `Dockerfile`, the Docker-in-Docker service pattern, and the Kaniko alternative.

---

## The Dockerfile

```dockerfile
# Dockerfile.example
FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (changes frequently — last layer)
COPY src/ ./src/

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Multi-stage build for CI efficiency

```dockerfile
FROM python:3.11-slim AS base
# ... base setup

FROM base AS test
RUN pip install pytest
COPY tests/ ./tests/
RUN pytest tests/                  # Tests run at BUILD time

FROM base AS production            # Only production dependencies
COPY src/ ./src/
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Multi-stage builds let you run tests inside Docker itself (`FROM base AS test`), then produce a lean final image (`FROM base AS production`) that doesn't include test tools. In CI, you build the `production` target: `docker build --target production`.

---

## Docker-in-Docker (DinD) Pattern

```yaml
build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind            # Runs a Docker daemon as a sidecar
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
    DOCKER_DRIVER: overlay2
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker build -t $CI_REGISTRY_IMAGE:latest .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
  after_script:
    - docker logout $CI_REGISTRY
```

### image: docker:24

The job runs inside the official Docker CLI image. This gives you the `docker` command, but no daemon — that's what `services` provides.

### services: docker:24-dind

`dind` = Docker-in-Docker. GitLab Runner starts this as a sidecar container with a Docker daemon. The job container connects to it via the `DOCKER_HOST` environment variable (set automatically). This is how you run `docker build` inside a CI container.

### DOCKER_TLS_CERTDIR: "/certs"

Enables TLS between the job container and the DinD daemon. Required since Docker 19.03+ for security. GitLab Runner mounts a shared volume at `/certs` — the daemon writes its TLS cert there, and the client reads it.

### DOCKER_DRIVER: overlay2

The storage driver for Docker layers. `overlay2` is the fastest and most compatible driver for CI environments.

### $CI_REGISTRY, $CI_REGISTRY_USER, $CI_REGISTRY_PASSWORD

Predefined variables GitLab injects automatically:
- `$CI_REGISTRY` → `registry.gitlab.com`
- `$CI_REGISTRY_USER` → your GitLab username (job token username)
- `$CI_REGISTRY_PASSWORD` → a short-lived job token (not your real password)
- `$CI_REGISTRY_IMAGE` → `registry.gitlab.com/group/project` (the full image path)

These let you push to the GitLab Registry without hardcoding credentials.

### Two tags: SHA + latest

```yaml
- docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
- docker build -t $CI_REGISTRY_IMAGE:latest .
```

Tagging with `$CI_COMMIT_SHA` gives you an **immutable, traceable** image — you can always find the exact commit that produced it. Tagging `latest` gives downstream tools (like staging deployments) a stable pointer. In production, avoid `latest` for deployments — always use the SHA tag.

---

## Kaniko — Docker Build Without DinD

```yaml
build-kaniko:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.14.0-debug
    entrypoint: [""]              # Override entrypoint to use shell
  script:
    - mkdir -p /kaniko/.docker
    # Write registry auth config
    - >-
      echo "{\"auths\":{\"$CI_REGISTRY\":{\"auth\":\"$(echo -n
      $CI_REGISTRY_USER:$CI_REGISTRY_PASSWORD | base64)\"}}}"
      > /kaniko/.docker/config.json
    # Build and push in one command (no Docker daemon needed)
    - >-
      /kaniko/executor
      --context $CI_PROJECT_DIR
      --dockerfile $CI_PROJECT_DIR/Dockerfile
      --destination $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      --cache=true
      --cache-repo=$CI_REGISTRY_IMAGE/cache
```

### Why Kaniko over DinD?

| | Docker-in-Docker | Kaniko |
|---|---|---|
| Docker daemon | Required (privileged) | Not needed |
| Security | Requires `privileged: true` | Runs unprivileged |
| Speed | Fast | Similar with caching |
| Cache | Local daemon cache | Registry-based cache |

Kaniko runs as a user-space build tool — it reads the Dockerfile and pushes layers directly to the registry, bypassing the need for a Docker daemon entirely. Preferred for security-conscious environments.

### entrypoint: [""]

Overrides Kaniko's default entrypoint so you can run shell commands (`mkdir`, `echo`) before invoking the executor. Without this override, the container would jump straight to the Kaniko executor.

### --cache=true and --cache-repo

Kaniko stores layer cache in the registry itself (at `$CI_REGISTRY_IMAGE/cache`). On subsequent builds, unchanged layers are pulled from this cache repo instead of rebuilt. This dramatically speeds up builds when only application code changes (base layers and dependencies are cached).

---

## Caching Docker Layers in CI

```yaml
build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_BUILDKIT: "1"         # Enable BuildKit for better caching
  cache:
    key: docker-layers-$CI_COMMIT_REF_SLUG
    paths:
      - .docker-cache/
  script:
    # Pull cache image first (ignore failure if not exists)
    - docker pull $CI_REGISTRY_IMAGE:cache || true
    # Build with cache-from
    - docker build
        --cache-from $CI_REGISTRY_IMAGE:cache
        --tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        --tag $CI_REGISTRY_IMAGE:cache
        .
    # Push both tags
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:cache
```

### DOCKER_BUILDKIT: "1"

Enables Docker BuildKit, which provides parallel layer building, better cache invalidation, and more efficient layer storage. Always enable this in CI.

### --cache-from

Tells Docker to reuse layers from a previously built image. The `|| true` on the pull ensures the build doesn't fail on the first run when no cache exists yet. On subsequent runs, unchanged layers (like `RUN pip install`) are pulled from the cache image instead of recomputed.

---

## Key Takeaways

- **`services: docker:24-dind`**: Provides the Docker daemon for `docker build` commands inside CI jobs
- **`$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA`**: The production-standard image tag — immutable and traceable
- **Kaniko**: Build Docker images without a daemon — better security, preferred in restricted environments
- **`--cache-from`**: Use a registry-stored cache image to skip rebuilding unchanged layers
- **`entrypoint: [""]`**: Required when using Kaniko (or any executor image) to run shell commands before the tool
- **`DOCKER_TLS_CERTDIR`**: Required for secure DinD communication since Docker 19.03
- **`docker logout` in `after_script`**: Cleans up credentials even if the build fails
