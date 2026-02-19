# Jenkinsfile Explanation - Disaster Recovery Scenario

This guide explains the Jenkinsfile patterns for automating Jenkins backup and disaster recovery, covering `JENKINS_HOME` structure, critical files, `tar` backup commands, retention policies, and restore procedures.

---

## 🏠 JENKINS_HOME Directory Structure

Jenkins stores everything in the `$JENKINS_HOME` directory (default: `/var/jenkins_home` on Docker, `/var/lib/jenkins` on Linux).

```
$JENKINS_HOME/
├── config.xml                   ← Jenkins global configuration
├── credentials.xml              ← Encrypted credential store
├── secrets/
│   ├── master.key               ← Master encryption key (CRITICAL)
│   └── hudson.util.Secret       ← Secret key
├── jobs/                        ← All pipeline job definitions
│   ├── my-pipeline/
│   │   ├── config.xml           ← Job configuration
│   │   └── builds/
│   │       ├── 1/               ← Build #1 data
│   │       ├── 2/               ← Build #2 data
│   │       └── ...
│   └── another-job/
│       └── config.xml
├── plugins/                     ← Installed plugins (*.jpi, *.hpi)
│   ├── git.jpi
│   ├── pipeline-stage-view.jpi
│   └── ...
├── users/                       ← User accounts and API tokens
│   └── admin/
│       └── config.xml
├── nodes/                       ← Jenkins agent configurations
├── workspace/                   ← Active build workspaces (EXCLUDE from backup)
└── caches/                      ← Plugin caches (EXCLUDE from backup)
```

### Critical files to back up:

| File/Directory | Why It's Critical | Without it |
|---|---|---|
| `config.xml` | Jenkins global settings, security config | Lose all configuration |
| `credentials.xml` | All stored credentials (encrypted) | Lose all secrets |
| `secrets/master.key` | Decryption key for credentials | Can't decrypt credentials.xml |
| `secrets/hudson.util.Secret` | Additional encryption key | Partial credential loss |
| `jobs/*/config.xml` | All pipeline job definitions | Lose all pipeline configurations |
| `users/` | User accounts and API tokens | All users locked out |
| `plugins/` | Installed plugins | Must reinstall all plugins manually |
| `nodes/` | Agent configurations | Must reconfigure all agents |

### What NOT to back up:

| Exclude | Why |
|---|---|
| `workspace/` | Active build files — temporary, can be recreated |
| `caches/` | Plugin download caches — can be regenerated |
| `jobs/*/builds/*/log` | Build logs — large, not needed for recovery |
| `fingerprints/` | Artifact fingerprints — can be regenerated |
| `*.tmp` | Temporary files |

---

## 📦 The Backup `tar` Command

```groovy
sh """
    tar czf /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz \
      --exclude=${JENKINS_HOME}/workspace \
      --exclude=${JENKINS_HOME}/caches \
      --exclude='${JENKINS_HOME}/jobs/*/builds/*/log' \
      -C / \
      ${JENKINS_HOME#/}
"""
```

### `tar` flags explained:

| Flag | Description |
|---|---|
| `c` | Create a new archive |
| `z` | Compress with gzip |
| `f` | Specify the output file name |
| `--exclude=PATH` | Exclude a path from the archive |
| `-C /` | Change to directory `/` before archiving (makes paths relative) |
| `${JENKINS_HOME#/}` | Strip the leading `/` from the path (e.g., `var/jenkins_home`) |

### Why `-C /` and `${JENKINS_HOME#/}`?

Without `-C /`:
```bash
tar czf backup.tar.gz /var/jenkins_home
# Archive contains: /var/jenkins_home/config.xml
# Extract: restores to /var/jenkins_home/config.xml ← absolute path (risky)
```

With `-C /`:
```bash
tar czf backup.tar.gz -C / var/jenkins_home
# Archive contains: var/jenkins_home/config.xml
# Extract: restores relative to wherever you run tar ← flexible
```

### Multiple excludes:

```bash
tar czf backup.tar.gz \
  --exclude=/var/jenkins_home/workspace \
  --exclude=/var/jenkins_home/caches \
  --exclude='/var/jenkins_home/jobs/*/builds/*/log' \
  --exclude='/var/jenkins_home/jobs/*/builds/*/archive' \
  --exclude='*.tmp' \
  -C / var/jenkins_home
```

### Archive naming convention:

```groovy
def timestamp = sh(script: 'date +%Y%m%d-%H%M%S', returnStdout: true).trim()
def backupFile = "jenkins-backup-${timestamp}-build${BUILD_NUMBER}.tar.gz"
// Example: jenkins-backup-20240115-143022-build42.tar.gz
```

Using timestamps makes it easy to identify when a backup was taken.

---

## 🔐 Protecting the Backup

### What makes `credentials.xml` safe to backup?

Jenkins uses a two-key encryption model:
```
credentials.xml
  └── Contains encrypted values (AES-256 encrypted with secret key)

secrets/hudson.util.Secret
  └── The secret key (encrypted with master key)

secrets/master.key
  └── The master key (plaintext — protects the secret key)
```

To decrypt `credentials.xml`, an attacker needs ALL THREE files. If your backup contains all three, they can decrypt your credentials. Therefore:

**Backup security options:**

1. **Encrypt the backup itself:**
```groovy
sh """
    tar czf - -C / var/jenkins_home \
      --exclude=workspace --exclude=caches | \
    gpg --symmetric --passphrase-fd 0 \
        --cipher-algo AES256 \
        --output /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz.gpg
"""
```

2. **Separate the master key backup:**
Store `secrets/master.key` in a different secure location (Vault, AWS Secrets Manager) and exclude it from the main backup.

3. **Use encrypted storage for the backup target:**
- AWS S3 with server-side encryption
- Azure Blob Storage with encryption at rest
- Encrypted NFS mount

---

## 🗄️ The `buildDiscarder` for Backup Retention

```groovy
options {
    buildDiscarder(logRotator(
        numToKeepStr: '30',           // Keep the last 30 backup builds
        artifactNumToKeepStr: '30'    // Keep artifacts (backup files) for 30 builds
    ))
}
```

**Why retention matters for backup pipelines:**
- Each backup file might be 500MB+
- 30 backups × 500MB = 15GB of storage
- Without retention, backup storage fills up and the backup job fails

**Retention strategies:**

```groovy
// Daily backup: keep 30 days
buildDiscarder(logRotator(
    daysToKeepStr: '30',
    artifactDaysToKeepStr: '30'
))

// Weekly backup: keep 12 weeks
buildDiscarder(logRotator(
    numToKeepStr: '12',
    artifactNumToKeepStr: '12'
))

// Grandfather-Father-Son (GFS) strategy:
// - Daily: keep 7
// - Weekly: keep 4
// - Monthly: keep 12
// This requires logic outside of simple buildDiscarder
```

---

## ☁️ Uploading Backup to External Storage

```groovy
stage('Upload to S3') {
    steps {
        withCredentials([
            string(credentialsId: 'aws-access-key-id', variable: 'AWS_ACCESS_KEY_ID'),
            string(credentialsId: 'aws-secret-key', variable: 'AWS_SECRET_ACCESS_KEY')
        ]) {
            sh """
                aws s3 cp /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz \
                  s3://company-backups/jenkins/${BUILD_NUMBER}/ \
                  --sse aws:kms \
                  --storage-class STANDARD_IA
            """
        }
    }
}
```

**S3 options:**

| Option | Description |
|---|---|
| `--sse aws:kms` | Server-side encryption with KMS key |
| `--storage-class STANDARD_IA` | Infrequent Access (cheaper for backups rarely read) |
| `--storage-class GLACIER` | Very cheap, but 3-5 hour retrieval (for archival) |

---

## ⏰ Scheduled Backup Pipeline

```groovy
triggers {
    cron('H 2 * * *')     // Run at ~2am every day
}
```

**Combined with parameterized restore:**

```groovy
parameters {
    choice(
        name: 'ACTION',
        choices: ['backup', 'restore', 'verify'],
        description: 'Operation to perform'
    )
    string(
        name: 'RESTORE_FROM',
        defaultValue: '',
        description: 'Build number to restore from (restore only)'
    )
}
```

---

## 🔄 Restore Procedure

### Step 1: Download the backup

```groovy
stage('Download Backup') {
    when { expression { params.ACTION == 'restore' } }
    steps {
        withCredentials([...]) {
            sh """
                aws s3 cp \
                  s3://company-backups/jenkins/${params.RESTORE_FROM}/jenkins-backup-${params.RESTORE_FROM}.tar.gz \
                  /tmp/jenkins-restore.tar.gz
            """
        }
    }
}
```

### Step 2: Stop Jenkins (critical!)

```bash
# If running as a systemd service
sudo systemctl stop jenkins

# If running in Docker
docker stop jenkins-container

# If running in Kubernetes
kubectl scale deployment jenkins --replicas=0 -n jenkins
```

### Step 3: Extract the backup

```bash
# Clear current JENKINS_HOME (be careful!)
sudo rm -rf /var/jenkins_home/*

# Extract backup
sudo tar xzf /tmp/jenkins-restore.tar.gz -C /
# or
sudo tar xzf /tmp/jenkins-restore.tar.gz -C / --strip-components=0
```

### Step 4: Verify file permissions

```bash
# Jenkins process runs as the 'jenkins' user
sudo chown -R jenkins:jenkins /var/jenkins_home
sudo chmod 700 /var/jenkins_home/secrets/
sudo chmod 600 /var/jenkins_home/secrets/*
```

### Step 5: Restart Jenkins

```bash
sudo systemctl start jenkins
# or
docker start jenkins-container
# or
kubectl scale deployment jenkins --replicas=1 -n jenkins
```

### Step 6: Verify restoration

```groovy
stage('Verify Restore') {
    steps {
        sh "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/login"
        sh "ls ${JENKINS_HOME}/jobs | wc -l"
        sh "ls ${JENKINS_HOME}/credentials.xml"
        sh "ls ${JENKINS_HOME}/secrets/master.key"
    }
}
```

---

## 🔍 Backup Verification Pipeline

Don't assume a backup works — verify it periodically:

```groovy
stage('Verify Backup Integrity') {
    steps {
        sh """
            # Verify the archive is valid (not corrupted)
            tar tzf /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz > /dev/null 2>&1
            echo "Archive integrity: OK"

            # Check key files are present
            tar tzf /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz | grep -q 'config.xml'
            tar tzf /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz | grep -q 'credentials.xml'
            tar tzf /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz | grep -q 'master.key'
            echo "Critical files present: OK"

            # Check backup size is reasonable (not suspiciously small)
            SIZE=\$(stat -c%s /backup/jenkins-backup-${BUILD_NUMBER}.tar.gz)
            echo "Backup size: \$SIZE bytes"
            if [ \$SIZE -lt 1000000 ]; then
                echo "WARNING: Backup is suspiciously small (<1MB)"
                exit 1
            fi
        """
    }
}
```

---

## ☸️ Kubernetes CronJob for Jenkins Backup

For teams running Jenkins in Kubernetes, a CronJob provides the same automation:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: jenkins-backup
  namespace: jenkins
spec:
  schedule: "0 2 * * *"        # Daily at 2am
  concurrencyPolicy: Forbid    # Don't run if previous is still running
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: amazon/aws-cli:latest
            command:
            - /bin/sh
            - -c
            - |
              TIMESTAMP=$(date +%Y%m%d-%H%M%S)
              tar czf /tmp/jenkins-backup-${TIMESTAMP}.tar.gz \
                --exclude=/jenkins-home/workspace \
                --exclude=/jenkins-home/caches \
                -C / jenkins-home
              aws s3 cp /tmp/jenkins-backup-${TIMESTAMP}.tar.gz \
                s3://company-backups/jenkins/
            volumeMounts:
            - name: jenkins-home
              mountPath: /jenkins-home
              readOnly: true
          volumes:
          - name: jenkins-home
            persistentVolumeClaim:
              claimName: jenkins-pvc
```

---

## 📋 Disaster Recovery Checklist

### Before disaster:
- [ ] Automated daily backups configured with `cron` trigger
- [ ] Backups stored in external storage (S3, Azure Blob, GCS)
- [ ] `master.key` stored separately (different credentials/location)
- [ ] Backup integrity verified monthly
- [ ] Restore procedure documented and tested
- [ ] RTO (Recovery Time Objective) and RPO (Recovery Point Objective) defined

### After disaster (restore):
- [ ] Identify the most recent healthy backup (by timestamp)
- [ ] Stop Jenkins before restoring
- [ ] Download and verify backup integrity with `tar tzf`
- [ ] Extract to clean JENKINS_HOME
- [ ] Fix file permissions (`chown -R jenkins:jenkins`)
- [ ] Start Jenkins and verify login works
- [ ] Verify jobs are present and credentials are accessible
- [ ] Trigger a test pipeline run to confirm full functionality

---

## 🎯 Key Takeaways

1. **`JENKINS_HOME`** contains everything: config, credentials, jobs, plugins, user accounts
2. **`secrets/master.key` + `credentials.xml`** are the most critical files — back them up securely
3. **Exclude `workspace/` and `caches/`** — they're temporary and waste backup space
4. **`tar czf` with `--exclude`** creates compressed, filtered backups efficiently
5. **`buildDiscarder(logRotator(...))`** prevents backup storage from filling up indefinitely
6. **`cron('H 2 * * *')`** schedules automated daily backups at 2am (distributed load with `H`)
7. **Verify backup integrity** with `tar tzf` (list contents without extracting)
8. **Stop Jenkins before restoring** — never restore to a running instance
9. **Test your restore procedure** before you need it — broken backups are discovered in disasters

---

*A backup you've never tested restoring from is not a backup — it's a guess. The disaster recovery pipeline is only as good as its last verified restore. Schedule periodic restore drills.*
