# AEGIS — FPGA Anomaly Scorer (Stage 4)

The "scoring brain": a tiny decision tree trained in Python, quantized to integer
math, and emitted as a Verilog circuit — the same model expressed two ways
(software + hardware), verified to agree, and characterized for latency.

This is **Stage 4** of the 5-stage packet-inspection pipeline: it takes a few
numbers describing a network message and outputs `verdict` (normal/suspicious)
and an 8-bit `score` (suspicion 0–255).

## Files

| File | What it is |
|------|------------|
| `tree_model.py` | Pure-Python: makes fake data, trains the tree, quantizes it. No libraries needed. |
| `build.py` | Runs the pipeline, prints a report, and writes the artifacts below. |
| `scorer.v` | **Auto-generated** Verilog — the combinational circuit (the brain as hardware). |
| `scorer_pipe.v` | Clocked 2-stage pipeline wrapper around `scorer.v` (gives fixed latency). |
| `tb_correctness.v` | Testbench: feeds all 500 vectors, checks hardware == Python. |
| `tb_latency.v` | Testbench: measures latency & jitter at 100 MHz. |
| `quant_params.json` | The float→16-bit recipe the Raspberry Pi uses before feeding the chip. |
| `test_vectors.txt` | 500 input→answer pairs (generated) used by the correctness test. |

## How to run

```bash
# 1. Train + quantize + generate Verilog (needs only Python, no pip installs)
python build.py

# 2. Prove the hardware matches Python on all 500 vectors
iverilog -o sim_correct.vvp scorer.v tb_correctness.v && vvp sim_correct.vvp

# 3. Measure latency and jitter at 100 MHz
iverilog -o sim_latency.vvp scorer.v scorer_pipe.v tb_latency.v && vvp sim_latency.vvp
```

## Results (the numbers to talk about)

- **Accuracy:** ~87% on unseen data (shallow depth-3 tree, kept small on purpose).
- **Float vs integer agreement:** 100% — quantization changed nothing about the decisions.
- **Hardware vs Python:** 500/500 vectors match, zero mismatches.
- **Latency:** exactly **20 ns (2 cycles @ 100 MHz)**, **zero jitter**.
- **Throughput:** one verdict per cycle = up to 100 M messages/sec (pipelined).

## The one-line story

> Same anomaly model expressed as Python and as Verilog, verified bit-exact across
> the full test set, with a deterministic 20 ns / zero-jitter latency at 100 MHz.

## Next steps (not done yet)

- Push accuracy up (deeper tree / small MLP) without blowing up the hardware.
- Synthesize on the real Basys 3 to get fmax + resource utilization numbers.
- Wire the Pi→FPGA UART bridge so real feature vectors flow into this core.
