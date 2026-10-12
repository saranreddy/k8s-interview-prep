# Module 10: Observability & Troubleshooting

**Weight**: 10% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Container and pod logs
- Events and event-driven debugging
- kubectl debug and ephemeral containers
- Resource metrics and monitoring
- Prometheus basics
- Distributed tracing concepts
- Troubleshooting methodology

## Edge Cases

1. **Logs from crashed containers**: Use `--previous` flag
2. **Ephemeral containers**: Can't be removed, stay until pod deleted
3. **Events expire**: Kept only ~1 hour by default
4. **Log rotation**: Container logs rotated, old logs lost
5. **Multi-container pods**: Must specify container name

---

## Labs

### Lab 1: Pod and container logs

```bash
# Create pod with logs
kubectl run logger --image=busybox -- sh -c 'while true; do echo "$(date) - Log message"; sleep 2; done'

# View logs
kubectl logs logger

# Follow logs (like tail -f)
kubectl logs logger -f

# Last 10 lines
kubectl logs logger --tail=10

# Since timestamp
kubectl logs logger --since=1h

# Previous container (if crashed)
kubectl logs logger --previous

# Multi-container pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: multi-container
spec:
  containers:
  - name: app
    image: busybox
    command: ['sh', '-c', 'while true; do echo "App log"; sleep 5; done']
  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'while true; do echo "Sidecar log"; sleep 5; done']
EOF

# Logs from specific container
kubectl logs multi-container -c app
kubectl logs multi-container -c sidecar

# All containers
kubectl logs multi-container --all-containers
```

### Lab 2: Events

```bash
# Get all events
kubectl get events

# Sort by timestamp
kubectl get events --sort-by=.metadata.creationTimestamp

# Watch events
kubectl get events --watch

# Events for specific resource
kubectl describe pod <pod-name>
# Events shown at bottom

# Events in all namespaces
kubectl get events --all-namespaces

# Filter by reason
kubectl get events --field-selector reason=Failed

# Filter by involved object
kubectl get events --field-selector involvedObject.name=my-pod
```

### Lab 3: kubectl debug and ephemeral containers

```bash
# Create pod without shell
kubectl run distroless --image=gcr.io/distroless/base

# Can't exec (no shell)
kubectl exec distroless -- sh
# Error: executable file not found

# Debug with ephemeral container
kubectl debug distroless -it --image=busybox --target=distroless

# Inside ephemeral container, you can inspect the pod
# ps aux shows processes from target container

# Debug node
kubectl debug node/<node-name> -it --image=ubuntu
# Creates pod on node with host namespaces

# Debug by copying pod
kubectl debug my-pod --copy-to=my-pod-debug --set-image=*=ubuntu
```

### Lab 4: Resource metrics

```bash
# Node metrics
kubectl top nodes

# Pod metrics
kubectl top pods

# Sort by CPU
kubectl top pods --sort-by=cpu

# Sort by memory
kubectl top pods --sort-by=memory

# All namespaces
kubectl top pods --all-namespaces

# Specific containers
kubectl top pods --containers
```

### Lab 5: Prometheus basics (conceptual)

```bash
# Install Prometheus (helm)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack

# Port forward to Prometheus
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090

# Open http://localhost:9090

# Example queries:
# - container_cpu_usage_seconds_total
# - container_memory_usage_bytes
# - up{job="kubernetes-nodes"}
# - rate(container_cpu_usage_seconds_total[5m])

# Port forward to Grafana
kubectl port-forward svc/prometheus-grafana 3000:80
# Default: admin/prom-operator
```

### Lab 6: Troubleshooting drill (timed exercise)

**Scenario**: A user reports the application at http://myapp.example.com is down.

**Your task** (15 minutes):
1. Verify the issue
2. Identify root cause
3. Propose fix

```bash
# Setup broken app
kubectl create namespace drill
kubectl create deployment web --image=nginx --namespace=drill
kubectl expose deployment web --port=80 --namespace=drill
kubectl create ingress web --class=nginx --rule="myapp.example.com/*=web:80" --namespace=drill

# Break it
kubectl scale deployment web --replicas=0 --namespace=drill

# Start troubleshooting timer!
```

<details>
<summary>Troubleshooting Steps</summary>

```bash
# 1. Check ingress
kubectl get ingress -n drill
kubectl describe ingress web -n drill

# 2. Check service
kubectl get svc web -n drill
kubectl describe svc web -n drill

# 3. Check endpoints
kubectl get endpoints web -n drill
# Empty! No pods backing service

# 4. Check deployment
kubectl get deployment web -n drill
# READY 0/0

# 5. Check pods
kubectl get pods -n drill
# No pods!

# 6. Check events
kubectl get events -n drill --sort-by=.metadata.creationTimestamp

# 7. Root cause: Deployment scaled to 0
# Fix:
kubectl scale deployment web --replicas=3 -n drill

# 8. Verify
kubectl get pods -n drill
kubectl get endpoints web -n drill
# Endpoints populated
```

</details>

### Lab 7: Common troubleshooting commands

```bash
# Pod stuck Pending
kubectl describe pod <pod-name>
kubectl get events --field-selector involvedObject.name=<pod-name>

# Pod CrashLoopBackOff
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>

# Service not routing
kubectl get endpoints <service-name>
kubectl describe service <service-name>

# DNS not working
kubectl run test --rm -it --image=busybox -- nslookup kubernetes
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Node issues
kubectl describe node <node-name>
kubectl top nodes
kubectl get events --field-selector involvedObject.kind=Node

# Check resource quotas
kubectl describe quota
kubectl describe limitrange

# Network connectivity
kubectl run test --rm -it --image=nicolaka/netshoot -- bash
# Inside: ping, curl, nslookup, traceroute

# API server health
kubectl get --raw /healthz
kubectl get --raw /livez
kubectl get --raw /readyz
kubectl get componentstatuses  # deprecated but useful
```

---

## Break-and-Fix Exercise

**Scenario**: An application is running but returning errors. Logs show database connection failures.

**Setup**:
```bash
kubectl create deployment app --image=nginx
kubectl set env deployment/app DATABASE_HOST=db-service.default.svc.cluster.local
```

**Your task**: Debug and fix the database connectivity issue.

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
# Check app logs
kubectl logs deployment/app
# Shows: "Can't connect to db-service"

# Check if service exists
kubectl get svc db-service
# Not found!

# Check DNS
kubectl run test --rm -it --image=busybox -- nslookup db-service
# Fails
```

**Root cause**: Database service doesn't exist.

**Fix**:
```bash
# Create database
kubectl create deployment db --image=postgres
kubectl expose deployment db --name=db-service --port=5432

# Or update app config if service name is wrong
kubectl set env deployment/app DATABASE_HOST=correct-service-name
```

</details>

---

## Interview Questions

### Question 1
How do you view logs from a crashed container?

<details>
<summary>Answer</summary>

**Problem**: Container crashed, current logs show nothing or only new container's logs.

**Solution**: Use `--previous` flag

```bash
# View previous container's logs
kubectl logs <pod-name> --previous

# With container name (multi-container pod)
kubectl logs <pod-name> -c <container-name> --previous

# Save to file
kubectl logs <pod-name> --previous > crash.log
```

**When container crashes**:
1. Kubernetes restarts container
2. Old container logs preserved (temporarily)
3. New container starts with fresh logs
4. `--previous` accesses old container's logs

**Limitations**:
- Only ONE previous container kept
- Logs lost if pod is deleted
- Logs lost after multiple restarts (only last kept)

**Example workflow**:
```bash
# Pod in CrashLoopBackOff
kubectl get pods
NAME    READY   STATUS             RESTARTS   AGE
app     0/1     CrashLoopBackOff   5          3m

# Current logs might be empty or partial
kubectl logs app

# Previous logs show the crash
kubectl logs app --previous
# Error: Database connection failed at startup
```

**Best practice**: Aggregate logs to external system (ELK, Loki, CloudWatch)

</details>

### Question 2
What are Kubernetes events? How long are they kept?

<details>
<summary>Answer</summary>

**Events**: Records of state changes and actions in the cluster.

**What triggers events**:
- Pod scheduled to node
- Container started/failed
- Image pulled
- Probe failed
- Volume mounted
- Node conditions changed
- Resource creation/deletion

**Viewing events**:
```bash
# All events
kubectl get events

# Sorted by time
kubectl get events --sort-by=.metadata.creationTimestamp

# For specific resource
kubectl describe pod <pod-name>
# Shows events at bottom

# Watch events
kubectl get events --watch

# Filter
kubectl get events --field-selector type=Warning
kubectl get events --field-selector involvedObject.name=my-pod
```

**Event retention**: **~1 hour by default**

- Events are etcd objects
- TTL controlled by kube-apiserver flag: `--event-ttl=1h`
- After TTL, events automatically deleted
- Not meant for long-term storage

**Event fields**:
```yaml
Type: Normal/Warning
Reason: Scheduled, Started, Failed, Pulled
Message: Human-readable description
Count: Number of occurrences
FirstTimestamp: First occurrence
LastTimestamp: Most recent occurrence
```

**Common event reasons**:
- **Scheduled**: Pod assigned to node
- **Pulled**: Image pulled successfully
- **Failed**: Image pull failed
- **Started**: Container started
- **Killing**: Container being killed
- **Unhealthy**: Probe failed
- **FailedScheduling**: Can't schedule pod

**Debugging with events**:
```bash
# Why is my pod pending?
kubectl get events --field-selector involvedObject.name=my-pod
# Event shows: "Insufficient cpu"

# Why did my pod restart?
kubectl describe pod my-pod
# Events show: "Liveness probe failed"
```

**Long-term event storage**:
- Use event exporter (to Elasticsearch, etc.)
- Enable audit logging
- Use monitoring tools (Prometheus, Grafana)

</details>

### Question 3
Explain ephemeral containers. When would you use kubectl debug?

<details>
<summary>Answer</summary>

**Ephemeral containers**: Temporary containers added to running pods for debugging.

**Why needed?**
- Distroless images (no shell)
- Minimal images (no debug tools)
- Can't modify running pod spec
- Don't want to rebuild image for debugging

**Creating ephemeral container**:
```bash
# Debug pod without shell
kubectl debug <pod-name> -it --image=busybox --target=<container-name>
```

**Characteristics**:
- Share pod's namespaces (network, IPC, PID)
- Can access other container's filesystem (via /proc)
- **Can't be removed** (stay until pod deleted)
- Don't have resource requests/limits
- Not counted in pod readiness

**kubectl debug use cases**:

**1. Debug distroless container**:
```bash
kubectl run distroless --image=gcr.io/distroless/base
kubectl debug distroless -it --image=busybox --target=distroless
# Now you have shell with debug tools
```

**2. Debug node**:
```bash
kubectl debug node/<node-name> -it --image=ubuntu
# Creates privileged pod on node
# Access node's filesystem at /host
```

**3. Copy and modify pod**:
```bash
kubectl debug my-pod --copy-to=my-pod-debug --set-image=*=ubuntu
# Creates copy of pod with ubuntu image
# Useful for changing image without affecting original
```

**4. Profile running pod**:
```bash
kubectl debug my-pod -it --image=brendangregg/perf --target=my-container
# Add performance profiling tools
```

**Limitations**:
- Requires Kubernetes 1.23+ for full support
- Ephemeral containers can't be removed
- Some features require feature gates
- Not all container runtimes support all features

**Alternative** (if ephemeral containers unavailable):
```bash
# Add debug sidecar to deployment
kubectl patch deployment my-app --patch '
spec:
  template:
    spec:
      containers:
      - name: debug
        image: busybox
        command: ["sleep", "infinity"]
'
```

</details>

### Question 4
Walk through your troubleshooting process for a failing pod.

<details>
<summary>Answer</summary>

**Systematic troubleshooting process**:

**Step 1: Check pod status**
```bash
kubectl get pods
# Statuses: Pending, Running, CrashLoopBackOff, ImagePullBackOff, Error
```

**Step 2: Describe pod**
```bash
kubectl describe pod <pod-name>
# Check:
# - Status and conditions
# - Events (at bottom)
# - Container states
# - Resource requests
# - Node placement
```

**Step 3: Check logs**
```bash
# Current logs
kubectl logs <pod-name>

# Previous container (if crashed)
kubectl logs <pod-name> --previous

# Specific container (multi-container)
kubectl logs <pod-name> -c <container-name>
```

**Step 4: Check events**
```bash
kubectl get events --field-selector involvedObject.name=<pod-name> --sort-by=.metadata.creationTimestamp
```

**Status-specific debugging**:

**Pending**:
```bash
# Check events for reason
kubectl describe pod <pod-name>
# Common causes:
# - Insufficient resources
# - Node selector mismatch
# - Taints/tolerations
# - PVC not bound

# Check scheduler
kubectl get pods -n kube-system -l component=kube-scheduler
```

**CrashLoopBackOff**:
```bash
# Check previous logs
kubectl logs <pod-name> --previous

# Check exit code in describe
kubectl describe pod <pod-name>
# Exit Code 0: Success but immediately exits
# Exit Code 1: Application error
# Exit Code 137: OOMKilled (memory limit)

# Check resource limits
kubectl describe pod <pod-name> | grep -A 5 Limits
```

**ImagePullBackOff**:
```bash
# Check image name
kubectl describe pod <pod-name>
# Look for "Failed to pull image" or "authentication required"

# Verify image exists
docker pull <image-name>

# Check image pull secrets
kubectl get secrets
```

**Running but not working**:
```bash
# Check if ready
kubectl get pod <pod-name>
# READY 0/1 means readiness probe failing

# Exec into pod
kubectl exec -it <pod-name> -- sh
# Test internally

# Check service and endpoints
kubectl get svc
kubectl get endpoints

# Network debugging
kubectl run test --rm -it --image=nicolaka/netshoot -- bash
```

**Step 5: Check related resources**
```bash
# Deployment/ReplicaSet
kubectl describe deployment <name>
kubectl describe replicaset <name>

# Service and endpoints
kubectl describe service <name>
kubectl get endpoints <name>

# ConfigMaps and Secrets
kubectl get configmap
kubectl describe configmap <name>
```

**Step 6: Check node**
```bash
kubectl describe node <node-name>
# Check:
# - Conditions (MemoryPressure, DiskPressure)
# - Capacity vs Allocatable
# - Events
```

**Quick checklist**:
- [ ] Pod status and conditions
- [ ] Events (kubectl describe)
- [ ] Logs (current and previous)
- [ ] Resource requests/limits
- [ ] Probes (liveness, readiness)
- [ ] Service and endpoints
- [ ] ConfigMap and Secret mounts
- [ ] PVC status
- [ ] Node health
- [ ] Network policies
- [ ] RBAC permissions

</details>

### Question 5
How would you troubleshoot high CPU or memory usage in a pod?

<details>
<summary>Answer</summary>

**Troubleshooting high resource usage**:

**Step 1: Identify the problem**
```bash
# Check current usage
kubectl top pods
kubectl top pods --sort-by=cpu
kubectl top pods --sort-by=memory

# Check specific containers
kubectl top pods --containers

# Compare to requests/limits
kubectl describe pod <pod-name> | grep -A 5 "Requests\|Limits"
```

**Step 2: Check if being throttled/killed**
```bash
# Describe pod
kubectl describe pod <pod-name>

# CPU throttling (not killed, just slowed)
# Check metrics over time

# Memory - check for OOMKilled
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState}'
# "exitCode": 137 means OOMKilled
```

**Step 3: Get detailed metrics** (if Prometheus available)
```promql
# CPU usage
rate(container_cpu_usage_seconds_total{pod="<pod-name>"}[5m])

# Memory usage
container_memory_usage_bytes{pod="<pod-name>"}

# CPU throttling
rate(container_cpu_cfs_throttled_seconds_total{pod="<pod-name>"}[5m])
```

**Step 4: Profile the application**
```bash
# Add ephemeral debug container
kubectl debug <pod-name> -it --image=ubuntu --target=<container-name>

# Inside debug container, install profiling tools
apt-get update && apt-get install -y sysstat htop

# Check CPU usage by process
top
htop

# Memory profile
cat /proc/meminfo
free -m

# Process-specific
cat /proc/<pid>/status
```

**Step 5: Application-level debugging**
```bash
# Exec into container
kubectl exec -it <pod-name> -- sh

# Check application logs
# Look for memory leaks, infinite loops, etc.

# Java apps - heap dump
kubectl exec <pod> -- jmap -dump:live,format=b,file=/tmp/heap.bin <pid>

# Go apps - pprof
# (requires pprof endpoints)
kubectl port-forward <pod> 6060:6060
go tool pprof http://localhost:6060/debug/pprof/heap
```

**Common causes and fixes**:

**High CPU**:
```yaml
# Cause: Infinite loop, heavy computation
# Fix: Fix application code

# Cause: Under-provisioned
# Fix: Increase limits
resources:
  limits:
    cpu: "2"  # Increase from 1
```

**High Memory**:
```yaml
# Cause: Memory leak
# Fix: Fix application code, restart periodically

# Cause: Under-provisioned
# Fix: Increase limits
resources:
  limits:
    memory: "2Gi"  # Increase from 512Mi

# Cause: No limit set, eating all node memory
# Fix: Set proper limits
```

**Throttling check**:
```bash
# CPU throttled but not killed
# Symptoms: Slow performance but running

# Check throttling
kubectl describe pod <pod> | grep -i throttl

# Solution: Increase CPU limit
kubectl set resources deployment <name> --limits=cpu=2
```

**OOMKilled**:
```bash
# Memory exceeded limit
# Symptoms: Container repeatedly killed and restarted

# Check for OOMKilled
kubectl describe pod <pod>
# State: Terminated, Reason: OOMKilled, Exit Code: 137

# Solutions:
# 1. Increase memory limit
# 2. Fix memory leak
# 3. Add memory-based HPA to scale before OOM
```

**Prevention**:
1. Set appropriate requests and limits
2. Load test before production
3. Monitor resource trends
4. Set up alerts (Prometheus/Grafana)
5. Use VPA for right-sizing

</details>
