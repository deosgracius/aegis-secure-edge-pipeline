"""
pi_bridge.py -- the Raspberry Pi gateway: node <-> FPGA bridge.

Plain-English summary
---------------------
The Pi sits in the middle. A sensor node sends it a 15-byte binary frame (see
../PROTOCOL.md). The Pi:
  1. parses the frame and checks the CRC (drops it if corrupted),
  2. recovers the original feature values,
  3. quantizes them to the 16-bit integers the FPGA expects,
  4. asks the FPGA for a verdict, and
  5. returns verdict + suspicion score.

Step 4 has two backends:
  - SimBackend   : emulates the chip in software using the SAME model that became
                   scorer.v (we proved they agree bit-for-bit). Default; no hardware.
  - SerialBackend: talks to the real Basys 3 over a serial port (needs pyserial +
                   the board). Wired up for tomorrow.

Run:  python pi_bridge.py
"""

import os
import struct
import sys

# import the scoring brain from the fpga-scorer folder next door
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "fpga-scorer"))
import tree_model as tm   # noqa: E402

# ---- frame constants (must match the C node and ../PROTOCOL.md) ----
MAGIC0, MAGIC1 = 0xAE, 0x51
PAYLOAD_LEN = 8                      # 4 x uint16
FRAME_LEN = 15
TX_SCALE = [1, 1, 100, 100]         # how the node scaled each feature


# ---------------------------------------------------------------------------
# CRC-16/CCITT-FALSE  (poly 0x1021, init 0xFFFF) -- identical to the C version
# ---------------------------------------------------------------------------
def crc16_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


# ---------------------------------------------------------------------------
# Frame build / parse
# ---------------------------------------------------------------------------
def build_frame(seq, feats_scaled):
    """Build a 15-byte frame from a sequence number and 4 tx-scaled uint16s.

    (This is what the C node does; we also use it to test round-trips.)
    """
    if len(feats_scaled) != 4:
        raise ValueError("need exactly 4 features")
    body = struct.pack("<HB4H", seq & 0xFFFF, PAYLOAD_LEN, *[v & 0xFFFF for v in feats_scaled])
    crc = crc16_ccitt(body)
    return bytes([MAGIC0, MAGIC1]) + body + struct.pack("<H", crc)


class FrameError(Exception):
    pass


def parse_frame(frame):
    """Validate and unpack a frame -> dict(seq, feats_scaled). Raises FrameError."""
    if len(frame) != FRAME_LEN:
        raise FrameError("wrong length %d (want %d)" % (len(frame), FRAME_LEN))
    if frame[0] != MAGIC0 or frame[1] != MAGIC1:
        raise FrameError("bad magic word")
    body = frame[2:13]                      # seq + len + payload
    seq, plen = struct.unpack("<HB", body[:3])
    if plen != PAYLOAD_LEN:
        raise FrameError("bad payload len %d" % plen)
    feats = list(struct.unpack("<4H", body[3:11]))
    got_crc = struct.unpack("<H", frame[13:15])[0]
    want_crc = crc16_ccitt(body)
    if got_crc != want_crc:
        raise FrameError("CRC mismatch: got 0x%04X want 0x%04X" % (got_crc, want_crc))
    return {"seq": seq, "feats_scaled": feats}


# ---------------------------------------------------------------------------
# FPGA backends
# ---------------------------------------------------------------------------
class SimBackend:
    """Emulates the FPGA in software using the canonical model (== scorer.v)."""
    name = "SIM (software model of the chip)"

    def __init__(self):
        tree, self.qparams = tm.canonical_model()
        self.tree_q = tm.quantize_tree(tree, self.qparams)   # the integer (chip) tree

    def score(self, feats_float):
        xq = tm.quantize_sample(feats_float, self.qparams)
        return tm.predict_quant(self.tree_q, xq)   # (verdict, score)


class SerialBackend:
    """Talks to the real Basys 3 over a serial port. Needs pyserial + hardware."""
    name = "SERIAL (real FPGA over UART)"

    def __init__(self, port, baud=115200):
        import serial   # only required if you actually use this backend
        self.qparams = tm.canonical_model()[1]
        self.ser = serial.Serial(port, baud, timeout=1)

    def score(self, feats_float):
        xq = tm.quantize_sample(feats_float, self.qparams)
        self.ser.write(struct.pack("<4H", *xq))          # send 16-bit features
        resp = self.ser.read(2)                          # verdict byte + score byte
        if len(resp) != 2:
            raise FrameError("no/short response from FPGA")
        return resp[0] & 1, resp[1]


# ---------------------------------------------------------------------------
# The bridge itself
# ---------------------------------------------------------------------------
class Bridge:
    def __init__(self, backend=None):
        self.backend = backend or SimBackend()
        self.qparams = tm.canonical_model()[1]

    def handle_frame(self, frame_bytes):
        """Full path: raw frame bytes -> (seq, verdict, score). Raises on bad frame."""
        info = parse_frame(frame_bytes)
        feats_float = [info["feats_scaled"][i] / TX_SCALE[i] for i in range(4)]
        verdict, score = self.backend.score(feats_float)
        return info["seq"], verdict, score


# ---------------------------------------------------------------------------
# Demo + self-test
# ---------------------------------------------------------------------------
def _node_would_send(seq, feats_float):
    """Mimic the MSP432 node: tx-scale the floats and frame them."""
    scaled = [max(0, min(0xFFFF, round(feats_float[i] * TX_SCALE[i]))) for i in range(4)]
    return build_frame(seq, scaled)


def main():
    print("=" * 68)
    print("AEGIS Pi gateway bridge")
    print("=" * 68)
    bridge = Bridge()
    print("FPGA backend: %s\n" % bridge.backend.name)

    # --- self-test 1: frame round-trips ---
    f = build_frame(42, [1100, 512, 120, 500])
    assert parse_frame(f) == {"seq": 42, "feats_scaled": [1100, 512, 120, 500]}
    print("[ok] frame build/parse round-trips")

    # --- self-test 2: CRC catches corruption ---
    bad = bytearray(f); bad[7] ^= 0xFF
    try:
        parse_frame(bytes(bad))
        print("[FAIL] corruption not detected"); sys.exit(1)
    except FrameError:
        print("[ok] CRC rejects a corrupted frame")

    # --- demo: run a few real-ish messages end to end ---
    X, y = tm.generate_dataset(8, seed=7)
    print("\nseq  features (pkt_rate,pkt_size,seq_gap,iat_var)        -> verdict (score)")
    print("-" * 68)
    for seq, (feats, truth) in enumerate(zip(X, y)):
        frame = _node_would_send(seq, feats)          # node side
        s, verdict, score = bridge.handle_frame(frame)  # pi + fpga side
        tag = "SUSPICIOUS" if verdict else "normal"
        print("%3d  (%6.0f, %6.0f, %5.2f, %5.2f)  ->  %-10s (%3d)  [truth=%s]"
              % (s, feats[0], feats[1], feats[2], feats[3], tag, score,
                 "anomaly" if truth else "normal"))
    print("-" * 68)
    print("Frame -> CRC check -> recover -> quantize -> chip verdict: working.")


if __name__ == "__main__":
    main()
