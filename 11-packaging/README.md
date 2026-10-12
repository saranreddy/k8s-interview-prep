# Module 11: Packaging & Delivery

**Weight**: 5% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Helm fundamentals and chart structure
- Helm templating and values
- Kustomize and overlay patterns
- Argo CD basics and GitOps
- Application packaging best practices
- Release management

## Edge Cases

1. **Helm dependency conflicts**: Charts requiring incompatible versions
2. **Kustomize merge conflicts**: Overlays overriding unexpected fields
3. **Argo CD sync loops**: App never reaches synced state
4. **Template rendering errors**: Invalid YAML from Helm templates
5. **Order-dependent resources**: Some resources must be created before others

---

## Labs

### Lab 1: Helm basics

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Add repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Search charts
helm search repo nginx

# Install chart
helm install my-nginx bitnami/nginx

# List releases
helm list

# Check status
helm status my-nginx

# Get values
helm get values my-nginx

# Upgrade
helm upgrade my-nginx bitnami/nginx --set service.type=LoadBalancer

# Rollback
helm rollback my-nginx 1

# Uninstall
helm uninstall my-nginx
```

### Lab 2: Create a Helm chart

```bash
# Create chart skeleton
helm create myapp

# Chart structure:
# myapp/
#   Chart.yaml          # Metadata
#   values.yaml         # Default values
#   templates/          # K8s manifests with templates
#     deployment.yaml
#     service.yaml
#     ingress.yaml
#   .helmignore         # Files to ignore

# Edit values.yaml
cat > myapp/values.yaml <<EOF
replicaCount: 2

image:
  repository: nginx
  tag: "1.19"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
EOF

# Lint chart
helm lint myapp

# Dry-run (see rendered manifests)
helm install --dry-run --debug myapp ./myapp

# Install
helm install myapp ./myapp

# Override values
helm install myapp ./myapp --set replicaCount=3
helm install myapp ./myapp -f custom-values.yaml
```

### Lab 3: Helm templating

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "myapp.fullname" . }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "myapp.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "myapp.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - containerPort: 80
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
        {{- if .Values.extraEnv }}
        env:
          {{- toYaml .Values.extraEnv | nindent 10 }}
        {{- end }}
```

### Lab 4: Kustomize basics

```bash
# Create base manifests
mkdir -p k8s-app/{base,overlays/dev,overlays/prod}

# base/deployment.yaml
cat > k8s-app/base/deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: nginx:1.19
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
EOF

# base/kustomization.yaml
cat > k8s-app/base/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- deployment.yaml
- service.yaml

commonLabels:
  app.kubernetes.io/name: myapp
EOF

# overlays/dev/kustomization.yaml
cat > k8s-app/overlays/dev/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: dev

resources:
- ../../base

replicas:
- name: myapp
  count: 1

images:
- name: nginx
  newTag: 1.19-dev
EOF

# overlays/prod/kustomization.yaml
cat > k8s-app/overlays/prod/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: prod

resources:
- ../../base

replicas:
- name: myapp
  count: 3

images:
- name: nginx
  newTag: 1.19

patches:
- path: resources-patch.yaml
EOF

# Build manifests
kubectl kustomize k8s-app/overlays/dev

# Apply
kubectl apply -k k8s-app/overlays/dev
kubectl apply -k k8s-app/overlays/prod
```

### Lab 5: Kustomize patches

```bash
# Strategic merge patch
cat > k8s-app/overlays/prod/resources-patch.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
      - name: app
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
EOF

# JSON6902 patch
cat > k8s-app/overlays/prod/kustomization.yaml <<EOF
patches:
- target:
    kind: Deployment
    name: myapp
  patch: |-
    - op: add
      path: /spec/template/spec/containers/0/env
      value:
      - name: ENV
        value: production
EOF
```

### Lab 6: Argo CD (conceptual)

```bash
# Install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -n argocd --all --timeout=300s

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port forward
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Create application
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/myrepo
    targetRevision: main
    path: k8s-app/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
EOF

# Sync app
kubectl -n argocd patch app myapp -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{}}}' --type merge
```

---

## Break-and-Fix Exercise

**Scenario**: A Helm chart deployment fails with a template rendering error.

**Setup**:
```bash
helm create broken-chart
# Intentionally break template
cat > broken-chart/templates/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.name }}
spec:
  replicas: {{ .Values.replicaCount
  # Missing closing brace ^
EOF

helm install broken broken-chart
```

**Your task**: Fix the Helm template error.

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
# Try to install
helm install broken broken-chart
# Error: template: broken-chart/templates/deployment.yaml: incomplete template

# Dry-run to see rendered template
helm install --dry-run --debug broken broken-chart
```

**Root cause**: Missing closing `}}` in template.

**Fix**:
```yaml
replicas: {{ .Values.replicaCount }}
```

**Verification**:
```bash
helm lint broken-chart
helm install broken broken-chart
```

</details>

---

## Interview Questions

### Question 1
What is Helm? Explain charts, releases, and repositories.

<details>
<summary>Answer</summary>

**Helm**: Package manager for Kubernetes (like apt/yum for Linux).

**Three core concepts**:

**1. Chart**:
- Package containing K8s manifest templates
- Includes metadata, default values, templates
- Versioned and distributable

Structure:
```
mychart/
├── Chart.yaml          # Metadata (name, version)
├── values.yaml         # Default configuration
├── templates/          # K8s manifest templates
│   ├── deployment.yaml
│   ├── service.yaml
│   └── _helpers.tpl
├── charts/             # Dependencies
└── README.md
```

**2. Release**:
- Running instance of a chart
- One chart → many releases
- Each release has unique name

Example:
```bash
# Same chart, three releases
helm install prod-db bitnami/postgresql
helm install dev-db bitnami/postgresql
helm install test-db bitnami/postgresql
```

**3. Repository**:
- Collection of charts
- HTTP server with index.yaml
- Charts can be shared via repos

Popular repos:
- Bitnami: https://charts.bitnami.com/bitnami
- Stable: https://charts.helm.sh/stable
- Your own: Harbor, ChartMuseum, GitHub Pages

**Helm workflow**:
```bash
# 1. Add repo
helm repo add bitnami https://charts.bitnami.com/bitnami

# 2. Search
helm search repo nginx

# 3. Install (creates release)
helm install my-nginx bitnami/nginx

# 4. Upgrade release
helm upgrade my-nginx bitnami/nginx --set replicaCount=3

# 5. Rollback release
helm rollback my-nginx 1

# 6. Uninstall release
helm uninstall my-nginx
```

**Benefits**:
- Reusable application packages
- Version control for deployments
- Easy upgrades and rollbacks
- Parameterized configurations
- Dependency management

**When to use**:
- Deploying complex applications
- Managing multiple environments
- Need rollback capability
- Sharing applications across teams

</details>

### Question 2
Helm vs Kustomize - what's the difference? When to use each?

<details>
<summary>Answer</summary>

| Aspect | Helm | Kustomize |
|--------|------|-----------|
| **Approach** | Templates + values | Base + overlays |
| **Language** | Go templates | YAML patches |
| **Complexity** | More powerful | Simpler |
| **Learning curve** | Steeper | Gentler |
| **Built-in to kubectl** | No (separate binary) | Yes (kubectl -k) |

**Helm**:

Strengths:
- Full templating power (conditionals, loops, functions)
- Package management (repos, versions)
- Release management (history, rollback)
- Large ecosystem of charts

```yaml
# Template
replicas: {{ .Values.replicaCount }}
image: {{ .Values.image.repository }}:{{ .Values.image.tag }}

# Values file
replicaCount: 3
image:
  repository: nginx
  tag: "1.19"
```

Weaknesses:
- Complex templating syntax
- Hard to read rendered output
- "Magic" (not pure YAML)

**Kustomize**:

Strengths:
- Pure YAML (no templates)
- Easy to understand
- Built into kubectl
- GitOps-friendly

```yaml
# Base
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp

# Overlay (dev)
namespace: dev
replicas:
- name: myapp
  count: 1

# Overlay (prod)
namespace: prod
replicas:
- name: myapp
  count: 3
```

Weaknesses:
- Limited templating (no conditionals)
- No package management
- Can't share across repos easily

**When to use Helm**:
- Complex applications
- Need conditionals/loops
- Want package distribution
- Using community charts (Prometheus, MySQL, etc.)
- Multiple teams/repos

**When to use Kustomize**:
- Simple applications
- GitOps workflows
- Environment variations (dev/stage/prod)
- Want to avoid templates
- Pure YAML preference

**Can use both**:
- Helm for base (e.g., Prometheus chart)
- Kustomize for customization
```bash
helm template prometheus prometheus/prometheus > base/prometheus.yaml
# Then use Kustomize overlays
```

**Real-world pattern**:
- Infrastructure charts (databases, monitoring): Helm
- Application deployment: Kustomize
- Simple apps: Kustomize
- Complex multi-component apps: Helm

</details>

### Question 3
What is GitOps? How does Argo CD implement it?

<details>
<summary>Answer</summary>

**GitOps**: Git as single source of truth for infrastructure and applications.

**Core principles**:
1. Declarative: Entire system described declaratively
2. Versioned: Stored in Git
3. Immutable: Git history is append-only
4. Automated: Software agents ensure actual state matches desired state

**Traditional deployment**:
```
Developer → kubectl apply → Cluster
(Imperative, no audit trail)
```

**GitOps deployment**:
```
Developer → Git Push → Argo CD → Cluster
(Declarative, versioned, automated)
```

**Argo CD**: Kubernetes controller implementing GitOps

**How it works**:
1. Monitor Git repo for changes
2. Compare desired state (Git) vs actual state (cluster)
3. Sync differences automatically (or on request)
4. Report sync status

**Argo CD architecture**:
```
Git Repo ← watches ← Argo CD (in cluster) → syncs → Application (in cluster)
```

**Creating Argo Application**:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo
    targetRevision: main
    path: k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true      # Delete resources not in Git
      selfHeal: true   # Revert manual changes
```

**Sync policies**:

**Manual sync**:
- Changes require manual approval
- Review before deployment

**Automated sync**:
- Changes auto-deployed
- Faster feedback

**Self-heal**:
- Reverts manual kubectl changes
- Enforces Git as source of truth

**Prune**:
- Deletes resources removed from Git
- Keeps cluster clean

**Benefits**:
- Audit trail (all changes in Git)
- Easy rollback (git revert)
- Disaster recovery (git clone)
- Multi-cluster management
- No cluster credentials on CI/CD

**Workflow**:
```bash
# 1. Developer commits
git add k8s/
git commit -m "Update image to v1.2.3"
git push

# 2. Argo CD detects change
# Shows "OutOfSync"

# 3. Auto-sync or manual sync
# Argo CD applies changes to cluster

# 4. Cluster updated
# Argo CD shows "Synced, Healthy"
```

**Argo CD vs Flux**:
- Both are GitOps tools
- Argo CD: Better UI, more features
- Flux: Lighter, true Kubernetes-native

</details>

### Question 4
How do you handle secrets in Helm charts?

<details>
<summary>Answer</summary>

**Problem**: Secrets shouldn't be in Git or Helm values files.

**Solutions**:

**1. External Secrets Operator** (best for production):
```yaml
# Store secret in AWS Secrets Manager, Vault, etc.
# Reference in K8s
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-secret
spec:
  secretStoreRef:
    name: aws-secrets-manager
  target:
    name: db-secret
  data:
  - secretKey: password
    remoteRef:
      key: prod/db/password
```

In Helm chart:
```yaml
# Just reference the secret name
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-secret
      key: password
```

**2. Sealed Secrets**:
```bash
# Encrypt secret
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# Commit sealed-secret.yaml to Git (safe!)
git add sealed-secret.yaml

# Helm chart includes sealed secret
# Controller decrypts in cluster
```

**3. Helm Secrets plugin**:
```bash
# Install plugin
helm plugin install https://github.com/jkroepke/helm-secrets

# Encrypt values file
helm secrets encrypt secrets.yaml

# Use encrypted file
helm secrets install myapp ./mychart -f secrets.yaml
```

**4. Separate values file** (manual, less secure):
```bash
# values.yaml (in Git)
image: nginx:1.19
replicas: 3

# secrets.yaml (NOT in Git, manual management)
database:
  password: supersecret

# Install
helm install myapp ./chart -f values.yaml -f secrets.yaml
```

**5. Pass at install time**:
```bash
# Don't store in values file at all
helm install myapp ./chart \
  --set database.password=$DB_PASSWORD
```

**6. Post-render hook**:
```bash
# Helm post-renderer that injects secrets
helm install myapp ./chart --post-renderer ./inject-secrets.sh
```

**Best practice**:
1. **Never** commit secrets to Git
2. Use external secret manager (AWS Secrets Manager, Vault)
3. Reference secrets by name in charts
4. Rotate secrets regularly
5. Use RBAC to limit secret access

**Chart design for secrets**:
```yaml
# Don't include secret values
# Just reference secret names
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretName }}  # User provides
      key: api-key

# Or make it conditional
{{- if .Values.existingSecret }}
secretKeyRef:
  name: {{ .Values.existingSecret }}
{{- else }}
# Create secret from values (dev only)
{{- end }}
```

</details>

### Question 5
What are Helm hooks? Give examples of when you'd use them.

<details>
<summary>Answer</summary>

**Helm hooks**: Execute K8s resources at specific points in release lifecycle.

**Available hooks**:
- pre-install
- post-install
- pre-delete
- post-delete
- pre-upgrade
- post-upgrade
- pre-rollback
- post-rollback
- test

**Hook lifecycle**:
```
helm install
  → pre-install hooks run
  → resources created
  → post-install hooks run
  → release complete
```

**Creating a hook**:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  annotations:
    "helm.sh/hook": pre-upgrade
    "helm.sh/hook-weight": "1"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: myapp:{{ .Values.image.tag }}
        command: ["./migrate-db.sh"]
      restartPolicy: Never
```

**Hook annotations**:

**helm.sh/hook**:
```yaml
"helm.sh/hook": pre-install,pre-upgrade
# Comma-separated list
```

**helm.sh/hook-weight**:
```yaml
"helm.sh/hook-weight": "5"
# Lower weight runs first (can be negative)
# Default: 0
```

**helm.sh/hook-delete-policy**:
```yaml
"helm.sh/hook-delete-policy": before-hook-creation
# Options:
# - before-hook-creation: Delete previous hook
# - hook-succeeded: Delete after success
# - hook-failed: Delete after failure
```

**Use cases**:

**1. Database migration** (pre-upgrade):
```yaml
annotations:
  "helm.sh/hook": pre-upgrade
  "helm.sh/hook-weight": "-1"
# Run before app upgrade
```

**2. Backup** (pre-delete):
```yaml
annotations:
  "helm.sh/hook": pre-delete
# Backup data before deletion
```

**3. Health check** (test):
```yaml
annotations:
  "helm.sh/hook": test
# Run with: helm test <release>
```

**4. Initial setup** (post-install):
```yaml
annotations:
  "helm.sh/hook": post-install
# Create initial admin user
```

**5. Cleanup** (post-delete):
```yaml
annotations:
  "helm.sh/hook": post-delete
# Remove PVCs, external resources
```

**Multiple hooks with weights**:
```yaml
# Hook 1: Backup (weight -2)
annotations:
  "helm.sh/hook": pre-upgrade
  "helm.sh/hook-weight": "-2"

# Hook 2: Stop traffic (weight -1)
annotations:
  "helm.sh/hook": pre-upgrade
  "helm.sh/hook-weight": "-1"

# Hook 3: Migrate (weight 0)
annotations:
  "helm.sh/hook": pre-upgrade
  "helm.sh/hook-weight": "0"

# Then regular resources deployed
```

**Hook failure**:
- Hook fails → entire release fails
- No partial state
- Can configure deletion policy

**Testing hooks**:
```bash
helm install --debug --dry-run myapp ./chart
# Shows hooks in output

helm install myapp ./chart
# Hooks execute

helm test myapp
# Runs test hooks
```

</details>
