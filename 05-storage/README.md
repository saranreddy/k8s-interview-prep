# Module 05: Storage

**Weight**: 8% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- PersistentVolume (PV) and PersistentVolumeClaim (PVC)
- StorageClass and dynamic provisioning
- Access modes: ReadWriteOnce, ReadOnlyMany, ReadWriteMany
- Volume binding modes: Immediate vs WaitForFirstConsumer
- Reclaim policies: Retain, Delete, Recycle
- Volume types: emptyDir, hostPath, configMap, secret

## Edge Cases

1. **PVC stuck Pending**: No PV available or StorageClass doesn't exist
2. **Zone mismatch**: PV in different zone than pod
3. **Reclaim policy**: Delete vs Retain - data loss risks
4. **ReadWriteMany**: Not supported by most cloud providers (EBS only RWO)
5. **Volume expansion**: Not all storage classes support online expansion

---

## Labs

### Lab 1: emptyDir and hostPath

```bash
# emptyDir (temporary storage, pod lifetime)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
spec:
  containers:
  - name: writer
    image: busybox
    command: ['sh', '-c', 'while true; do date >> /data/log.txt; sleep 5; done']
    volumeMounts:
    - name: shared-data
      mountPath: /data
  - name: reader
    image: busybox
    command: ['sh', '-c', 'tail -f /data/log.txt']
    volumeMounts:
    - name: shared-data
      mountPath: /data
  volumes:
  - name: shared-data
    emptyDir: {}
EOF

kubectl logs emptydir-demo -c reader

# hostPath (node's filesystem - dangerous!)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-demo
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: host-data
      mountPath: /usr/share/nginx/html
  volumes:
  - name: host-data
    hostPath:
      path: /tmp/nginx-data
      type: DirectoryOrCreate
EOF
```

### Lab 2: Manual PV and PVC

```bash
# Create PersistentVolume
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: manual-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  hostPath:
    path: /mnt/data
EOF

# Create PersistentVolumeClaim
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: manual-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
EOF

# Check binding
kubectl get pv
kubectl get pvc

# Use in pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pv-pod
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: storage
      mountPath: /usr/share/nginx/html
  volumes:
  - name: storage
    persistentVolumeClaim:
      claimName: manual-pvc
EOF
```

### Lab 3: StorageClass and dynamic provisioning

```bash
# Check available StorageClasses
kubectl get storageclass

# Create StorageClass (example for local development)
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
EOF

# PVC with StorageClass (auto-provisions PV)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
spec:
  storageClassName: fast
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF

kubectl get pvc dynamic-pvc --watch
```

### Lab 4: Access modes

```bash
# ReadWriteOnce (most common)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rwo-pvc
spec:
  accessModes:
  - ReadWriteOnce  # One node can mount read-write
  resources:
    requests:
      storage: 1Gi
EOF

# ReadOnlyMany
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rom-pvc
spec:
  accessModes:
  - ReadOnlyMany  # Many nodes can mount read-only
  resources:
    requests:
      storage: 1Gi
EOF

# ReadWriteMany (requires NFS or similar)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rwm-pvc
spec:
  accessModes:
  - ReadWriteMany  # Many nodes can mount read-write
  resources:
    requests:
      storage: 1Gi
EOF
```

### Lab 5: VolumeBindingMode

```bash
# Immediate binding (default)
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: immediate-binding
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: Immediate  # PV created immediately
EOF

# WaitForFirstConsumer (better for topology)
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: wait-binding
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer  # PV created when pod scheduled
EOF

# PVC waits until pod is created
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: wait-pvc
spec:
  storageClassName: wait-binding
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF

# Stays Pending until pod uses it
kubectl get pvc wait-pvc
```

### Lab 6: Volume expansion

```bash
# StorageClass with allowVolumeExpansion
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: expandable
provisioner: kubernetes.io/no-provisioner
allowVolumeExpansion: true
EOF

# Create PVC
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: expandable-pvc
spec:
  storageClassName: expandable
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF

# Expand by editing PVC
kubectl patch pvc expandable-pvc -p '{"spec":{"resources":{"requests":{"storage":"2Gi"}}}}'

# Check status
kubectl get pvc expandable-pvc --watch
```

---

## Break-and-Fix Exercise

**Scenario**: Your StatefulSet pods are stuck in Pending because PVCs can't bind.

**Setup**:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: nginx
  replicas: 3
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
        image: nginx
  volumeClaimTemplates:
  - metadata:
      name: www
    spec:
      storageClassName: missing-storage-class
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 1Gi
EOF
```

**Your task**: Fix the storage issue and get pods running.

<details>
<summary>Solution</summary>

**Diagnosis**:
```bash
kubectl get pvc
# Shows PVCs in Pending state

kubectl describe pvc www-web-0
# Shows: "waiting for a volume to be created"
# or "storageclass.storage.k8s.io "missing-storage-class" not found"
```

**Fix**:
```bash
# Option 1: Use existing StorageClass
kubectl get storageclass
kubectl patch statefulset web -p '{"spec":{"volumeClaimTemplates":[{"metadata":{"name":"www"},"spec":{"storageClassName":"standard"}}]}}'

# Or delete and recreate with correct class
kubectl delete statefulset web
# Edit YAML with correct storageClassName
kubectl apply -f fixed-statefulset.yaml
```

**Verification**:
```bash
kubectl get pvc
# All Bound
kubectl get pods
# All Running
```

</details>

---

## Interview Questions

### Question 1
Explain the difference between PV, PVC, and StorageClass.

<details>
<summary>Answer</summary>

**PersistentVolume (PV)**:
- Cluster resource representing storage
- Provisioned by admin or dynamically
- Lifecycle independent of pods
- Examples: EBS volume, NFS share, local disk

**PersistentVolumeClaim (PVC)**:
- Request for storage by user
- Binds to a PV
- Used by pods like a volume
- Namespace-scoped (PV is cluster-scoped)

**StorageClass**:
- Template for dynamic PV provisioning
- Defines provisioner and parameters
- Enables automatic PV creation

**Relationship**:
```
StorageClass → creates → PersistentVolume ← binds to ← PersistentVolumeClaim ← used by ← Pod
```

**Example flow**:
1. User creates PVC requesting 10Gi storage
2. StorageClass provisioner creates PV (e.g., AWS EBS volume)
3. PVC binds to PV
4. Pod mounts PVC as volume
5. Data persists even if pod is deleted

</details>

### Question 2
What are access modes? Which mode does AWS EBS support?

<details>
<summary>Answer</summary>

**Three access modes**:

| Mode | Abbreviation | Meaning | Use Case |
|------|--------------|---------|----------|
| ReadWriteOnce | RWO | One node, read-write | Databases, most apps |
| ReadOnlyMany | ROX | Many nodes, read-only | Static content |
| ReadWriteMany | RWX | Many nodes, read-write | Shared storage |

**AWS EBS**: Only supports **ReadWriteOnce (RWO)**
- Block storage attached to one EC2 instance
- Can't be shared across nodes
- For RWX, use EFS (Elastic File System)

**Cloud provider support**:
- **AWS EBS**: RWO only
- **AWS EFS**: RWO, ROX, RWX
- **GCP Persistent Disk**: RWO only
- **Azure Disk**: RWO only
- **Azure Files**: RWO, ROX, RWX
- **NFS**: RWO, ROX, RWX

**Common mistake**:
```yaml
# Won't work with EBS!
spec:
  accessModes:
  - ReadWriteMany
  storageClassName: gp2  # EBS
```

</details>

### Question 3
What is volumeBindingMode? When should you use WaitForFirstConsumer?

<details>
<summary>Answer</summary>

**Two modes**:

**Immediate** (default):
- PV provisioned/bound immediately when PVC created
- Problem: PV might be in wrong zone for pod

**WaitForFirstConsumer**:
- PV provisioned only when pod using PVC is scheduled
- Ensures PV is in same zone as pod

**Example scenario** (why WaitForFirstConsumer matters):

```
Cluster: 3 nodes in us-east-1a, us-east-1b, us-east-1c
PVC created → PV provisioned in us-east-1a (Immediate mode)
Pod scheduled → lands on node in us-east-1c
Result: Pod can't mount PV (zone mismatch) → Pending forever
```

**With WaitForFirstConsumer**:
```
PVC created → stays Pending
Pod scheduled → lands on node in us-east-1c
PV provisioned → created in us-east-1c
Result: Pod can mount PV → Running
```

**Configuration**:
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp2-delayed
provisioner: kubernetes.io/aws-ebs
volumeBindingMode: WaitForFirstConsumer
parameters:
  type: gp2
```

**When to use**:
- Multi-zone clusters
- Topology-aware scheduling
- Most production workloads with cloud storage

**AWS EBS best practice**: Always use WaitForFirstConsumer

</details>

### Question 4
What happens to data when a PVC is deleted? Explain reclaim policies.

<details>
<summary>Answer</summary>

**Three reclaim policies**:

**Retain**:
- PV remains after PVC deleted
- Data preserved
- Manual cleanup required
- Status: Released (not available for new claims)

**Delete** (default for dynamic provisioning):
- PV and underlying storage deleted
- Data lost permanently
- Automatic cleanup

**Recycle** (deprecated):
- Basic scrub (`rm -rf /volume/*`)
- PV made available for new claims
- Don't use (deprecated)

**Example**:
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-pv
spec:
  persistentVolumeReclaimPolicy: Retain  # or Delete
  capacity:
    storage: 10Gi
```

**Scenario**: PVC with 100GB database deleted

**With Retain**:
```bash
kubectl delete pvc database-pvc
# PV status: Released (not Bound)
# EBS volume still exists
# Data intact
# Manual steps:
# 1. Backup data if needed
# 2. Delete PV: kubectl delete pv my-pv
# 3. Delete EBS volume in AWS console
```

**With Delete**:
```bash
kubectl delete pvc database-pvc
# PV automatically deleted
# EBS volume automatically deleted
# Data LOST FOREVER
```

**Best practice**:
- Production: Use **Retain** for safety
- Development: Use **Delete** for cleanup
- Always backup before deleting PVCs!

**Change policy** (before deleting PVC):
```bash
kubectl patch pv my-pv -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

</details>

### Question 5
Why might a PVC stay in Pending state? How do you troubleshoot?

<details>
<summary>Answer</summary>

**Common causes**:

1. **No StorageClass** (or doesn't exist)
2. **No matching PV** (manual provisioning)
3. **Insufficient capacity**
4. **Zone mismatch** (Immediate binding)
5. **Access mode not supported**
6. **Provisioner failure**
7. **Quota exceeded**

**Troubleshooting**:

```bash
# 1. Describe PVC
kubectl describe pvc my-pvc
# Look for Events at bottom

# 2. Check StorageClass exists
kubectl get storageclass
kubectl describe storageclass <name>

# 3. Check available PVs
kubectl get pv

# 4. Check provisioner pods (for dynamic provisioning)
kubectl get pods -n kube-system
# Look for ebs-csi-controller, nfs-provisioner, etc.

# 5. Check provisioner logs
kubectl logs -n kube-system <provisioner-pod>

# 6. Check resource quotas
kubectl get resourcequota
kubectl describe resourcequota
```

**Common errors and fixes**:

**Error**: `waiting for a volume to be created`
```bash
# Cause: StorageClass doesn't exist
# Fix: Create StorageClass or use existing one
kubectl get storageclass
kubectl edit pvc my-pvc  # Change storageClassName
```

**Error**: `volume.beta.kubernetes.io/storage-provisioner: not set`
```bash
# Cause: No default StorageClass
# Fix: Set a default
kubectl patch storageclass <name> -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

**Error**: `failed to provision volume: zone mismatch`
```bash
# Cause: PV in different zone
# Fix: Use WaitForFirstConsumer
kubectl get storageclass <name> -o yaml
# Check volumeBindingMode
```

**Error**: `requested access modes not compatible`
```bash
# Cause: Asking for RWX on EBS
# Fix: Use EFS or change to RWO
```

</details>
