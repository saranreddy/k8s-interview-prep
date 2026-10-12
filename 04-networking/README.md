# Module 04: Networking

**Weight**: 12% | **Status**: Track in [PROGRESS.md](../PROGRESS.md)

## Topics

- Service types: ClusterIP, NodePort, LoadBalancer, ExternalName
- Headless Services and StatefulSet networking
- CoreDNS and service discovery
- Ingress controllers and Ingress resources
- NetworkPolicy for pod-to-pod firewalling
- CNI (Container Network Interface) basics

## Edge Cases

1. **Service with no endpoints**: Service exists but no pods match selector
2. **DNS resolution failures**: CoreDNS pod down or misconfigured
3. **Default-deny NetworkPolicy**: Blocks all traffic including DNS
4. **NodePort port conflicts**: Multiple services can't use same NodePort
5. **Ingress without controller**: Resource created but no controller to implement it

---

## Labs

### Lab 1: ClusterIP Service

```bash
# Create deployment
kubectl create deployment nginx --image=nginx --replicas=3

# Expose as ClusterIP (default)
kubectl expose deployment nginx --port=80 --target-port=80

# Get service details
kubectl get svc nginx
kubectl describe svc nginx

# Check endpoints
kubectl get endpoints nginx

# Test from within cluster
kubectl run test --image=busybox --rm -it --restart=Never -- wget -O- http://nginx

# Check DNS resolution
kubectl run test --image=busybox --rm -it --restart=Never -- nslookup nginx
# Returns: nginx.default.svc.cluster.local
```

### Lab 2: NodePort Service

```bash
# Create NodePort service
kubectl expose deployment nginx --type=NodePort --port=80 --name=nginx-nodeport

# Get NodePort
kubectl get svc nginx-nodeport
# Shows port like 30000-32767

# Access from outside cluster
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
NODE_PORT=$(kubectl get svc nginx-nodeport -o jsonpath='{.spec.ports[0].nodePort}')
curl http://$NODE_IP:$NODE_PORT
```

### Lab 3: LoadBalancer Service

```bash
# LoadBalancer (requires cloud provider or MetalLB)
kubectl expose deployment nginx --type=LoadBalancer --port=80 --name=nginx-lb

# In cloud: Gets external IP
kubectl get svc nginx-lb --watch

# In kind/minikube: Stays <pending>
# Use minikube tunnel or port-forward instead
kubectl port-forward svc/nginx-lb 8080:80
```

### Lab 4: Headless Service

```bash
# Headless service (clusterIP: None)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: nginx-headless
spec:
  clusterIP: None
  selector:
    app: nginx
  ports:
  - port: 80
EOF

# DNS returns pod IPs directly (not service VIP)
kubectl run test --image=busybox --rm -it --restart=Never -- nslookup nginx-headless
# Returns multiple A records (one per pod)

# Used with StatefulSets for stable pod DNS
# pod-0.service-name.namespace.svc.cluster.local
```

### Lab 5: CoreDNS and service discovery

```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# CoreDNS config
kubectl get configmap -n kube-system coredns -o yaml

# Test DNS from pod
kubectl run test --image=busybox --rm -it --restart=Never -- sh
# Inside pod:
nslookup kubernetes
nslookup kubernetes.default
nslookup kubernetes.default.svc.cluster.local

# Check pod DNS config
kubectl run test-dns --image=busybox --command -- sleep 3600
kubectl exec test-dns -- cat /etc/resolv.conf
```

### Lab 6: Ingress

```bash
# Install ingress controller (nginx)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Wait for controller
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Create ingress resource
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: myapp.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx
            port:
              number: 80
EOF

# Test (add to /etc/hosts first)
kubectl get ingress
curl http://myapp.local
```

### Lab 7: NetworkPolicy

```bash
# Create test namespace
kubectl create namespace network-test

# Deploy frontend and backend
kubectl create deployment frontend --image=nginx --namespace=network-test
kubectl create deployment backend --image=nginx --namespace=network-test
kubectl expose deployment backend --port=80 --namespace=network-test

# Test connectivity (works by default)
kubectl run test --image=busybox --rm -it --restart=Never --namespace=network-test \
  -- wget -O- http://backend

# Default deny all ingress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: network-test
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

# Now connectivity blocked
kubectl run test --image=busybox --rm -it --restart=Never --namespace=network-test \
  -- wget -O- --timeout=5 http://backend
# Times out

# Allow specific ingress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: network-test
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 80
EOF

# Label test pod as frontend
kubectl run test --image=busybox --rm -it --restart=Never --namespace=network-test \
  --labels=app=frontend \
  -- wget -O- http://backend
# Works now
```

### Lab 8: NetworkPolicy for egress

```bash
# Deny all egress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-egress
  namespace: network-test
spec:
  podSelector:
    matchLabels:
      app: restricted
  policyTypes:
  - Egress
EOF

# Deploy restricted pod
kubectl run restricted --image=busybox --labels=app=restricted --namespace=network-test \
  --command -- sleep 3600

# Can't reach anything
kubectl exec -it restricted --namespace=network-test -- wget -O- --timeout=5 http://backend
# Times out

# Allow DNS and specific egress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-and-backend
  namespace: network-test
spec:
  podSelector:
    matchLabels:
      app: restricted
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    - podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
  - to:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - protocol: TCP
      port: 80
EOF
```

---

## Break-and-Fix Exercise

**Scenario**: You deployed a NetworkPolicy to secure your app, but now pods can't resolve DNS, and nothing works.

**Setup**:
```bash
kubectl create namespace broken-network
kubectl create deployment app --image=nginx --namespace=broken-network

cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: broken-network
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
EOF
```

**Symptoms**:
```bash
kubectl run test --image=busybox --rm -it --restart=Never --namespace=broken-network \
  -- nslookup kubernetes
# Fails: can't resolve
```

**Your task**:
1. Diagnose the networking issue
2. Fix DNS resolution
3. Verify pods can resolve names

<details>
<summary>Solution</summary>

**Root cause**: NetworkPolicy denies all egress, including DNS queries to CoreDNS.

**Fix**:
```bash
# Allow DNS egress
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: broken-network
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
EOF
```

**Verification**:
```bash
kubectl run test --image=busybox --rm -it --restart=Never --namespace=broken-network \
  -- nslookup kubernetes
# Works now
```

**Key learning**: Always allow DNS egress when using default-deny policies!

</details>

---

## Interview Questions

### Question 1
Explain the difference between ClusterIP, NodePort, LoadBalancer, and ExternalName services.

<details>
<summary>Answer</summary>

| Type | Scope | Use Case | How it works |
|------|-------|----------|--------------|
| **ClusterIP** | Internal only | Default, internal communication | Virtual IP in cluster |
| **NodePort** | External via node | Dev/test external access | Opens port on every node |
| **LoadBalancer** | External via LB | Production external access | Cloud provider creates LB |
| **ExternalName** | DNS alias | External service proxy | DNS CNAME record |

**ClusterIP** (default):
```yaml
spec:
  type: ClusterIP
  ports:
  - port: 80
```
- Gets virtual IP (10.96.0.0/12 range)
- Only accessible within cluster
- DNS: `service-name.namespace.svc.cluster.local`

**NodePort**:
```yaml
spec:
  type: NodePort
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080  # Optional, auto-assigned if omitted
```
- Builds on ClusterIP
- Opens port (30000-32767) on EVERY node
- Access via `<NodeIP>:<NodePort>`
- kube-proxy forwards to pods

**LoadBalancer**:
```yaml
spec:
  type: LoadBalancer
  ports:
  - port: 80
```
- Builds on NodePort
- Cloud provider creates external load balancer
- Gets external IP
- Routes to NodePort, then to pods

**ExternalName**:
```yaml
spec:
  type: ExternalName
  externalName: api.example.com
```
- No proxy, just DNS CNAME
- Pods resolve `my-service` → `api.example.com`
- No port forwarding

**Progression**: ClusterIP → NodePort → LoadBalancer (each builds on previous)

</details>

### Question 2
What is a headless service? When would you use it?

<details>
<summary>Answer</summary>

**Headless Service**:
- `clusterIP: None` in spec
- No virtual IP assigned
- DNS returns pod IPs directly

**Regular Service**:
```bash
$ nslookup my-service
Name: my-service.default.svc.cluster.local
Address: 10.96.5.10  # Service virtual IP
```

**Headless Service**:
```bash
$ nslookup my-headless-service
Name: my-headless-service.default.svc.cluster.local
Address: 10.244.1.5  # Pod IP 1
Address: 10.244.2.8  # Pod IP 2
Address: 10.244.3.2  # Pod IP 3
```

**Creating headless service**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-headless
spec:
  clusterIP: None  # This makes it headless
  selector:
    app: my-app
  ports:
  - port: 80
```

**Use cases**:

**1. StatefulSets** (most common):
```yaml
apiVersion: apps/v1
kind: StatefulSet
spec:
  serviceName: nginx-headless  # Must be headless
```
- Each pod gets stable DNS: `pod-0.nginx-headless.default.svc.cluster.local`
- Direct pod-to-pod communication
- Example: Database replica set (connect to specific replica)

**2. Client-side load balancing**:
- Client gets all pod IPs
- Client chooses which pod to connect to
- Example: gRPC load balancing

**3. Custom service discovery**:
- Application needs to know all pod IPs
- Example: Clustering (Elasticsearch, Cassandra)

**4. Avoiding kube-proxy overhead**:
- Direct pod-to-pod, no iptables rules
- Slightly better performance

**With StatefulSet**:
```bash
# Stable network identities
web-0.nginx-headless.default.svc.cluster.local
web-1.nginx-headless.default.svc.cluster.local
web-2.nginx-headless.default.svc.cluster.local

# Even if pod restarts, DNS name stays same
# (IP may change, but name is stable)
```

</details>

### Question 3
How does CoreDNS work? What happens if CoreDNS pods are down?

<details>
<summary>Answer</summary>

**CoreDNS role**:
- Cluster DNS server
- Resolves service names to IPs
- Runs as deployment in `kube-system` namespace

**DNS resolution flow**:
1. Pod makes DNS query (e.g., `curl http://nginx`)
2. Pod's `/etc/resolv.conf` points to CoreDNS service IP
3. Query goes to CoreDNS pod
4. CoreDNS:
   - Checks if it's a service name → returns service IP
   - Checks if it's pod name → returns pod IP
   - External name → forwards to upstream DNS
5. Pod receives IP and connects

**Pod DNS config**:
```bash
$ cat /etc/resolv.conf
nameserver 10.96.0.10  # CoreDNS service IP
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

**DNS name formats**:
```
# Service
<service>
<service>.<namespace>
<service>.<namespace>.svc.cluster.local

# Headless service pod
<pod-name>.<service>.<namespace>.svc.cluster.local

# Pod (if hostname set)
<pod-ip-with-dashes>.<namespace>.pod.cluster.local
# Example: 10-244-1-5.default.pod.cluster.local
```

**If CoreDNS is down**:
- DNS queries fail
- Services can't be resolved by name
- But direct IP connections still work
- Existing connections unaffected

**Troubleshooting**:
```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns

# Test DNS from a pod
kubectl run test --image=busybox --rm -it --restart=Never -- nslookup kubernetes

# Check CoreDNS config
kubectl get configmap -n kube-system coredns -o yaml
```

**CoreDNS Corefile**:
```
.:53 {
    errors
    health
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
        pods insecure
        fallthrough in-addr.arpa ip6.arpa
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}
```

**Common issues**:
- CoreDNS pod evicted (resource pressure)
- NetworkPolicy blocking DNS
- Node DNS config issues
- CoreDNS config syntax errors

</details>

### Question 4
Explain NetworkPolicy. How do you implement default-deny while allowing DNS?

<details>
<summary>Answer</summary>

**NetworkPolicy**:
- Firewall rules for pod-to-pod communication
- Requires CNI plugin support (Calico, Cilium, Weave)
- Default: All traffic allowed
- Once a policy selects a pod, that pod is isolated

**Default-deny ingress**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}  # Matches all pods
  policyTypes:
  - Ingress
```

**Default-deny egress**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
```

**Allow DNS (critical!)**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP  # DNS can use TCP for large responses
      port: 53
```

**Complete example** (default-deny + DNS + specific access):
```yaml
# 1. Deny all
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
# 2. Allow DNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
---
# 3. Allow frontend → backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
```

**Policies are additive**: Multiple policies = union of allowed traffic

**Common mistake**:
```yaml
# WRONG: This blocks DNS!
policyTypes:
- Egress
egress: []  # Empty = deny all
```

**Best practice**:
1. Start with default-deny
2. Add DNS egress immediately
3. Add specific rules as needed
4. Test thoroughly

</details>

### Question 5
What is an Ingress controller? What happens if you create an Ingress without a controller?

<details>
<summary>Answer</summary>

**Ingress vs Ingress Controller**:

| Component | What it is | Role |
|-----------|-----------|------|
| **Ingress** | Kubernetes resource | Configuration/rules |
| **Ingress Controller** | Application (nginx, HAProxy, etc.) | Implements the rules |

**Ingress resource** (just configuration):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 80
```

**What Ingress provides**:
- HTTP/HTTPS routing
- Virtual hosting (multiple domains)
- Path-based routing
- TLS termination
- Load balancing

**Without Ingress Controller**:
```bash
kubectl apply -f ingress.yaml
# Resource created successfully

kubectl get ingress
# Shows ingress, but NO IP ADDRESS

# Nothing actually happens!
# No traffic routing, no load balancer
```

**Analogy**: Ingress is like a recipe. Ingress Controller is the chef who cooks it.

**Popular Ingress Controllers**:
1. **NGINX Ingress Controller** (most common)
2. **Traefik**
3. **HAProxy**
4. **AWS ALB Ingress Controller**
5. **GCE Ingress Controller**
6. **Contour**
7. **Istio Gateway**

**How Ingress Controller works**:
1. Watches for Ingress resources
2. Reads rules and configuration
3. Configures itself (e.g., updates nginx.conf)
4. Reloads to apply changes
5. Routes traffic based on rules

**Installing NGINX Ingress Controller**:
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Creates:
# - Namespace: ingress-nginx
# - Deployment: ingress-nginx-controller
# - Service: LoadBalancer (gets external IP)
# - ConfigMaps, ServiceAccounts, RBAC
```

**IngressClass**:
```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
spec:
  controller: k8s.io/ingress-nginx
```

Multiple controllers can coexist:
```yaml
spec:
  ingressClassName: nginx  # Use nginx controller
```

**Advanced Ingress features**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: advanced-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
      - path: /web
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

</details>
