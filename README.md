# Kubernetes Interview Prep

[![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![Progress](https://img.shields.io/badge/Progress-0%25-red)]()
[![License](https://img.shields.io/badge/License-MIT-blue.svg)]()

A comprehensive, hands-on Kubernetes refresher course designed to prepare you for technical interviews through practical labs, break-and-fix exercises, and targeted interview questions.

## Who This Is For

This repo is for engineers who:
- Used Kubernetes ~2 years ago and need a refresher
- Want hands-on practice with every core concept
- Are preparing for Kubernetes-focused interviews
- Learn best by doing (not just reading docs)

## How It Works

Each module follows a consistent structure:

1. **Concepts**: Core theory and edge cases you need to know
2. **Labs**: Hands-on exercises with kubectl commands and YAML manifests
3. **Break-and-Fix**: A broken scenario you must diagnose and repair
4. **Interview Questions**: 5 questions with detailed answers

**To pass a module**: Fix the break-and-fix scenario + answer 4 out of 5 interview questions correctly.

## Quick Start

```bash
# Clone the repo
git clone <repo-url>
cd kubernetes-interview-prep

# Set up your cluster (see 00-setup)
cd 00-setup
cat README.md

# Track your progress
python scripts/progress.py
```

## Progress

Track your completion in [PROGRESS.md](PROGRESS.md). Update module status as you complete them, then run:

```bash
python scripts/progress.py
```

This auto-calculates your overall completion percentage.

## Modules

- **[00-setup](00-setup/)** (5%) - Cluster setup with kind/k3s
- **[01-architecture](01-architecture/)** (8%) - Control plane components
- **[02-workloads](02-workloads/)** (12%) - Deployments, StatefulSets, Jobs
- **[03-scheduling](03-scheduling/)** (10%) - Resource requests, affinity, taints
- **[04-networking](04-networking/)** (12%) - Services, Ingress, NetworkPolicy
- **[05-storage](05-storage/)** (8%) - PV, PVC, StorageClass
- **[06-config](06-config/)** (6%) - ConfigMaps and Secrets
- **[07-health](07-health/)** (7%) - Probes, PDBs, graceful termination
- **[08-security](08-security/)** (10%) - RBAC, Pod Security, IRSA
- **[09-scaling](09-scaling/)** (7%) - HPA, VPA, Cluster Autoscaler
- **[10-observability](10-observability/)** (10%) - Logging, debugging, monitoring
- **[11-packaging](11-packaging/)** (5%) - Helm, Kustomize, Argo CD
- **[mock-interview](mock-interview/)** - Final checkpoint

## Cost Note

This course is designed to be cost-effective:

- **Primary work**: Use kind (free, runs in Docker) or k3s on a single EC2 t3.medium instance (~$30/month if left running, or ~$0.05/hour)
- **EKS session**: Module 00 includes a short EKS walkthrough near the end. Spin up the cluster, complete the exercises (~2 hours), then tear it down immediately. Cost: ~$0.20 for compute + $0.20 for EKS control plane = **~$0.40 total**

**Recommendation**: Use kind locally or k3s on EC2 for 95% of the course. Only create EKS when you reach that specific section.

## Contributing

Found an issue or want to improve something? PRs are welcome!

## License

MIT - Built for Saran Alla (saranreddy2002@gmail.com)
