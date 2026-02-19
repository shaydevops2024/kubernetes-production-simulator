# Jenkinsfile Explanation - Credentials and Secrets Scenario

This guide explains how Jenkins securely manages credentials, covers all credential types, and shows how Jenkins credentials integrate with Kubernetes Secrets.

---

## 🔐 Jenkins Credentials Store

Jenkins has a built-in encrypted credential store. Credentials are stored in `$JENKINS_HOME/credentials.xml`, encrypted with a master key (`$JENKINS_HOME/secrets/master.key`).

**Where to add credentials in Jenkins UI:**
`Jenkins` → `Manage Jenkins` → `Credentials` → `System` → `Global credentials` → `Add Credentials`

**Credential scopes:**

| Scope | Description |
|---|---|
| `Global` | Available to all jobs on the instance |
| `System` | Available only to Jenkins itself (e.g., email server settings) |
| `Folder` | Available only within a specific folder |

---

## 🔑 The `withCredentials()` Step

```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-registry-creds',
    usernameVariable: 'REGISTRY_USER',
    passwordVariable: 'REGISTRY_PASS'
)]) {
    sh "docker login ${REGISTRY} -u ${REGISTRY_USER} -p ${REGISTRY_PASS}"
    sh "docker push ${REGISTRY}/my-app:${BUILD_NUMBER}"
}
```

**What it is:** A pipeline step that securely injects credentials into a limited scope.

**Security guarantees:**
- Values are **masked** in console logs (shown as `****`)
- Variables are **only available** inside the `withCredentials` block
- Jenkins **never writes** credentials to disk in plaintext
- Even with `set -x` in shell, the values are masked

---

## 📂 Credential Types In Detail

### 1. Username + Password

**Common use:** Docker registry, Nexus, Artifactory, Git repositories

```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-hub',
    usernameVariable: 'DOCKER_USER',
    passwordVariable: 'DOCKER_PASS'
)]) {
    sh "docker login -u ${DOCKER_USER} -p ${DOCKER_PASS}"
}
```

**In Jenkins UI:** Enter username and password → Jenkins stores both encrypted.

---

### 2. Secret Text

**Common use:** API tokens, Slack webhooks, single-value secrets

```groovy
withCredentials([string(
    credentialsId: 'github-api-token',
    variable: 'GITHUB_TOKEN'
)]) {
    sh "curl -H 'Authorization: token ${GITHUB_TOKEN}' https://api.github.com/repos/..."
}
```

**In Jenkins UI:** Enter a single secret string.

---

### 3. SSH Username with Private Key

**Common use:** Git SSH authentication, server deployments

```groovy
withCredentials([sshUserPrivateKey(
    credentialsId: 'git-deploy-key',
    keyFileVariable: 'SSH_KEY_FILE',
    usernameVariable: 'SSH_USER'
)]) {
    sh '''
        eval $(ssh-agent -s)
        ssh-add ${SSH_KEY_FILE}
        git clone git@github.com:company/repo.git
    '''
}
```

**What Jenkins does:** Writes the private key to a temporary file (`SSH_KEY_FILE`), then deletes it after the block.

---

### 4. Secret File

**Common use:** Kubeconfig files, `.env` files, certificates, JSON service account keys

```groovy
withCredentials([file(
    credentialsId: 'production-kubeconfig',
    variable: 'KUBECONFIG'
)]) {
    sh "kubectl --kubeconfig=${KUBECONFIG} apply -f k8s/"
    sh "kubectl --kubeconfig=${KUBECONFIG} rollout status deployment/my-app"
}
```

**What Jenkins does:** Writes the file to a temp location, sets the variable to its path, then deletes it.

---

### 5. Certificate

**Common use:** PKI certificates, Java keystores, client authentication

```groovy
withCredentials([certificate(
    credentialsId: 'ssl-keystore',
    keystoreVariable: 'JKS_FILE',
    passwordVariable: 'JKS_PASSWORD'
)]) {
    sh """
        keytool -list -keystore ${JKS_FILE} -storepass ${JKS_PASSWORD}
        java -Djavax.net.ssl.keyStore=${JKS_FILE} \
             -Djavax.net.ssl.keyStorePassword=${JKS_PASSWORD} \
             -jar app.jar
    """
}
```

---

## 🔗 Using Credentials as Environment Variables (Alternative)

For credentials used throughout a pipeline, you can bind them in the `environment {}` block:

```groovy
environment {
    // Binds credentialsId 'aws-creds' as two env vars
    AWS_ACCESS_KEY_ID     = credentials('aws-access-key-id')
    AWS_SECRET_ACCESS_KEY = credentials('aws-secret-key')

    // For username+password, appends _USR and _PSW suffixes
    DOCKER_CREDS = credentials('docker-hub')
    // Creates: DOCKER_CREDS_USR and DOCKER_CREDS_PSW
}
```

**Usage:**
```groovy
sh "aws s3 ls"  // Uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY automatically
sh "docker login -u ${DOCKER_CREDS_USR} -p ${DOCKER_CREDS_PSW}"
```

**When to use `environment {}` vs `withCredentials()`:**
- `environment {}` → credential needed across multiple stages
- `withCredentials()` → credential needed in only one place (least privilege)

---

## ☸️ Jenkins Credentials vs Kubernetes Secrets

Understanding the relationship between Jenkins credentials and Kubernetes Secrets:

### Jenkins stores credentials for the CI/CD pipeline:
```
Jenkins Credential Store
├── docker-registry-creds (username+password)  → Used by: Docker push stage
├── production-kubeconfig (secret file)         → Used by: Deploy stage
├── github-api-token (secret text)              → Used by: GitHub API calls
└── slack-webhook (secret text)                 → Used by: post{} notifications
```

### Kubernetes stores secrets for the application:
```
Kubernetes Secret Store
├── db-credentials (Opaque)        → Used by: Application pods
├── tls-certificate (kubernetes.io/tls) → Used by: Ingress TLS
└── registry-pull-secret (docker-registry) → Used by: Pod image pulls
```

### Kubernetes Secret YAML structure:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
data:
  username: cG9zdGdyZXM=     # base64 encoded "postgres"
  password: c2VjcmV0MTIz     # base64 encoded "secret123"
```

**Important:** Kubernetes secrets are base64-encoded, NOT encrypted by default. To truly secure them:
- Enable etcd encryption at rest
- Use external secret managers (Vault, AWS Secrets Manager, Sealed Secrets)

**How Jenkins creates Kubernetes Secrets:**
```groovy
withCredentials([usernamePassword(
    credentialsId: 'db-creds',
    usernameVariable: 'DB_USER',
    passwordVariable: 'DB_PASS'
)]) {
    sh """
        kubectl create secret generic db-credentials \
          --from-literal=username=${DB_USER} \
          --from-literal=password=${DB_PASS} \
          --namespace=production \
          --dry-run=client -o yaml | kubectl apply -f -
    """
}
```

The `--dry-run=client -o yaml | kubectl apply -f -` pattern creates or updates the secret idempotently.

---

## 🛡️ Secret Management Best Practices

### 1. Never hardcode secrets in Jenkinsfile
```groovy
// WRONG - secret in plaintext, committed to git
environment {
    DB_PASSWORD = 'super-secret-123'
}

// CORRECT - reference Jenkins credential by ID
withCredentials([string(credentialsId: 'db-password', variable: 'DB_PASSWORD')]) {
    sh "connect-to-db --password=${DB_PASSWORD}"
}
```

### 2. Use credential IDs that describe the credential
```
docker-hub-prod-creds      ✅ (clear purpose)
creds1                     ❌ (unclear)
```

### 3. Rotate credentials regularly
- Set calendar reminders for credential rotation
- Jenkins has no built-in expiry — manage this manually

### 4. Audit credential usage
Jenkins logs which jobs accessed which credentials. Review in:
`Manage Jenkins` → `Credentials` → Click a credential → `Usage`

### 5. Integrate with external secret managers (production recommendation)

**HashiCorp Vault:**
```groovy
withVault(
    vaultSecrets: [[
        path: 'secret/docker-registry',
        secretValues: [
            [envVar: 'DOCKER_USER', vaultKey: 'username'],
            [envVar: 'DOCKER_PASS', vaultKey: 'password']
        ]
    ]]
) {
    sh "docker login -u ${DOCKER_USER} -p ${DOCKER_PASS}"
}
```

**AWS Secrets Manager:**
```groovy
script {
    def secret = sh(
        script: "aws secretsmanager get-secret-value --secret-id prod/db-password --query SecretString --output text",
        returnStdout: true
    ).trim()
    withEnv(["DB_PASSWORD=${secret}"]) {
        sh "connect-to-db --password=${DB_PASSWORD}"
    }
}
```

---

## 🔍 Kubernetes Secret Types Reference

| Type | Description | Common Use |
|---|---|---|
| `Opaque` | Arbitrary key-value pairs | Database passwords, API keys |
| `kubernetes.io/tls` | TLS certificate + key | Ingress HTTPS |
| `kubernetes.io/dockerconfigjson` | Docker registry credentials | Image pull secrets |
| `kubernetes.io/service-account-token` | ServiceAccount token | Pod auth to API server |
| `kubernetes.io/ssh-auth` | SSH private key | Git access from pods |
| `kubernetes.io/basic-auth` | Username + password | Basic auth |

### Creating a Docker registry pull secret:
```groovy
withCredentials([usernamePassword(
    credentialsId: 'docker-registry',
    usernameVariable: 'DOCKER_USER',
    passwordVariable: 'DOCKER_PASS'
)]) {
    sh """
        kubectl create secret docker-registry registry-pull-secret \
          --docker-server=my-registry.com \
          --docker-username=${DOCKER_USER} \
          --docker-password=${DOCKER_PASS} \
          --namespace=production \
          --dry-run=client -o yaml | kubectl apply -f -
    """
}
```

### Referencing in a Pod spec:
```yaml
spec:
  imagePullSecrets:
  - name: registry-pull-secret
  containers:
  - name: app
    image: my-registry.com/my-app:v1.0
```

---

## 🎯 Key Takeaways

1. **Jenkins Credentials Store** encrypts secrets at rest — never hardcode secrets in Jenkinsfiles
2. **`withCredentials()`** provides scoped, masked credential injection
3. **Five types:** `usernamePassword`, `string` (secret text), `sshUserPrivateKey`, `file`, `certificate`
4. **`environment { CREDS = credentials('id') }`** binds credentials as pipeline-wide env vars
5. **Jenkins credentials ≠ Kubernetes Secrets** — Jenkins manages CI/CD secrets; K8s manages app secrets
6. **K8s Secrets are base64, not encrypted** — use etcd encryption at rest or external secret managers for production
7. **Least privilege:** Use `withCredentials()` over pipeline-level `environment {}` when possible
8. **Audit credential usage** — Jenkins tracks which jobs access which credentials

---

*Proper credential management is the foundation of pipeline security. The patterns here eliminate the most common security mistake in CI/CD: committing secrets to source control.*
