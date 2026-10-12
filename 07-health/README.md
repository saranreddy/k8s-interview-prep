# Module 07: Health & Lifecycle

**Weight**: 7% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Liveness, readiness, and startup probes
- Probe types: HTTP, TCP, exec
- Probe timing: initialDelaySeconds, periodSeconds, timeoutSeconds, failureThreshold
- PreStop hooks and graceful termination
- Pod Disruption Budgets (PDBs)
- Termination grace period

## Edge Cases

1. **Liveness probe restart loop**: Probe fails repeatedly, pod never becomes healthy
2. **Readiness probe blocking deployment**: All new pods fail readiness, rollout stuck
3. **PDB blocking drain**: Can't drain node because PDB blocks pod eviction
4. **PreStop timeout**: Hook takes longer than terminationGracePeriodSeconds
5. **Startup probe interaction**: Liveness/readiness disabled until startup succeeds

---

## Labs

### Lab 1: Liveness probe

```bash
# HTTP liveness probe
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: liveness-http
spec:
  containers:
  - name: app
    image: nginx
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 1
      failureThreshold: 3
EOF

# Exec liveness probe
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: liveness-exec
spec:
  containers:
  - name: app
    image: busybox
    args:
    - /bin/sh
    - -c
    - touch /tmp/healthy; sleep 30; rm /tmp/healthy; sleep 600
    livenessProbe:
      exec:
        command:
        - cat
        - /tmp/healthy
      initialDelaySeconds: 5
      periodSeconds: 5
EOF

# Watch it restart after 30s
kubectl get pod liveness-exec --watch
```

### Lab 2: Readiness probe

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: readiness-demo
  labels:
    app: demo
spec:
  containers:
  - name: app
    image: nginx
    readinessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 3
---
apiVersion: v1
kind: Service
metadata:
  name: demo-service
spec:
  selector:
    app: demo
  ports:
  - port: 80
EOF

# Check service endpoints
kubectl get endpoints demo-service

# Pod removed from endpoints if readiness fails
kubectl exec readiness-demo -- mv /usr/share/nginx/html/index.html /tmp/
kubectl get endpoints demo-service --watch
```

### Lab 3: Startup probe

```bash
# For slow-starting containers
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: startup-demo
spec:
  containers:
  - name: app
    image: nginx
    startupProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 0
      periodSeconds: 5
      failureThreshold: 30  # 30 * 5 = 150s max startup time
    livenessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 5
    readinessProbe:
      httpGet:
        path: /
        port: 80
      periodSeconds: 3
EOF

# Liveness/readiness disabled until startup succeeds
```

### Lab 4: PreStop hook

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: prestop-demo
spec:
  containers:
  - name: nginx
    image: nginx
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "echo Graceful shutdown; sleep 15; nginx -s quit"]
  terminationGracePeriodSeconds: 30
EOF

# Observe graceful shutdown
kubectl delete pod prestop-demo --wait=false
kubectl get events --watch
```

### Lab 5: Pod Disruption Budget

```bash
# Create deployment
kubectl create deployment nginx --image=nginx --replicas=3

# Create PDB (at least 2 pods must be available)
cat <<EOF | kubectl apply -f -
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: nginx-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: nginx
EOF

# Try to drain (respects PDB)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# PDB status
kubectl get pdb nginx-pdb
```

### Lab 6: Graceful termination flow

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: graceful-demo
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'trap "echo Received SIGTERM; sleep 10; echo Exiting" TERM; while true; do sleep 1; done']
  terminationGracePeriodSeconds: 20
EOF

# Watch termination
kubectl logs graceful-demo --follow &
kubectl delete pod graceful-demo
# Observe: SIGTERM sent → waits 20s → SIGKILL
```

---

## Break-and-Fix Exercise

**Scenario**: Your deployment rollout is stuck because new pods never become ready.

**Setup**:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: broken-readiness
spec:
  replicas: 3
  selector:
    matchLabels:
      app: broken
  template:
    metadata:
      labels:
        app: broken
    spec:
      containers:
      - name: app
        image: nginx
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
EOF
```

**Your task**: Fix the readiness probe so deployment completes.

<details>
<summary>Solution</summary>

**Root cause**: Readiness probe checks wrong path (/health doesn't exist) and wrong port (nginx runs on 80, not 8080).

**Fix**:
```bash
kubectl edit deployment broken-readiness
# Change:
#   path: / (or add /health endpoint)
#   port: 80
```

**Verification**:
```bash
kubectl rollout status deployment broken-readiness
kubectl get pods
```

</details>

---

## Interview Questions

### Question 1
What's the difference between liveness, readiness, and startup probes?

<details>
<summary>Answer</summary>

| Probe Type | Purpose | On Failure | Use Case |
|------------|---------|------------|----------|
| **Liveness** | Is app alive? | Restart container | Detect deadlocks |
| **Readiness** | Ready for traffic? | Remove from Service | Slow startup, dependencies |
| **Startup** | Has app started? | Restart container | Slow-starting apps |

**Liveness**: "Is the application still working?"
- If fails: kubelet restarts container
- Example: Detect app deadlock/freeze
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  periodSeconds: 10
```

**Readiness**: "Can the application handle traffic?"
- If fails: Pod removed from Service endpoints
- Container NOT restarted
- Example: Database connection lost, cache warming
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  periodSeconds: 5
```

**Startup**: "Has the application finished starting?"
- If fails: kubelet restarts container
- Disables liveness/readiness checks until succeeds
- Example: App takes 2 minutes to initialize
```yaml
startupProbe:
  httpGet:
    path: /
    port: 8080
  failureThreshold: 30
  periodSeconds: 10  # Max 300s startup time
```

**Probe interactions**:
1. Startup probe runs first
2. Liveness/readiness disabled until startup succeeds
3. Then liveness + readiness run in parallel

**Common patterns**:
```yaml
# Fast-starting app
livenessProbe: yes
readinessProbe: yes
startupProbe: no

# Slow-starting app
livenessProbe: yes
readinessProbe: yes
startupProbe: yes  # Protects against early liveness failures
```

</details>

### Question 2
Explain the termination lifecycle. What happens when you delete a pod?

<details>
<summary>Answer</summary>

**Pod termination sequence**:

1. **Pod marked for deletion**
   - Pod status: Terminating
   - Grace period starts (default 30s)

2. **Two parallel actions**:
   
   **A. PreStop hook** (if defined):
   - Container preStop hook executes
   - Example: Close connections, save state
   
   **B. Endpoint removal**:
   - Pod removed from Service endpoints
   - New traffic stops routing to pod
   - Existing connections may continue

3. **SIGTERM sent**
   - Container receives SIGTERM signal
   - Application should begin graceful shutdown

4. **Grace period waits**
   - Kubelet waits for terminationGracePeriodSeconds
   - Default: 30 seconds

5. **SIGKILL sent**
   - If still running after grace period
   - Forceful termination

**Timeline example** (30s grace period):
```
t=0s:  kubectl delete pod
       - Pod status: Terminating
       - PreStop hook runs
       - Removed from endpoints
       - SIGTERM sent to container

t=0-30s: Application shutting down gracefully

t=30s: SIGKILL sent (if still running)
       Pod deleted from API
```

**Configuration**:
```yaml
spec:
  terminationGracePeriodSeconds: 60  # Wait 60s before SIGKILL
  containers:
  - name: app
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "nginx -s quit; sleep 10"]
```

**Best practices**:
1. Handle SIGTERM in application
2. Set terminationGracePeriodSeconds > app shutdown time
3. Use preStop hook for cleanup (optional)
4. Close connections before exiting

**Common issue**: Immediate connection drops
- Endpoint removal not instant (can take 1-2s)
- Solution: Add delay in preStop hook
```yaml
preStop:
  exec:
    command: ["/bin/sh", "-c", "sleep 5"]  # Let endpoints update
```

</details>

### Question 3
What is a Pod Disruption Budget? When would it block node draining?

<details>
<summary>Answer</summary>

**PodDisruptionBudget (PDB)**: Limits how many pods can be unavailable during voluntary disruptions.

**Voluntary disruptions**:
- Node drain (kubectl drain)
- Cluster autoscaling down
- Manual pod deletion
- Deployment rollout (not blocked by PDB)

**Involuntary disruptions** (PDB doesn't prevent):
- Node failure
- Out of memory kill
- Kernel panic

**Creating PDB**:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2  # At least 2 pods must stay available
  selector:
    matchLabels:
      app: my-app
```

**Or with maxUnavailable**:
```yaml
spec:
  maxUnavailable: 1  # At most 1 pod can be unavailable
  selector:
    matchLabels:
      app: my-app
```

**Percentage-based**:
```yaml
spec:
  minAvailable: 75%  # Keep at least 75% of pods
```

**When PDB blocks drain**:

Example: 3 replicas, minAvailable: 2

```bash
kubectl drain node1

# Node has 2 of the 3 pods
# Evicting both would leave only 1 available (< 2)
# Result: Drain waits/blocks
```

**Check PDB status**:
```bash
kubectl get pdb
NAME      MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
app-pdb   2               N/A               1                     5m

# ALLOWED DISRUPTIONS = how many pods can be evicted now
# 0 = drain will block
```

**Force drain** (dangerous!):
```bash
kubectl drain node1 --disable-eviction --force
# Bypasses PDB, deletes pods immediately
```

**Best practices**:
- Always use PDB for critical apps
- minAvailable ≥ 1 (avoid zero replicas)
- Test drain in dev before production
- Monitor ALLOWED DISRUPTIONS

**Common issue**: PDB too strict
```yaml
replicas: 3
minAvailable: 3  # Can NEVER drain!
# Fix: Use minAvailable: 2 or maxUnavailable: 1
```

</details>

### Question 4
How do you troubleshoot a pod stuck in CrashLoopBackOff with failing liveness probes?

<details>
<summary>Answer</summary>

**CrashLoopBackOff**: Container starts → crashes/exits → kubelet restarts with exponential backoff.

**Possible causes**:
1. Application error
2. Failing liveness probe
3. Resource limits (OOMKilled)
4. Missing dependencies

**Troubleshooting steps**:

**1. Check pod events**:
```bash
kubectl describe pod <pod-name>
# Look for:
# - Liveness probe failed
# - Back-off restarting failed container
# - Exit code (0=success, 1=error, 137=SIGKILL/OOM)
```

**2. Check logs**:
```bash
# Current container logs
kubectl logs <pod-name>

# Previous container logs (before restart)
kubectl logs <pod-name> --previous

# All restarts
kubectl logs <pod-name> --all-containers --previous
```

**3. Check liveness probe configuration**:
```bash
kubectl get pod <pod-name> -o yaml | grep -A 10 livenessProbe
```

**Common liveness probe issues**:

**Issue 1**: Probe too aggressive
```yaml
# BAD
livenessProbe:
  httpGet:
    path: /health
  initialDelaySeconds: 1  # Too short!
  periodSeconds: 1        # Too frequent!
  failureThreshold: 1     # No tolerance!
  timeoutSeconds: 1

# Container starts → probe runs immediately → fails → restart loop
```

**Fix**: Increase delays
```yaml
# GOOD
livenessProbe:
  httpGet:
    path: /health
  initialDelaySeconds: 30  # Wait for app to start
  periodSeconds: 10
  failureThreshold: 3      # Tolerate 3 failures
  timeoutSeconds: 5
```

**Issue 2**: Wrong endpoint
```yaml
# Probe checks /health but endpoint doesn't exist
livenessProbe:
  httpGet:
    path: /health  # Returns 404
```

**Issue 3**: Startup time too long
- Liveness fails before app finishes starting
- Solution: Use startupProbe
```yaml
startupProbe:
  httpGet:
    path: /health
  failureThreshold: 30
  periodSeconds: 10  # 300s max startup
livenessProbe:
  httpGet:
    path: /health
  periodSeconds: 10
```

**4. Temporary disable liveness probe**:
```bash
kubectl edit pod <pod-name>
# Comment out livenessProbe section
# Or edit deployment and rollout
```

**5. Check resource limits**:
```bash
kubectl describe pod <pod-name> | grep -A 5 "Last State"
# Look for: OOMKilled, Exit Code 137
```

**Quick fix workflow**:
```bash
# 1. Get logs
kubectl logs <pod> --previous

# 2. Check events
kubectl describe pod <pod>

# 3. Temporarily remove liveness probe
kubectl edit deployment <name>
# Remove livenessProbe section

# 4. Let pod stabilize and debug
kubectl exec -it <pod> -- /bin/sh

# 5. Fix root cause, re-enable liveness probe
```

</details>

### Question 5
What's the difference between minAvailable and maxUnavailable in PDB?

<details>
<summary>Answer</summary>

**Both control disruption tolerance, but from opposite perspectives**:

**minAvailable**: Minimum pods that must remain available
**maxUnavailable**: Maximum pods that can be unavailable

**Example**: Deployment with 5 replicas

**minAvailable: 3**
```yaml
spec:
  minAvailable: 3
  # At least 3 must stay available
  # Can evict at most 2 at a time
```

**maxUnavailable: 2**
```yaml
spec:
  maxUnavailable: 2
  # At most 2 can be unavailable
  # At least 3 must stay available
```

**Same result!** Both allow evicting 2 pods.

**When they differ**:

Deployment scales: 5 → 7 replicas

**minAvailable: 3**
- Still need 3 available
- Can now evict 4 pods (7-3=4)

**maxUnavailable: 2**
- Still max 2 unavailable
- Can evict 2 pods (same as before)

**Percentage-based**:

```yaml
# minAvailable: 50%
# 10 replicas → at least 5 available
# Scale to 20 → at least 10 available (scales with replicas)

# maxUnavailable: 50%
# 10 replicas → max 5 unavailable
# Scale to 20 → max 10 unavailable (scales with replicas)
```

**When to use each**:

**Use minAvailable**:
- You care about absolute availability
- Example: "Must have 3 API servers always"
```yaml
minAvailable: 3  # Always 3, regardless of scale
```

**Use maxUnavailable**:
- You care about disruption rate
- Example: "Update slowly, only 1 pod at a time"
```yaml
maxUnavailable: 1  # Slow rolling updates
```

**Common patterns**:

**High availability**:
```yaml
minAvailable: 2
# For 3 replicas: Can evict 1
# For 5 replicas: Can evict 3
# Always 2+ available
```

**Gradual rollouts**:
```yaml
maxUnavailable: 25%
# Limits disruption rate
# 100 replicas: Max 25 down at once
```

**Can't use both** in same PDB:
```yaml
# INVALID
spec:
  minAvailable: 2
  maxUnavailable: 1  # Error: can't specify both
```

</details>
