/**
 * arcade-k8s.js — Real Kubernetes integration for DevOps Survival.
 *
 * Provides two public functions:
 *   arcadeSetup(onProgress, onDone, onError)
 *   arcadeExecute(cmd, args, scenarioId)  → Promise<{output, error}>
 *
 * The list of scenario IDs that have real K8s namespaces.
 */

const ARCADE_REAL_SCENARIOS = [
  // Batch 1
  'nginx_config', 'crashloop', 'disk_space', 'cpu_spike',
  'oom_crash', 'docker_restart', 'silent_deploy', 'disk_errors',
  // Batch 2
  'ssl_cert_expired', 'etcd_failure', 'node_notready', 'db_conn_pool',
  'log_rotation_fail', 'network_policy_block', 'resource_quota', 'configmap_missing',
  // Batch 3
  'secret_rotation', 'hpa_not_scaling', 'pvc_pending', 'liveness_probe',
  'rbac_denied', 'docker_registry', 'dns_fail', 'zombie_proc',
];

/**
 * Stream setup progress via SSE.
 * @param {function(msg:string, pct:number)} onProgress
 * @param {function()} onDone
 * @param {function(err:string)} onError
 */
async function arcadeSetup(onProgress, onDone, onError) {
  try {
    const resp = await fetch('/api/arcade/setup', { method: 'POST' });
    if (!resp.ok) {
      onError(`Server error ${resp.status}`);
      return;
    }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // SSE packets are separated by double newlines
      const packets = buf.split('\n\n');
      buf = packets.pop(); // keep trailing incomplete packet

      for (const packet of packets) {
        for (const line of packet.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            onProgress(data.msg, data.pct);
            if (data.pct >= 100) {
              // Give the UI 400ms to show 100% before transitioning
              setTimeout(onDone, 400);
              return;
            }
          } catch (_) { /* ignore malformed event */ }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err.message);
  }
}

/**
 * Execute a kubectl command against the real cluster.
 * Only works for scenario IDs in ARCADE_REAL_SCENARIOS.
 *
 * @param {string}   cmd        — must be 'kubectl'
 * @param {string[]} args       — kubectl arguments
 * @param {string}   scenarioId — e.g. 'crashloop'
 * @returns {Promise<{output:string, error:string}>}
 */
async function arcadeExecute(cmd, args, scenarioId) {
  try {
    const resp = await fetch('/api/arcade/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd, args, scenario: scenarioId })
    });
    if (!resp.ok) {
      return { output: '', error: `HTTP ${resp.status}: backend error` };
    }
    const data = await resp.json();
    return { output: data.output || '', error: data.error || '' };
  } catch (err) {
    return { output: '', error: `Connection error: ${err.message}` };
  }
}
