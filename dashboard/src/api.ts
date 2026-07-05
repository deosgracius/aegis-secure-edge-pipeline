// api.ts -- typed calls to the AEGIS control plane (proxied via /api).

export type Device = {
  id: string;
  name: string;
  type: string;
  criticality: string;
  status: string;
};

export type Incident = {
  id: number;
  device_id: string;
  score: number;
  status: string;
  summary: string;
  ts: string;
};

export type Investigation = {
  id: number;
  incident_id: number | null;
  device_id: string;
  diagnosis: string;
  reasoning: string;
  runbook: string | null;
  proposed_action: string;
  target_device: string;
  status: string;
  decided_by: string | null;
  decision_note: string | null;
  result: Record<string, unknown> | null;
  transcript: string[];
  ts: string;
};

// Demo auth: the dashboard acts as the "operator". In a real deployment this
// token comes from a login / OAuth flow, not a constant.
const TOKEN = "operator-demo-token";
const authHeaders = { Authorization: `Bearer ${TOKEN}` };

async function get<T>(path: string): Promise<T> {
  const r = await fetch("/api" + path, { headers: authHeaders });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const getDevices = () => get<Device[]>("/devices");
export const getIncidents = () => get<Incident[]>("/incidents");
export const getApprovals = () => get<Investigation[]>("/approvals");
export const getStats = () =>
  get<Record<string, number>>("/stats");

export async function decide(
  invId: number,
  approved: boolean,
  by: string,
  note = ""
): Promise<Investigation> {
  const r = await fetch(`/api/investigations/${invId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify({ approved, by, note }),
  });
  if (!r.ok) throw new Error(`decision -> ${r.status}`);
  return r.json();
}
