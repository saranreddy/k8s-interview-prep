# Module 00: Setup

**Weight**: 5% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Choosing between kind, k3s, and EKS
- Installing kubectl and cluster setup
- Verifying cluster health
- Basic kubectl commands and context management
- kubeconfig structure

## Edge Cases

1. **Multiple kubeconfig files**: How to merge contexts and switch between clusters
2. **Certificate expiration**: What happens when cluster certificates expire
3. **Version skew**: kubectl vs cluster version compatibility
4. **Port conflicts**: kind/k3s port already in use
5. **Resource constraints**: Minimum requirements for local clusters

---

## Labs

### Lab 1: Install kind and create a cluster

```bash
# Install kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Create a cluster
kind create cluster --name interview-prep

# Verify
kubectl cluster-info --context kind-interview-prep
kubectl get nodes
```

### Lab 2: Install kubectl

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify version
kubectl version --client

# Check version skew
kubectl version
```

### Lab 3: Explore kubeconfig

```bash
# View current config
kubectl config view

# List contexts
kubectl config get-contexts

# View current context
kubectl config current-context

# Switch context (if you have multiple)
kubectl config use-context kind-interview-prep

# View raw kubeconfig file
cat ~/.kube/config
```

### Lab 4: Basic cluster exploration

```bash
# Get cluster info
kubectl cluster-info
kubectl cluster-info dump > cluster-dump.txt

# Get all namespaces
kubectl get namespaces

# Get all pods across all namespaces
kubectl get pods -A

# Get nodes with more details
kubectl get nodes -o wide
kubectl describe node <node-name>

# Check component status
kubectl get --raw /healthz
kubectl get --raw /livez
kubectl get --raw /readyz
```

### Lab 5: Alternative setup with k3s (EC2)

```bash
# On a fresh EC2 t3.medium (Ubuntu 22.04)
curl -sfL https://get.k3s.io | sh -

# Check status
sudo systemctl status k3s

# Copy kubeconfig
mkdir ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config

# Test
kubectl get nodes
```

### Lab 6: EKS cluster (do this last, tear down immediately)

```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create cluster (takes ~15 minutes, costs ~$0.10/hour)
eksctl create cluster \
  --name interview-prep-eks \
  --region us-east-1 \
  --nodes 2 \
  --node-type t3.medium \
  --managed

# Verify
kubectl get nodes

# When done, DELETE IMMEDIATELY
eksctl delete cluster --name interview-prep-eks --region us-east-1
```

---

## Break-and-Fix Exercise

**Scenario**: You've installed kind and created a cluster, but kubectl commands are failing with "connection refused".

**Symptoms**:
```bash
$ kubectl get nodes
The connection to the server localhost:8080 was refused - did you specify the right host or port?
```

**Your task**:
1. Diagnose why kubectl cannot connect
2. Fix the issue
3. Verify the cluster is working

<details>
<summary>Hints</summary>

- Check if the cluster is actually running
- Check your kubeconfig
- Check the KUBECONFIG environment variable

</details>

<details>
<summary>Solution</summary>

**Root cause**: kubectl is not using the correct kubeconfig context, or the KUBECONFIG environment variable is not set.

**Fix**:
```bash
# Check if cluster exists
kind get clusters

# If cluster exists but kubectl fails, check kubeconfig
kubectl config view

# Set context explicitly
kubectl config use-context kind-interview-prep

# Or verify KUBECONFIG is set (should point to ~/.kube/config)
echo $KUBECONFIG
export KUBECONFIG=~/.kube/config

# If cluster doesn't exist, recreate it
kind create cluster --name interview-prep
```

**Verification**:
```bash
kubectl cluster-info
kubectl get nodes
```

</details>

---

## Interview Questions

### Question 1
What is the difference between `kubectl get pods` and `kubectl get pods -o wide`? When would you use each?

<details>
<summary>Answer</summary>

**Basic `kubectl get pods`**:
- Shows: NAME, READY, STATUS, RESTARTS, AGE
- Use for: Quick status check

**`kubectl get pods -o wide`**:
- Additionally shows: IP, NODE, NOMINATED NODE, READINESS GATES
- Use for: Debugging networking issues, checking pod placement, verifying node assignments

**Other useful formats**:
- `-o yaml`: Full object definition
- `-o json`: Machine-readable format
- `-o custom-columns`: Custom output
- `--show-labels`: Display labels

</details>

### Question 2
Explain the kubeconfig file structure. What are contexts, clusters, and users?

<details>
<summary>Answer</summary>

**Structure**:
```yaml
clusters:          # List of Kubernetes clusters
- name: prod
  cluster:
    server: https://prod.example.com
    certificate-authority-data: ...

users:             # Authentication credentials
- name: admin
  user:
    client-certificate-data: ...
    client-key-data: ...

contexts:          # Combines cluster + user + namespace
- name: prod-admin
  context:
    cluster: prod
    user: admin
    namespace: default

current-context: prod-admin
```

**Definitions**:
- **Cluster**: API server endpoint and CA certificate
- **User**: Credentials (cert, token, or auth provider)
- **Context**: Cluster + User + optional default namespace
- **Current-context**: The active context kubectl uses

**Practical use**:
```bash
kubectl config use-context prod-admin
kubectl config set-context --current --namespace=dev
```

</details>

### Question 3
What is the kubectl version skew policy? What happens if your kubectl is 2 minor versions ahead of the cluster?

<details>
<summary>Answer</summary>

**Version Skew Policy**:
- kubectl supports +/- 1 minor version from the cluster
- Example: kubectl 1.28 works with clusters 1.27, 1.28, 1.29
- If skew is larger, some features may not work or commands may fail

**If kubectl is 2 versions ahead** (e.g., kubectl 1.29, cluster 1.27):
- Most read operations will work
- Create/update operations may fail if using newer API features
- New flags or resources won't be available in older clusters
- You'll get warnings or errors about API version mismatches

**Best practice**:
- Keep kubectl within 1 minor version of your cluster
- Use the cluster's version when possible
- Test commands in dev before using in prod

**Check version skew**:
```bash
kubectl version
# Client shows kubectl version
# Server shows cluster version
```

</details>

### Question 4
You run `kubectl get nodes` and see a node in "NotReady" state. What are the possible causes and how would you troubleshoot?

<details>
<summary>Answer</summary>

**Possible causes**:
1. kubelet is down or crashed
2. Network connectivity issues
3. Resource pressure (disk, memory, PIDs)
4. Container runtime (Docker/containerd) is down
5. CNI plugin issues

**Troubleshooting steps**:
```bash
# 1. Check node conditions
kubectl describe node <node-name>
# Look at Conditions section: MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable

# 2. SSH to the node and check kubelet
sudo systemctl status kubelet
sudo journalctl -u kubelet -f

# 3. Check container runtime
sudo systemctl status containerd  # or docker
docker ps  # or crictl ps

# 4. Check disk space
df -h

# 5. Check node logs
kubectl get events --sort-by=.metadata.creationTimestamp

# 6. Try restarting kubelet
sudo systemctl restart kubelet
```

**Common fixes**:
- Restart kubelet: `sudo systemctl restart kubelet`
- Clean up disk space: `docker system prune -a`
- Restart container runtime
- Check CNI configuration in `/etc/cni/net.d/`

</details>

### Question 5
Explain the difference between kind, k3s, minikube, and EKS. When would you use each?

<details>
<summary>Answer</summary>

| Tool | Type | Use Case | Pros | Cons |
|------|------|----------|------|------|
| **kind** | Docker-based | CI/CD, local testing | Fast, multi-node, no VM | Requires Docker |
| **k3s** | Lightweight K8s | Edge, IoT, low-resource | Single binary, production-ready | Less features than full K8s |
| **minikube** | VM or container | Learning, development | Easy, multiple drivers | Slow start, single-node by default |
| **EKS** | Managed cloud | Production workloads | Fully managed, AWS integration | Costs money, slower iteration |

**When to use**:
- **kind**: Local development, testing manifests, CI pipelines, multi-node scenarios
- **k3s**: Resource-constrained environments, single-node production, edge computing
- **minikube**: Learning Kubernetes, quick local setup, testing with addons
- **EKS**: Production applications, enterprise workloads, AWS-native apps

**For this course**:
- Use **kind** (free, fast) for most exercises
- Try **k3s** on EC2 for persistence and EBS integration
- Spin up **EKS** only for the EKS-specific section, then tear it down

</details>
