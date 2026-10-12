# Module 01: Architecture & Control Plane

**Weight**: 8% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Kubernetes architecture overview
- Control plane components: API server, etcd, scheduler, controller manager
- Node components: kubelet, kube-proxy, container runtime
- How components communicate
- Control plane high availability

## Edge Cases

1. **etcd quorum loss**: What happens when you lose majority of etcd nodes
2. **API server down**: Which operations still work when the API server is unavailable
3. **Scheduler unavailable**: Pods stuck in Pending, existing pods unaffected
4. **Controller manager failure**: Existing resources work, but no reconciliation happens
5. **kubelet crash**: Pods on that node become unreachable but keep running

---

## Labs

### Lab 1: Explore control plane components

```bash
# View all system pods
kubectl get pods -n kube-system

# Check API server
kubectl get pods -n kube-system -l component=kube-apiserver
kubectl logs -n kube-system <kube-apiserver-pod>

# Check etcd
kubectl get pods -n kube-system -l component=etcd

# Check scheduler
kubectl get pods -n kube-system -l component=kube-scheduler

# Check controller manager
kubectl get pods -n kube-system -l component=kube-controller-manager
```

### Lab 2: Understand API server interactions

```bash
# Enable API request logging
kubectl get pods -v=8

# Direct API server calls
kubectl get --raw /api/v1/namespaces/default/pods

# View API resources
kubectl api-resources

# View API versions
kubectl api-versions

# Explain a resource
kubectl explain pod
kubectl explain pod.spec.containers
```

### Lab 3: Examine etcd

```bash
# For kind cluster, exec into etcd pod
kubectl exec -n kube-system <etcd-pod> -- etcdctl version

# List etcd members (requires proper env vars)
kubectl exec -n kube-system <etcd-pod> -- sh -c \
  "ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  member list"

# Get all keys (be careful, this can be huge)
kubectl exec -n kube-system <etcd-pod> -- sh -c \
  "ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  get / --prefix --keys-only"
```

### Lab 4: Scheduler in action

```bash
# Create a pod and watch scheduling
kubectl run nginx --image=nginx
kubectl get events --watch

# Check scheduler logs
kubectl logs -n kube-system -l component=kube-scheduler

# Create an unschedulable pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: unschedulable
spec:
  containers:
  - name: nginx
    image: nginx
  nodeSelector:
    disktype: ssd-that-does-not-exist
EOF

# Pod stays Pending
kubectl get pod unschedulable
kubectl describe pod unschedulable
```

### Lab 5: Controller manager patterns

```bash
# Create a deployment and watch reconciliation
kubectl create deployment nginx --image=nginx --replicas=3

# Check ReplicaSet creation
kubectl get rs

# Delete a pod and watch it recreate
kubectl delete pod <nginx-pod-name>
kubectl get pods --watch

# Scale deployment
kubectl scale deployment nginx --replicas=5

# Check controller manager logs
kubectl logs -n kube-system -l component=kube-controller-manager | grep nginx
```

### Lab 6: Kubelet and node health

```bash
# Get node details
kubectl get nodes -o wide
kubectl describe node <node-name>

# Check kubelet API directly (from node)
# SSH to node first
curl -k https://localhost:10250/healthz

# Get kubelet logs (on the node)
sudo journalctl -u kubelet -f

# Check container runtime
crictl ps
crictl images
```

---

## Break-and-Fix Exercise

**Scenario**: The scheduler pod has crashed in your cluster. New pods are stuck in Pending state, but existing pods continue running.

**Symptoms**:
```bash
$ kubectl get pods -n kube-system | grep scheduler
# No scheduler pod or CrashLoopBackOff

$ kubectl run test --image=nginx
pod/test created

$ kubectl get pod test
NAME   READY   STATUS    RESTARTS   AGE
test   0/1     Pending   0          30s
```

**Your task**:
1. Diagnose why new pods can't be scheduled
2. Fix the scheduler
3. Verify new pods can be scheduled

<details>
<summary>Hints</summary>

- Check the kube-system namespace for scheduler pods
- Look at scheduler logs
- Check for configuration issues
- Consider restarting the scheduler

</details>

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
# Check scheduler status
kubectl get pods -n kube-system -l component=kube-scheduler

# If in CrashLoopBackOff, check logs
kubectl logs -n kube-system <scheduler-pod> --previous

# Common causes:
# - Configuration file syntax error
# - Missing permissions
# - Port conflict
```

**Fix** (for kind/kubeadm clusters):
```bash
# Option 1: Delete the pod (it will be recreated by kubelet)
kubectl delete pod -n kube-system <scheduler-pod>

# Option 2: Check and fix the manifest (on control plane node)
# SSH to control plane
sudo cat /etc/kubernetes/manifests/kube-scheduler.yaml
# Fix any syntax errors
sudo systemctl restart kubelet

# Option 3: For corrupted static pod manifest
# Remove and re-add the manifest
sudo mv /etc/kubernetes/manifests/kube-scheduler.yaml /tmp/
# Wait a few seconds
sudo mv /tmp/kube-scheduler.yaml /etc/kubernetes/manifests/
```

**Verification**:
```bash
# Check scheduler is running
kubectl get pods -n kube-system -l component=kube-scheduler

# Create a test pod
kubectl run test2 --image=nginx

# Should go to Running
kubectl get pod test2 --watch

# Previous pending pod should also schedule
kubectl get pod test
```

</details>

---

## Interview Questions

### Question 1
Explain the role of each control plane component and what happens if it fails.

<details>
<summary>Answer</summary>

| Component | Role | If it fails |
|-----------|------|-------------|
| **API Server** | Central management hub; validates and processes all REST requests | No new operations possible. Existing pods keep running. kubectl stops working. |
| **etcd** | Distributed key-value store; source of truth for cluster state | With quorum: cluster continues. Without quorum: API server becomes read-only, no new changes. |
| **Scheduler** | Assigns pods to nodes based on resource requirements and constraints | New pods stuck in Pending. Existing pods unaffected. |
| **Controller Manager** | Runs controllers (Deployment, ReplicaSet, Node, etc.) that reconcile desired vs actual state | No automatic reconciliation. Manual operations work. No auto-healing. |
| **kubelet** | Agent on each node; manages pod lifecycle | Pods on that node become unreachable but continue running. No new pods can be scheduled to that node. |
| **kube-proxy** | Network proxy; maintains network rules for Services | Service networking breaks on that node. Pods can't reach Services. |

**Key insight**: Kubernetes is designed for distributed resilience. Individual component failures don't always mean total cluster failure.

</details>

### Question 2
How does the scheduler decide which node to place a pod on?

<details>
<summary>Answer</summary>

**Scheduling process** (two phases):

**1. Filtering (Predicates)**:
- Eliminates nodes that don't meet requirements:
  - Insufficient resources (CPU, memory)
  - nodeSelector doesn't match
  - Node is unschedulable (cordoned)
  - Taints that pod doesn't tolerate
  - Pod affinity/anti-affinity rules
  - Volume constraints (PV node affinity)

**2. Scoring (Priorities)**:
- Ranks remaining nodes:
  - Balanced resource allocation
  - Least requested resources
  - Node affinity preferences
  - Pod topology spread
  - Image locality (is image already on node?)

**3. Binding**:
- Selects highest-scoring node
- Creates Binding object to assign pod to node
- kubelet on that node pulls image and starts pod

**Edge cases**:
- If no nodes pass filtering: pod stays Pending
- If all nodes score equally: random selection
- Priority and preemption: high-priority pods can evict low-priority pods

**Example**:
```yaml
spec:
  nodeSelector:           # Filtering
    disktype: ssd
  affinity:
    nodeAffinity:        # Scoring preference
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 1
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - us-east-1a
```

</details>

### Question 3
What is stored in etcd? Can you access etcd directly?

<details>
<summary>Answer</summary>

**What's stored in etcd**:
- All Kubernetes objects: Pods, Services, ConfigMaps, Secrets, etc.
- Cluster configuration and state
- Resource quotas and limits
- RBAC policies
- Custom Resource Definitions (CRDs)

**Data format**:
- Keys: `/registry/<resource-type>/<namespace>/<name>`
- Values: Protobuf-encoded objects
- Example: `/registry/pods/default/nginx`

**Can you access etcd directly?**

Yes, but you shouldn't in production:

```bash
# Requires certificates (etcd uses mTLS)
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  get /registry/pods/default/nginx
```

**Why avoid direct access**:
- Bypasses API server validation
- No audit logging
- Risk of corruption
- No RBAC enforcement
- Secrets stored in plaintext (unless encryption-at-rest is enabled)

**Use cases for direct access**:
- Disaster recovery
- Debugging stuck resources
- Backup and restore
- Cluster migration

**Best practice**: Always use `kubectl` or the API server.

</details>

### Question 4
Explain etcd quorum. What happens if you lose 2 nodes in a 5-node etcd cluster?

<details>
<summary>Answer</summary>

**Quorum definition**:
- Majority of nodes must be available for writes
- Formula: `(n/2) + 1` where n = total nodes
- Read operations can work with minority (depending on consistency)

**Cluster sizes and quorum**:
| Total Nodes | Quorum Needed | Can Tolerate |
|-------------|---------------|--------------|
| 1 | 1 | 0 failures |
| 3 | 2 | 1 failure |
| 5 | 3 | 2 failures |
| 7 | 4 | 3 failures |

**5-node cluster losing 2 nodes**:
- Remaining: 3 nodes
- Quorum: 3 (still met! ✓)
- **Cluster continues operating normally**

**If you lose 3 nodes** (only 2 remain):
- Remaining: 2 nodes
- Quorum: 3 (NOT met ✗)
- **Cluster becomes read-only**
- API server returns errors for write operations
- No new pods, services, or config changes

**Why odd numbers**:
- 4-node cluster tolerates only 1 failure (same as 3-node)
- 6-node cluster tolerates only 2 failures (same as 5-node)
- Even numbers don't improve fault tolerance but add overhead

**Recovery**:
```bash
# If quorum is lost, you need to restore from backup or
# reconfigure the cluster with remaining members

# Check member health
etcdctl member list
etcdctl endpoint health

# Remove dead members (if quorum exists)
etcdctl member remove <member-id>
```

</details>

### Question 5
What is a static pod? How does kubelet run control plane components?

<details>
<summary>Answer</summary>

**Static pods**:
- Managed directly by kubelet (not the API server)
- Defined by manifest files in a directory on the node
- Kubelet watches the directory and automatically creates/updates pods
- Can't be managed with `kubectl delete` (kubelet recreates them)

**How it works**:
```bash
# Static pod manifest directory (configurable)
/etc/kubernetes/manifests/

# Kubelet config points to this directory
staticPodPath: /etc/kubernetes/manifests
```

**Control plane as static pods** (kubeadm clusters):
```bash
# On control plane node
ls -la /etc/kubernetes/manifests/
# kube-apiserver.yaml
# kube-controller-manager.yaml
# kube-scheduler.yaml
# etcd.yaml
```

**Why static pods for control plane**:
- Bootstrap problem: API server can't manage itself
- High availability: kubelet ensures control plane stays up
- Node-local: Each control plane node runs its own components

**Mirror pods**:
- API server creates read-only "mirror" pods for static pods
- You can see them with `kubectl get pods -n kube-system`
- But you can't modify or delete them via API

**Try to delete a static pod**:
```bash
kubectl delete pod -n kube-system kube-apiserver-<node>
# Pod deleted (from API server view)
# But kubelet immediately recreates it from the manifest file
```

**When to use static pods**:
- Control plane components
- Node-level monitoring agents (though DaemonSets are better)
- Critical system services that must run even if API server is down

</details>
