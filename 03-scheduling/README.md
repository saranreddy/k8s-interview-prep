# Module 03: Scheduling

**Weight**: 10% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Resource requests and limits (CPU, memory)
- Quality of Service (QoS) classes: Guaranteed, Burstable, BestEffort
- Node affinity and pod affinity/anti-affinity
- Taints and tolerations
- Topology spread constraints
- Priority and preemption
- Resource quotas and LimitRanges

## Edge Cases

1. **Pending pods**: No nodes match scheduling requirements (resources, affinity, taints)
2. **OOMKilled vs throttling**: Memory limits kill pods, CPU limits throttle them
3. **Eviction**: Node pressure (disk, memory, PIDs) triggers kubelet evictions
4. **Preemption**: High-priority pods evict lower-priority pods to make room
5. **Fractional CPU**: 100m = 0.1 CPU, minimum is 1m (0.001)

---

## Labs

### Lab 1: Resource requests and limits

```bash
# Pod with requests and limits
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: resource-demo
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
EOF

# Check scheduling based on requests
kubectl describe pod resource-demo | grep -A 5 "Requests"

# Create pod that exceeds node capacity
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: too-big
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "1000Gi"  # More than any node has
        cpu: "1000"
EOF

# Pod stays Pending
kubectl get pod too-big
kubectl describe pod too-big
# Events show: "0/1 nodes available: Insufficient memory"
```

### Lab 2: QoS classes

```bash
# Guaranteed QoS (requests == limits for all resources)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: qos-guaranteed
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "128Mi"
        cpu: "500m"
      limits:
        memory: "128Mi"
        cpu: "500m"
EOF

# Burstable QoS (has requests, but limits differ or missing)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: qos-burstable
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
EOF

# BestEffort QoS (no requests or limits)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: qos-besteffort
spec:
  containers:
  - name: app
    image: nginx
EOF

# Check QoS class
kubectl get pod qos-guaranteed -o jsonpath='{.status.qosClass}'
kubectl get pod qos-burstable -o jsonpath='{.status.qosClass}'
kubectl get pod qos-besteffort -o jsonpath='{.status.qosClass}'
```

### Lab 3: Node affinity

```bash
# Label nodes
kubectl label node <node-name> env=production
kubectl label node <node-name> tier=frontend

# Required node affinity (must match)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: affinity-required
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: env
            operator: In
            values:
            - production
  containers:
  - name: nginx
    image: nginx
EOF

# Preferred node affinity (soft requirement)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: affinity-preferred
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
          - key: tier
            operator: In
            values:
            - frontend
      - weight: 20
        preference:
          matchExpressions:
          - key: env
            operator: In
            values:
            - production
  containers:
  - name: nginx
    image: nginx
EOF
```

### Lab 4: Pod affinity and anti-affinity

```bash
# Deploy app with anti-affinity (spread across nodes)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-spread
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - web
            topologyKey: kubernetes.io/hostname
      containers:
      - name: nginx
        image: nginx
EOF

# Check pods are on different nodes
kubectl get pods -o wide

# Pod affinity (co-locate with cache)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: with-cache
  labels:
    app: cache
spec:
  containers:
  - name: redis
    image: redis
---
apiVersion: v1
kind: Pod
metadata:
  name: app-needs-cache
spec:
  affinity:
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - cache
        topologyKey: kubernetes.io/hostname
  containers:
  - name: app
    image: nginx
EOF
```

### Lab 5: Taints and tolerations

```bash
# Taint a node
kubectl taint nodes <node-name> env=production:NoSchedule

# Regular pods won't schedule there
kubectl run test --image=nginx
kubectl get pod test -o wide
# Should NOT be on tainted node

# Pod with toleration
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: toleration-demo
spec:
  tolerations:
  - key: "env"
    operator: "Equal"
    value: "production"
    effect: "NoSchedule"
  containers:
  - name: nginx
    image: nginx
EOF

# CAN schedule on tainted node
kubectl get pod toleration-demo -o wide

# Taint effects:
# NoSchedule: Don't schedule new pods
# PreferNoSchedule: Try to avoid scheduling
# NoExecute: Evict existing pods

# Remove taint
kubectl taint nodes <node-name> env=production:NoSchedule-
```

### Lab 6: Topology spread constraints

```bash
# Even distribution across zones
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: topology-spread
spec:
  replicas: 6
  selector:
    matchLabels:
      app: spread-demo
  template:
    metadata:
      labels:
        app: spread-demo
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: spread-demo
      containers:
      - name: nginx
        image: nginx
EOF

# Check distribution
kubectl get pods -o wide
```

### Lab 7: Priority and preemption

```bash
# Create priority classes
cat <<EOF | kubectl apply -f -
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 1000
globalDefault: false
description: "High priority workloads"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: low-priority
value: 100
globalDefault: false
description: "Low priority workloads"
EOF

# Deploy low-priority pods
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: low-priority-app
spec:
  replicas: 10
  selector:
    matchLabels:
      app: low-priority
  template:
    metadata:
      labels:
        app: low-priority
    spec:
      priorityClassName: low-priority
      containers:
      - name: nginx
        image: nginx
        resources:
          requests:
            memory: "128Mi"
            cpu: "500m"
EOF

# Deploy high-priority pod that needs resources
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: high-priority-pod
spec:
  priorityClassName: high-priority
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        memory: "1Gi"
        cpu: "2"
EOF

# Watch preemption (low-priority pods evicted)
kubectl get pods --watch
```

---

## Break-and-Fix Exercise

**Scenario**: You deployed 3 replicas of an application, but only 2 are running. One pod has been Pending for 10 minutes.

**Setup**:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pending-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pending-app
  template:
    metadata:
      labels:
        app: pending-app
    spec:
      containers:
      - name: app
        image: nginx
        resources:
          requests:
            memory: "10Gi"
            cpu: "8"
EOF
```

**Your task**:
1. Find why the pod is Pending
2. Fix the issue without reducing replica count
3. Verify all 3 pods are running

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
kubectl get pods
# Shows 2 Running, 1 Pending

kubectl describe pod <pending-pod>
# Events show: "0/N nodes are available: Insufficient cpu (N), Insufficient memory (N)"
```

**Root cause**: Resource requests (10Gi memory, 8 CPU) exceed available node capacity.

**Fix**:
```bash
# Reduce resource requests to reasonable values
kubectl edit deployment pending-app

# Change requests to:
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
```

**Verification**:
```bash
kubectl get pods
# All 3 should now be Running
```

</details>

---

## Interview Questions

### Question 1
What's the difference between requests and limits? What happens if a pod exceeds each?

<details>
<summary>Answer</summary>

| Aspect | Requests | Limits |
|--------|----------|--------|
| **Purpose** | Scheduling decision | Resource enforcement |
| **CPU behavior** | Guaranteed minimum | **Throttled** if exceeded |
| **Memory behavior** | Scheduling only | **OOMKilled** if exceeded |
| **Node capacity** | Sum of requests ≤ node capacity | Can overcommit |

**Requests**:
- Scheduler uses requests to pick a node
- Guarantees minimum resources
- Node won't accept pod if requests can't be met
- CFS (Completely Fair Scheduler) shares ensure pod gets at least this much

**Limits**:
- Maximum resources pod can use
- **CPU**: Process throttled if trying to exceed (no crash)
- **Memory**: Process killed (OOMKilled) if exceeding (can't throttle memory)

**Example**:
```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "250m"    # Guaranteed 0.25 CPU
  limits:
    memory: "128Mi" # Killed if exceeds 128Mi
    cpu: "500m"     # Throttled if trying to use more than 0.5 CPU
```

**Scenarios**:
1. **CPU exceeded**: Container throttled, continues running (slower)
2. **Memory exceeded**: Container killed, pod shows OOMKilled
3. **No limits set**: Can use all available resources (risky!)

</details>

### Question 2
Explain QoS classes. In what order are pods evicted under node pressure?

<details>
<summary>Answer</summary>

**Three QoS classes**:

**1. Guaranteed** (highest priority):
- All containers have requests == limits for CPU and memory
- Most protected from eviction

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "500m"
  limits:
    memory: "128Mi"
    cpu: "500m"
```

**2. Burstable** (medium priority):
- At least one container has requests or limits
- Requests ≠ limits (can burst)

```yaml
resources:
  requests:
    memory: "64Mi"
  limits:
    memory: "128Mi"
```

**3. BestEffort** (lowest priority):
- No requests or limits set
- First to be evicted

```yaml
# No resources section at all
```

**Eviction order under node pressure**:

1. **BestEffort** pods first (evict all)
2. **Burstable** pods exceeding requests
3. **Burstable** pods within requests (by priority)
4. **Guaranteed** pods (last resort)

**Within same QoS class**:
- Pods exceeding requests evicted first
- Then sorted by priority class
- Then by usage relative to requests

**Node pressure triggers**:
- `memory.available < threshold`
- `nodefs.available < threshold` (disk)
- `nodefs.inodesFree < threshold`
- `imagefs.available < threshold`

**Check evictions**:
```bash
kubectl get events --field-selector reason=Evicted
kubectl describe node <node> | grep -A 10 "Conditions"
```

</details>

### Question 3
How do taints and tolerations work? What's the difference between NoSchedule, PreferNoSchedule, and NoExecute?

<details>
<summary>Answer</summary>

**Concept**:
- **Taints**: Applied to nodes to repel pods
- **Tolerations**: Applied to pods to allow scheduling on tainted nodes
- Together: Control which pods can schedule on which nodes

**Taint syntax**:
```bash
kubectl taint nodes <node> key=value:Effect
```

**Three effects**:

**1. NoSchedule**:
- New pods without toleration WON'T be scheduled
- Existing pods NOT affected

```bash
kubectl taint nodes node1 dedicated=gpu:NoSchedule
```

**2. PreferNoSchedule**:
- Scheduler TRIES to avoid placing pods here
- But will if no other options
- Soft version of NoSchedule

```bash
kubectl taint nodes node1 maintenance=soon:PreferNoSchedule
```

**3. NoExecute**:
- New pods won't be scheduled
- Existing pods WITHOUT toleration are EVICTED
- Can specify `tolerationSeconds` to delay eviction

```bash
kubectl taint nodes node1 failing=true:NoExecute
```

**Toleration syntax**:
```yaml
tolerations:
- key: "dedicated"
  operator: "Equal"
  value: "gpu"
  effect: "NoSchedule"

# Or tolerate any value
- key: "env"
  operator: "Exists"
  effect: "NoSchedule"
```

**NoExecute with grace period**:
```yaml
tolerations:
- key: "node.kubernetes.io/unreachable"
  operator: "Exists"
  effect: "NoExecute"
  tolerationSeconds: 300  # Evict after 5 minutes
```

**Common use cases**:
- Dedicated nodes for GPU workloads
- Node maintenance (drain without cordoning)
- Node failures (NoExecute for unreachable nodes)
- Multi-tenancy (separate customer workloads)

**Built-in taints**:
```
node.kubernetes.io/not-ready
node.kubernetes.io/unreachable
node.kubernetes.io/out-of-disk
node.kubernetes.io/memory-pressure
node.kubernetes.io/disk-pressure
node.kubernetes.io/network-unavailable
node.kubernetes.io/unschedulable
```

</details>

### Question 4
What is pod priority and preemption? Give an example scenario.

<details>
<summary>Answer</summary>

**Priority**:
- Numeric value assigned to pods via PriorityClass
- Higher number = higher priority
- Affects scheduling order and preemption

**Preemption**:
- When cluster lacks resources for a high-priority pod
- Scheduler evicts lower-priority pods to make room
- Evicted pods get graceful termination period

**Creating PriorityClass**:
```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical
value: 1000000
globalDefault: false
description: "Critical production workloads"
preemptionPolicy: PreemptLowerPriority  # Default
```

**Using PriorityClass**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: critical-pod
spec:
  priorityClassName: critical
  containers:
  - name: app
    image: nginx
```

**Preemption process**:
1. High-priority pod can't be scheduled (insufficient resources)
2. Scheduler identifies lower-priority pods to evict
3. Eviction ensures high-priority pod CAN schedule
4. Graceful termination for evicted pods
5. High-priority pod scheduled

**Example scenario**:

```yaml
# Low priority batch jobs running
apiVersion: batch/v1
kind: Job
metadata:
  name: data-processing
spec:
  template:
    spec:
      priorityClassName: low-priority  # value: 100
      containers:
      - name: worker
        image: processor
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
```

```yaml
# Critical user-facing pod arrives
apiVersion: v1
kind: Pod
metadata:
  name: user-api
spec:
  priorityClassName: critical  # value: 1000000
  containers:
  - name: api
    image: api-server
    resources:
      requests:
        memory: "4Gi"
        cpu: "2"
```

**What happens**:
1. Cluster has 8Gi memory, 4 CPUs available
2. Two batch job pods using all resources
3. Critical user-api pod arrives
4. Scheduler preempts ONE batch job pod
5. user-api pod schedules immediately
6. Evicted batch job pod recreated later (when resources available)

**PreemptionPolicy**:
```yaml
preemptionPolicy: Never  # This pod won't preempt others
# Useful for best-effort batch workloads
```

**System priorities**:
```
system-node-critical: 2000001000  # kubelet, etc.
system-cluster-critical: 2000000000  # coredns, metrics-server
```

</details>

### Question 5
How do topology spread constraints differ from pod anti-affinity?

<details>
<summary>Answer</summary>

**Both spread pods across topology domains, but**:

| Feature | Pod Anti-Affinity | Topology Spread |
|---------|-------------------|-----------------|
| **Control** | Binary (yes/no) | Gradual (max skew) |
| **Flexibility** | Hard constraint | Soft or hard |
| **Granularity** | Coarse | Fine-grained |
| **Use case** | HA (different nodes) | Even distribution |

**Pod Anti-Affinity**:

```yaml
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app: web
      topologyKey: kubernetes.io/hostname
```

- Each pod MUST be on different node
- With 3 nodes, max 3 pods
- Rigid: Can't schedule if constraint not met

**Topology Spread**:

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: web
```

- Pods spread across zones with max difference of 1
- Example: 3 zones → 3, 3, 2 pods (skew = 1) ✓
- Example: 3 zones → 5, 2, 2 pods (skew = 3) ✗

**maxSkew**:
- 0: Perfect balance (very strict)
- 1: At most 1 pod difference
- Higher: More flexibility

**whenUnsatisfiable**:
- `DoNotSchedule`: Hard constraint (like required affinity)
- `ScheduleAnyway`: Soft constraint (like preferred affinity)

**Real-world example**:

Deploy 6 replicas across 3 zones:

```yaml
# Anti-affinity: Would only allow 3 pods (1 per zone) - TOO STRICT
# Topology spread with maxSkew: 1
# Result: 2 pods in each zone - PERFECT
```

**Multiple constraints**:
```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  # Spread across zones
- maxSkew: 2
  topologyKey: kubernetes.io/hostname
  # Spread across nodes
```

**When to use**:
- **Anti-affinity**: HA requirement, different hosts MANDATORY
- **Topology spread**: Even distribution, optimal resource usage, gradual scaling

</details>
