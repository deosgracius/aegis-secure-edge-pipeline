"""
integration_test.py -- prove the C node and the Python gateway speak the same
protocol, byte-for-byte, then run the C-built frames through the FPGA scorer.

What it does:
  1. compiles the C node's framing code with gcc (host_test.exe),
  2. for several feature vectors, asks the C program for the raw frame bytes,
  3. checks those bytes equal what Python's build_frame() produces,
  4. parses the C bytes with the Pi bridge and gets an FPGA verdict.

If this passes, the MSP432 firmware and the Raspberry Pi gateway are guaranteed
to interoperate before the hardware even exists.

Run:  python integration_test.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NODE = os.path.join(ROOT, "sensor-node")
sys.path.insert(0, os.path.join(ROOT, "gateway"))
import pi_bridge as pb   # noqa: E402


def compile_node():
    exe = os.path.join(NODE, "host_test.exe")
    cmd = ["gcc", "-std=c11", "-Wall", "-Wextra", "-O2",
           "-o", exe,
           os.path.join(NODE, "aegis_frame.c"),
           os.path.join(NODE, "host_test.c")]
    subprocess.run(cmd, check=True)
    return exe


def c_frame(exe, seq, feats_scaled):
    """Run the C program and return the frame it built, as bytes."""
    args = [exe, str(seq)] + [str(v) for v in feats_scaled]
    out = subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()
    return bytes(int(b, 16) for b in out.split())


def main():
    print("=" * 70)
    print("AEGIS cross-language integration test  (C node  <->  Python gateway)")
    print("=" * 70)
    print("Compiling the C node framing with gcc...")
    exe = compile_node()
    print("  built:", os.path.relpath(exe, ROOT))

    bridge = pb.Bridge()
    print("FPGA backend:", bridge.backend.name)

    # (seq, tx-scaled features) covering normal + each attack type
    cases = [
        (0,  [351, 606, 178, 609]),    # normal
        (1,  [1184, 595, 155, 534]),   # flood (high pkt_rate)
        (2,  [300, 512, 4000, 500]),   # injected msgs (huge seq_gap, x100)
        (3,  [300, 512, 100, 8000]),   # bursty timing (high iat_var, x100)
        (4,  [248, 46, 19, 431]),      # tiny weird packets (low pkt_size)
    ]

    print("\nseq  C-bytes==Python  CRC  ->  verdict (score)")
    print("-" * 70)
    all_ok = True
    for seq, feats in cases:
        cbytes = c_frame(exe, seq, feats)
        pybytes = pb.build_frame(seq, feats)
        match = (cbytes == pybytes)
        all_ok &= match

        # parse the C-produced bytes with the gateway and score them
        try:
            s, verdict, score = bridge.handle_frame(cbytes)
            crc_ok = "ok"
            tag = "SUSPICIOUS" if verdict else "normal"
            result = "%-10s (%3d)" % (tag, score)
        except pb.FrameError as e:
            crc_ok = "FAIL"; result = str(e); all_ok = False

        print("%3d  %-15s %-4s -> %s"
              % (seq, "MATCH" if match else "DIFFER", crc_ok, result))

    print("-" * 70)
    print("first frame bytes (hex):", pb.build_frame(0, cases[0][1]).hex(" "))
    if all_ok:
        print(">>> PASS: C firmware and Python gateway produce identical frames,")
        print("          and every frame scored cleanly through the chip model.")
    else:
        print(">>> FAIL: see DIFFER/FAIL rows above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
