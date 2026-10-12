# Module 01: Architecture & Control Plane - Personal Notes

## Deep-Dive Topics Covered

### API Request Pipeline
1. **Authentication** (authn) - Who are you? (client certs, tokens, OIDC)
2. **Authorization** (authz) - What can you do? (RBAC evaluation)
3. **Mutating Admission** - Webhooks that modify requests (add defaults, inject sidecars)
4. **Schema Validation** - Validate against OpenAPI schema
5. **Validating Admission** - Webhooks that accept/reject (policy enforcement)
6. **Persistence** - Write to etcd

### Webhook Deadlock
- Webhook running in cluster calls API server
- API server calls webhook to validate webhook's own request
- Deadlock: webhook can't respond without completing request
- Solution: Webhook namespace exemption or failurePolicy: Ignore

### Node Unreachable Timeline
- **40s**: Node considered unreachable (node-monitor-grace-period)
- **300s** (5 min): Default tolerationSeconds for node.kubernetes.io/unreachable
- **StatefulSet edge case**: Pods NOT evicted automatically (require manual deletion or force-delete)
- Regular pods: Evicted and rescheduled after toleration expires

### Leader Election with Leases
- **Not Raft** - uses optimistic locking on Lease objects
- Lease object in coordination.k8s.io/v1
- Leader updates renewTime periodically
- Other instances watch Lease, become leader if renewTime expires
- Used by: scheduler, controller-manager, cloud-controller-manager

### Watches and Resource Versions
- **Watch**: Long-running HTTP connection for real-time updates
- **resourceVersion**: Consistent read point in etcd MVCC
- **410 Gone**: Watch resourceVersion too old (compacted from etcd)
- **Thundering herd**: All watches break, clients reconnect simultaneously
- **APF** (API Priority and Fairness): Protects API server from overload

### etcd MVCC
- **MVCC** (Multi-Version Concurrency Control): Keeps multiple versions
- **Compaction**: Removes old versions (frees history, not space)
- **Defragmentation**: Reclaims disk space (requires downtime per member)
- **NOSPACE**: etcd storage quota exceeded (2GB default)
  - Cluster becomes read-only
  - Fix: Compact, defrag, increase quota

### Static and Mirror Pods
- **Static pods**: Defined by files in /etc/kubernetes/manifests/
- Managed by kubelet, not API server
- **Mirror pods**: Read-only API representations of static pods
- Control plane runs as static pods (kube-apiserver, etcd, etc.)
- Can't be deleted via kubectl (kubelet recreates them)

### kubeadm Certificate Expiry
- Default: Certs expire after 1 year
- Check: `kubeadm certs check-expiration`
- Renew: `kubeadm certs renew all`
- Automatic renewal: On control plane upgrade
- API server cert in /etc/kubernetes/pki/

### etcd Snapshot and Restore
- **Snapshot**: `etcdctl snapshot save backup.db`
- **Restore**: `etcdctl snapshot restore backup.db --data-dir=/new/path`
- Requires stopping API server and etcd
- Restore creates new cluster with same data
- Critical for disaster recovery

## Key Takeaways
- API request pipeline has 6 stages before persistence
- Leader election uses Leases, not Raft consensus
- Node failure has multi-stage timeline (40s, 300s, StatefulSet exceptions)
- etcd compaction ≠ defragmentation (history vs space)
- Static pods are kubelet-managed, mirror pods are API representations
- Watch 410 Gone requires full relist (can cause thundering herd)

## Commands to Remember
```bash
# Check cert expiry
kubeadm certs check-expiration

# Renew certs
kubeadm certs renew all

# etcd snapshot
ETCDCTL_API=3 etcdctl snapshot save backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# etcd restore
ETCDCTL_API=3 etcdctl snapshot restore backup.db --data-dir=/var/lib/etcd-restore
```

## Mistakes Made
- Initially thought leader election used Raft (it uses Leases with optimistic locking)
- Confused pod eviction timeline (need to account for both node-monitor-grace-period and tolerationSeconds)
- Didn't realize compaction alone doesn't free disk space (need defrag)

## Questions to Review
- Walk through the full API request pipeline with examples
- Explain the complete timeline when a node becomes unreachable
- Why do StatefulSet pods require manual deletion when node is lost?
- How does leader election work without Raft consensus?
- What's the difference between etcd compaction and defragmentation?
