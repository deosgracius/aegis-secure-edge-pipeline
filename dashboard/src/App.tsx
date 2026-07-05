import { useCallback, useEffect, useState } from "react";
import {
  decide,
  getApprovals,
  getDevices,
  getIncidents,
  getStats,
  type Device,
  type Incident,
  type Investigation,
} from "./api";

const OPERATOR = "operator-deo";

export default function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [approvals, setApprovals] = useState<Investigation[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, i, a, s] = await Promise.all([
        getDevices(),
        getIncidents(),
        getApprovals(),
        getStats(),
      ]);
      setDevices(d);
      setIncidents(i);
      setApprovals(a);
      setStats(s);
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
