# Project 12: Enterprise Secrets Management Platform

Build a production-grade secrets management system using **HashiCorp Vault**. You'll learn how secrets are stored, rotated, dynamically generated, and audited — the way it's actually done in real companies.

---

## What You're Building

A full Vault-powered secrets platform where:

- **Secrets never live in your code or config files** — Vault is the single source of truth
- **Database credentials are generated on-demand** — Vault creates a unique username/password per app, per request, and they expire automatically
- **Certificates are issued dynamically** — your PKI infrastructure runs inside Vault
- **Every action is audited** — who accessed what secret, when, from where
- **Emergency break-glass** — documented procedure for when Vault is unavailable

You'll also deploy a **Secrets Dashboard UI** so you can visually see all of this happening in real time.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Secrets Dashboard UI (:5555)                      │
│         Vault Status · KV Secrets · DB Credentials · PKI             │
│              Transit Encryption · Audit Logs                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ API calls (hvac / vault CLI)
                ┌───────────▼──────────────┐
                │    HashiCorp Vault        │
                │  ┌────────────────────┐  │
                │  │  KV v2 (secrets/)  │  │  ← Store app secrets
                │  │  Database Engine   │  │  ← Dynamic DB creds
                │  │  PKI Engine        │  │  ← TLS certificates
                │  │  Transit Engine    │  │  ← Encrypt/decrypt data
                │  │  Audit Logging     │  │  ← Who did what, when
                │  │  Kubernetes Auth   │  │  ← Pod identity
                │  └────────────────────┘  │
                └───────────┬──────────────┘
                            │ dynamic credentials
                ┌───────────▼──────────────┐
                │       PostgreSQL          │
                │  (Vault manages users)    │
                └───────────────────────────┘
```

---

## Folder Structure

```
project-12-secrets-management/
├── README.md              ← You are here
├── app/
│   ├── README.md          ← App overview, API endpoints, environment variables
│   ├── main.py            ← FastAPI dashboard (Vault client)
│   ├── Dockerfile         ← Container definition
│   └── requirements.txt   ← Python dependencies
├── local/
│   ├── README.md          ← Step-by-step local setup guide with DevOps tasks
│   ├── docker-compose.yml ← Vault + PostgreSQL + Dashboard
│   └── vault/
│       └── init.sh        ← Vault initialization script (enables engines, configures DB)
├── main/
│   └── README.md          ← K8s deployment guide — what you must build
└── solution/
    ├── k8s/               ← Complete Kubernetes manifests
    ├── helm/              ← Vault Helm chart values
    └── scripts/           ← Setup, rotation, and break-glass scripts
```

---

## Your DevOps Journey

This project has **5 phases**. Each builds on the previous.

### Phase 1 — Understand the App (app/)
Read how the Vault dashboard works. Understand what API endpoints it exposes and how it talks to Vault. You don't write the app — you deploy and configure the infrastructure around it.

### Phase 2 — Run Locally (local/)
Start the full stack with Docker Compose: Vault + PostgreSQL + Dashboard. Explore every Vault feature through the UI and CLI. This is your learning sandbox.

### Phase 3 — Dynamic Secrets (local/ tasks)
Configure database secrets engine, request dynamic credentials, watch them expire. Understand WHY dynamic secrets matter over static passwords.

### Phase 4 — PKI & Encryption (local/ tasks)
Set up a PKI certificate authority inside Vault. Generate certificates for services. Use Transit engine to encrypt sensitive data at rest.

### Phase 5 — Deploy to Kubernetes (main/)
Deploy Vault to your Kind cluster, configure Kubernetes auth, inject secrets into pods using Vault Agent, and automate rotation.

---

## Key Concepts You'll Learn

| Concept | Why It Matters |
|---------|---------------|
| **Dynamic Secrets** | Database passwords that auto-expire eliminate the "shared password" problem |
| **Secret Leases** | Every secret has a TTL — when it expires, it's gone. Forces rotation. |
| **Kubernetes Auth** | Pods authenticate to Vault using their ServiceAccount token — no static tokens |
| **Vault Agent Injector** | Secrets are injected into pods as files — app doesn't need Vault SDK |
| **PKI Engine** | Vault becomes your Certificate Authority — no more self-signed cert hell |
| **Transit Engine** | Encrypt-as-a-service — apps encrypt data without managing encryption keys |
| **Audit Logging** | Compliance requirement — every secret access is logged with who/when/where |
| **Break-Glass** | Emergency procedure when Vault is down — sealed, unreachable, or misconfigured |

---

## Prerequisites

- Docker & Docker Compose installed
- `kubectl` configured for a Kind cluster (for Phase 5)
- `vault` CLI installed (optional — the dashboard UI covers most things)
- Basic understanding of containers and Kubernetes

---

## Start Here

**→ [Read app/README.md](./app/README.md)** — understand the dashboard app

Then follow the progression: `app/` → `local/` → `main/`
