# Mock Interview - Final Checkpoint

**Purpose**: Comprehensive interview simulation covering all modules.

## Format

This mock interview consists of:
1. **System design question** (15 minutes)
2. **Architecture discussion** (10 minutes)
3. **Troubleshooting scenario** (15 minutes)
4. **Rapid-fire questions** (20 minutes)

Total time: ~60 minutes

---

## Part 1: System Design (15 minutes)

**Scenario**: Design a Kubernetes deployment for a three-tier web application (frontend, API, database) that needs to:
- Handle 10,000 requests per second
- Scale automatically based on load
- Run in multiple availability zones
- Support zero-downtime deployments
- Meet SOC 2 security requirements

**What to cover**:
- Workload types (Deployment, StatefulSet)
- Scaling strategy (HPA, Cluster Autoscaler)
- High availability (replicas, pod anti-affinity, PDBs)
- Storage (PVC, StorageClass)
- Networking (Services, Ingress)
- Security (RBAC, Pod Security, NetworkPolicy)
- Observability (logging, monitoring, alerting)

<details>
<summary>Sample Answer Outline</summary>

**Frontend** (Stateless):
```yaml
- Deployment: 10+ replicas
- HPA: Scale 5-50 based on CPU/custom metrics
- Service: ClusterIP
- Ingress: TLS termination, path routing
- Pod anti-affinity: Spread across zones
- PDB: minAvailable: 5
- Resources: requests/limits set
- Readiness probe: HTTP /health
```

**API** (Stateless):
```yaml
- Deployment: 20+ replicas
- HPA: Scale 10-100 based on RPS
- Service: ClusterIP
- Pod anti-affinity: Spread across zones
- PDB: minAvailable: 10
- SecurityContext: runAsNonRoot, drop ALL capabilities
- NetworkPolicy: Only frontend and database can connect
```

**Database** (Stateful):
```yaml
- StatefulSet: 3 replicas (primary + 2 replicas)
- Headless Service: For stable DNS
- PVC per pod: SSD storage with WaitForFirstConsumer
- Pod anti-affinity: Different zones
- PDB: maxUnavailable: 1
- Backup: CronJob with pre/post hooks
- Security: Secrets for credentials
```

**Cross-cutting concerns**:
- Namespace per environment
- RBAC: ServiceAccounts with least privilege
- Pod Security: Restricted level
- Monitoring: Prometheus + Grafana
- Logging: Centralized (ELK, Loki)
- GitOps: Argo CD for deployments

</details>

---

## Part 2: Architecture Discussion (10 minutes)

**Questions**:

1. **Explain the request flow** from external user to database and back. What components are involved at each step?

2. **A node fails suddenly**. Walk through what happens to:
   - Running pods on that node
   - Pending pods
   - Services
   - StatefulSet pods

3. **You need to upgrade the Kubernetes cluster** from 1.27 to 1.28. What's your process and what risks do you consider?

4. **Design a multi-cluster strategy** for DR (disaster recovery). How do you handle:
   - State replication
   - Traffic failover
   - Data consistency

<details>
<summary>Sample Answers</summary>

**Request flow**:
```
1. User → DNS → LoadBalancer IP
2. LoadBalancer → Ingress Controller pod
3. Ingress → Frontend Service (ClusterIP)
4. Service → Frontend Pod (via kube-proxy iptables rules)
5. Frontend Pod → API Service
6. API Service → API Pod
7. API Pod → Database Service (headless)
8. Database Service → StatefulSet pod
9. Response flows back through same path
```

**Node failure**:
- Pods: Marked Terminating after ~40s, recreated elsewhere
- Services: Endpoints updated, no new traffic to failed node
- StatefulSet: Pods recreated with same identity and PVC
- PVs: If zone-locked, pod may stay Pending until node recovers

**Cluster upgrade**:
1. Backup etcd
2. Review release notes
3. Update control plane (one minor version at a time)
4. Drain and upgrade worker nodes (rolling)
5. Verify workloads after each node
6. Test critical paths

**Multi-cluster DR**:
- Database: Async replication to secondary cluster
- GitOps: Same manifests, different clusters
- DNS: GeoDNS or Global Load Balancer
- Failover: Manual or automated based on health checks
- Data: RPO/RTO requirements drive replication strategy

</details>

---

## Part 3: Troubleshooting Scenario (15 minutes)

**Scenario**: 

Production is down. Users report 502 Bad Gateway errors. You have 15 minutes to diagnose and propose a fix.

**Environment**:
- Microservices architecture
- Frontend → API → Database
- Recently deployed a new API version
- Ingress shows healthy
- Metrics show traffic is reaching the cluster

**Your task**: Walk through your troubleshooting process out loud. What commands do you run? What are you checking?

<details>
<summary>Troubleshooting Process</summary>

```bash
# 1. Verify the symptom
curl https://app.example.com
# 502 Bad Gateway

# 2. Check Ingress
kubectl get ingress -n prod
kubectl describe ingress app-ingress -n prod
# Looks good, backend service exists

# 3. Check Service
kubectl get svc api-service -n prod
kubectl describe svc api-service -n prod
# Service exists

# 4. Check Endpoints
kubectl get endpoints api-service -n prod
# EMPTY! No endpoints

# Root cause found: Service has no backend pods

# 5. Why no endpoints? Check pods
kubectl get pods -n prod -l app=api
# Shows: 0/3 pods Running, all CrashLoopBackOff

# 6. Check pod logs
kubectl logs -n prod <api-pod> --previous
# Error: Database connection failed: connection refused

# 7. Check database service
kubectl get svc database -n prod
# Service exists but wrong name!

# 8. Check what API is connecting to
kubectl get deployment api -n prod -o yaml | grep DATABASE_HOST
# DATABASE_HOST=database-service
# But actual service name is: database

# Root cause: Recent deployment changed DATABASE_HOST to wrong value

# Fix:
kubectl set env deployment/api -n prod DATABASE_HOST=database

# Verify:
kubectl get pods -n prod -l app=api --watch
# Pods coming up

kubectl get endpoints api-service -n prod
# Endpoints populated

curl https://app.example.com
# 200 OK
```

**Summary**: New deployment had incorrect database hostname in environment variable. API pods couldn't connect to database, failing health checks, resulting in empty service endpoints and 502 errors.

</details>

---

## Part 4: Rapid-Fire Questions (20 minutes)

Answer quickly and concisely. Aim for 1-2 minutes per question.

### Workloads & Scheduling

1. **Q**: What happens if you delete a ReplicaSet but not the Deployment?
   <details><summary>A</summary>Deployment controller immediately recreates the ReplicaSet. Pods continue running unaffected.</details>

2. **Q**: A pod is Pending with "Insufficient cpu". Two options: add nodes or reduce requests. How do you decide?
   <details><summary>A</summary>Check actual usage of running pods (kubectl top). If pods use much less than requested, reduce requests. If pods are near limits, add nodes.</details>

3. **Q**: Explain the difference between DaemonSet and Deployment with pod anti-affinity.
   <details><summary>A</summary>DaemonSet: One pod per node automatically, managed by DaemonSet controller. Deployment + anti-affinity: Manual replica count, scheduler tries to spread but doesn't guarantee one per node.</details>

### Networking

4. **Q**: Service shows endpoints but connection times out. What do you check?
   <details><summary>A</summary>NetworkPolicy (might be blocking), pod readiness (might be failing), firewall rules, kube-proxy status, DNS resolution.</details>

5. **Q**: Headless service returns 3 pod IPs. One pod is deleted. What happens to DNS?
   <details><summary>A</summary>DNS returns only 2 IPs after ~30-60s (DNS caching + kubelet sync delay). Clients might still try the old IP until cache expires.</details>

6. **Q**: You need to expose different services on the same domain but different paths. How?
   <details><summary>A</summary>Single Ingress resource with multiple path rules, each pointing to different services.</details>

### Storage

7. **Q**: PVC is bound but pod can't mount it (Permission denied). What's wrong?
   <details><summary>A</summary>Check fsGroup in pod securityContext. Volume ownership might not match pod's user. Or SELinux context mismatch.</details>

8. **Q**: Can you expand a PVC? What's required?
   <details><summary>A</summary>Yes, if StorageClass has allowVolumeExpansion: true. Edit PVC's storage request. Some storage backends require pod restart to resize filesystem.</details>

### Security

9. **Q**: Pod needs to call Kubernetes API to list pods. What do you set up?
   <details><summary>A</summary>Create ServiceAccount, create Role with list pods permission, create RoleBinding linking SA to Role, set pod's serviceAccountName.</details>

10. **Q**: What's the difference between authentication and authorization in Kubernetes?
    <details><summary>A</summary>Authentication: Who are you? (certificates, tokens, OIDC). Authorization: What can you do? (RBAC, ABAC).</details>

### Config & Secrets

11. **Q**: You updated a ConfigMap but pods still have old values. Why?
    <details><summary>A</summary>Environment variables don't update (need pod restart). Volume mounts update after ~60s. SubPath mounts never update.</details>

12. **Q**: How do you rotate a Secret without downtime?
    <details><summary>A</summary>Create new Secret with new name, update Deployment to reference new Secret, rollout happens gradually with zero downtime, delete old Secret after rollout.</details>

### Scaling & Performance

13. **Q**: HPA shows target 80%, current 120%, but not scaling up. Why?
    <details><summary>A</summary>At maxReplicas already, or recent scale-up (stabilization window), or deployment rollout in progress, or resource quota exceeded.</details>

14. **Q**: Cluster Autoscaler added a node but pod still Pending. Why?
    <details><summary>A</summary>Node not ready yet (initializing), pod affinity rules exclude the new node, taints on node without tolerations, or pod needs resources larger than node size.</details>

### Observability

15. **Q**: How do you find which pod is consuming the most CPU?
    <details><summary>A</summary>`kubectl top pods --sort-by=cpu --all-namespaces`</details>

16. **Q**: Container restarted 10 times. How do you find out why?
    <details><summary>A</summary>`kubectl logs <pod> --previous` for last container's logs, `kubectl describe pod` for exit code and events.</details>

### Packaging

17. **Q**: Helm upgrade failed halfway. How do you rollback?
    <details><summary>A</summary>`helm rollback <release> <revision>` or `helm rollback <release>` (to previous). Check history with `helm history <release>`.</details>

18. **Q**: What's the difference between Kustomize bases and overlays?
    <details><summary>A</summary>Base: Common resources shared across environments. Overlays: Environment-specific patches (dev/prod) that build on base.</details>

### Architecture

19. **Q**: etcd is at 95% capacity. What do you do?
    <details><summary>A</summary>Defragment etcd, increase etcd storage, review retention policies for events/logs, consider scaling out etcd cluster.</details>

20. **Q**: You need to run a sensitive workload. List 5 security measures.
    <details><summary>A</summary>1) RunAsNonRoot, 2) Drop all capabilities, 3) NetworkPolicy default-deny, 4) ReadOnlyRootFilesystem, 5) PodSecurity restricted level, 6) Dedicated namespace with RBAC, 7) Secrets from external vault.</details>

---

## Final Challenge: Hands-On Troubleshooting

Set up this broken environment and fix it:

```bash
# Setup (intentionally broken)
kubectl create namespace challenge

# Deployment with missing image tag
kubectl create deployment api --image=nginx: --replicas=3 -n challenge

# Service with wrong selector
kubectl create service clusterip api --tcp=80:80 -n challenge
kubectl set selector service api app=wrong -n challenge

# Ingress pointing to wrong port
kubectl create ingress api --class=nginx \
  --rule="api.local/*=api:8080" -n challenge

# ConfigMap mounted but pod expects different key
kubectl create configmap app-config --from-literal=config=value -n challenge

# Your mission: Get the application working
# Time limit: 20 minutes
```

<details>
<summary>Solution Steps</summary>

```bash
# 1. Fix image tag
kubectl set image deployment/api -n challenge nginx=nginx:latest

# 2. Fix service selector
kubectl set selector service api app=api -n challenge

# 3. Fix ingress port
kubectl edit ingress api -n challenge
# Change port from 8080 to 80

# 4. Check what key pod expects and fix ConfigMap
kubectl get deployment api -n challenge -o yaml
# Adjust ConfigMap or deployment accordingly

# 5. Verify
kubectl get pods -n challenge
kubectl get endpoints api -n challenge
curl -H "Host: api.local" http://<ingress-ip>
```

</details>

---

## Completion Criteria

You've successfully completed the mock interview if you can:

- ✓ Design a production-ready architecture
- ✓ Explain the reasoning behind your choices
- ✓ Troubleshoot issues systematically
- ✓ Answer rapid-fire questions confidently
- ✓ Fix the hands-on challenge in under 20 minutes

## Next Steps

1. **If you passed**: Congratulations! You're interview-ready. Consider:
   - Getting CKA/CKAD certified
   - Contributing to open-source K8s projects
   - Mentoring others

2. **If you struggled**: No problem! Focus on:
   - Modules where you had difficulty
   - More hands-on practice
   - Review troubleshooting methodology
   - Retake this mock interview in 1-2 weeks

## Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [CNCF Landscape](https://landscape.cncf.io/)
- [Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way)
- [Practice questions](https://github.com/dgkanatsios/CKAD-exercises)

---

**Remember**: The goal isn't to memorize every flag or API version. It's to understand concepts deeply, troubleshoot systematically, and design robust systems.

Good luck! 🚀
