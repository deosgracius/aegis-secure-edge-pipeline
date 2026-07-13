"""
run_demo.py -- the AEGIS story in one command.

Narrates the full pipeline end to end: sensors stream telemetry, the gateway
checks and scores it, suspicious messages open incidents, the knowledge graph is
consulted, and a human-approved remediation quarantines the right node while the
gateway (a single point of failure) is protected.

Deterministic -- no server, no LLM, no hardware.  Run:  python run_demo.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for sub in ("control-plane", "gateway", "fpga-scorer"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import store          # noqa: E402
import pi_bridge as pb  # noqa: E402


def rule(c="-"):
    print(c * 66)


def main():
    dbfile = os.path.join(ROOT, "control-plane", "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()
    bridge = pb.Bridge()

    rule("=")
    print("  AEGIS - secure, hardware-accelerated edge security (demo)")
    rule("=")

    messages = [
        ("sensor-node-1", "sn1", [351, 606, 1.78, 6.09], "normal traffic"),
        ("sensor-node-1", "sn1", [1184, 595, 1.55, 5.34], "a packet-rate FLOOD"),
        ("sensor-node-2", "sn2", [300, 512, 42.0, 5.0], "REPLAYED messages"),
    ]

    print("\n[1] Sensor nodes stream authenticated telemetry to the gateway.")
    print("    The gateway verifies each frame's CRC, then the FPGA scorer")
    print("    returns a verdict in 20 ns.\n")
    for seq, (name, dev, feats, desc) in enumerate(messages):
        frame = pb._node_would_send(seq, feats)
        info = pb.parse_frame(frame)                 # CRC verified
        _, verdict, score = bridge.handle_frame(frame)
        res = store.ingest_telemetry(dev, seq, info["feats_scaled"], verdict, score)
        tag = "SUSPICIOUS" if verdict else "normal"
        print("    %-14s sends %-22s -> %-10s (score %d)"
              % (name, desc, tag, score))
        if res["incident_id"]:
            print("        -> incident #%d opened" % res["incident_id"])

    print("\n[2] Two incidents are open. Before acting, the agent asks the")
    print("    knowledge graph what would break if it quarantined each device:\n")
    for dev in ("sn1", "pi"):
        imp = store.device_impact(dev)
        verdict = "SAFE to quarantine" if imp["safe_to_quarantine"] \
            else "NOT safe - breaks %s" % ", ".join(imp["breaks_if_quarantined"])
        print("    %-14s : %s" % (store.list_devices() and dev, verdict))

    print("\n[3] The agent proposes remediations; a human approves them.\n")
    inv1 = store.save_investigation("sn1", {"action": "quarantine",
        "target_device": "sn1", "diagnosis": "packet-rate flood",
        "reasoning": "pkt_rate >> baseline; blast radius safe",
        "runbook": "rb-001-traffic-flood"}, ["auto"])
    r1 = store.decide_investigation(inv1, approved=True, by="operator")
    print("    approve: quarantine sensor-node-1  -> %s" % r1["status"].upper())

    inv2 = store.save_investigation("pi", {"action": "quarantine",
        "target_device": "pi", "diagnosis": "(mistaken)",
        "reasoning": "operator error", "runbook": "rb-005-gateway-degradation"}, ["auto"])
    r2 = store.decide_investigation(inv2, approved=True, by="operator")
    print("    approve: quarantine pi-gateway     -> %s  (%s)"
          % (r2["status"].upper(), r2["result"]["reason"]))

    print("\n[4] Final device status:\n")
    for d in store.list_devices():
        mark = "  X quarantined" if d["status"] == "quarantined" else "  . active"
        print("    %-16s %s" % (d["name"], mark))

    rule("=")
    print("  The right node was isolated; the gateway (single point of")
    print("  failure) was protected - even from an approved mistake.")
    rule("=")


if __name__ == "__main__":
    main()
