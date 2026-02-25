#!/bin/bash
# Install OpenFaaS on Kubernetes using Helm
# OpenFaaS gives you a proper FaaS platform — function auto-scaling, UI, CLI, event connectors
#
# Prerequisites:
#   - kubectl configured
#   - Helm 3 installed
#   - A running Kubernetes cluster

set -e

echo "==> Adding OpenFaaS Helm repo..."
helm repo add openfaas https://openfaas.github.io/faas-netes/
helm repo update

echo "==> Creating namespaces..."
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml

echo "==> Generating admin password..."
PASSWORD=$(head -c 12 /dev/urandom | shasum | cut -d ' ' -f1)
kubectl -n openfaas create secret generic basic-auth \
  --from-literal=basic-auth-user=admin \
  --from-literal=basic-auth-password="$PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "Admin password: $PASSWORD"
echo "Save this — you'll need it to log into the OpenFaaS UI and CLI"
echo ""

echo "==> Installing OpenFaaS..."
helm upgrade --install openfaas openfaas/openfaas \
  --namespace openfaas \
  -f openfaas-values.yaml

echo ""
echo "==> Waiting for OpenFaaS to be ready..."
kubectl rollout status -n openfaas deploy/gateway --timeout=120s

echo ""
echo "==> OpenFaaS installed!"
echo ""
echo "Access the UI:"
echo "  kubectl port-forward -n openfaas svc/gateway 8080:8080"
echo "  Open http://localhost:8080  (user: admin, pass: $PASSWORD)"
echo ""
echo "Install faas-cli:"
echo "  curl -sL https://cli.openfaas.com | sudo sh"
echo ""
echo "Login:"
echo "  echo -n $PASSWORD | faas-cli login --username admin --password-stdin --gateway http://localhost:8080"
