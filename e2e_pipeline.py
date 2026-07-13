"""
e2e_pipeline.py -- the full data-path integration test, end to end.

Fires synthetic messages through the ENTIRE spine and asserts the right thing
happens at each hop -- deterministically, with no LLM, so it runs in CI:

  sensor node frame (bytes)         [gateway/pi_bridge]
    -> CRC check + recover features
    -> quantize + score             [== the FPGA model in tree_model]
    -> ingest                       [control plane]
    -> incident opened iff suspicious
    -> remediation + guardrail      [knowledge graph]
    -> quarantine the right node; a single point of failure is protected

Run (venv):  python e2e_pipeline.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "control-plane"))
sys.path.insert(0, os.path.join(ROOT, "gateway"))
sys.path.insert(0, os.path.join(ROOT, "fpga-scorer"))

import store          # noqa: E402
import pi_bridge as pb  # noqa: E402

# name, device, FLOAT features [pkt_rate, pkt_size, seq_gap, iat_var], expect_suspicious
CASES = [
    ("normal",       "sn1", [351, 606, 1.78, 6.09], False),
    ("flood",        "sn1", [1184, 595, 1.55, 5.34], True),
    ("replay",       "sn2", [300, 512, 42.0, 5.0],   True),
    ("bursty-timing","sn2", [300, 512, 1.0, 82.0],   True),
    ("undersized",   "sn1", [248, 46, 0.19, 4.31],   True),
]


def prop(target):
    return {"action": "quarantine", "target_device": target,
            "diagnosis": "flood", "reasoning": "pkt_rate >> baseline",
            "runbook": "rb-001-traffic-flood"}


def main():
    dbfile = os.path.join(ROOT, "control-plane", "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()
    bridge = pb.Bridge()

    print("=" * 64)
    print("AEGIS end-to-end pipeline test")
    print("=" * 64)
    print("%-14s %-5s frame->verdict  incident?" % ("case", "dev"))
    print("-" * 64)

    expected_incidents = 0
    for seq, (name, dev, feats, expect) in enumerate(CASES):
        # 1. node builds an authenticated frame; 2. gateway parses + scores it
        frame = pb._node_would_send(seq, feats)
        info = pb.parse_frame(frame)                    # CRC verified here
        _, verdict, score = bridge.handle_frame(frame)  # == FPGA model verdict
        # 3. control plane ingests -> opens an incident if suspicious
        res = store.ingest_telemetry(dev, seq, info["feats_scaled"], verdict, score)
        opened = res["incident_id"] is not None
        assert verdict == (1 if expect else 0), "%s: verdict %d" % (name, verdict)
        assert opened == expect, "%s: incident=%s" % (name, opened)
        if expect:
            expected_incidents += 1
        print("%-14s %-5s   %d (score %3d)   %s"
              % (name, dev, verdict, score, "opened" if opened else "-"))

    stats = store.counts()
    assert stats["incidents"] == expected_incidents
    print("-" * 64)
    print("incidents opened: %d (attacks), 0 for the normal message" % expected_incidents)

    # 4. remediation: quarantine the flagged sensor (safe), protect the gateway (SPOF)
    inv_sn1 = store.save_investigation("sn1", prop("sn1"), ["auto"])
    r1 = store.decide_investigation(inv_sn1, approved=True, by="e2e")
    assert r1["status"] == "executed", r1

    inv_pi = store.save_investigation("pi", prop("pi"), ["auto"])
    r2 = store.decide_investigation(inv_pi, approved=True, by="e2e")
    assert r2["status"] == "blocked", r2

    devs = {d["id"]: d["status"] for d in store.list_devices()}
    assert devs["sn1"] == "quarantined" and devs["pi"] == "active", devs
    print("remediation: sn1 -> quarantined; pi (gateway/SPOF) -> BLOCKED, stays active")
    print("=" * 64)
    print(">>> PASS: full pipeline works node-frame -> quarantine, guardrail intact.")


if __name__ == "__main__":
    main()
