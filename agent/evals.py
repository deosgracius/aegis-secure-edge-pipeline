"""
evals.py -- golden-incident eval harness for the AEGIS agent.

Each golden case seeds the control plane with a known attack signature, runs the
agent (with the auto-approver policy, no human in the loop), and checks that the
agent's proposed action and target match the expected outcome. This is how you
show an agent is *reliable*, not just that it runs once.

Run (with the venv):  python evals.py
Needs ANTHROPIC_API_KEY (loaded from ../../.env.txt automatically).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "control-plane"))
sys.path.insert(0, HERE)

import store          # noqa: E402
import agent          # noqa: E402

# feature vectors are tx-scaled ints: [pkt_rate, pkt_size, seq_gap*100, iat_var*100]
GOLDEN = [
    {"name": "flood",       "device": "sn1", "feats": [1150, 512, 100, 500],
     "expect_action": "quarantine"},
    {"name": "replay",      "device": "sn2", "feats": [300, 512, 4200, 500],
     "expect_action": "quarantine"},
    {"name": "timing_burst","device": "sn1", "feats": [320, 512, 100, 8200],
     "expect_action": "quarantine"},
    {"name": "undersized",  "device": "sn2", "feats": [300, 60, 100, 500],
     "expect_action": "quarantine"},
    {"name": "gateway_spof","device": "pi",  "feats": None,
     "expect_action": "notify_operator"},   # pi is a SPOF -> must NOT quarantine
]


def seed_case(case):
    if case["feats"] is not None:
        for i in range(3):
            store.ingest_telemetry(case["device"], i, case["feats"], 1, 255)


def main():
    # fresh DB
    dbfile = os.path.join(HERE, "..", "control-plane", "aegis.db")
    if os.path.exists(dbfile):
        os.remove(dbfile)
    store.setup()

    print("=" * 66)
    print("AEGIS agent -- golden incident evals  (model: %s)" % agent.MODEL)
    print("=" * 66)

    passed = 0
    for case in GOLDEN:
        # reset device status so each case starts clean
        try:
            store.set_device_status(case["device"], "active")
        except ValueError:
            pass
        seed_case(case)

        final = agent.investigate(
            case["device"],
            "FPGA flagged suspicious telemetry (score 255)",
            approver=agent.auto_approver)
        prop = final.get("proposal") or {}
        got = prop.get("action", "<none>")
        ok = (got == case["expect_action"] and
              (case["expect_action"] != "quarantine" or
               prop.get("target_device") == case["device"]))
        passed += ok
        print("[%s] %-14s expected=%-15s got=%-15s (%d model calls)"
              % ("PASS" if ok else "FAIL", case["name"],
                 case["expect_action"], got, final.get("n_calls", 0)))
        if not ok:
            print("      diagnosis:", prop.get("diagnosis"))

    print("-" * 66)
    print("Score: %d/%d golden incidents handled correctly" % (passed, len(GOLDEN)))
    sys.exit(0 if passed == len(GOLDEN) else 1)


if __name__ == "__main__":
    main()
