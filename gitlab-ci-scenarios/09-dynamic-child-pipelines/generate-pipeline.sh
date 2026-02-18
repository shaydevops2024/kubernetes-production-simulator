#!/bin/sh
# generate-pipeline.sh - Generates child pipeline YAML based on detected changes
# This script outputs valid .gitlab-ci.yml to stdout

cat << 'HEADER'
# Auto-generated child pipeline
# Only includes jobs for changed services

stages:
  - build
  - test
  - deploy
HEADER

# Build-all override
if [ "$BUILD_ALL" = "true" ]; then
  API_CHANGED=true
  WEB_CHANGED=true
  WORKER_CHANGED=true
fi

# Generate API service jobs
if [ "$API_CHANGED" = "true" ]; then
cat << 'API'

# --- API Service ---
build-api:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.14.0-debug
    entrypoint: [""]
  script:
    - /kaniko/executor
        --context $CI_PROJECT_DIR/services/api
        --destination $CI_REGISTRY_IMAGE/api:$CI_COMMIT_SHA
        --cache=true

test-api:
  stage: test
  image: python:3.11
  script:
    - cd services/api
    - pip install -r requirements.txt
    - pytest tests/ -v
  needs: [build-api]

deploy-api:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl set image deployment/api api=$CI_REGISTRY_IMAGE/api:$CI_COMMIT_SHA -n production
  needs: [test-api]
  environment:
    name: production/api
API
fi

# Generate Web service jobs
if [ "$WEB_CHANGED" = "true" ]; then
cat << 'WEB'

# --- Web Service ---
build-web:
  stage: build
  image: node:20-alpine
  script:
    - cd services/web
    - npm ci
    - npm run build
  artifacts:
    paths:
      - services/web/dist/

test-web:
  stage: test
  image: node:20-alpine
  script:
    - cd services/web
    - npm ci
    - npm test
  needs: [build-web]

deploy-web:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl set image deployment/web web=$CI_REGISTRY_IMAGE/web:$CI_COMMIT_SHA -n production
  needs: [test-web]
  environment:
    name: production/web
WEB
fi

# Generate Worker service jobs
if [ "$WORKER_CHANGED" = "true" ]; then
cat << 'WORKER'

# --- Worker Service ---
build-worker:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.14.0-debug
    entrypoint: [""]
  script:
    - /kaniko/executor
        --context $CI_PROJECT_DIR/services/worker
        --destination $CI_REGISTRY_IMAGE/worker:$CI_COMMIT_SHA
        --cache=true

test-worker:
  stage: test
  image: python:3.11
  script:
    - cd services/worker
    - pip install -r requirements.txt
    - pytest tests/ -v
  needs: [build-worker]

deploy-worker:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl set image deployment/worker worker=$CI_REGISTRY_IMAGE/worker:$CI_COMMIT_SHA -n production
  needs: [test-worker]
  environment:
    name: production/worker
WORKER
fi

# If nothing changed, add a no-op job
if [ "$API_CHANGED" != "true" ] && [ "$WEB_CHANGED" != "true" ] && [ "$WORKER_CHANGED" != "true" ]; then
cat << 'NOOP'

no-changes:
  stage: build
  script:
    - echo "No service changes detected. Nothing to build."
NOOP
fi
