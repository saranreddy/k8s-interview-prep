# Module 08: Security

**Weight**: 10% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- RBAC: Roles, ClusterRoles, RoleBindings, ClusterRoleBindings
- ServiceAccounts and token projection
- Pod Security Standards: Privileged, Baseline, Restricted
- SecurityContext: runAsUser, runAsNonRoot, capabilities, seccomp
- IRSA (IAM Roles for Service Accounts) on EKS
- Network Policies (covered in Module 04)

## Edge Cases

1. **Forbidden errors**: Missing RBAC permissions
2. **Default ServiceAccount**: Pods use default SA if not specified
3. **Running as root**: Security risk, many images default to root
4. **Privilege escalation**: allowPrivilegeEscalation defaults to true
5. **Namespace-level RBAC**: Roles are namespaced, ClusterRoles are not

---

## Labs

### Lab 1: ServiceAccounts

```bash
# Create ServiceAccount
kubectl create serviceaccount my-sa

# Check it
kubectl get serviceaccount my-sa -o yaml

# Use in pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: sa-pod
spec:
  serviceAccountName: my-sa
  containers:
  - name: app
    image: nginx
EOF

# Check mounted token
kubectl exec sa-pod -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
```

### Lab 2: Create Role and RoleBinding

```bash
# Create Role (namespace-scoped)
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
EOF

# Create RoleBinding
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods
  namespace: default
subjects:
- kind: ServiceAccount
  name: my-sa
  namespace: default
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
EOF

# Test permissions
kubectl auth can-i list pods --as=system:serviceaccount:default:my-sa
# yes
kubectl auth can-i delete pods --as=system:serviceaccount:default:my-sa
# no
```

### Lab 3: ClusterRole and ClusterRoleBinding

```bash
# ClusterRole (cluster-wide)
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list"]
EOF

# ClusterRoleBinding
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: read-nodes
subjects:
- kind: ServiceAccount
  name: my-sa
  namespace: default
roleRef:
  kind: ClusterRole
  name: node-reader
  apiGroup: rbac.authorization.k8s.io
EOF

# Test
kubectl auth can-i list nodes --as=system:serviceaccount:default:my-sa
```

### Lab 4: SecurityContext at pod level

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: security-context-demo
spec:
  securityContext:
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
  containers:
  - name: app
    image: busybox
    command: ["sh", "-c", "sleep 3600"]
EOF

# Check user/group
kubectl exec security-context-demo -- id
# uid=1000 gid=3000 groups=2000
```

### Lab 5: SecurityContext at container level

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: security-context-container
spec:
  containers:
  - name: app
    image: nginx
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
        add:
        - NET_BIND_SERVICE
      readOnlyRootFilesystem: true
    volumeMounts:
    - name: cache
      mountPath: /var/cache/nginx
    - name: run
      mountPath: /var/run
  volumes:
  - name: cache
    emptyDir: {}
  - name: run
    emptyDir: {}
EOF
```

### Lab 6: Pod Security Standards

```bash
# Label namespace for Pod Security Standards
kubectl label namespace default pod-security.kubernetes.io/enforce=baseline
kubectl label namespace default pod-security.kubernetes.io/warn=restricted

# Try to create privileged pod (blocked)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: privileged-pod
spec:
  containers:
  - name: app
    image: nginx
    securityContext:
      privileged: true
EOF
# Error: violates PodSecurity "baseline"

# Restricted pod (passes)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: restricted-pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: nginx
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
EOF
```

### Lab 7: Check RBAC permissions

```bash
# Check your permissions
kubectl auth can-i create deployments
kubectl auth can-i delete pods --namespace kube-system
kubectl auth can-i '*' '*' --all-namespaces

# Check as another user
kubectl auth can-i get pods --as=system:serviceaccount:default:my-sa

# Debug Forbidden errors
kubectl auth can-i list pods --as=system:serviceaccount:default:my-sa -v=10
```

---

## Break-and-Fix Exercise

**Scenario**: Your application pod keeps getting `Forbidden` errors when trying to list pods in its namespace.

**Setup**:
```bash
kubectl create serviceaccount app-sa

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  serviceAccountName: app-sa
  containers:
  - name: app
    image: bitnami/kubectl
    command: ['sh', '-c', 'while true; do kubectl get pods; sleep 5; done']
EOF
```

**Symptoms**:
```bash
kubectl logs app-pod
# Error: pods is forbidden: User "system:serviceaccount:default:app-sa" cannot list resource "pods"
```

**Your task**: Fix the RBAC permissions.

<details>
<summary>Solution</summary>

**Root cause**: ServiceAccount has no permissions.

**Fix**:
```bash
# Create Role
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-lister
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
EOF

# Create RoleBinding
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-sa-binding
subjects:
- kind: ServiceAccount
  name: app-sa
roleRef:
  kind: Role
  name: pod-lister
  apiGroup: rbac.authorization.k8s.io
EOF
```

**Verification**:
```bash
kubectl logs app-pod
# Should now list pods successfully
```

</details>

---

## Interview Questions

### Question 1
Explain RBAC in Kubernetes. What's the difference between Role and ClusterRole?

<details>
<summary>Answer</summary>

**RBAC** (Role-Based Access Control): Controls who can do what in the cluster.

**Four components**:
1. **Role / ClusterRole**: Defines permissions (what can be done)
2. **RoleBinding / ClusterRoleBinding**: Grants permissions (who can do it)

**Role vs ClusterRole**:

| Aspect | Role | ClusterRole |
|--------|------|-------------|
| **Scope** | Namespace | Cluster-wide |
| **Resources** | Namespaced resources | All resources including cluster-scoped |
| **Use case** | App-specific permissions | Admin, cluster resources, cross-namespace |

**Role example** (namespace-scoped):
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
# Can only access pods in "default" namespace
```

**ClusterRole example** (cluster-wide):
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
- apiGroups: [""]
  resources: ["nodes"]  # Cluster-scoped resource
  verbs: ["get", "list"]
```

**Bindings**:

**RoleBinding** (namespace-scoped):
```yaml
kind: RoleBinding
# Grants Role or ClusterRole permissions in ONE namespace
```

**ClusterRoleBinding** (cluster-wide):
```yaml
kind: ClusterRoleBinding
# Grants ClusterRole permissions across ALL namespaces
```

**Combinations**:

| Binding Type | Role Type | Result |
|--------------|-----------|--------|
| RoleBinding | Role | Namespace access |
| RoleBinding | ClusterRole | Namespace access (using cluster role) |
| ClusterRoleBinding | ClusterRole | Cluster-wide access |

**Checking permissions**:
```bash
kubectl auth can-i create deployments
kubectl auth can-i delete pods --namespace kube-system
kubectl auth can-i '*' '*'  # Am I cluster-admin?
```

</details>

### Question 2
What is a ServiceAccount? How does a pod use it?

<details>
<summary>Answer</summary>

**ServiceAccount**: Identity for processes running in pods.

**Why needed?**
- Pods need to talk to Kubernetes API
- ServiceAccount provides credentials
- Enables RBAC for pod-to-API communication

**Default behavior**:
- Every namespace has a "default" ServiceAccount
- Pods use "default" SA unless specified
- Token auto-mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`

**Creating ServiceAccount**:
```bash
kubectl create serviceaccount my-app-sa
```

**Using in pod**:
```yaml
spec:
  serviceAccountName: my-app-sa
```

**What's mounted in pod?**
```bash
$ ls /var/run/secrets/kubernetes.io/serviceaccount/
ca.crt      # API server CA certificate
namespace   # Pod's namespace
token       # JWT token for authentication
```

**Token content**:
```bash
kubectl exec <pod> -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
# Returns JWT token

# Decode JWT (not secret, just base64)
# Contains: namespace, service account name, expiry
```

**Using token to call API**:
```bash
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -H "Authorization: Bearer $TOKEN" \
     --cacert /var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
     https://kubernetes.default.svc/api/v1/namespaces/default/pods
```

**Disabling auto-mount**:
```yaml
spec:
  automountServiceAccountToken: false
# Pod won't have token
# Use when pod doesn't need API access
```

**Best practices**:
1. Create dedicated SA per application
2. Grant minimal permissions via RBAC
3. Don't use "default" SA for apps
4. Disable auto-mount if not needed

**ServiceAccount vs User**:
- ServiceAccount: For pods/applications
- User: For humans (managed outside K8s)

</details>

### Question 3
What are Pod Security Standards? Explain the three levels.

<details>
<summary>Answer</summary>

**Pod Security Standards**: Kubernetes-defined policies to enforce pod security.

**Three levels** (increasingly restrictive):

**1. Privileged**:
- No restrictions
- Allows all capabilities
- For trusted workloads (system pods)

**2. Baseline**:
- Minimally restrictive
- Prevents known privilege escalations
- Default for most apps

Restrictions:
- No privileged containers
- No hostPath volumes (with exceptions)
- No host network/PID/IPC
- Limited capabilities

**3. Restricted**:
- Heavily restricted
- Current security best practices
- For security-critical apps

Additional restrictions:
- Must run as non-root
- Must drop ALL capabilities
- No privilege escalation
- seccomp profile required
- Read-only root filesystem (recommended)

**Applying to namespace**:
```bash
# Enforce baseline, warn on restricted
kubectl label namespace default \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted
```

**Three modes**:
- **enforce**: Reject violating pods
- **warn**: Allow but show warning
- **audit**: Allow and log event

**Example violations**:

**Baseline violation**:
```yaml
# REJECTED
spec:
  containers:
  - name: app
    securityContext:
      privileged: true  # Not allowed
```

**Restricted violation**:
```yaml
# REJECTED at restricted level
spec:
  containers:
  - name: app
    image: nginx  # Runs as root by default
```

**Restricted-compliant pod**:
```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: nginx
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
```

**Migration strategy**:
1. Start with warn/audit only
2. Fix violations
3. Enable enforce

</details>

### Question 4
Explain securityContext. What's the difference between pod and container level?

<details>
<summary>Answer</summary>

**securityContext**: Security settings for pods and containers.

**Two levels**:

**Pod-level** (applies to all containers):
```yaml
spec:
  securityContext:
    runAsUser: 1000        # Run as UID 1000
    runAsGroup: 3000       # Primary GID
    fsGroup: 2000          # Volume ownership GID
    fsGroupChangePolicy: "OnRootMismatch"
    supplementalGroups: [4000, 5000]
```

**Container-level** (overrides pod-level):
```yaml
spec:
  containers:
  - name: app
    securityContext:
      runAsUser: 2000      # Override pod-level
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      privileged: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
        add:
        - NET_BIND_SERVICE
      seccompProfile:
        type: RuntimeDefault
      seLinuxOptions:
        level: "s0:c123,c456"
```

**Common settings**:

**runAsUser/runAsGroup**:
- UID/GID for container process
- 0 = root (avoid!)

**fsGroup**:
- Volume ownership group
- Files in volume owned by this GID
- Example: fsGroup: 2000 → all files have GID 2000

**runAsNonRoot**:
- Fails if image runs as root
- Security best practice

**allowPrivilegeEscalation**:
- Can process gain more privileges?
- Default: true (bad!)
- Set to false

**privileged**:
- Container has all host capabilities
- Like root on host
- Very dangerous

**capabilities**:
- Linux capabilities (fine-grained privileges)
- Drop all, add only needed
```yaml
capabilities:
  drop: [ALL]
  add: [NET_BIND_SERVICE]  # Bind to port <1024
```

**readOnlyRootFilesystem**:
- Container filesystem read-only
- Prevents tampering
- Need emptyDir for /tmp

**Example with volumes**:
```yaml
spec:
  securityContext:
    fsGroup: 2000
  containers:
  - name: app
    image: nginx
    securityContext:
      runAsUser: 1000
      readOnlyRootFilesystem: true
    volumeMounts:
    - name: cache
      mountPath: /var/cache/nginx
  volumes:
  - name: cache
    emptyDir: {}
```

**Checking effective user**:
```bash
kubectl exec pod -- id
# uid=1000 gid=3000 groups=2000
```

</details>

### Question 5
How do you troubleshoot "Forbidden" errors in Kubernetes?

<details>
<summary>Answer</summary>

**Forbidden error**: User/ServiceAccount lacks required RBAC permissions.

**Troubleshooting steps**:

**1. Identify the subject**:
```bash
# Who is making the request?
# - User: kubectl uses your credentials
# - ServiceAccount: pod uses its SA
kubectl get pod <pod> -o yaml | grep serviceAccountName
```

**2. Check current permissions**:
```bash
# Can I do this action?
kubectl auth can-i create deployments
kubectl auth can-i delete pods --namespace kube-system

# Check as another user/SA
kubectl auth can-i list pods \
  --as=system:serviceaccount:default:my-sa

# Check all permissions
kubectl auth can-i --list
```

**3. Find existing Roles/ClusterRoles**:
```bash
# List all roles
kubectl get roles --all-namespaces
kubectl get clusterroles

# Describe role
kubectl describe role <name>
kubectl describe clusterrole <name>
```

**4. Check RoleBindings**:
```bash
# Who has access?
kubectl get rolebindings --all-namespaces
kubectl get clusterrolebindings

# Describe binding
kubectl describe rolebinding <name>

# Find bindings for a ServiceAccount
kubectl get rolebindings,clusterrolebindings --all-namespaces -o json | \
  jq '.items[] | select(.subjects[]?.name=="my-sa")'
```

**5. Enable verbose logging**:
```bash
kubectl get pods --as=system:serviceaccount:default:my-sa -v=10
# Shows detailed API calls and authorization checks
```

**6. Check audit logs** (if enabled):
```bash
# On control plane node
grep "Forbidden" /var/log/kubernetes/audit/audit.log
```

**Common scenarios**:

**Scenario 1**: Pod can't list pods
```bash
# Check permission
kubectl auth can-i list pods --as=system:serviceaccount:default:app-sa
# no

# Grant permission
kubectl create role pod-reader --verb=get,list --resource=pods
kubectl create rolebinding app-binding --role=pod-reader --serviceaccount=default:app-sa
```

**Scenario 2**: Can't access resources in another namespace
```bash
# RoleBinding only grants access in its own namespace
# Solution: Create RoleBinding in target namespace
# Or use ClusterRoleBinding for cluster-wide
```

**Scenario 3**: Can't access cluster-scoped resources
```bash
# Need ClusterRole + ClusterRoleBinding
kubectl create clusterrole node-reader --verb=get,list --resource=nodes
kubectl create clusterrolebinding node-binding \
  --clusterrole=node-reader \
  --serviceaccount=default:app-sa
```

**Quick fix**:
```bash
# Temporary admin (DANGEROUS, dev only!)
kubectl create clusterrolebinding debug-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=default:app-sa

# Remove after debugging!
kubectl delete clusterrolebinding debug-admin
```

**Best practices**:
- Principle of least privilege
- Grant only needed permissions
- Use namespaced Roles when possible
- Avoid cluster-admin
- Regular permission audits

</details>
