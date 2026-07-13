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

// The bearer token is obtained by logging in (MFA or Google SSO) and kept in
// localStorage. A demo shortcut uses the static operator service token.
let _token = localStorage.getItem("aegis_token") || "";

export const hasToken = () => !!_token;
export function setToken(t: string) {
  _token = t;
  localStorage.setItem("aegis_token", t);
}
export function clearToken() {
  _token = "";
  localStorage.removeItem("aegis_token");
}
function authHeaders(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {};
}

export async function loginMfa(username: string, totp: string) {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, totp }),
  });
  if (!r.ok) throw new Error("login failed");
  const data = await r.json();
  setToken(data.token);
  return data;
}

export async function oauthStart() {
  const r = await fetch("/api/auth/oauth/login");
  if (!r.ok) throw new Error("Google SSO not configured");
  const { authorization_url } = await r.json();
  window.location.href = authorization_url;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch("/api" + path, { headers: authHeaders() });
  if (r.status === 401) clearToken(); // session expired -> back to login
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export type Topology = {
  nodes: {
    id: string;
    name: string;
    type: string;
    criticality: string;
    status: string;
  }[];
  edges: { source: string; target: string; flow: string }[];
};

export const getTopology = () => get<Topology>("/topology");
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
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ approved, by, note }),
  });
  if (!r.ok) throw new Error(`decision -> ${r.status}`);
  return r.json();
}
