"""
arcade_routes.py — Real Kubernetes backend for DevOps Survival arcade game.

Sets up dedicated namespaces for each of the 8 original scenarios with real
broken K8s resources. The game terminal proxies kubectl commands to this backend
and gets back real cluster output.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from kubernetes import client as k8s, config as k8s_config
from kubernetes.client.rest import ApiException
import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/arcade")

# ── K8s client init ────────────────────────────────────────────────────────────
try:
    k8s_config.load_incluster_config()
    logger.info("Arcade: using in-cluster K8s config")
except Exception:
    try:
        k8s_config.load_kube_config()
        logger.info("Arcade: using kubeconfig")
    except Exception as e:
        logger.error(f"Arcade: K8s unavailable: {e}")

core_v1 = k8s.CoreV1Api()
apps_v1 = k8s.AppsV1Api()
networking_v1 = k8s.NetworkingV1Api()
autoscaling_v2 = k8s.AutoscalingV2Api()
rbac_v1 = k8s.RbacAuthorizationV1Api()

# ── Scenario namespace mapping ─────────────────────────────────────────────────
SCENARIO_NS = {
    "nginx_config":         "arcade-nginx-config",
    "crashloop":            "arcade-crashloop",
    "disk_space":           "arcade-disk-space",
    "cpu_spike":            "arcade-cpu-spike",
    "oom_crash":            "arcade-oom-crash",
    "docker_restart":       "arcade-docker-restart",
    "silent_deploy":        "arcade-silent-deploy",
    "disk_errors":          "arcade-disk-errors",
    # Batch 2
    "ssl_cert_expired":     "arcade-ssl-cert",
    "etcd_failure":         "arcade-etcd-failure",
    "node_notready":        "arcade-node-notready",
    "db_conn_pool":         "arcade-db-conn-pool",
    "log_rotation_fail":    "arcade-log-rotation",
    "network_policy_block": "arcade-network-policy",
    "resource_quota":       "arcade-resource-quota",
    "configmap_missing":    "arcade-configmap-missing",
    # Batch 3
    "secret_rotation":      "arcade-secret-rotation",
    "hpa_not_scaling":      "arcade-hpa-scaling",
    "pvc_pending":          "arcade-pvc-pending",
    "liveness_probe":       "arcade-liveness-probe",
    "rbac_denied":          "arcade-rbac-denied",
    "docker_registry":      "arcade-docker-registry",
    "dns_fail":             "arcade-dns-fail",
    "zombie_proc":          "arcade-zombie-proc",
}

ALLOWED_KUBECTL = {
    "get", "logs", "describe", "rollout", "delete",
    "scale", "patch", "create", "explain", "api-resources",
}

# ── Formatting helpers ─────────────────────────────────────────────────────────

def _age(ts) -> str:
    if not ts:
        return "<unknown>"
    now = datetime.now(timezone.utc)
    s = int((now - ts).total_seconds())
    if s < 60:    return f"{s}s"
    if s < 3600:  return f"{s//60}m{s%60}s"
    if s < 86400: return f"{s//3600}h{(s%3600)//60}m"
    return f"{s//86400}d{(s%86400)//3600}h"


def _pod_status(pod) -> str:
    if pod.status.reason:
        return pod.status.reason
    if pod.status.init_container_statuses:
        for ic in pod.status.init_container_statuses:
            if ic.state.waiting:
                return ic.state.waiting.reason or "Init:0/1"
            if ic.state.terminated and ic.state.terminated.exit_code != 0:
                return "Init:Error"
    if pod.status.container_statuses:
        for cs in pod.status.container_statuses:
            if cs.state.waiting:
                return cs.state.waiting.reason or "Pending"
            if cs.state.terminated:
                if cs.state.terminated.reason == "OOMKilled":
                    return "OOMKilled"
                if cs.state.terminated.exit_code != 0:
                    return "Error"
    return pod.status.phase or "Unknown"


def _pod_ready(pod) -> str:
    cs = pod.status.container_statuses or []
    total = len(pod.spec.containers) if pod.spec else 1
    return f"{sum(1 for c in cs if c.ready)}/{total}"


def _pod_restarts(pod) -> int:
    return sum(c.restart_count or 0 for c in (pod.status.container_statuses or []))


def _find_pod(name_prefix: str, ns: str):
    try:
        pods = core_v1.list_namespaced_pod(ns).items
    except ApiException:
        return None
    # Exact match first
    for p in pods:
        if p.metadata.name == name_prefix:
            return p
    # Prefix match — prefer pods that are NOT fully healthy (broken state is more informative)
    broken, healthy = [], []
    for p in pods:
        if not p.metadata.name.startswith(name_prefix):
            continue
        cs = p.status.container_statuses or []
        if all(c.ready for c in cs) and (p.status.phase or "").lower() == "running":
            healthy.append(p)
        else:
            broken.append(p)
    if broken:
        return broken[0]
    if healthy:
        return healthy[0]
    return None

# ── kubectl output formatters ──────────────────────────────────────────────────

def fmt_get_pods(ns: str) -> str:
    try:
        pods = core_v1.list_namespaced_pod(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not pods:
        return "No resources found."
    hdr = f"{'NAME':<52} {'READY':<7} {'STATUS':<22} {'RESTARTS':<10} AGE"
    rows = [hdr]
    for p in pods:
        rows.append(
            f"{p.metadata.name:<52} {_pod_ready(p):<7} {_pod_status(p):<22}"
            f" {str(_pod_restarts(p)):<10} {_age(p.metadata.creation_timestamp)}"
        )
    return "\n".join(rows)


def fmt_get_deployments(ns: str) -> str:
    try:
        deploys = apps_v1.list_namespaced_deployment(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not deploys:
        return "No resources found."
    hdr = f"{'NAME':<35} {'READY':<8} {'UP-TO-DATE':<12} {'AVAILABLE':<12} AGE"
    rows = [hdr]
    for d in deploys:
        desired = d.spec.replicas or 0
        ready   = d.status.ready_replicas or 0
        utd     = d.status.updated_replicas or 0
        avail   = d.status.available_replicas or 0
        rows.append(
            f"{d.metadata.name:<35} {f'{ready}/{desired}':<8} {str(utd):<12}"
            f" {str(avail):<12} {_age(d.metadata.creation_timestamp)}"
        )
    return "\n".join(rows)


def fmt_pod_logs(name_prefix: str, ns: str) -> str:
    pod = _find_pod(name_prefix, ns)
    if not pod:
        return f'Error from server (NotFound): pods "{name_prefix}" not found'
    container = pod.spec.containers[0].name if pod.spec.containers else None
    # Try previous (crash) logs first
    for prev in (True, False):
        try:
            logs = core_v1.read_namespaced_pod_log(
                pod.metadata.name, ns,
                container=container, previous=prev, tail_lines=80
            )
            if logs and logs.strip():
                return logs
        except Exception:
            pass
    return "(no logs available — pod may not have started yet)"


def fmt_describe_pod(name_prefix: str, ns: str) -> str:
    pod = _find_pod(name_prefix, ns)
    if not pod:
        return f'Error from server (NotFound): pods "{name_prefix}" not found'
    p = pod
    owner = (p.metadata.owner_references[0].name
             if p.metadata.owner_references else "<none>")
    lines = [
        f"Name:           {p.metadata.name}",
        f"Namespace:      {p.metadata.namespace}",
        f"Node:           {p.spec.node_name or '<none>'}",
        f"Status:         {p.status.phase or 'Unknown'}",
        f"IP:             {p.status.pod_ip or '<none>'}",
        f"Controlled By:  ReplicaSet/{owner}",
        "",
    ]

    # Init containers
    if p.spec.init_containers:
        lines.append("Init Containers:")
        for ic in p.spec.init_containers:
            lines.append(f"  {ic.name}:")
            lines.append(f"    Image:    {ic.image}")
            ics = next(
                (s for s in (p.status.init_container_statuses or []) if s.name == ic.name),
                None
            )
            if ics:
                if ics.state.terminated:
                    t = ics.state.terminated
                    lines += [
                        f"    State:    Terminated",
                        f"      Reason:    {t.reason or 'Completed'}",
                        f"      Exit Code: {t.exit_code}",
                    ]
                elif ics.state.running:
                    lines.append(f"    State:    Running")
                elif ics.state.waiting:
                    lines += [
                        f"    State:    Waiting",
                        f"      Reason:  {ics.state.waiting.reason}",
                    ]
        lines.append("")

    # Main containers
    lines.append("Containers:")
    for c in p.spec.containers:
        lines.append(f"  {c.name}:")
        lines.append(f"    Image:          {c.image}")
        cs = next(
            (s for s in (p.status.container_statuses or []) if s.name == c.name),
            None
        )
        if cs:
            if cs.state.waiting:
                lines += [
                    f"    State:          Waiting",
                    f"      Reason:       {cs.state.waiting.reason}",
                ]
            elif cs.state.running:
                lines.append(f"    State:          Running")
            elif cs.state.terminated:
                t = cs.state.terminated
                lines += [
                    f"    State:          Terminated",
                    f"      Reason:       {t.reason or 'Completed'}",
                    f"      Exit Code:    {t.exit_code}",
                ]
            if cs.last_state and cs.last_state.terminated:
                lt = cs.last_state.terminated
                lines += [
                    f"    Last State:     Terminated",
                    f"      Reason:       {lt.reason or 'Error'}",
                    f"      Exit Code:    {lt.exit_code}",
                    f"      Finished:     {_age(lt.finished_at)} ago",
                ]
            lines += [
                f"    Ready:          {cs.ready}",
                f"    Restart Count:  {cs.restart_count}",
            ]
        # Resource limits
        if c.resources:
            lim = c.resources.limits or {}
            req = c.resources.requests or {}
            if lim:
                lines.append("    Limits:")
                for k, v in lim.items():
                    lines.append(f"      {k}:  {v}")
            if req:
                lines.append("    Requests:")
                for k, v in req.items():
                    lines.append(f"      {k}:  {v}")
        # Security context
        if c.security_context and c.security_context.read_only_root_filesystem is not None:
            lines += [
                "    Security Context:",
                f"      readOnlyRootFilesystem: {str(c.security_context.read_only_root_filesystem).lower()}",
            ]
        lines.append("")

    # Conditions
    lines.append("Conditions:")
    lines.append(f"  {'Type':<22} Status")
    lines.append(f"  {'----':<22} ------")
    for cond in (p.status.conditions or []):
        lines.append(f"  {cond.type:<22} {cond.status}")
    lines.append("")

    # Events
    lines.append("Events:")
    try:
        events = core_v1.list_namespaced_event(
            ns, field_selector=f"involvedObject.name={p.metadata.name}"
        ).items
        if events:
            lines.append(f"  {'Type':<9} {'Reason':<20} {'Age':<8} {'From':<22} Message")
            lines.append(f"  {'----':<9} {'------':<20} {'---':<8} {'----':<22} -------")
            for ev in events[-10:]:
                etype  = ev.type or "Normal"
                reason = (ev.reason or "")[:18]
                age    = _age(ev.last_timestamp or ev.event_time)
                src    = ((ev.source.component or "") if ev.source else "")[:20]
                msg    = (ev.message or "")[:90]
                lines.append(f"  {etype:<9} {reason:<20} {age:<8} {src:<22} {msg}")
        else:
            lines.append("  <none>")
    except Exception:
        lines.append("  <events unavailable>")

    return "\n".join(lines)


def fmt_rollout_history(deploy_name: str, ns: str) -> str:
    try:
        d = apps_v1.read_namespaced_deployment(deploy_name, ns)
    except ApiException:
        return f'Error from server (NotFound): deployments.apps "{deploy_name}" not found'
    try:
        sel = ",".join(f"{k}={v}" for k, v in d.spec.selector.match_labels.items())
        rsets = apps_v1.list_namespaced_replica_set(ns, label_selector=sel).items
    except Exception:
        rsets = []

    rev_rsets = []
    for rs in rsets:
        ann = rs.metadata.annotations or {}
        rev = ann.get("deployment.kubernetes.io/revision")
        if rev:
            rev_rsets.append((int(rev), rs))
    rev_rsets.sort(key=lambda x: x[0])

    lines = [f"deployment.apps/{deploy_name}", f"{'REVISION':<12} CHANGE-CAUSE"]
    for rev, rs in rev_rsets:
        cause = (rs.metadata.annotations or {}).get("kubernetes.io/change-cause", "<none>")
        lines.append(f"{str(rev):<12} {cause}")
    return "\n".join(lines)


def fmt_get_nodes() -> str:
    try:
        nodes = core_v1.list_node().items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    hdr = f"{'NAME':<30} {'STATUS':<12} {'ROLES':<20} {'AGE':<10} VERSION"
    rows = [hdr]
    for n in nodes:
        ready = "Ready"
        for cond in (n.status.conditions or []):
            if cond.type == "Ready" and cond.status != "True":
                ready = "NotReady"
        roles = [k.replace("node-role.kubernetes.io/", "")
                 for k in (n.metadata.labels or {})
                 if k.startswith("node-role.kubernetes.io/")]
        role_str = ",".join(roles) if roles else "<none>"
        version = (n.status.node_info.kubelet_version
                   if n.status and n.status.node_info else "<unknown>")
        rows.append(
            f"{n.metadata.name:<30} {ready:<12} {role_str:<20}"
            f" {_age(n.metadata.creation_timestamp):<10} {version}"
        )
    return "\n".join(rows)


def fmt_get_networkpolicies(ns: str) -> str:
    try:
        policies = networking_v1.list_namespaced_network_policy(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not policies:
        return "No resources found."
    hdr = f"{'NAME':<35} {'POD-SELECTOR':<25} AGE"
    rows = [hdr]
    for p in policies:
        sel = p.spec.pod_selector
        if sel and sel.match_labels:
            selector = ",".join(f"{k}={v}" for k, v in sel.match_labels.items())
        else:
            selector = "<all pods>"
        rows.append(
            f"{p.metadata.name:<35} {selector:<25} {_age(p.metadata.creation_timestamp)}"
        )
    return "\n".join(rows)


def fmt_get_resourcequota(ns: str) -> str:
    try:
        quotas = core_v1.list_namespaced_resource_quota(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not quotas:
        return "No resources found."
    rows = []
    for q in quotas:
        hard = q.spec.hard or {}
        used = (q.status.used or {}) if q.status else {}
        rows.append(f"{'NAME':<20} {'AGE':<10} {'RESOURCE':<30} {'USED':<10} HARD")
        rows.append(f"{'----':<20} {'---':<10} {'--------':<30} {'----':<10} ----")
        first = True
        for resource in sorted(hard.keys()):
            name_col = q.metadata.name if first else ""
            age_col  = _age(q.metadata.creation_timestamp) if first else ""
            rows.append(
                f"{name_col:<20} {age_col:<10} {resource:<30}"
                f" {used.get(resource, '0'):<10} {hard[resource]}"
            )
            first = False
        rows.append("")
    return "\n".join(rows)


def fmt_get_hpa(ns: str) -> str:
    try:
        hpas = autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not hpas:
        return "No resources found."
    hdr = f"{'NAME':<30} {'REFERENCE':<35} {'TARGETS':<20} {'MINPODS':<9} {'MAXPODS':<9} {'REPLICAS':<10} AGE"
    lines = [hdr]
    for h in hpas:
        name = h.metadata.name
        ref  = f"{h.spec.scale_target_ref.kind}/{h.spec.scale_target_ref.name}"
        min_r = h.spec.min_replicas or 1
        max_r = h.spec.max_replicas
        replicas = (h.status.current_replicas or 0) if h.status else 0
        targets = "<unknown>/50%"
        if h.spec.metrics:
            m = h.spec.metrics[0]
            if m.type == "Resource" and m.resource:
                tgt = m.resource.target.average_utilization
                cur = "<unknown>"
                if h.status and h.status.current_metrics:
                    for cm in h.status.current_metrics:
                        if cm.type == "Resource" and cm.resource:
                            cur = f"{cm.resource.current.average_utilization}%"
                targets = f"{cur}/{tgt}%"
        age = _age(h.metadata.creation_timestamp)
        lines.append(f"{name:<30} {ref:<35} {targets:<20} {min_r:<9} {max_r:<9} {replicas:<10} {age}")
    return "\n".join(lines)


def fmt_get_pvc(ns: str) -> str:
    try:
        pvcs = core_v1.list_namespaced_persistent_volume_claim(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not pvcs:
        return "No resources found."
    hdr = f"{'NAME':<25} {'STATUS':<10} {'VOLUME':<20} {'CAPACITY':<10} {'ACCESS MODES':<14} {'STORAGECLASS':<20} AGE"
    lines = [hdr]
    for p in pvcs:
        name     = p.metadata.name
        status   = p.status.phase or "Unknown"
        volume   = p.spec.volume_name or ""
        capacity = (p.status.capacity or {}).get("storage", "") if p.status else ""
        access   = ",".join(p.spec.access_modes or [])
        sc       = p.spec.storage_class_name or ""
        age      = _age(p.metadata.creation_timestamp)
        lines.append(f"{name:<25} {status:<10} {volume:<20} {capacity:<10} {access:<14} {sc:<20} {age}")
    return "\n".join(lines)


def fmt_get_secrets(ns: str) -> str:
    try:
        secrets = core_v1.list_namespaced_secret(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not secrets:
        return "No resources found."
    hdr = f"{'NAME':<45} {'TYPE':<35} {'DATA':<6} AGE"
    lines = [hdr]
    for s in secrets:
        name  = s.metadata.name
        stype = s.type or "Opaque"
        data  = len(s.data) if s.data else 0
        age   = _age(s.metadata.creation_timestamp)
        lines.append(f"{name:<45} {stype:<35} {data:<6} {age}")
    return "\n".join(lines)


def fmt_get_clusterroles() -> str:
    try:
        roles = rbac_v1.list_cluster_role().items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    visible = [r for r in roles if not r.metadata.name.startswith("system:")]
    hdr = f"{'NAME':<50} CREATED AT"
    lines = [hdr]
    for r in visible[:25]:
        name = r.metadata.name
        age  = _age(r.metadata.creation_timestamp)
        lines.append(f"{name:<50} {age}")
    return "\n".join(lines)


def fmt_get_services(ns: str) -> str:
    try:
        svcs = core_v1.list_namespaced_service(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not svcs:
        return "No resources found."
    hdr = f"{'NAME':<30} {'TYPE':<12} {'CLUSTER-IP':<16} {'EXTERNAL-IP':<16} {'PORT(S)':<20} AGE"
    lines = [hdr]
    for s in svcs:
        name     = s.metadata.name
        stype    = s.spec.type or "ClusterIP"
        cip      = s.spec.cluster_ip or "<none>"
        ext_ip   = "<none>"
        if s.status and s.status.load_balancer and s.status.load_balancer.ingress:
            ext_ip = (s.status.load_balancer.ingress[0].ip
                      or s.status.load_balancer.ingress[0].hostname or "<pending>")
        ports = ",".join(
            f"{p.port}/{p.protocol}" + (f":{p.node_port}" if p.node_port else "")
            for p in (s.spec.ports or [])
        )
        age = _age(s.metadata.creation_timestamp)
        lines.append(f"{name:<30} {stype:<12} {cip:<16} {ext_ip:<16} {ports:<20} {age}")
    return "\n".join(lines)


def fmt_get_events(ns: str) -> str:
    try:
        events = core_v1.list_namespaced_event(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not events:
        return "No resources found."
    events.sort(
        key=lambda e: (e.last_timestamp or e.event_time
                       or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True
    )
    hdr = f"{'LAST SEEN':<12} {'TYPE':<10} {'REASON':<22} {'OBJECT':<40} MESSAGE"
    lines = [hdr]
    for ev in events[:25]:
        age    = _age(ev.last_timestamp or ev.event_time)
        etype  = ev.type or "Normal"
        reason = (ev.reason or "")[:20]
        obj    = (f"{ev.involved_object.kind}/{ev.involved_object.name}"
                  if ev.involved_object else "")[:38]
        msg    = (ev.message or "")[:80]
        lines.append(f"{age:<12} {etype:<10} {reason:<22} {obj:<40} {msg}")
    return "\n".join(lines)


def fmt_get_configmaps(ns: str) -> str:
    try:
        cms = core_v1.list_namespaced_config_map(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    cms = [cm for cm in cms if not cm.metadata.name.startswith("kube-")]
    if not cms:
        return "No resources found."
    hdr = f"{'NAME':<45} {'DATA':<6} AGE"
    lines = [hdr]
    for cm in cms:
        data = len(cm.data) if cm.data else 0
        age  = _age(cm.metadata.creation_timestamp)
        lines.append(f"{cm.metadata.name:<45} {data:<6} {age}")
    return "\n".join(lines)


def fmt_get_pods_wide(ns: str) -> str:
    try:
        pods = core_v1.list_namespaced_pod(ns).items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    if not pods:
        return "No resources found."
    hdr = f"{'NAME':<52} {'READY':<7} {'STATUS':<22} {'RESTARTS':<10} {'AGE':<8} {'IP':<16} NODE"
    rows = [hdr]
    for p in pods:
        ip   = p.status.pod_ip or "<none>"
        node = p.spec.node_name or "<none>"
        rows.append(
            f"{p.metadata.name:<52} {_pod_ready(p):<7} {_pod_status(p):<22}"
            f" {str(_pod_restarts(p)):<10} {_age(p.metadata.creation_timestamp):<8}"
            f" {ip:<16} {node}"
        )
    return "\n".join(rows)


def fmt_describe_deployment(name: str, ns: str) -> str:
    try:
        d = apps_v1.read_namespaced_deployment(name, ns)
    except ApiException:
        return f'Error from server (NotFound): deployments.apps "{name}" not found'
    spec   = d.spec
    status = d.status
    desired   = spec.replicas or 0
    ready     = status.ready_replicas or 0
    available = status.available_replicas or 0
    strategy  = spec.strategy.type if spec.strategy else "RollingUpdate"
    lines = [
        f"Name:               {d.metadata.name}",
        f"Namespace:          {d.metadata.namespace}",
        f"Replicas:           {desired} desired | {ready} ready | {available} available",
        f"Strategy:           {strategy}",
        "",
        "Pod Template:",
        "  Containers:",
    ]
    for c in (spec.template.spec.containers or []):
        lines.append(f"    {c.name}:")
        lines.append(f"      Image:    {c.image}")
        if c.resources:
            lim = c.resources.limits or {}
            req = c.resources.requests or {}
            if lim:
                lines.append("      Limits:   " + "  ".join(f"{k}={v}" for k, v in lim.items()))
            if req:
                lines.append("      Requests: " + "  ".join(f"{k}={v}" for k, v in req.items()))
        if c.liveness_probe:
            lines.append(f"      Liveness: configured")
        if c.readiness_probe:
            lines.append(f"      Readiness: configured")
    lines.append("")
    lines.append("Conditions:")
    for cond in (status.conditions or []):
        lines.append(f"  {cond.type:<25} {cond.status:<8} {cond.message or ''}")
    lines.append("")
    lines.append("Events:")
    try:
        events = core_v1.list_namespaced_event(
            ns, field_selector=f"involvedObject.name={d.metadata.name}"
        ).items
        if events:
            for ev in events[-5:]:
                age = _age(ev.last_timestamp or ev.event_time)
                lines.append(f"  {ev.type or 'Normal':<9} {(ev.reason or ''):<20} {age:<8} {ev.message or ''}")
        else:
            lines.append("  <none>")
    except Exception:
        lines.append("  <events unavailable>")
    return "\n".join(lines)


def fmt_describe_node(name: str) -> str:
    try:
        nodes = core_v1.list_node().items
    except ApiException as e:
        return f"Error from server: {e.reason}"
    node = None
    if name:
        for n in nodes:
            if n.metadata.name == name or n.metadata.name.startswith(name):
                node = n
                break
    if not node and nodes:
        node = nodes[0]
    if not node:
        return f'Error from server (NotFound): nodes "{name}" not found'
    n = node
    ready_status = "Unknown"
    for cond in (n.status.conditions or []):
        if cond.type == "Ready":
            ready_status = "True" if cond.status == "True" else "False"
    roles = [k.replace("node-role.kubernetes.io/", "") for k in (n.metadata.labels or {})
             if k.startswith("node-role.kubernetes.io/")]
    info = n.status.node_info if n.status and n.status.node_info else None
    lines = [
        f"Name:               {n.metadata.name}",
        f"Roles:              {','.join(roles) if roles else '<none>'}",
        f"Status:             {'Ready' if ready_status == 'True' else 'NotReady'}",
        f"Age:                {_age(n.metadata.creation_timestamp)}",
        "",
    ]
    if info:
        lines += [
            "System Info:",
            f"  OS Image:          {info.os_image or '<unknown>'}",
            f"  Kernel Version:    {info.kernel_version or '<unknown>'}",
            f"  Container Runtime: {info.container_runtime_version or '<unknown>'}",
            f"  Kubelet Version:   {info.kubelet_version or '<unknown>'}",
            "",
        ]
    if n.status and n.status.capacity:
        lines.append("Capacity:")
        for k, v in sorted(n.status.capacity.items()):
            lines.append(f"  {k}: {v}")
        lines.append("")
    lines.append("Conditions:")
    lines.append(f"  {'Type':<25} {'Status':<10} Reason")
    for cond in (n.status.conditions or []):
        lines.append(f"  {cond.type:<25} {cond.status:<10} {cond.reason or 'Unknown'}")
    return "\n".join(lines)


def fmt_rollout_status(deploy_name: str, ns: str) -> str:
    try:
        d = apps_v1.read_namespaced_deployment(deploy_name, ns)
    except ApiException:
        return f'Error from server (NotFound): deployments.apps "{deploy_name}" not found'
    desired   = d.spec.replicas or 0
    ready     = d.status.ready_replicas or 0
    available = d.status.available_replicas or 0
    if ready == desired and available == desired and desired > 0:
        return f'deployment "{deploy_name}" successfully rolled out'
    return (
        f'Waiting for deployment "{deploy_name}" rollout to finish: '
        f'{ready} of {desired} updated replicas are available...'
    )


def fmt_pod_logs_flags(name_prefix: str, ns: str,
                       previous: bool = False, tail: int = 80,
                       container: str = None) -> str:
    pod = _find_pod(name_prefix, ns)
    if not pod:
        return f'Error from server (NotFound): pods "{name_prefix}" not found'
    c_name = container or (pod.spec.containers[0].name if pod.spec.containers else None)
    modes = [True, False] if previous else [False, True]
    for prev in modes:
        try:
            logs = core_v1.read_namespaced_pod_log(
                pod.metadata.name, ns, container=c_name, previous=prev, tail_lines=tail
            )
            if logs and logs.strip():
                return logs
        except Exception:
            pass
    return "(no logs available — pod may not have started yet)"


_EXPLAIN_MAP = {
    "pod": (
        "KIND:     Pod\nVERSION:  v1\n\nDESCRIPTION:\n"
        "  Pod is a collection of containers that can run on a host.\n\n"
        "FIELDS:\n  apiVersion <string>\n  kind <string>\n  metadata <ObjectMeta>\n"
        "  spec <PodSpec>\n    containers <[]Container> -required-\n    volumes <[]Volume>\n"
        "    nodeSelector <map[string]string>\n    serviceAccountName <string>\n"
        "  status <PodStatus>"
    ),
    "deployment": (
        "KIND:     Deployment\nVERSION:  apps/v1\n\nDESCRIPTION:\n"
        "  Deployment enables declarative updates for Pods and ReplicaSets.\n\n"
        "FIELDS:\n  spec <DeploymentSpec> -required-\n"
        "    replicas <integer>  (default: 1)\n"
        "    selector <LabelSelector> -required-\n"
        "    template <PodTemplateSpec> -required-\n"
        "    strategy <DeploymentStrategy>\n      type: RollingUpdate | Recreate"
    ),
    "service": (
        "KIND:     Service\nVERSION:  v1\n\nDESCRIPTION:\n"
        "  Service is a named abstraction of software service.\n\n"
        "FIELDS:\n  spec <ServiceSpec>\n    ports <[]ServicePort>\n"
        "    selector <map[string]string>\n"
        "    type <string>  (ClusterIP|NodePort|LoadBalancer|ExternalName)"
    ),
    "configmap": (
        "KIND:     ConfigMap\nVERSION:  v1\n\nDESCRIPTION:\n"
        "  ConfigMap holds configuration data for pods to consume.\n\n"
        "FIELDS:\n  data <map[string]string>  (non-binary key/value pairs)\n"
        "  binaryData <map[string][]byte>  (binary data)"
    ),
    "secret": (
        "KIND:     Secret\nVERSION:  v1\n\nDESCRIPTION:\n"
        "  Secret holds secret data. Values are base64-encoded.\n\n"
        "FIELDS:\n  data <map[string][]byte>  (base64-encoded)\n"
        "  stringData <map[string]string>  (plain text, written at creation)\n"
        "  type <string>  (Opaque|kubernetes.io/dockerconfigjson|...)"
    ),
    "networkpolicy": (
        "KIND:     NetworkPolicy\nVERSION:  networking.k8s.io/v1\n\nDESCRIPTION:\n"
        "  Describes what network traffic is allowed for a set of pods.\n\n"
        "FIELDS:\n  spec <NetworkPolicySpec>\n"
        "    podSelector <LabelSelector> -required-\n"
        "    ingress <[]NetworkPolicyIngressRule>\n"
        "    egress <[]NetworkPolicyEgressRule>\n"
        "    policyTypes <[]string>  (Ingress|Egress)"
    ),
    "persistentvolumeclaim": (
        "KIND:     PersistentVolumeClaim\nVERSION:  v1\n\nFIELDS:\n"
        "  spec <PersistentVolumeClaimSpec>\n"
        "    accessModes <[]string>  (ReadWriteOnce|ReadOnlyMany|ReadWriteMany)\n"
        "    resources <ResourceRequirements>\n"
        "    storageClassName <string>"
    ),
    "horizontalpodautoscaler": (
        "KIND:     HorizontalPodAutoscaler\nVERSION:  autoscaling/v2\n\nFIELDS:\n"
        "  spec <HorizontalPodAutoscalerSpec>\n"
        "    scaleTargetRef <CrossVersionObjectReference> -required-\n"
        "    minReplicas <integer>\n    maxReplicas <integer> -required-\n"
        "    metrics <[]MetricSpec>"
    ),
}


def fmt_explain(resource: str) -> str:
    key = resource.lower().split(".")[0]
    aliases = {
        "pods": "pod", "deployments": "deployment", "services": "service",
        "svc": "service", "configmaps": "configmap", "cm": "configmap",
        "secrets": "secret", "netpol": "networkpolicy",
        "networkpolicies": "networkpolicy", "pvc": "persistentvolumeclaim",
        "persistentvolumeclaims": "persistentvolumeclaim",
        "hpa": "horizontalpodautoscaler",
        "horizontalpodautoscalers": "horizontalpodautoscaler",
    }
    key = aliases.get(key, key)
    if key in _EXPLAIN_MAP:
        return _EXPLAIN_MAP[key]
    return f"error: couldn't find resource for \"{resource}\"\nRun 'kubectl api-resources' to see available resource types."


def fmt_api_resources() -> str:
    return "\n".join([
        f"{'NAME':<40} {'SHORTNAMES':<15} {'APIVERSION':<28} {'NAMESPACED':<12} KIND",
        f"{'pods':<40} {'po':<15} {'v1':<28} {'true':<12} Pod",
        f"{'services':<40} {'svc':<15} {'v1':<28} {'true':<12} Service",
        f"{'configmaps':<40} {'cm':<15} {'v1':<28} {'true':<12} ConfigMap",
        f"{'secrets':<40} {'':<15} {'v1':<28} {'true':<12} Secret",
        f"{'events':<40} {'ev':<15} {'v1':<28} {'true':<12} Event",
        f"{'namespaces':<40} {'ns':<15} {'v1':<28} {'false':<12} Namespace",
        f"{'nodes':<40} {'no':<15} {'v1':<28} {'false':<12} Node",
        f"{'persistentvolumeclaims':<40} {'pvc':<15} {'v1':<28} {'true':<12} PersistentVolumeClaim",
        f"{'persistentvolumes':<40} {'pv':<15} {'v1':<28} {'false':<12} PersistentVolume",
        f"{'resourcequotas':<40} {'quota':<15} {'v1':<28} {'true':<12} ResourceQuota",
        f"{'serviceaccounts':<40} {'sa':<15} {'v1':<28} {'true':<12} ServiceAccount",
        f"{'deployments':<40} {'deploy':<15} {'apps/v1':<28} {'true':<12} Deployment",
        f"{'replicasets':<40} {'rs':<15} {'apps/v1':<28} {'true':<12} ReplicaSet",
        f"{'statefulsets':<40} {'sts':<15} {'apps/v1':<28} {'true':<12} StatefulSet",
        f"{'daemonsets':<40} {'ds':<15} {'apps/v1':<28} {'true':<12} DaemonSet",
        f"{'horizontalpodautoscalers':<40} {'hpa':<15} {'autoscaling/v2':<28} {'true':<12} HorizontalPodAutoscaler",
        f"{'networkpolicies':<40} {'netpol':<15} {'networking.k8s.io/v1':<28} {'true':<12} NetworkPolicy",
        f"{'ingresses':<40} {'ing':<15} {'networking.k8s.io/v1':<28} {'true':<12} Ingress",
        f"{'clusterroles':<40} {'':<15} {'rbac.authorization.k8s.io/v1':<28} {'false':<12} ClusterRole",
        f"{'clusterrolebindings':<40} {'':<15} {'rbac.authorization.k8s.io/v1':<28} {'false':<12} ClusterRoleBinding",
        f"{'storageclasses':<40} {'sc':<15} {'storage.k8s.io/v1':<28} {'false':<12} StorageClass",
    ])


def do_rollout_undo(deploy_name: str, ns: str) -> str:
    try:
        d = apps_v1.read_namespaced_deployment(deploy_name, ns)
    except ApiException:
        return f'Error from server (NotFound): deployments.apps "{deploy_name}" not found'

    ann = d.metadata.annotations or {}
    current_rev = int(ann.get("deployment.kubernetes.io/revision", "1"))
    target_rev  = current_rev - 1
    if target_rev < 1:
        return f'error: no previous revision for deployment "{deploy_name}"'

    try:
        sel = ",".join(f"{k}={v}" for k, v in d.spec.selector.match_labels.items())
        rsets = apps_v1.list_namespaced_replica_set(ns, label_selector=sel).items
    except Exception:
        return f"error: could not list ReplicaSets for deployment"

    target_rs = None
    for rs in rsets:
        rs_ann = rs.metadata.annotations or {}
        if rs_ann.get("deployment.kubernetes.io/revision") == str(target_rev):
            target_rs = rs
            break

    if not target_rs:
        return f'error: could not find revision {target_rev} for "{deploy_name}"'

    try:
        patch = {"spec": {"template": target_rs.spec.template.to_dict()}}
        apps_v1.patch_namespaced_deployment(deploy_name, ns, patch)
        return f"deployment.apps/{deploy_name} rolled back"
    except ApiException as e:
        return f"Error: {e.reason}"


def do_delete_pod(name_prefix: str, ns: str) -> str:
    pod = _find_pod(name_prefix, ns)
    if not pod:
        return f'Error from server (NotFound): pods "{name_prefix}" not found'
    try:
        core_v1.delete_namespaced_pod(pod.metadata.name, ns)
        return f'pod "{pod.metadata.name}" deleted'
    except ApiException as e:
        return f"Error: {e.reason}"

def do_scale(deploy_name: str, ns: str, replicas: int) -> str:
    try:
        apps_v1.patch_namespaced_deployment(deploy_name, ns, {"spec": {"replicas": replicas}})
        return f'deployment.apps "{deploy_name}" scaled'
    except ApiException as e:
        if e.status == 404:
            return f'Error from server (NotFound): deployments.apps "{deploy_name}" not found'
        return f"Error: {e.reason}"


def do_delete_networkpolicy(name: str, ns: str) -> str:
    try:
        networking_v1.delete_namespaced_network_policy(name, ns)
        return f'networkpolicy.networking.k8s.io "{name}" deleted'
    except ApiException as e:
        if e.status == 404:
            return f'Error from server (NotFound): networkpolicies.networking.k8s.io "{name}" not found'
        return f"Error: {e.reason}"


def do_rollout_restart(deploy_name: str, ns: str) -> str:
    try:
        patch = {"spec": {"template": {"metadata": {"annotations": {
            "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
        }}}}}
        apps_v1.patch_namespaced_deployment(deploy_name, ns, patch)
        return f"deployment.apps/{deploy_name} restarted"
    except ApiException as e:
        if e.status == 404:
            return f'Error from server (NotFound): deployments.apps "{deploy_name}" not found'
        return f"Error: {e.reason}"


def do_create_configmap(name: str, ns: str, data: dict) -> str:
    if not name:
        return "error: must specify configmap name"
    try:
        core_v1.create_namespaced_config_map(ns, k8s.V1ConfigMap(
            metadata=k8s.V1ObjectMeta(name=name, namespace=ns),
            data=data or {}
        ))
        return f"configmap/{name} created"
    except ApiException as e:
        if e.status == 409:
            return f'Error from server (AlreadyExists): configmaps "{name}" already exists'
        return f"Error: {e.reason}"


def do_create_secret(name: str, ns: str, data: dict) -> str:
    if not name:
        return "error: must specify secret name"
    import base64
    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in (data or {}).items()}
    try:
        core_v1.create_namespaced_secret(ns, k8s.V1Secret(
            metadata=k8s.V1ObjectMeta(name=name, namespace=ns),
            type="Opaque",
            data=encoded
        ))
        return f"secret/{name} created"
    except ApiException as e:
        if e.status == 409:
            return f'Error from server (AlreadyExists): secrets "{name}" already exists'
        return f"Error: {e.reason}"


def do_patch_deployment(name: str, ns: str, patch_str: str) -> str:
    try:
        import json as _json
        patch = _json.loads(patch_str)
    except (ValueError, TypeError):
        return f"error: invalid patch — must be valid JSON"
    try:
        apps_v1.patch_namespaced_deployment(name, ns, patch)
        return f"deployment.apps/{name} patched"
    except ApiException as e:
        if e.status == 404:
            return f'Error from server (NotFound): deployments.apps "{name}" not found'
        return f"Error: {e.reason}"


# ── Flag parser ────────────────────────────────────────────────────────────────

def _parse_flags(args: list) -> dict:
    """Extract kubectl flags, return {clean, fmt, tail, previous, container}."""
    clean, fmt, tail, previous, container = [], None, None, False, None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-o", "--output") and i + 1 < len(args):
            i += 1; fmt = args[i].lower()
        elif a.startswith("-o=") or a.startswith("--output="):
            fmt = a.split("=", 1)[1].lower()
        elif a.startswith("--tail="):
            try: tail = int(a.split("=", 1)[1])
            except ValueError: pass
        elif a == "--tail" and i + 1 < len(args):
            i += 1
            try: tail = int(args[i])
            except ValueError: pass
        elif a in ("--previous", "-p"):
            previous = True
        elif a == "--show-labels":
            fmt = "wide"
        elif a in ("-c", "--container") and i + 1 < len(args):
            i += 1; container = args[i]
        elif a.startswith("-c=") or a.startswith("--container="):
            container = a.split("=", 1)[1]
        elif a in ("-n", "--namespace", "-l", "--selector",
                   "--field-selector", "--sort-by") and i + 1 < len(args):
            i += 1  # consume value, ignore (namespace enforced by scenario)
        elif a in ("-A", "--all-namespaces", "--watch", "-w",
                   "--no-headers", "-f", "--follow"):
            pass  # accepted but ignored
        elif a.startswith("-"):
            pass  # unknown flag
        else:
            clean.append(a)
        i += 1
    return {"clean": clean, "fmt": fmt, "tail": tail,
            "previous": previous, "container": container}


# ── Main kubectl dispatcher ────────────────────────────────────────────────────

async def run_kubectl(args: list, ns: str) -> str:
    if not args:
        return (
            "kubectl controls the Kubernetes cluster manager.\n\n"
            "Usage: kubectl [command] [TYPE] [NAME] [flags]\n\n"
            "Basic commands:\n"
            "  get         Display one or many resources\n"
            "  describe    Show details of a specific resource\n"
            "  logs        Print the logs for a container in a pod\n"
            "  rollout     Manage the rollout of a resource\n"
            "  scale       Set a new size for a deployment\n"
            "  delete      Delete resources by name\n"
            "  create      Create a resource (configmap, secret)\n"
            "  patch       Update field(s) of a resource\n"
            "  explain     Documentation of resource specs\n"
            "  api-resources  List API resource types\n\n"
            "Use 'kubectl <command> --help' for more information."
        )

    sub = args[0].lower()
    rest = args[1:]

    if sub not in ALLOWED_KUBECTL:
        return (
            f'error: unknown command "{sub}" for "kubectl"\n'
            f"Run 'kubectl --help' for usage."
        )

    p = _parse_flags(rest)
    clean = p["clean"]
    fmt   = p["fmt"]

    # ── GET ──────────────────────────────────────────────────────────────────
    if sub == "get":
        res  = (clean[0] if clean else "").lower()
        name = clean[1] if len(clean) > 1 else ""

        if res in ("pods", "po", "pod"):
            return fmt_get_pods_wide(ns) if fmt == "wide" else fmt_get_pods(ns)

        if res in ("deployments", "deploy", "deployment"):
            return fmt_get_deployments(ns)

        if res in ("services", "svc", "service"):
            return fmt_get_services(ns)

        if res in ("events", "event", "ev"):
            return fmt_get_events(ns)

        if res in ("configmaps", "configmap", "cm"):
            return fmt_get_configmaps(ns)

        if res in ("nodes", "node", "no"):
            return fmt_get_nodes()

        if res in ("networkpolicies", "networkpolicy", "netpol"):
            return fmt_get_networkpolicies(ns)

        if res in ("resourcequota", "resourcequotas", "quota"):
            return fmt_get_resourcequota(ns)

        if res in ("hpa", "horizontalpodautoscaler", "horizontalpodautoscalers"):
            return fmt_get_hpa(ns)

        if res in ("pvc", "persistentvolumeclaim", "persistentvolumeclaims"):
            return fmt_get_pvc(ns)

        if res in ("secret", "secrets"):
            return fmt_get_secrets(ns)

        if res in ("clusterrole", "clusterroles"):
            return fmt_get_clusterroles()

        if res == "all":
            return (
                "=== pods ===\n" + fmt_get_pods(ns) +
                "\n\n=== deployments ===\n" + fmt_get_deployments(ns) +
                "\n\n=== services ===\n" + fmt_get_services(ns)
            )

        if not res:
            return "error: must specify the type of resource to get\nExample: kubectl get pods"

        return (
            f'error: the server doesn\'t have a resource type "{res}"\n'
            f"Run 'kubectl api-resources' to see available types."
        )

    # ── LOGS ──────────────────────────────────────────────────────────────────
    if sub == "logs":
        name = clean[0] if clean else ""
        if not name:
            return "error: pod name required\nUsage: kubectl logs <pod-name> [flags]"
        return fmt_pod_logs_flags(
            name, ns,
            previous=p["previous"],
            tail=p["tail"] or 80,
            container=p["container"]
        )

    # ── DESCRIBE ─────────────────────────────────────────────────────────────
    if sub == "describe":
        res  = (clean[0] if clean else "").lower()
        name = clean[1] if len(clean) > 1 else ""

        if res in ("pod", "pods", "po"):
            return fmt_describe_pod(name, ns)

        if res in ("deployment", "deploy", "deployments"):
            if not name:
                try:
                    deploys = apps_v1.list_namespaced_deployment(ns).items
                    if deploys:
                        name = deploys[0].metadata.name
                except Exception:
                    pass
            return fmt_describe_deployment(name, ns) if name else \
                "error: must specify deployment name"

        if res in ("node", "nodes", "no"):
            return fmt_describe_node(name)

        if res in ("service", "svc", "services"):
            return fmt_get_services(ns) + "\n(use kubectl get svc for service info)"

        if not res:
            return "error: must specify resource type\nUsage: kubectl describe <type> [name]"

        return f"error: describe '{res}' not supported — try: pod, deployment, node"

    # ── ROLLOUT ───────────────────────────────────────────────────────────────
    if sub == "rollout":
        action = (clean[0] if clean else "").lower()
        target = clean[1] if len(clean) > 1 else ""
        deploy_name = target.split("/")[-1] if "/" in target else target

        if action == "undo":
            if not deploy_name:
                return "error: must specify deployment\nUsage: kubectl rollout undo deploy/<name>"
            return do_rollout_undo(deploy_name, ns)
        if action == "history":
            if not deploy_name:
                return "error: must specify deployment\nUsage: kubectl rollout history deploy/<name>"
            return fmt_rollout_history(deploy_name, ns)
        if action == "status":
            if not deploy_name:
                return "error: must specify deployment\nUsage: kubectl rollout status deploy/<name>"
            return fmt_rollout_status(deploy_name, ns)
        if action == "restart":
            if not deploy_name:
                return "error: must specify deployment\nUsage: kubectl rollout restart deploy/<name>"
            return do_rollout_restart(deploy_name, ns)
        return (
            f"error: unknown rollout command: {action}\n"
            "Available: undo, history, status, restart"
        )

    # ── DELETE ────────────────────────────────────────────────────────────────
    if sub == "delete":
        res  = (clean[0] if clean else "").lower()
        name = clean[1] if len(clean) > 1 else ""

        if res in ("pod", "pods", "po"):
            if not name:
                return "error: must specify pod name\nUsage: kubectl delete pod <name>"
            return do_delete_pod(name, ns)

        if res in ("networkpolicy", "networkpolicies", "netpol"):
            if not name:
                return "error: must specify networkpolicy name\nUsage: kubectl delete networkpolicy <name>"
            return do_delete_networkpolicy(name, ns)

        if res in ("deployment", "deploy"):
            return "error: deleting deployments is not allowed — use 'kubectl rollout undo' to restore"

        if not res:
            return "error: must specify resource type\nUsage: kubectl delete <type> <name>"

        return f"error: delete '{res}' not supported in arcade mode"

    # ── SCALE ─────────────────────────────────────────────────────────────────
    if sub == "scale":
        target = clean[0] if clean else ""
        deploy_name = target.split("/")[-1] if "/" in target else target

        replicas = None
        for a in rest:
            if a.startswith("--replicas="):
                try: replicas = int(a.split("=", 1)[1])
                except ValueError: pass
        if replicas is None:
            return "error: required flag \"--replicas\" not set\nUsage: kubectl scale deployment/<name> --replicas=N"
        if not deploy_name:
            return "error: must specify deployment name\nUsage: kubectl scale deployment/<name> --replicas=N"
        return do_scale(deploy_name, ns, replicas)

    # ── PATCH ─────────────────────────────────────────────────────────────────
    if sub == "patch":
        res  = (clean[0] if clean else "").lower()
        name = clean[1] if len(clean) > 1 else ""

        patch_str = None
        for j, a in enumerate(rest):
            if a in ("-p", "--patch") and j + 1 < len(rest):
                patch_str = rest[j + 1]; break
            elif a.startswith("-p=") or a.startswith("--patch="):
                patch_str = a.split("=", 1)[1]; break

        if not patch_str:
            return "error: must specify --patch with JSON content\nUsage: kubectl patch deployment <name> -p '{...}'"

        if res in ("deployment", "deploy"):
            deploy_name = name.split("/")[-1] if "/" in name else name
            return do_patch_deployment(deploy_name, ns, patch_str)

        return f"error: patch for '{res}' not supported in arcade mode"

    # ── CREATE ────────────────────────────────────────────────────────────────
    if sub == "create":
        res = (clean[0] if clean else "").lower()

        if res == "configmap":
            name = clean[1] if len(clean) > 1 else ""
            data = {}
            for a in rest:
                if a.startswith("--from-literal="):
                    kv = a[len("--from-literal="):]
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        data[k] = v
            return do_create_configmap(name, ns, data)

        if res == "secret":
            sub2 = clean[1] if len(clean) > 1 else ""
            name = clean[2] if len(clean) > 2 else ""
            if sub2 != "generic":
                return "error: use 'kubectl create secret generic <name> --from-literal=key=val'"
            data = {}
            for a in rest:
                if a.startswith("--from-literal="):
                    kv = a[len("--from-literal="):]
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        data[k] = v
            return do_create_secret(name, ns, data)

        if not res:
            return "error: must specify resource type\nUsage: kubectl create configmap|secret <name>"

        return f"error: 'create {res}' not supported in arcade mode — try: configmap, secret"

    # ── EXPLAIN ───────────────────────────────────────────────────────────────
    if sub == "explain":
        resource = clean[0] if clean else ""
        if not resource:
            return "error: must specify resource type\nUsage: kubectl explain <resource>"
        return fmt_explain(resource)

    # ── API-RESOURCES ─────────────────────────────────────────────────────────
    if sub == "api-resources":
        return fmt_api_resources()

    return f'error: unknown command "{sub}" for "kubectl"'

# ── Namespace + deployment helpers ────────────────────────────────────────────

def _ensure_ns(ns: str):
    try:
        core_v1.read_namespace(ns)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespace(k8s.V1Namespace(
                metadata=k8s.V1ObjectMeta(name=ns)
            ))
        else:
            raise


def _upsert_deploy(deploy: k8s.V1Deployment, ns: str):
    name = deploy.metadata.name
    try:
        apps_v1.read_namespaced_deployment(name, ns)
        apps_v1.replace_namespaced_deployment(name, ns, deploy)
    except ApiException as e:
        if e.status == 404:
            apps_v1.create_namespaced_deployment(ns, deploy)
        else:
            raise


def _deploy(name: str, ns: str, containers: list,
            init_containers: list = None, volumes: list = None) -> k8s.V1Deployment:
    labels = {"app": name}
    spec_kwargs = {"containers": containers}
    if init_containers:
        spec_kwargs["init_containers"] = init_containers
    if volumes:
        spec_kwargs["volumes"] = volumes
    return k8s.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s.V1ObjectMeta(name=name, namespace=ns),
        spec=k8s.V1DeploymentSpec(
            replicas=1,
            selector=k8s.V1LabelSelector(match_labels=labels),
            template=k8s.V1PodTemplateSpec(
                metadata=k8s.V1ObjectMeta(labels=labels),
                spec=k8s.V1PodSpec(**spec_kwargs)
            )
        )
    )


def _res(cpu_lim="200m", mem_lim="128Mi", cpu_req="50m", mem_req="64Mi", extra_lim=None):
    lim = {"cpu": cpu_lim, "memory": mem_lim}
    if extra_lim:
        lim.update(extra_lim)
    return k8s.V1ResourceRequirements(
        limits=lim,
        requests={"cpu": cpu_req, "memory": mem_req}
    )

# ── Scenario setup functions ───────────────────────────────────────────────────

async def _setup_nginx_config(ns: str):
    """R1: nginx working. R2: init container writes bad config -> CrashLoopBackOff."""
    # R1 — plain nginx (working)
    r1 = _deploy("nginx-proxy", ns, [
        k8s.V1Container(name="nginx", image="nginx:alpine", resources=_res())
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # R2 — init writes broken nginx.conf (missing semicolons) into shared volume
    vol = k8s.V1Volume(name="cfg", empty_dir=k8s.V1EmptyDirVolumeSource())
    init_c = k8s.V1Container(
        name="config-writer",
        image="busybox:1.36",
        command=["sh", "-c",
            "printf 'worker_processes auto;\\nevents { worker_connections 768 }\\n"
            "http {\\n  server {\\n    listen 80\\n"
            "    server_name localhost;\\n"
            "    location / { return 200; }\\n"
            "  }\\n}\\n' > /etc/nginx/nginx.conf"
        ],
        volume_mounts=[k8s.V1VolumeMount(name="cfg", mount_path="/etc/nginx")]
    )
    main_c = k8s.V1Container(
        name="nginx",
        image="nginx:alpine",
        resources=_res(),
        volume_mounts=[k8s.V1VolumeMount(name="cfg", mount_path="/etc/nginx")]
    )
    r2 = _deploy("nginx-proxy", ns, [main_c], init_containers=[init_c], volumes=[vol])
    _upsert_deploy(r2, ns)


async def _setup_crashloop(ns: str):
    """R1: api pod sleeps. R2: api pod crashes on startup."""
    r1 = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c", "echo 'api-server v1.2.0 started' && sleep 3600"],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'api-server v1.3.0-beta starting...' && "
                "echo 'INFO:  Loading configuration from env...' && "
                "echo 'ERROR: Failed to connect to postgres://db:5432/prod: connection refused' && "
                "echo 'FATAL: Missing required environment variable DB_HOST' && "
                "echo 'panic: runtime error: nil pointer dereference' && "
                "echo 'goroutine 1 [running]:' && "
                "echo 'main.connectDB(0xc0000b4000)' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_disk_space(ns: str):
    """R1: data-logger works fine. R2: fills ephemeral storage -> Evicted."""
    r1 = _deploy("data-logger", ns, [
        k8s.V1Container(
            name="data-logger", image="busybox:1.36",
            command=["sh", "-c", "echo 'data-logger v1.0 started' && sleep 3600"],
            resources=_res("100m", "64Mi", "50m", "32Mi",
                          extra_lim={"ephemeral-storage": "200Mi"})
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("data-logger", ns, [
        k8s.V1Container(
            name="data-logger", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'data-logger v2.0 started — writing metric buffers...' && "
                "i=0 && while true; do "
                "  dd if=/dev/urandom bs=512K count=1 >> /tmp/metrics-$i.log 2>/dev/null; "
                "  i=$((i+1)); "
                "done"
            ],
            resources=_res("100m", "64Mi", "50m", "32Mi",
                          extra_lim={"ephemeral-storage": "2Mi"})
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_cpu_spike(ns: str):
    """R1: stress-worker sleeps. R2: tight CPU limit + busy loop."""
    r1 = _deploy("stress-worker", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c", "echo 'worker v1.0 started' && sleep 3600"],
            resources=_res("500m", "128Mi", "100m", "64Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("stress-worker", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'worker v2.0 started — processing queue...' && "
                "while true; do :; done"
            ],
            resources=_res("50m", "128Mi", "50m", "64Mi")  # dangerously low CPU limit
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_oom_crash(ns: str):
    """R1: transformer sleeps. R2: allocates 200 MB with 32 Mi limit -> OOMKilled."""
    r1 = _deploy("data-transformer", ns, [
        k8s.V1Container(
            name="transformer", image="busybox:1.36",
            command=["sh", "-c", "echo 'DataTransformer v1.2.0 started' && sleep 3600"],
            resources=_res("200m", "256Mi", "50m", "128Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # python:3.11-alpine allocates 200 MB to guarantee OOMKill at 32 Mi limit
    r2 = _deploy("data-transformer", ns, [
        k8s.V1Container(
            name="transformer", image="python:3.11-alpine",
            command=["python3", "-c",
                "import sys\n"
                "print('DataTransformer v1.3.0 starting...')\n"
                "print('INFO: Loading 200MB dataset into processing buffer...')\n"
                "sys.stdout.flush()\n"
                "x = bytearray(200 * 1024 * 1024)\n"
                "print('Done')\n"
                "import time; time.sleep(3600)\n"
            ],
            resources=_res("200m", "32Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_docker_restart(ns: str):
    """R1: nginx as payment-service. R2: nonexistent image -> ImagePullBackOff."""
    r1 = _deploy("payment-service", ns, [
        k8s.V1Container(
            name="payment", image="nginx:alpine",
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("payment-service", ns, [
        k8s.V1Container(
            name="payment",
            image="registry.example.internal/payment-service:v2.0.0-bad-20240115",
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_silent_deploy(ns: str):
    """R1: nginx with correct readiness probe. R2: wrong probe path -> 0/1 Ready."""
    r1 = _deploy("frontend", ns, [
        k8s.V1Container(
            name="frontend", image="nginx:alpine",
            readiness_probe=k8s.V1Probe(
                http_get=k8s.V1HTTPGetAction(path="/", port=80),
                initial_delay_seconds=3, period_seconds=5
            ),
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("frontend", ns, [
        k8s.V1Container(
            name="frontend", image="nginx:alpine",
            readiness_probe=k8s.V1Probe(
                http_get=k8s.V1HTTPGetAction(path="/healthz", port=80),
                initial_delay_seconds=3, period_seconds=5, failure_threshold=3
            ),
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_disk_errors(ns: str):
    """R1: processor works. R2: readOnlyRootFilesystem=true -> write fails -> CrashLoop."""
    r1 = _deploy("syslog-processor", ns, [
        k8s.V1Container(
            name="processor", image="busybox:1.36",
            command=["sh", "-c", "echo 'syslog-processor v1.0 started' && sleep 3600"],
            security_context=k8s.V1SecurityContext(read_only_root_filesystem=False),
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("syslog-processor", ns, [
        k8s.V1Container(
            name="processor", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'syslog-processor v2.0 starting...' && "
                "echo 'Initializing log pipeline...' && "
                "touch /tmp/app.log && "
                "echo 'pipeline ready' >> /tmp/app.log && "
                "sleep 3600"
            ],
            security_context=k8s.V1SecurityContext(read_only_root_filesystem=True),
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r2, ns)

async def _setup_ssl_cert(ns: str):
    """R1: nginx running. R2: SSL cert load failure -> CrashLoopBackOff."""
    r1 = _deploy("nginx-proxy", ns, [
        k8s.V1Container(name="nginx", image="nginx:alpine", resources=_res())
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("nginx-proxy", ns, [
        k8s.V1Container(
            name="nginx", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'nginx: [notice] using the epoll event method' && "
                "echo 'nginx: [notice] nginx/1.25.3' && "
                "echo 'nginx/1.25.3: SSL_CTX_use_certificate_file() failed' && "
                "echo '  error:0200100D:system library:fopen:Permission denied' && "
                "echo '  error:20074002:BIO routines:file_ctrl:system lib' && "
                "echo '  error:140DC002:SSL routines:use_certificate_chain_file:system lib' && "
                "echo 'nginx: [emerg] SSL_CTX_use_certificate_file(\"/etc/ssl/certs/server.crt\") failed' && "
                "echo 'nginx: configuration file /etc/nginx/nginx.conf test failed' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_etcd_failure(ns: str):
    """R1: etcd-sim running. R2: crashes with leader election failure."""
    r1 = _deploy("etcd-sim", ns, [
        k8s.V1Container(
            name="etcd", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'etcd v3.5.9 started, leader elected on member 8c39e9e80a21cbcc' && "
                "sleep 3600"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("etcd-sim", ns, [
        k8s.V1Container(
            name="etcd", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'etcd v3.5.9 starting...' && "
                "echo 'INFO: etcd Version: 3.5.9' && "
                "echo 'INFO: Git SHA: Not provided (using release build)' && "
                "echo 'INFO: Go Version: go1.20.7' && "
                "echo 'WARNING: etcd configuration is not provided; falling back to default configuration' && "
                "echo 'ERROR: failed to find local member in cluster peers: {ClusterID:8c39e9e80a21cbcc}: member not found' && "
                "echo 'ERROR: member 8c39e9e80a21cbcc failed to find cluster peers' && "
                "echo 'CRITICAL: leader election timed out after 5s — failed to reach quorum' && "
                "echo 'CRITICAL: cluster degraded. No new writes accepted.' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_node_notready(ns: str):
    """R1: api-deployment running. R2: impossible CPU request -> Pending."""
    r1 = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c", "echo 'api-server v2.1.0 started' && sleep 3600"],
            resources=_res("200m", "128Mi", "50m", "64Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # Request 100 CPU cores — impossible to schedule on any node
    r2 = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c", "echo 'api-server v2.2.0 started' && sleep 3600"],
            resources=k8s.V1ResourceRequirements(
                requests={"cpu": "100", "memory": "128Mi"},
                limits={"cpu": "100", "memory": "256Mi"}
            )
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_db_conn_pool(ns: str):
    """R1: api-service sleeping. R2: crashes with DB connection pool errors."""
    r1 = _deploy("api-service", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c", "echo 'api-service v3.1.0 started' && sleep 3600"],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("api-service", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'api-service v3.2.0 starting...' && "
                "echo 'INFO: Connecting to postgres://prod-db:5432/appdb' && "
                "echo 'INFO: Connection pool initialized (size: 100/100)' && "
                "echo 'WARN: All connections busy (100/100) — request queued' && "
                "echo 'WARN: Waiting for available connection... attempt 1/3' && "
                "echo 'WARN: Waiting for available connection... attempt 2/3' && "
                "echo 'WARN: Waiting for available connection... attempt 3/3' && "
                "echo 'ERROR: connection pool exhausted after 30s timeout' && "
                "echo 'ERROR: pq: sorry, too many clients already (max_connections=100)' && "
                "echo 'FATAL: failed to acquire database connection: context deadline exceeded' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_log_rotation(ns: str):
    """R1: log-worker sleeping. R2: crashes with log rotation failure errors."""
    r1 = _deploy("log-worker", ns, [
        k8s.V1Container(
            name="logger", image="busybox:1.36",
            command=["sh", "-c", "echo 'log-worker v1.0 started' && sleep 3600"],
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("log-worker", ns, [
        k8s.V1Container(
            name="logger", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'log-worker v2.0 started...' && "
                "echo 'INFO: logrotate /etc/logrotate.d/app' && "
                "echo 'WARNING: logrotate state file /var/lib/logrotate/status is read-only' && "
                "echo 'ERROR: logrotate postrotate script failed with exit code 127' && "
                "echo 'ERROR: failed to create /var/log/app.log.1.gz: No space left on device' && "
                "echo 'FATAL: disk usage at 97%: /var/log consuming 38.2G of 40G' && "
                "echo 'FATAL: log rotation aborted. Manual intervention required.' && "
                "exit 1"
            ],
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_network_policy(ns: str):
    """R1: payment-service working. R2: crashes + NetworkPolicy blocks egress."""
    r1 = _deploy("payment-service", ns, [
        k8s.V1Container(
            name="payment", image="busybox:1.36",
            command=["sh", "-c", "echo 'payment-service v1.4.0 started' && sleep 3600"],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # Create NetworkPolicy blocking all egress from payment-service pods
    policy = k8s.V1NetworkPolicy(
        metadata=k8s.V1ObjectMeta(name="block-payment-egress", namespace=ns),
        spec=k8s.V1NetworkPolicySpec(
            pod_selector=k8s.V1LabelSelector(match_labels={"app": "payment-service"}),
            policy_types=["Egress"],
            egress=[]  # empty = deny all egress
        )
    )
    try:
        networking_v1.read_namespaced_network_policy("block-payment-egress", ns)
        networking_v1.replace_namespaced_network_policy("block-payment-egress", ns, policy)
    except ApiException as e:
        if e.status == 404:
            networking_v1.create_namespaced_network_policy(ns, policy)
        else:
            logger.error(f"NetworkPolicy error: {e}")

    r2 = _deploy("payment-service", ns, [
        k8s.V1Container(
            name="payment", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'payment-service v1.5.0 starting...' && "
                "echo 'INFO: Connecting to postgres://prod-db:5432/payments' && "
                "sleep 2 && "
                "echo 'ERROR: dial tcp 10.96.0.5:5432: i/o timeout (NetworkPolicy blocking egress)' && "
                "echo 'ERROR: connection to database failed after 5 retries' && "
                "echo 'FATAL: NetworkPolicy block-payment-egress is denying all egress on port 5432' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_resource_quota(ns: str):
    """R1: 1 worker replica fits quota. R2: 5 replicas -> quota blocks pod creation."""
    quota = k8s.V1ResourceQuota(
        metadata=k8s.V1ObjectMeta(name="staging-quota", namespace=ns),
        spec=k8s.V1ResourceQuotaSpec(
            hard={"pods": "3", "requests.cpu": "500m",
                  "limits.cpu": "1500m", "requests.memory": "384Mi"}
        )
    )
    try:
        core_v1.read_namespaced_resource_quota("staging-quota", ns)
        core_v1.replace_namespaced_resource_quota("staging-quota", ns, quota)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_resource_quota(ns, quota)
        else:
            logger.error(f"ResourceQuota error: {e}")

    # R1: 1 replica — fits within quota (pods: 1/3)
    r1 = _deploy("worker-job", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c", "echo 'worker-job v1.0 started' && sleep 3600"],
            resources=_res("200m", "128Mi", "100m", "64Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # R2: 5 replicas — quota allows only 3 pods total, so 2+ will be rejected
    r2 = _deploy("worker-job", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c", "echo 'worker-job v2.0 started' && sleep 3600"],
            resources=_res("200m", "128Mi", "100m", "64Mi")
        )
    ])
    r2.spec.replicas = 5
    _upsert_deploy(r2, ns)


async def _setup_configmap_missing(ns: str):
    """R1: worker-service with worker-config. R2: references missing worker-config-v2."""
    # Create ConfigMap for R1
    cm = k8s.V1ConfigMap(
        metadata=k8s.V1ObjectMeta(name="worker-config", namespace=ns),
        data={"DB_HOST": "postgres:5432", "LOG_LEVEL": "info", "MAX_WORKERS": "4"}
    )
    try:
        core_v1.read_namespaced_config_map("worker-config", ns)
        core_v1.replace_namespaced_config_map("worker-config", ns, cm)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_config_map(ns, cm)

    # R1: works fine with worker-config
    r1 = _deploy("worker-service", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c", "echo 'worker-service v2.0 started' && sleep 3600"],
            env_from=[k8s.V1EnvFromSource(
                config_map_ref=k8s.V1ConfigMapEnvSource(name="worker-config")
            )],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    # R2: references worker-config-v2 which does not exist -> CreateContainerConfigError
    r2 = _deploy("worker-service", ns, [
        k8s.V1Container(
            name="worker", image="busybox:1.36",
            command=["sh", "-c", "echo 'worker-service v2.1 started' && sleep 3600"],
            env_from=[k8s.V1EnvFromSource(
                config_map_ref=k8s.V1ConfigMapEnvSource(name="worker-config-v2")
            )],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_secret_rotation(ns: str):
    """R1: auth-service uses auth-secret (exists). R2: references auth-secret-v2 (missing) → CreateContainerConfigError."""
    secret = k8s.V1Secret(
        metadata=k8s.V1ObjectMeta(name="auth-secret", namespace=ns),
        string_data={"API_KEY": "sk-prod-abc123", "DB_PASSWORD": "secret123"}
    )
    try:
        core_v1.read_namespaced_secret("auth-secret", ns)
        core_v1.replace_namespaced_secret("auth-secret", ns, secret)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_secret(ns, secret)

    r1 = _deploy("auth-service", ns, [
        k8s.V1Container(
            name="auth", image="busybox:1.36",
            command=["sh", "-c", "echo 'auth-service v2.0.0 started — API key loaded from auth-secret' && sleep 3600"],
            env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="auth-secret"))],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("auth-service", ns, [
        k8s.V1Container(
            name="auth", image="busybox:1.36",
            command=["sh", "-c", "echo 'auth-service v2.1.0 started' && sleep 3600"],
            env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="auth-secret-v2"))],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_hpa_not_scaling(ns: str):
    """api-deployment with HPA. metrics-server unavailable → TARGETS shows <unknown>/50%."""
    r1 = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="busybox:1.36",
            command=["sh", "-c", "echo 'api-service v1.4.0 started' && sleep 3600"],
            resources=_res("200m", "128Mi", "100m", "64Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    hpa = k8s.V2HorizontalPodAutoscaler(
        metadata=k8s.V1ObjectMeta(name="api-deployment-hpa", namespace=ns),
        spec=k8s.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=k8s.V2CrossVersionObjectReference(
                api_version="apps/v1", kind="Deployment", name="api-deployment"
            ),
            min_replicas=1,
            max_replicas=10,
            metrics=[k8s.V2MetricSpec(
                type="Resource",
                resource=k8s.V2ResourceMetricSource(
                    name="cpu",
                    target=k8s.V2MetricTarget(type="Utilization", average_utilization=50)
                )
            )]
        )
    )
    try:
        autoscaling_v2.read_namespaced_horizontal_pod_autoscaler("api-deployment-hpa", ns)
        autoscaling_v2.replace_namespaced_horizontal_pod_autoscaler("api-deployment-hpa", ns, hpa)
    except ApiException as e:
        if e.status == 404:
            autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(ns, hpa)
        else:
            logger.error(f"HPA error: {e}")


async def _setup_pvc_pending(ns: str):
    """PVC with non-existent StorageClass → Pending. postgres pod mounts it → pod stays Pending."""
    pvc = k8s.V1PersistentVolumeClaim(
        metadata=k8s.V1ObjectMeta(name="postgres-data", namespace=ns),
        spec=k8s.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            storage_class_name="fast-ssd",
            resources=k8s.V1ResourceRequirements(requests={"storage": "10Gi"})
        )
    )
    try:
        core_v1.read_namespaced_persistent_volume_claim("postgres-data", ns)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_persistent_volume_claim(ns, pvc)

    postgres = _deploy("postgres", ns, [
        k8s.V1Container(
            name="postgres", image="busybox:1.36",
            command=["sh", "-c", "echo 'postgres started' && sleep 3600"],
            volume_mounts=[k8s.V1VolumeMount(name="data", mount_path="/var/lib/postgresql/data")],
            resources=_res()
        )
    ])
    postgres.spec.template.spec.volumes = [
        k8s.V1Volume(
            name="data",
            persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name="postgres-data")
        )
    ]
    _upsert_deploy(postgres, ns)


async def _setup_liveness_probe(ns: str):
    """R1: cache-service no probe (healthy). R2: liveness exec /bin/false → probe always fails → pod restarts."""
    r1 = _deploy("cache-service", ns, [
        k8s.V1Container(
            name="cache", image="busybox:1.36",
            command=["sh", "-c", "echo 'cache-service v3.1.0 started' && sleep 3600"],
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("cache-service", ns, [
        k8s.V1Container(
            name="cache", image="busybox:1.36",
            command=["sh", "-c", "echo 'cache-service v3.2.0 started' && sleep 3600"],
            liveness_probe=k8s.V1Probe(
                _exec=k8s.V1ExecAction(command=["/bin/false"]),
                initial_delay_seconds=5,
                period_seconds=10,
                failure_threshold=1
            ),
            resources=_res("100m", "64Mi", "50m", "32Mi")
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_rbac_denied(ns: str):
    """R1: ci-runner healthy. R2: crashes immediately with RBAC forbidden error logs → CrashLoopBackOff."""
    r1 = _deploy("ci-runner", ns, [
        k8s.V1Container(
            name="runner", image="busybox:1.36",
            command=["sh", "-c", "echo 'ci-runner v1.2 started' && sleep 3600"],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("ci-runner", ns, [
        k8s.V1Container(
            name="runner", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'ci-runner v1.3 started' && "
                "echo 'INFO: Connecting to Kubernetes API server...' && "
                "echo 'INFO: Listing pods in namespace staging...' && "
                "echo 'ERROR: pods is forbidden: User \"system:serviceaccount:staging:ci-runner\" "
                "cannot list resource \"pods\" in API group \"\" in the namespace \"staging\"' && "
                "echo 'ERROR: deployments is forbidden: User \"system:serviceaccount:staging:ci-runner\" "
                "cannot create resource \"deployments\" in API group \"apps\" in the namespace \"staging\"' && "
                "echo 'FATAL: Insufficient RBAC permissions — ClusterRole ci-runner-role is missing verbs: list, create' && "
                "echo 'FATAL: Pipeline aborted.' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_docker_registry(ns: str):
    """Deployment with non-existent registry image → ImagePullBackOff on all pods."""
    broken = _deploy("api-deployment", ns, [
        k8s.V1Container(
            name="api", image="registry.example.com/api-service:v1.2.0",
            image_pull_policy="Always",
            command=["sh", "-c", "echo 'api started' && sleep 3600"],
            resources=_res()
        )
    ])
    broken.spec.replicas = 2
    _upsert_deploy(broken, ns)


async def _setup_dns_fail(ns: str):
    """R1: coredns-sim healthy. R2: crashes with Corefile parse errors → CrashLoopBackOff."""
    r1 = _deploy("coredns-sim", ns, [
        k8s.V1Container(
            name="coredns", image="busybox:1.36",
            command=["sh", "-c", "echo 'CoreDNS v1.10.1 started — listening on :53' && sleep 3600"],
            resources=_res("100m", "128Mi", "50m", "64Mi")
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("coredns-sim", ns, [
        k8s.V1Container(
            name="coredns", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'CoreDNS v1.10.1 started' && "
                "echo 'INFO: Parsing Corefile configuration...' && "
                "echo 'ERROR: Corefile parse error: unknown plugin \"forward\" at line 8' && "
                "echo 'ERROR: plugin/forward: syntax error in upstream address: \"8.8.8.8:53:443\"' && "
                "echo 'ERROR: failed to initialize plugin chain: invalid Corefile' && "
                "echo 'FATAL: Failed to start CoreDNS: Corefile validation failed' && "
                "echo 'FATAL: DNS resolution will fail for all pods in cluster' && "
                "exit 1"
            ],
            resources=_res("100m", "128Mi", "50m", "64Mi")
        )
    ])
    _upsert_deploy(r2, ns)


async def _setup_zombie_proc(ns: str):
    """R1: zombie-monitor healthy. R2: prints zombie process alerts then crashes → CrashLoopBackOff."""
    r1 = _deploy("zombie-monitor", ns, [
        k8s.V1Container(
            name="monitor", image="busybox:1.36",
            command=["sh", "-c", "echo 'zombie-monitor v1.0.0 started — PID reaper enabled' && sleep 3600"],
            resources=_res()
        )
    ])
    _upsert_deploy(r1, ns)
    await asyncio.sleep(1)

    r2 = _deploy("zombie-monitor", ns, [
        k8s.V1Container(
            name="monitor", image="busybox:1.36",
            command=["sh", "-c",
                "echo 'zombie-monitor v1.1.0 started' && "
                "echo 'WARN: 47 zombie processes detected (Z state) on prod-node-01' && "
                "echo 'WARN: 156 zombie processes detected (Z state) on prod-node-01' && "
                "echo 'WARN: 203 zombie processes detected (Z state) on prod-node-01' && "
                "echo 'ERROR: PID namespace near exhaustion — 203/256 PIDs consumed' && "
                "echo 'ERROR: fork() failed: Resource temporarily unavailable (EAGAIN)' && "
                "echo 'ERROR: Parent PID 7825 not reaping children — systemd misconfiguration detected' && "
                "echo 'FATAL: Unable to spawn new processes — system instability imminent' && "
                "exit 1"
            ],
            resources=_res()
        )
    ])
    _upsert_deploy(r2, ns)


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(msg: str, pct: int) -> str:
    return f"data: {json.dumps({'msg': msg, 'pct': pct})}\n\n"

# ── Endpoints ─────────────────────────────────────────────────────────────────

SCENARIO_SETUP = [
    ("nginx_config",         "arcade-nginx-config",   "NGINX config scenario",           _setup_nginx_config),
    ("crashloop",            "arcade-crashloop",      "API crash-loop scenario",          _setup_crashloop),
    ("disk_space",           "arcade-disk-space",     "Ephemeral storage scenario",       _setup_disk_space),
    ("cpu_spike",            "arcade-cpu-spike",      "CPU throttling scenario",          _setup_cpu_spike),
    ("oom_crash",            "arcade-oom-crash",      "OOM crash scenario",               _setup_oom_crash),
    ("docker_restart",       "arcade-docker-restart", "ImagePullBackOff scenario",        _setup_docker_restart),
    ("silent_deploy",        "arcade-silent-deploy",  "Silent deploy scenario",           _setup_silent_deploy),
    ("disk_errors",          "arcade-disk-errors",    "Filesystem errors scenario",       _setup_disk_errors),
    ("ssl_cert_expired",     "arcade-ssl-cert",       "SSL cert expiry scenario",         _setup_ssl_cert),
    ("etcd_failure",         "arcade-etcd-failure",   "etcd failure scenario",            _setup_etcd_failure),
    ("node_notready",        "arcade-node-notready",  "Node unschedulable scenario",      _setup_node_notready),
    ("db_conn_pool",         "arcade-db-conn-pool",   "DB connection pool scenario",      _setup_db_conn_pool),
    ("log_rotation_fail",    "arcade-log-rotation",   "Log rotation failure scenario",    _setup_log_rotation),
    ("network_policy_block", "arcade-network-policy", "NetworkPolicy block scenario",     _setup_network_policy),
    ("resource_quota",       "arcade-resource-quota", "ResourceQuota exceeded scenario",  _setup_resource_quota),
    ("configmap_missing",    "arcade-configmap-missing", "Missing ConfigMap scenario",      _setup_configmap_missing),
    ("secret_rotation",      "arcade-secret-rotation",   "Secret rotation scenario",        _setup_secret_rotation),
    ("hpa_not_scaling",      "arcade-hpa-scaling",        "HPA not scaling scenario",        _setup_hpa_not_scaling),
    ("pvc_pending",          "arcade-pvc-pending",        "PVC stuck pending scenario",      _setup_pvc_pending),
    ("liveness_probe",       "arcade-liveness-probe",     "Liveness probe failure scenario", _setup_liveness_probe),
    ("rbac_denied",          "arcade-rbac-denied",        "RBAC denied scenario",            _setup_rbac_denied),
    ("docker_registry",      "arcade-docker-registry",    "Docker registry auth scenario",   _setup_docker_registry),
    ("dns_fail",             "arcade-dns-fail",           "DNS resolution failure scenario", _setup_dns_fail),
    ("zombie_proc",          "arcade-zombie-proc",        "Zombie process exhaustion scenario", _setup_zombie_proc),
]


@router.post("/setup")
async def setup_scenarios():
    """Stream SSE progress while setting up all 24 scenario namespaces."""
    async def generate():
        yield _sse("Connecting to Kubernetes cluster...", 3)
        await asyncio.sleep(0.4)

        yield _sse("Creating scenario namespaces...", 8)
        for _, ns, _, _ in SCENARIO_SETUP:
            try:
                _ensure_ns(ns)
            except Exception as e:
                logger.error(f"Namespace {ns}: {e}")
        await asyncio.sleep(0.3)

        total = len(SCENARIO_SETUP)
        for i, (sid, ns, label, fn) in enumerate(SCENARIO_SETUP):
            pct = 12 + int((i / total) * 78)
            yield _sse(f"Deploying: {label}...", pct)
            try:
                await fn(ns)
            except Exception as e:
                logger.error(f"Setup {sid} failed: {e}")
            await asyncio.sleep(0.3)

        yield _sse("Waiting for cluster to stabilize...", 93)
        await asyncio.sleep(2)
        yield _sse("War room ready — initiating breach...", 100)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/execute")
async def execute_command(body: dict):
    """Execute a whitelisted kubectl command in the scenario's namespace."""
    cmd      = body.get("cmd", "")
    args     = body.get("args", [])
    scenario = body.get("scenario", "")

    ns = SCENARIO_NS.get(scenario)
    if not ns:
        return JSONResponse({"output": "", "error": f"Unknown scenario: {scenario}"})

    if cmd != "kubectl":
        return JSONResponse({"output": "", "error": f"Only kubectl is supported via arcade backend"})

    output = await run_kubectl(args, ns)
    return JSONResponse({"output": output, "error": ""})


@router.get("/status/{scenario}")
async def get_scenario_status(scenario: str):
    """Return pod health for a scenario namespace — used by frontend to auto-detect resolution."""
    ns = SCENARIO_NS.get(scenario)
    if not ns:
        return JSONResponse({"healthy": False, "error": f"Unknown scenario: {scenario}"})
    try:
        pods = core_v1.list_namespaced_pod(ns).items
    except ApiException as e:
        return JSONResponse({"healthy": False, "error": str(e.reason), "ready": 0, "total": 0, "pods": []})

    if not pods:
        return JSONResponse({"healthy": False, "ready": 0, "total": 0, "pods": []})

    total = len(pods)
    ready_count = 0
    pod_list = []
    for p in pods:
        status = _pod_status(p)
        ready  = _pod_ready(p)
        cs     = p.status.container_statuses or []
        is_ready   = bool(cs) and all(c.ready for c in cs)
        is_running = (p.status.phase or "").lower() == "running"
        if is_ready and is_running:
            ready_count += 1
        pod_list.append({"name": p.metadata.name, "ready": ready, "status": status})

    healthy = (ready_count == total and total > 0)
    return JSONResponse({"healthy": healthy, "ready": ready_count, "total": total, "pods": pod_list})


@router.delete("/cleanup")
async def cleanup_scenarios():
    """Delete all arcade-* namespaces."""
    deleted, errors = [], []
    for _, ns, _, _ in SCENARIO_SETUP:
        try:
            core_v1.delete_namespace(ns)
            deleted.append(ns)
        except ApiException as e:
            if e.status != 404:
                errors.append(f"{ns}: {e.reason}")
    return JSONResponse({"deleted": deleted, "errors": errors})
