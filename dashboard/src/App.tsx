import { useCallback, useEffect, useState } from "react";
import {
  decide,
  getApprovals,
  getDevices,
  getIncidents,
  getStats,
  getTopology,
  type Device,
  type Incident,
  type Investigation,
  type Topology,
} from "./api";

const OPERATOR = "operator-deo";

export default function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [approvals, setApprovals] = useState<Investigation[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [topology, setTopology] = useState<Topology | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, i, a, s, t] = await Promise.all([
        getDevices(),
        getIncidents(),
        getApprovals(),
        getStats(),
        getTopology(),
      ]);
      setDevices(d);
      setIncidents(i);
      setApprovals(a);
      setStats(s);
      setTopology(t);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [refresh]);

  const act = async (id: number, approved: boolean) => {
    await decide(id, approved, OPERATOR);
    refresh();
  };

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">◈</span> AEGIS
          <span className="sub">Security Operations</span>
        </div>
        <div className="stats">
          <Stat label="devices" value={stats.devices} />
          <Stat label="telemetry" value={stats.telemetry} />
          <Stat label="open incidents" value={stats.open_incidents} warn />
          <Stat label="awaiting approval" value={approvals.length} warn />
        </div>
      </header>

      {error && <div className="error">backend unreachable: {error}</div>}

      {topology && (
        <section className="panel graph-panel">
          <h2>Live Topology</h2>
          <div className="panel-body">
            <TopologyGraph topo={topology} />
          </div>
        </section>
      )}

      <main>
        <Panel title="Topology & Devices">
          {devices.map((d) => (
            <DeviceRow key={d.id} d={d} />
          ))}
        </Panel>

        <Panel title="Anomaly Feed">
          {incidents.length === 0 && <Empty>no incidents</Empty>}
          {incidents.map((i) => (
            <div className="incident" key={i.id}>
              <div className="row">
                <span className="tag danger">#{i.id}</span>
                <span className="score">score {i.score}</span>
              </div>
              <div className="summary">{i.summary}</div>
            </div>
          ))}
        </Panel>

        <Panel title={`Approval Queue (${approvals.length})`}>
          {approvals.length === 0 && <Empty>nothing awaiting a decision</Empty>}
          {approvals.map((a) => (
            <ApprovalCard key={a.id} a={a} onDecide={act} />
          ))}
        </Panel>
      </main>
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value?: number; warn?: boolean }) {
  return (
    <div className={"stat" + (warn && value ? " on" : "")}>
      <div className="num">{value ?? "–"}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

function TopologyGraph({ topo }: { topo: Topology }) {
  const W = 900;
  const H = 230;
  const colOf: Record<string, number> = {
    sensor: 0, gateway: 1, accelerator: 2, server: 2, ui: 3,
  };
  const colX = [110, 360, 610, 820];
  const crit: Record<string, string> = {
    high: "#e5604d", medium: "#e8a13a", low: "#5bbf7a",
  };

  const byCol: Record<number, Topology["nodes"]> = { 0: [], 1: [], 2: [], 3: [] };
  topo.nodes.forEach((n) => byCol[colOf[n.type] ?? 2].push(n));

  const pos: Record<string, { x: number; y: number }> = {};
  Object.entries(byCol).forEach(([c, nodes]) => {
    const x = colX[Number(c)];
    nodes.forEach((n, i) => {
      pos[n.id] = { x, y: (H / (nodes.length + 1)) * (i + 1) };
    });
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
      {topo.edges.map((e, idx) => {
        const a = pos[e.source];
        const b = pos[e.target];
        if (!a || !b) return null;
        return (
          <line key={idx} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="#4a3f30" strokeWidth={1.5} />
        );
      })}
      {topo.nodes.map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const quar = n.status === "quarantined";
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={13}
                    fill={quar ? "#3a1f1a" : "#1d3324"}
                    stroke={crit[n.criticality] ?? "#888780"} strokeWidth={2.5} />
            {quar && (
              <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize={13} fill="#e5604d">
                ✕
              </text>
            )}
            <text x={p.x} y={p.y + 30} textAnchor="middle" fontSize={12} fill="#f2ebe0">
              {n.name}
            </text>
            <text x={p.x} y={p.y + 44} textAnchor="middle" fontSize={10}
                  fill={quar ? "#e5604d" : "#a89a86"}>
              {quar ? "quarantined" : n.type}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function DeviceRow({ d }: { d: Device }) {
  const quarantined = d.status === "quarantined";
  return (
    <div className="device">
      <span className={"dot " + d.criticality} title={d.criticality} />
      <div className="dev-main">
        <div className="dev-name">{d.name}</div>
        <div className="dev-type">{d.type}</div>
      </div>
      <span className={"status " + (quarantined ? "quar" : "ok")}>
        {d.status}
      </span>
    </div>
  );
}

function ApprovalCard({
  a,
  onDecide,
}: {
  a: Investigation;
  onDecide: (id: number, approved: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const dangerous = a.proposed_action === "quarantine";
  return (
    <div className="approval">
      <div className="row">
        <span className={"action " + (dangerous ? "danger" : "info")}>
          {a.proposed_action.replace("_", " ")}
        </span>
        <span className="arrow">→</span>
        <span className="target">{a.target_device}</span>
      </div>
      <div className="diag">{a.diagnosis}</div>
      <button className="link" onClick={() => setOpen(!open)}>
        {open ? "hide" : "show"} agent reasoning
      </button>
      {open && (
        <div className="transcript">
          <p className="reason">{a.reasoning}</p>
          <ol>
            {a.transcript.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}
      <div className="btns">
        <button className="approve" onClick={() => onDecide(a.id, true)}>
          Approve
        </button>
        <button className="reject" onClick={() => onDecide(a.id, false)}>
          Reject
        </button>
      </div>
    </div>
  );
}
