# Module 06: Config & Secrets

**Weight**: 6% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- ConfigMaps for configuration data
- Secrets for sensitive data
- Mounting as environment variables vs volumes
- Base64 encoding and security considerations
- subPath mounts and updates
- Immutable ConfigMaps and Secrets

## Edge Cases

1. **Environment variables don't update**: Pods must be restarted to get new values
2. **Volume mounts DO update**: Files update automatically (with delay)
3. **subPath mounts don't update**: Mounted file never changes
4. **Base64 is not encryption**: Secrets are not encrypted by default
5. **ConfigMap size limit**: 1MB maximum per ConfigMap

---

## Labs

### Lab 1: ConfigMap basics

```bash
# Create ConfigMap from literal values
kubectl create configmap app-config \
  --from-literal=DB_HOST=localhost \
  --from-literal=DB_PORT=5432

# Create from file
echo "Hello from config file" > config.txt
kubectl create configmap file-config --from-file=config.txt

# Create from env file
cat <<EOF > app.env
API_KEY=abc123
DEBUG=true
EOF
kubectl create configmap env-config --from-env-file=app.env

# View ConfigMap
kubectl get configmap app-config -o yaml
kubectl describe configmap app-config
```

### Lab 2: Using ConfigMap as environment variables

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: config-env-pod
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'echo "DB_HOST=\$DB_HOST, DB_PORT=\$DB_PORT"; sleep 3600']
    env:
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: DB_HOST
    - name: DB_PORT
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: DB_PORT
EOF

kubectl logs config-env-pod
```

### Lab 3: Using ConfigMap as volume

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: config-volume-pod
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'while true; do cat /config/DB_HOST; sleep 5; done']
    volumeMounts:
    - name: config
      mountPath: /config
  volumes:
  - name: config
    configMap:
      name: app-config
EOF

# Check files created
kubectl exec config-volume-pod -- ls /config
kubectl exec config-volume-pod -- cat /config/DB_HOST

# Update ConfigMap (pod sees change automatically after ~60s)
kubectl create configmap app-config \
  --from-literal=DB_HOST=newhost \
  --from-literal=DB_PORT=5432 \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl logs config-volume-pod --tail=5
```

### Lab 4: Secret basics

```bash
# Create secret from literal
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=supersecret

# Create from file
echo -n 'admin' > username.txt
echo -n 'supersecret' > password.txt
kubectl create secret generic db-secret-file \
  --from-file=username=username.txt \
  --from-file=password=password.txt

# View secret
kubectl get secret db-secret -o yaml
# Values are base64 encoded

# Decode
kubectl get secret db-secret -o jsonpath='{.data.password}' | base64 -d
```

### Lab 5: Using secrets

```bash
# As environment variables
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: secret-env-pod
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'echo "User=\$DB_USER, Pass=\$DB_PASS"; sleep 3600']
    env:
    - name: DB_USER
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: username
    - name: DB_PASS
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
EOF

# As volume
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: secret-volume-pod
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'cat /secrets/username; cat /secrets/password; sleep 3600']
    volumeMounts:
    - name: secrets
      mountPath: /secrets
      readOnly: true
  volumes:
  - name: secrets
    secret:
      secretName: db-secret
EOF
```

### Lab 6: subPath behavior

```bash
# Without subPath (all keys mounted, directory)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: no-subpath
spec:
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
    - name: config
      mountPath: /etc/nginx/conf.d
  volumes:
  - name: config
    configMap:
      name: nginx-config
EOF

# With subPath (specific key, file)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: with-subpath
spec:
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
    - name: config
      mountPath: /etc/nginx/nginx.conf
      subPath: nginx.conf  # Mounts specific key as file
  volumes:
  - name: config
    configMap:
      name: nginx-config
EOF

# subPath caveat: Updates don't propagate!
```

### Lab 7: Immutable ConfigMaps

```bash
# Immutable ConfigMap (can't be updated)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: immutable-config
data:
  key: value
immutable: true
EOF

# Try to update (fails)
kubectl patch configmap immutable-config -p '{"data":{"key":"newvalue"}}'
# Error: field is immutable

# Benefits: Better performance, prevents accidental changes
```

---

## Break-and-Fix Exercise

**Scenario**: You updated a ConfigMap with new database configuration, but the application still uses old values.

**Setup**:
```bash
kubectl create configmap db-config --from-literal=DB_HOST=oldhost

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'echo "Connecting to \$DB_HOST"; sleep 3600']
    env:
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: db-config
          key: DB_HOST
EOF

kubectl create configmap db-config --from-literal=DB_HOST=newhost --dry-run=client -o yaml | kubectl apply -f -
```

**Your task**: Get the app to use the new configuration.

<details>
<summary>Solution</summary>

**Root cause**: Environment variables are set at pod startup and never update.

**Fix**:
```bash
# Option 1: Restart the pod
kubectl delete pod app
kubectl apply -f pod.yaml

# Option 2: Use deployment and trigger rollout
kubectl rollout restart deployment app-deployment

# Option 3: Use volumes instead of env vars (updates automatically)
```

**Best practice**: Use volumes for config that changes frequently.

</details>

---

## Interview Questions

### Question 1
What's the difference between ConfigMap and Secret? Is Secret actually secure?

<details>
<summary>Answer</summary>

**ConfigMap**: Non-sensitive configuration
**Secret**: Sensitive data (passwords, tokens, keys)

**Similarities**:
- Both store key-value pairs
- Both can be used as env vars or volumes
- Both have 1MB size limit

**Differences**:

| Aspect | ConfigMap | Secret |
|--------|-----------|--------|
| **Encoding** | Plain text | Base64 (not encryption!) |
| **Use case** | Config files, settings | Passwords, keys, tokens |
| **RBAC** | Separate permissions | Separate permissions |
| **Encryption** | No | Optional (at rest) |

**Is Secret secure?**

**By default: NO!**
- Base64 is encoding, not encryption
- Anyone with API access can decode
- Stored in etcd in plaintext by default

```bash
# Easy to decode
kubectl get secret my-secret -o jsonpath='{.data.password}' | base64 -d
```

**To make Secrets secure**:
1. **Enable encryption at rest** (encrypts etcd)
2. **Use RBAC** (limit who can read secrets)
3. **Use external secret managers** (AWS Secrets Manager, Vault)
4. **Network policies** (limit pod access)
5. **Audit logging** (track secret access)

**Best practices**:
- Never commit secrets to git
- Use external secret managers in production
- Rotate secrets regularly
- Use short-lived tokens when possible

</details>

### Question 2
Env vars vs volume mounts for ConfigMaps - when updates take effect?

<details>
<summary>Answer</summary>

**Key difference**: Update behavior

**Environment variables**:
```yaml
env:
- name: CONFIG_VALUE
  valueFrom:
    configMapKeyRef:
      name: my-config
      key: value
```
- Set at pod startup
- **NEVER update** even if ConfigMap changes
- Pod must be restarted to see new values

**Volume mounts**:
```yaml
volumeMounts:
- name: config
  mountPath: /config
volumes:
- name: config
  configMap:
    name: my-config
```
- Files mounted in pod
- **Automatically update** when ConfigMap changes
- Update delay: ~60 seconds (kubelet sync period)

**Comparison**:

| Feature | Env Vars | Volume Mounts |
|---------|----------|---------------|
| **Updates** | Never | Yes (~60s) |
| **Restart needed** | Yes | No |
| **Partial values** | Easy (one key) | All or specific keys |
| **App needs** | Restart/redeploy | Reload config file |

**Exception - subPath mounts**:
```yaml
volumeMounts:
- name: config
  mountPath: /app/config.yaml
  subPath: config.yaml  # This NEVER updates!
```
- subPath creates a bind mount
- Does NOT update automatically
- Same as env vars (need restart)

**When to use each**:

**Environment variables**:
- Simple key-value config
- Values don't change often
- Application reads on startup

**Volume mounts**:
- Config files (nginx.conf, application.yaml)
- Values change frequently
- Application can reload config (SIGHUP)

**Real-world example**:
```yaml
# Static config (rarely changes)
env:
- name: DATABASE_TYPE
  value: "postgres"

# Dynamic config (might change)
volumeMounts:
- name: config
  mountPath: /etc/app/
volumes:
- name: config
  configMap:
    name: app-config
```

</details>

### Question 3
What is subPath? Why would updates not work with subPath?

<details>
<summary>Answer</summary>

**subPath**: Mounts a specific file/directory from a volume instead of the entire volume.

**Without subPath** (mounts entire ConfigMap as directory):
```yaml
volumeMounts:
- name: config
  mountPath: /config  # Creates /config/key1, /config/key2
volumes:
- name: config
  configMap:
    name: my-config
```

Result:
```
/config/
  ├── key1
  ├── key2
  └── key3
```

**With subPath** (mounts specific key as file):
```yaml
volumeMounts:
- name: config
  mountPath: /app/config.yaml
  subPath: config.yaml  # Mounts only this key
volumes:
- name: config
  configMap:
    name: my-config
```

Result:
```
/app/config.yaml  (single file)
```

**Why use subPath?**
1. Mount file to specific location (e.g., /etc/nginx/nginx.conf)
2. Mix ConfigMap with existing directory
3. Avoid overwriting entire directory

**Why updates don't work with subPath?**

**Technical reason**:
- Regular mount: Symlink to kubelet-managed directory that updates
- subPath mount: Direct bind mount that doesn't follow updates

**Regular mount** (updates work):
```bash
# Inside pod
/config/key1 -> /var/lib/kubelet/.../..data/key1
# ..data is symlink that kubelet updates
```

**subPath mount** (updates DON'T work):
```bash
# Direct mount, no symlink
/app/config.yaml (static bind mount)
```

**Workaround for subPath updates**:
1. Don't use subPath (if possible)
2. Restart pod when ConfigMap changes
3. Use init container to copy file
4. Use reloader controller (stakater/reloader)

**Example with reloader**:
```yaml
metadata:
  annotations:
    configmap.reloader.stakater.com/reload: "my-config"
# Pod auto-restarts when ConfigMap changes
```

</details>

### Question 4
How would you inject multiple environment variables from a ConfigMap?

<details>
<summary>Answer</summary>

**Three methods**:

**1. Individual keys** (verbose but explicit):
```yaml
env:
- name: DB_HOST
  valueFrom:
    configMapKeyRef:
      name: db-config
      key: host
- name: DB_PORT
  valueFrom:
    configMapKeyRef:
      name: db-config
      key: port
```

**2. envFrom** (all keys at once):
```yaml
envFrom:
- configMapRef:
    name: db-config
# Creates env vars for ALL keys in ConfigMap
# Key names become env var names
```

**3. envFrom with prefix**:
```yaml
envFrom:
- configMapRef:
    name: db-config
  prefix: DB_
# Keys: host, port
# Env vars: DB_host, DB_port
```

**Example**:

ConfigMap:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DATABASE_HOST: "localhost"
  DATABASE_PORT: "5432"
  API_KEY: "abc123"
  DEBUG: "true"
```

Pod with envFrom:
```yaml
spec:
  containers:
  - name: app
    image: myapp
    envFrom:
    - configMapRef:
        name: app-config
```

Result inside pod:
```bash
echo $DATABASE_HOST  # localhost
echo $DATABASE_PORT  # 5432
echo $API_KEY        # abc123
echo $DEBUG          # true
```

**Multiple ConfigMaps**:
```yaml
envFrom:
- configMapRef:
    name: app-config
- configMapRef:
    name: feature-flags
- secretRef:
    name: api-secrets
```

**Precedence** (if duplicate keys):
1. env (highest - explicit values)
2. Last envFrom entry
3. First envFrom entry

**Best practice**: Use envFrom for simplicity, individual env for control

</details>

### Question 5
What are immutable ConfigMaps? Why would you use them?

<details>
<summary>Answer</summary>

**Immutable ConfigMaps** (Kubernetes 1.19+):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: immutable-config
data:
  key: value
immutable: true
```

**Restrictions**:
- Can't update data
- Can't change immutable field back to false
- Must delete and recreate to change

**Why use immutable ConfigMaps?**

**1. Performance**:
- Kubelet doesn't watch for changes
- Reduces API server load
- Scales better with many pods

**2. Safety**:
- Prevents accidental changes
- Ensures consistency across pods
- "Infrastructure as code" enforcement

**3. Reliability**:
- No unexpected updates
- Easier debugging (config never changes)
- Reproducible deployments

**Use cases**:

**Good for immutable**:
```yaml
# Application code checksums
# CA certificates
# Fixed configuration
immutable: true
```

**Bad for immutable**:
```yaml
# Feature flags (change frequently)
# Dynamic configuration
# Development environments
immutable: false
```

**Workflow with immutable ConfigMaps**:
```bash
# 1. Create versioned ConfigMap
kubectl create configmap app-config-v2 --from-file=config.yaml --dry-run=client -o yaml | 
  kubectl apply -f - --field-manager=kubectl-client-side-apply

# 2. Mark as immutable
kubectl patch configmap app-config-v2 -p '{"immutable":true}'

# 3. Update deployment to use new version
kubectl set env deployment/app --from=configmap/app-config-v2

# 4. Old ConfigMap can be deleted after rollout
kubectl delete configmap app-config-v1
```

**Best practice**: 
- Production: Use immutable + versioned names
- Development: Use mutable for fast iteration

</details>
