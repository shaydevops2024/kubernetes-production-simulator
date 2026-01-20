# Makefile
# Convenient commands for the project

.PHONY: help setup build deploy test clean status logs

help:
	@echo "🚀 Kubernetes Demo Project"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup    - Create kind cluster"
	@echo "  make build    - Build Docker image"
	@echo "  make deploy   - Deploy everything to Kubernetes"
	@echo "  make test     - Run load test"
	@echo "  make status   - Show cluster status"
	@echo "  make logs     - Show application logs"
	@echo "  make clean    - Delete everything"

setup:
	@echo "Creating kind cluster..."
	kind create cluster --name k8s-multi-demo
	@echo "✅ Cluster created!"

build:
	@echo "Building Docker image..."
	cd app && docker build -t k8s-multi-demo-app:latest .
	kind load docker-image k8s-multi-demo-app:latest --name k8s-multi-demo
	@echo "✅ Image built and loaded!"

deploy:
	@echo "Deploying application..."
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh

test:
	@echo "Running load test..."
	chmod +x scripts/load-test.sh
	./scripts/load-test.sh

status:
	@echo "📊 Cluster Status:"
	@echo ""
	kubectl get nodes
	@echo ""
	kubectl get pods -n k8s-multi-demo
	@echo ""
	kubectl get svc -n k8s-multi-demo
	@echo ""
	kubectl get hpa -n k8s-multi-demo

logs:
	kubectl logs -f -l app=k8s-multi-demo-app -n k8s-multi-demo --tail=50

clean:
	@echo "🗑️  Deleting cluster..."
	kind delete cluster --name k8s-multi-demo
	@echo "✅ Cluster deleted!"
