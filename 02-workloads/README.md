# Module 02: Workloads

**Weight**: 12% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Pod fundamentals and multi-container patterns
- Deployments and rolling updates
- ReplicaSets and replication
- StatefulSets for stateful applications
- DaemonSets for per-node workloads
- Jobs and CronJobs for batch processing
- Init containers and sidecar containers

## Edge Cases

1. **CrashLoopBackOff**: Container exits immediately, kubelet backs off restarts exponentially
2. **ImagePullBackOff**: Image doesn't exist, registry auth fails, or rate limited
3. **Stuck rollout**: New pods fail to become ready, deployment never completes
4. **CronJob concurrencyPolicy**: What happens when a job runs longer than the schedule interval
5. **StatefulSet pod identity**: Pod names are stable, but IPs can change

---

## Labs

### Lab 1: Pod basics and multi-container patterns

```bash
# Single container pod
kubectl run nginx --image=nginx

# Multi-container pod (sidecar pattern)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: sidecar-example
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'while true; do echo "$(date) - App log" >> /var/log/app.log; sleep 2; done']
    volumeMounts:
    - name: logs
      mountPath: /var/log
  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'tail -f /var/log/app.log']
    volumeMounts:
    - name: logs
      mountPath: /var/log
  volumes:
  - name: logs
    emptyDir: {}
EOF

# Check both containers
kubectl logs sidecar-example -c app
kubectl logs sidecar-example -c sidecar

# Exec into specific container
kubectl exec -it sidecar-example -c app -- sh
```

### Lab 2: Deployments and rolling updates

```bash
# Create deployment
kubectl create deployment nginx --image=nginx:1.19 --replicas=3

# Check deployment, replicaset, and pods
kubectl get deployment,rs,pod

# Update image (triggers rolling update)
kubectl set image deployment/nginx nginx=nginx:1.20

# Watch rollout
kubectl rollout status deployment/nginx

# Check rollout history
kubectl rollout history deployment/nginx

# Rollback to previous version
kubectl rollout undo deployment/nginx

# Rollback to specific revision
kubectl rollout undo deployment/nginx --to-revision=1

# Pause and resume rollout
kubectl rollout pause deployment/nginx
kubectl set image deployment/nginx nginx=nginx:1.21
kubectl rollout resume deployment/nginx
```

### Lab 3: Deployment strategies

```bash
# RollingUpdate (default)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rolling-update
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.19
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 3
EOF

# Recreate strategy (all pods killed before new ones start)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recreate-example
spec:
  replicas: 3
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: nginx-recreate
  template:
    metadata:
      labels:
        app: nginx-recreate
    spec:
      containers:
      - name: nginx
        image: nginx:1.19
EOF
```

### Lab 4: StatefulSets

```bash
# StatefulSet with headless service
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: nginx-headless
spec:
  clusterIP: None
  selector:
    app: nginx-stateful
  ports:
  - port: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: nginx-headless
  replicas: 3
  selector:
    matchLabels:
      app: nginx-stateful
  template:
    metadata:
      labels:
        app: nginx-stateful
    spec:
      containers:
      - name: nginx
        image: nginx:1.19
        ports:
        - containerPort: 80
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:
  - metadata:
      name: www
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 1Gi
EOF

# Observe pod creation order
kubectl get pods -w

# Check stable network identities
kubectl get pods -l app=nginx-stateful -o wide
# Names: web-0, web-1, web-2 (stable)

# Check DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup nginx-headless
# Each pod has DNS: web-0.nginx-headless.default.svc.cluster.local

# Scale StatefulSet
kubectl scale statefulset web --replicas=5
# Scales up: web-3, web-4 (in order)
kubectl scale statefulset web --replicas=2
# Scales down: web-4, web-3 (reverse order)

# Delete and observe recreation
kubectl delete pod web-0
# Recreated with same name: web-0
```

### Lab 5: DaemonSets

```bash
# Create DaemonSet (runs on every node)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      hostPID: true
      containers:
      - name: node-exporter
        image: prom/node-exporter:latest
        ports:
        - containerPort: 9100
        securityContext:
          privileged: true
EOF

# Check one pod per node
kubectl get pods -o wide
kubectl get daemonset node-exporter

# DaemonSet with node selector (only on specific nodes)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ssd-monitor
spec:
  selector:
    matchLabels:
      app: ssd-monitor
  template:
    metadata:
      labels:
        app: ssd-monitor
    spec:
      nodeSelector:
        disktype: ssd
      containers:
      - name: monitor
        image: busybox
        command: ['sh', '-c', 'while true; do echo "monitoring"; sleep 60; done']
EOF

# Won't schedule until nodes have disktype=ssd label
kubectl label node <node-name> disktype=ssd
```

### Lab 6: Jobs and CronJobs

```bash
# Simple Job
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: pi-calculation
spec:
  template:
    spec:
      containers:
      - name: pi
        image: perl
        command: ["perl", "-Mbignum=bpi", "-wle", "print bpi(2000)"]
      restartPolicy: Never
  backoffLimit: 4
EOF

# Watch job completion
kubectl get jobs -w
kubectl logs <pod-name>

# Job with parallelism
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: parallel-job
spec:
  completions: 5
  parallelism: 2
  template:
    spec:
      containers:
      - name: worker
        image: busybox
        command: ['sh', '-c', 'echo "Processing item"; sleep 10']
      restartPolicy: Never
EOF

# CronJob (scheduled jobs)
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hello-cron
spec:
  schedule: "*/1 * * * *"  # Every minute
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: hello
            image: busybox
            command: ['sh', '-c', 'date; echo "Hello from CronJob"']
          restartPolicy: OnFailure
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
EOF

# Watch CronJob create jobs
kubectl get cronjobs
kubectl get jobs --watch

# CronJob concurrency policies
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: long-running-cron
spec:
  schedule: "*/1 * * * *"
  concurrencyPolicy: Forbid  # Allow / Forbid / Replace
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: sleep
            image: busybox
            command: ['sh', '-c', 'echo "Starting"; sleep 120; echo "Done"']
          restartPolicy: OnFailure
EOF
```

### Lab 7: Init containers

```bash
# Pod with init container
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  initContainers:
  - name: init-myservice
    image: busybox
    command: ['sh', '-c', 'until nslookup myservice; do echo waiting for myservice; sleep 2; done']
  - name: init-mydb
    image: busybox
    command: ['sh', '-c', 'until nslookup mydb; do echo waiting for mydb; sleep 2; done']
  containers:
  - name: app
    image: nginx
EOF

# Pod stuck in Init:0/2 until dependencies exist
kubectl get pod init-demo

# Create the services
kubectl create service clusterip myservice --tcp=80:80
kubectl create service clusterip mydb --tcp=3306:3306

# Now init containers complete and app starts
kubectl get pod init-demo --watch
```

---

## Break-and-Fix Exercise

**Scenario**: You've deployed an application, but it's stuck in CrashLoopBackOff. The pod keeps restarting and never becomes ready.

**Setup**:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: broken-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: broken-app
  template:
    metadata:
      labels:
        app: broken-app
    spec:
      containers:
      - name: app
        image: nginx:1.19
        command: ['sh', '-c', 'echo "Starting app"; exit 1']
EOF
```

**Symptoms**:
```bash
$ kubectl get pods
NAME                          READY   STATUS             RESTARTS   AGE
broken-app-xxx-yyy            0/1     CrashLoopBackOff   5          3m

$ kubectl describe pod broken-app-xxx-yyy
# Shows: Back-off restarting failed container
```

**Your task**:
1. Diagnose why the pod is crashing
2. Fix the deployment
3. Verify pods are running

<details>
<summary>Hints</summary>

- Check pod logs
- Check the container command
- Look at restart count and exit code
- Check events in `kubectl describe`

</details>

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
# Check current logs
kubectl logs <pod-name>

# Check previous container logs
kubectl logs <pod-name> --previous

# Describe pod for events
kubectl describe pod <pod-name>
# Shows: "Back-off 40s restarting failed container"

# Check restart count
kubectl get pod <pod-name>
# RESTARTS column shows increasing count
```

**Root cause**: Container command exits immediately with code 1, causing kubelet to restart it repeatedly.

**Fix**:
```bash
# Option 1: Fix the command
kubectl set image deployment/broken-app app=nginx:1.19
kubectl set env deployment/broken-app --env="FIX=true" --env-
kubectl edit deployment broken-app
# Remove the failing command, let nginx run normally

# Or apply corrected manifest
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: broken-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: broken-app
  template:
    metadata:
      labels:
        app: broken-app
    spec:
      containers:
      - name: app
        image: nginx:1.19
        # Remove the bad command, let nginx run normally
EOF
```

**Verification**:
```bash
kubectl get pods
# All should show Running
kubectl describe deployment broken-app
# Should show successful rollout
```

**Key learning**: CrashLoopBackOff means the container starts then exits/crashes. Check logs and exit codes!

</details>

---

## Interview Questions

### Question 1
What's the difference between a Deployment and a StatefulSet? When would you use each?

<details>
<summary>Answer</summary>

| Feature | Deployment | StatefulSet |
|---------|-----------|-------------|
| **Pod naming** | Random suffix (nginx-abc123) | Ordered index (nginx-0, nginx-1) |
| **Pod identity** | Interchangeable | Stable, persistent identity |
| **Scaling** | Parallel, any order | Sequential (0→1→2 or 2→1→0) |
| **Storage** | Shared or separate PVCs | Dedicated PVC per pod |
| **Network** | Any Service type | Requires headless Service |
| **DNS** | Service DNS only | Per-pod DNS records |
| **Use case** | Stateless apps | Stateful apps (databases) |

**Use Deployment for**:
- Web servers, APIs, microservices
- Stateless applications
- When any pod can handle any request
- When you want fast scaling

**Use StatefulSet for**:
- Databases (MySQL, PostgreSQL, Cassandra)
- Distributed systems needing stable identity (Kafka, ZooKeeper)
- Applications requiring ordered startup/shutdown
- When pods need persistent, unique storage

**Example**: 
- **Deployment**: nginx web server (any pod serves any request)
- **StatefulSet**: PostgreSQL primary-replica setup (each pod has specific role and storage)

</details>

### Question 2
Explain pod restart policies. What happens with Never, OnFailure, and Always?

<details>
<summary>Answer</summary>

**Three restart policies**:

| Policy | Behavior | Use Case |
|--------|----------|----------|
| **Always** | Restart on exit (any code) | Long-running services, Deployments |
| **OnFailure** | Restart only on non-zero exit | Jobs, retryable batch work |
| **Never** | Don't restart | One-shot tasks, debugging |

**Detailed behavior**:

```yaml
# Always (default for Deployments/ReplicaSets)
restartPolicy: Always
# Exit code 0 → restart after short delay
# Exit code 1 → restart with exponential backoff (10s, 20s, 40s... up to 5 min)
```

```yaml
# OnFailure (common for Jobs)
restartPolicy: OnFailure
# Exit code 0 → pod stays Completed, no restart
# Exit code 1 → restart with backoff
```

```yaml
# Never (common for one-shot Jobs)
restartPolicy: Never
# Exit code 0 → pod stays Completed
# Exit code 1 → pod stays Failed, creates new pod if backoffLimit allows
```

**Restart behavior with multiple containers**:
- If ANY container needs restart, the ENTIRE pod restarts
- All containers stop, then all containers start

**Common issue**:
```bash
# Job with restartPolicy: Always is invalid!
apiVersion: batch/v1
kind: Job
spec:
  template:
    spec:
      restartPolicy: Always  # ERROR! Jobs only allow Never or OnFailure
```

**Exponential backoff**:
```
Attempt 1: immediate
Attempt 2: 10s
Attempt 3: 20s
Attempt 4: 40s
Attempt 5: 80s
Attempt 6+: 5 minutes (capped)
```

This explains CrashLoopBackOff!

</details>

### Question 3
How does a rolling update work in a Deployment? What are maxUnavailable and maxSurge?

<details>
<summary>Answer</summary>

**Rolling update process**:
1. Create new ReplicaSet with updated spec
2. Scale up new ReplicaSet by `maxSurge`
3. Wait for new pods to be Ready
4. Scale down old ReplicaSet by `maxUnavailable`
5. Repeat until all pods updated

**maxUnavailable**:
- Maximum pods that can be unavailable during update
- Can be number (2) or percentage (25%)
- Lower = safer but slower

**maxSurge**:
- Maximum extra pods beyond desired count
- Can be number (2) or percentage (25%)
- Higher = faster but uses more resources

**Examples**:

```yaml
# Conservative (zero downtime)
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0    # Never have fewer than desired
    maxSurge: 1          # Only 1 extra pod at a time
# With 4 replicas: 4 old → 5 (4 old + 1 new) → 4 (3 old + 1 new) → ... → 4 new
```

```yaml
# Aggressive (faster updates)
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 2
    maxSurge: 2
# With 4 replicas: 4 old → 6 (2 old + 4 new) → 4 new
# Up to 6 pods at once, 2 can be unavailable
```

```yaml
# Percentage-based
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 25%
    maxSurge: 25%
# With 8 replicas: 2 can be unavailable, can surge to 10 total
```

**Stuck rollout**:
```bash
# If new pods never become Ready, rollout stalls
kubectl rollout status deployment/myapp
# Waiting for deployment "myapp" rollout to finish: 2 out of 4 new replicas updated...

# Check why pods aren't ready
kubectl describe pod <new-pod>
kubectl logs <new-pod>

# Abort and rollback
kubectl rollout undo deployment/myapp
```

**Progressive deadline**:
```yaml
spec:
  progressDeadlineSeconds: 600  # Fail if not progressing after 10 min
```

</details>

### Question 4
What is CrashLoopBackOff vs ImagePullBackOff? How do you troubleshoot each?

<details>
<summary>Answer</summary>

| Issue | Cause | Container State | Troubleshooting |
|-------|-------|-----------------|-----------------|
| **CrashLoopBackOff** | Container starts then exits/crashes | Running → Terminated → Waiting | Check logs, exit code |
| **ImagePullBackOff** | Can't pull container image | Waiting | Check image name, registry auth |

**CrashLoopBackOff**:

Causes:
- Application error/crash
- Missing dependencies
- Configuration error
- Port already in use
- Exit command in Dockerfile

Troubleshoot:
```bash
# Check current logs
kubectl logs <pod> -c <container>

# Check previous container instance
kubectl logs <pod> -c <container> --previous

# Describe for exit code
kubectl describe pod <pod>
# Look for: "Exit Code: 1" or "Exit Code: 137" (OOMKilled)

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp
```

**ImagePullBackOff**:

Causes:
- Image doesn't exist
- Typo in image name/tag
- Private registry without credentials
- Registry rate limiting (Docker Hub)
- Network issues

Troubleshoot:
```bash
# Describe pod for detailed error
kubectl describe pod <pod>
# Look for: "Failed to pull image" or "authentication required"

# Check image name
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].image}'

# Check image pull secrets
kubectl get pod <pod> -o yaml | grep imagePullSecrets -A 5

# Test pulling image manually (on node)
docker pull <image>

# Check pull secret (if using private registry)
kubectl get secret <pull-secret> -o yaml
```

**Common fixes**:

CrashLoopBackOff:
```bash
# Fix application code
# Add proper health checks
# Check environment variables
kubectl set env deployment/app KEY=value
```

ImagePullBackOff:
```bash
# Fix image name
kubectl set image deployment/app container=correct/image:tag

# Add image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<user> \
  --docker-password=<pass>

kubectl patch serviceaccount default -p '{"imagePullSecrets":[{"name":"regcred"}]}'
```

</details>

### Question 5
Explain CronJob concurrencyPolicy. What happens with Allow, Forbid, and Replace?

<details>
<summary>Answer</summary>

**Scenario**: CronJob runs every minute, but job takes 3 minutes to complete.

**Three policies**:

**1. Allow** (default):
- New jobs start even if previous jobs still running
- Can have multiple jobs running concurrently

```yaml
concurrencyPolicy: Allow
schedule: "*/1 * * * *"  # Every minute
# Timeline:
# Min 0: Job-1 starts (runs 3 min)
# Min 1: Job-2 starts (runs 3 min) ← Both running
# Min 2: Job-3 starts (runs 3 min) ← All three running
# Min 3: Job-1 completes, Job-4 starts
```

**2. Forbid**:
- Skip new job if previous job still running
- Prevents overlapping jobs

```yaml
concurrencyPolicy: Forbid
schedule: "*/1 * * * *"
# Timeline:
# Min 0: Job-1 starts (runs 3 min)
# Min 1: Skipped (Job-1 still running)
# Min 2: Skipped (Job-1 still running)
# Min 3: Job-1 completes, Job-2 starts
# Min 4: Skipped (Job-2 still running)
```

**3. Replace**:
- Kill previous job and start new one
- Only one job runs at a time

```yaml
concurrencyPolicy: Replace
schedule: "*/1 * * * *"
# Timeline:
# Min 0: Job-1 starts (runs 3 min)
# Min 1: Job-1 killed, Job-2 starts
# Min 2: Job-2 killed, Job-3 starts
# Min 3: Job-3 killed, Job-4 starts
```

**When to use each**:

| Policy | Use Case | Example |
|--------|----------|---------|
| **Allow** | Independent tasks, can run concurrently | Log rotation, sending emails |
| **Forbid** | Tasks that shouldn't overlap | Database backup (prevent corruption) |
| **Replace** | Only latest run matters | Health check, cache warming |

**Additional controls**:

```yaml
spec:
  # How many successful jobs to keep
  successfulJobsHistoryLimit: 3
  
  # How many failed jobs to keep
  failedJobsHistoryLimit: 1
  
  # Deadline for job to start
  startingDeadlineSeconds: 60
```

**startingDeadlineSeconds**:
- If CronJob controller is down and misses schedules
- When it comes back, it catches up on missed runs
- But only if within startingDeadlineSeconds

Example:
```yaml
schedule: "*/15 * * * *"  # Every 15 minutes
startingDeadlineSeconds: 3600  # 1 hour
# If controller down for 2 hours, it will NOT run 8 missed jobs
# It will only run jobs within the last hour (4 jobs)
```

</details>
