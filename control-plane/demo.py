"""
demo.py -- end-to-end: gateway -> control plane -> knowledge graph.

Drives the service layer directly (no HTTP needed) to prove the whole flow:
  1. set up the DB and seed devices from the topology,
  2. generate readings, score them with the SAME gateway/FPGA model,
  3. ingest them -- suspicious ones auto-open incidents,
  4. for each open incident, ask the knowledge graph whether it's safe to
     quarantine the offending device (the check the AI agent will make),
  5. quarantine a device that's safe to pull.

Run (with the venv that has fastapi/sqlalchemy):
    python demo.py
"""

import os
import sys

# reach the gateway (scoring) and fpga-scorer (data) folders
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gateway"))
sys.path.insert(0, os.path.join(HERE, "..", "fpga-scorer"))

import store                       # noqa: E402
import pi_bridge as pb             # noqa: E402
import tree_model as tm            # noqa: E402


def main():
    # fresh DB each run so the demo is reproducible
    dbfile = os.path.join(HERE, "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)

    print("=" * 70)
    print("AEGIS control plane -- end-to-end demo")
    print("=" * 70)
    store.setup()
    print("DB ready, devices seeded:",
          ", ".join(d["name"] for d in store.list_devices()))

    bridge = pb.Bridge()           # same FPGA-model scorer as the real path
    X, y = tm.generate_dataset(20, seed=5)
    sensors = ["sn1", "sn2"]

    print("\nIngesting 20 readings from the two sensor nodes...")
    for i, feats in enumerate(X):
        device_id = sensors[i % 2]
        # node -> gateway: build frame, score it, get verdict
        frame = pb._node_would_send(i, feats)
        seq, verdict, score = bridge.handle_frame(frame)
        feats_scaled = pb.parse_frame(frame)["feats_scaled"]
        res = store.ingest_telemetry(device_id, seq, feats_scaled, verdict, score)
        if res["incident_id"]:
            print("  ! incident #%d opened for %s (score %d)"
                  % (res["incident_id"], device_id, score))

    print("\nStats:", store.counts())

    print("\n--- Open incidents, with the agent's safe-to-quarantine check ---")
    for inc in store.list_incidents(status="open"):
        impact = store.device_impact(inc["device_id"])
        verdict = ("SAFE to quarantine" if impact["safe_to_quarantine"]
                   else "DO NOT quarantine -- breaks %s" % impact["breaks_if_quarantined"])
        print("  incident #%d  %s" % (inc["id"], inc["summary"]))
        print("        knowledge-graph check: %s" % verdict)

    # act on the first safe one (what the agent would do after human approval)
    for inc in store.list_incidents(status="open"):
        if store.device_impact(inc["device_id"])["safe_to_quarantine"]:
            dev = store.set_device_status(inc["device_id"], "quarantined")
            print("\nQuarantined %s (incident #%d). It was safe -- nothing downstream breaks."
                  % (dev["name"], inc["id"]))
            break

    print("\nDevice statuses now:")
    for d in store.list_devices():
        print("  %-14s %s" % (d["name"], d["status"]))
    print("=" * 70)


if __name__ == "__main__":
    main()
