# Module 09: Scaling

**Weight**: 7% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Horizontal Pod Autoscaler (HPA)
- Vertical Pod Autoscaler (VPA)
- Cluster Autoscaler and Karpenter
- Metrics Server
- Custom and external metrics
- Scaling behavior and policies

## Edge Cases

1. **HPA without resource requests**: Can't calculate target utilization
2. **HPA flapping**: Scaling up and down repeatedly
3. **VPA vs HPA conflict**: Can't use both on same metric
4. **Cluster Autoscaler delays**: Node provisioning takes minutes
5. **Scale-down blocked**: Pods without PDB or local storage prevent scale-down

---

## Labs

### Lab 1: Install Metrics Server

```bash
# Install metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Wait for it to be ready
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=metrics-server --timeout=60s

# Check metrics
kubectl top nodes
kubectl top pods
```

### Lab 2: Basic HPA

```bash
# Create deployment with resource requests (required!)
kubectl create deployment nginx --image=nginx --replicas=1
kubectl set resources deployment nginx --limits=cpu=200m,memory=256Mi --requests=cpu=100m,memory=128Mi

# Create HPA
kubectl autoscale deployment nginx --cpu-percent=50 --min=1 --max=10

# Check HPA
kubectl get hpa nginx --watch

# Generate load
kubectl run load-generator --image=busybox --restart=Never -- /bin/sh -c "while true; do wget -q -O- http://nginx; done"

# Watch scaling
kubectl get hpa --watch
kubectl get pods -w
```

### Lab 3: HPA with custom metrics

```bash
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nginx-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 4
        periodSeconds: 30
      selectPolicy: Max
EOF

kubectl describe hpa nginx-hpa
```

### Lab 4: VPA (conceptual, requires VPA installation)

```bash
# Install VPA (on real cluster)
# git clone https://github.com/kubernetes/autoscaler.git
# cd autoscaler/vertical-pod-autoscaler
# ./hack/vpa-up.sh

# VPA example
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: nginx-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx
  updatePolicy:
    updateMode: "Auto"  # or "Off" for recommendations only
  resourcePolicy:
    containerPolicies:
    - containerName: nginx
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: 2
        memory: 2Gi
EOF

# Check recommendations
kubectl describe vpa nginx-vpa
```

### Lab 5: Cluster Autoscaler concepts

```bash
# On cloud providers (EKS, GKE, AKS)
# Cluster Autoscaler watches for pending pods
# Adds nodes to node group/pool
# Removes underutilized nodes

# Example node with scale-down prevention
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: prevent-scale-down
  annotations:
    cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
spec:
  containers:
  - name: nginx
    image: nginx
EOF

# Trigger scale-up by creating pending pods
kubectl create deployment scale-test --image=nginx --replicas=100
kubectl set resources deployment scale-test --requests=cpu=1,memory=1Gi

# Watch pending pods (would trigger CA to add nodes)
kubectl get pods --field-selector=status.phase=Pending --watch
```

### Lab 6: Testing scale behavior

```bash
# Create deployment
kubectl create deployment scale-demo --image=nginx --replicas=3
kubectl set resources deployment scale-demo --requests=cpu=100m,memory=128Mi

# Manual scale
kubectl scale deployment scale-demo --replicas=10

# Watch rollout
kubectl rollout status deployment scale-demo

# Scale down
kubectl scale deployment scale-demo --replicas=2

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp | grep scale
```

---

## Break-and-Fix Exercise

**Scenario**: You created an HPA, but it shows "unknown" for current CPU utilization and won't scale.

**Setup**:
```bash
kubectl create deployment broken-hpa --image=nginx
kubectl autoscale deployment broken-hpa --cpu-percent=50 --min=1 --max=10
```

**Symptoms**:
```bash
$ kubectl get hpa
NAME         REFERENCE               TARGETS         MINPODS   MAXPODS   REPLICAS
broken-hpa   Deployment/broken-hpa   <unknown>/50%   1         10        1
```

**Your task**: Fix the HPA configuration.

<details>
<summary>Solution</summary>

**Root cause**: Deployment has no CPU resource requests. HPA can't calculate utilization without requests.

**Fix**:
```bash
kubectl set resources deployment broken-hpa --requests=cpu=100m,memory=128Mi
```

**Verification**:
```bash
kubectl get hpa broken-hpa
# Should show current CPU percentage
```

**Key learning**: Always set resource requests when using HPA!

</details>

---

## Interview Questions

### Question 1
How does HPA work? What metrics can it use?

<details>
<summary>Answer</summary>

**HPA** (Horizontal Pod Autoscaler): Automatically scales pods based on metrics.

**How it works**:
1. HPA controller runs every 15s (default)
2. Queries metrics from Metrics Server (or custom metrics API)
3. Calculates desired replicas:
   ```
   desiredReplicas = ceil[currentReplicas * (currentMetric / targetMetric)]
   ```
4. Updates Deployment/ReplicaSet scale
5. Respects min/max bounds

**Metric types**:

**1. Resource metrics** (CPU, memory):
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 50  # Target 50% of requests
```

**2. Custom metrics** (from apps):
```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"
```

**3. External metrics** (outside cluster):
```yaml
metrics:
- type: External
  external:
    metric:
      name: pubsub.googleapis.com/subscription/num_undelivered_messages
    target:
      type: Value
      value: "100"
```

**Requirements**:
- Metrics Server installed
- Pods must have resource requests
- Target must support scale subresource

**Example calculation**:
```
Current: 3 replicas, 80% CPU
Target: 50% CPU
Desired: ceil(3 * (80 / 50)) = ceil(4.8) = 5 replicas
```

**Scaling limits**:
- Max scale-up: 2x current replicas (default)
- Max scale-down: 50% current replicas (default)
- Configurable via behavior policies

</details>

### Question 2
What is HPA flapping? How do you prevent it?

<details>
<summary>Answer</summary>

**Flapping**: HPA scales up and down repeatedly in short periods.

**Causes**:
1. Metric oscillation (near threshold)
2. Too aggressive scaling policies
3. Slow application startup
4. Bursty workload

**Example flapping**:
```
10:00 - 2 pods, CPU 60% → scale up to 3
10:01 - 3 pods, CPU 40% → scale down to 2
10:02 - 2 pods, CPU 60% → scale up to 3
# Repeat forever
```

**Prevention methods**:

**1. Stabilization window**:
```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300  # Wait 5 min before scale-down
  scaleUp:
    stabilizationWindowSeconds: 60   # Quick scale-up
```

**2. Conservative thresholds**:
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70  # Higher threshold = less sensitive
```

**3. Scaling policies**:
```yaml
behavior:
  scaleDown:
    policies:
    - type: Percent
      value: 10       # Scale down max 10% at a time
      periodSeconds: 60
  scaleUp:
    policies:
    - type: Percent
      value: 50       # Scale up faster
      periodSeconds: 30
```

**4. Min/max replicas buffer**:
```yaml
spec:
  minReplicas: 3   # Don't go below 3
  maxReplicas: 20
```

**5. Combine multiple metrics**:
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70
- type: Resource
  resource:
    name: memory
    target:
      averageUtilization: 80
# Scales based on highest metric
```

**Best practice HPA**:
```yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 4
        periodSeconds: 30
      selectPolicy: Max
```

</details>

### Question 3
VPA vs HPA - when to use each? Can you use both?

<details>
<summary>Answer</summary>

**VPA** (Vertical Pod Autoscaler): Adjusts CPU/memory requests/limits
**HPA** (Horizontal Pod Autoscaler): Adjusts number of replicas

| Aspect | VPA | HPA |
|--------|-----|-----|
| **What it scales** | Resources per pod | Number of pods |
| **Use case** | Right-sizing, unknown resource needs | Handle variable load |
| **Disruption** | Restarts pods | No restart |
| **Stateful apps** | Good fit | Not ideal |

**When to use VPA**:
- Don't know optimal resource requests
- Single-instance apps (databases, caches)
- Batch jobs with variable resource needs
- Cost optimization (right-sizing)

**When to use HPA**:
- Stateless applications
- Predictable resource per pod
- Need to scale for load
- Multiple replicas acceptable

**Can you use both?**

**Yes, but carefully**:
- VPA on memory, HPA on CPU (different metrics)
- VPA in "Off" mode (recommendations only) + HPA active
- VPA for resource recommendations, manual adjustment, then HPA

**Don't do this**:
```yaml
# CONFLICT: Both scaling on CPU
VPA: Auto mode, adjusting CPU requests
HPA: Scaling replicas based on CPU
# Results in unpredictable behavior
```

**Safe combination**:
```yaml
# VPA adjusts memory
VPA:
  resourcePolicy:
    containerPolicies:
    - containerName: app
      mode: Auto
      controlledResources: ["memory"]

# HPA scales on CPU
HPA:
  metrics:
  - type: Resource
    resource:
      name: cpu
```

**Real-world patterns**:

**Pattern 1**: VPA for recommendations
```yaml
VPA:
  updateMode: "Off"  # Only provide recommendations
# Review recommendations
# Manually update deployment
# Use HPA for scaling
```

**Pattern 2**: Different resources
```yaml
VPA: Scale memory (slow-changing)
HPA: Scale replicas based on CPU (fast-changing)
```

**Pattern 3**: Time-based
```yaml
# Use VPA during development (right-size)
# Once stable, switch to HPA (production scaling)
```

</details>

### Question 4
How does Cluster Autoscaler work? What prevents a node from scaling down?

<details>
<summary>Answer</summary>

**Cluster Autoscaler (CA)**: Automatically adds/removes nodes based on pod scheduling.

**Scale-up trigger**:
1. Pods are Pending (can't be scheduled)
2. Reason: Insufficient resources
3. CA evaluates node groups/pools
4. Adds node(s) to accommodate pods
5. Takes ~5 minutes on most clouds

**Scale-down trigger**:
1. Node underutilized (<50% requests for >10 min)
2. All pods can be moved to other nodes
3. CA drains and removes node
4. Takes ~10 minutes (grace periods)

**What prevents scale-down?**

**1. System pods without PDB**:
- kube-system pods often block
- Solution: Add PDB

**2. Pods with local storage**:
- emptyDir prevents scale-down
- Data would be lost

**3. Pods with annotation**:
```yaml
metadata:
  annotations:
    cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
```

**4. Pods not controlled by Deployment/ReplicaSet**:
- Standalone pods
- StatefulSets (sometimes)

**5. PodDisruptionBudget prevents eviction**:
```yaml
minAvailable: 3
# If eviction violates PDB, node won't scale down
```

**6. Recently scaled up** (<10 min ago)

**Configuration**:
```yaml
# Cluster Autoscaler deployment
args:
- --scale-down-unneeded-time=10m
- --scale-down-delay-after-add=10m
- --scale-down-utilization-threshold=0.5
- --max-node-provision-time=15m
```

**Node group limits**:
```yaml
# EKS example
nodeGroup:
  minSize: 2
  maxSize: 10
  desiredCapacity: 3
```

**Troubleshooting scale-down**:
```bash
# Check CA logs
kubectl logs -n kube-system deployment/cluster-autoscaler

# Look for scale-down reasons
kubectl get events -n kube-system | grep ScaleDown

# Check what's preventing scale-down
kubectl describe nodes | grep -A 5 "Non-terminated Pods"
```

**Karpenter** (modern alternative):
- Faster (seconds, not minutes)
- More flexible node selection
- No pre-defined node groups
- Better bin-packing

</details>

### Question 5
What's the difference between CPU requests and limits for HPA calculations?

<details>
<summary>Answer</summary>

**HPA uses requests, NOT limits!**

**Why requests?**
- Requests define guaranteed resources
- Scheduler uses requests for placement
- HPA calculates utilization against requests
- Limits are enforcement caps, not guarantees

**Calculation**:
```
CPU Utilization = (Current CPU Usage) / (CPU Requests) * 100%
```

**Example 1**:
```yaml
resources:
  requests:
    cpu: 100m
  limits:
    cpu: 500m

# Pod using 150m CPU
Utilization = 150 / 100 = 150%
# HPA sees 150% utilization
# Limits are irrelevant
```

**Example 2**:
```yaml
resources:
  requests:
    cpu: 400m
  limits:
    cpu: 500m

# Pod using 150m CPU
Utilization = 150 / 400 = 37.5%
# HPA sees 37.5% utilization
```

**Common mistake**:
```yaml
# NO requests set!
resources:
  limits:
    cpu: 500m

# HPA shows: <unknown>/50%
# Can't calculate utilization without requests
```

**Best practices**:

**1. Always set requests**:
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

**2. Reasonable request values**:
- Too low → constant scaling
- Too high → waste resources
- Target: 60-80% utilization under load

**3. Requests should match actual usage**:
```bash
# Check actual usage
kubectl top pods

# Adjust requests accordingly
kubectl set resources deployment app --requests=cpu=200m
```

**4. HPA target around 70%**:
```yaml
spec:
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70  # 70% of requests
```

**Memory-based HPA** (same concept):
```yaml
spec:
  metrics:
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 80  # 80% of memory requests
```

**Multi-metric HPA** (uses highest):
```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70
- type: Resource
  resource:
    name: memory
    target:
      averageUtilization: 80
# Scales based on whichever is higher
```

</details>
