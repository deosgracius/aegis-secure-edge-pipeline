# AEGIS

![CI](https://github.com/deosgracius/aegis-secure-edge-pipeline/actions/workflows/ci.yml/badge.svg)

A secure-by-design, hardware-accelerated edge pipeline: secure sensor nodes emit
an authenticated binary feed → an FPGA scores it for anomalies at deterministic
latency → a gateway runs an AI security agent (later) that reasons about posture
behind a human approval gate.

This repo is being built **bottom-up, vertical-slice first**. What works today
runs entirely on a laptop — no FPGA board, no sensor hardware required.

📐 **[ARCHITECTURE.md](ARCHITECTURE.md)** — system diagram, the trust spine, and
the security model.

## Layers (and status)

| Folder | Layer | Status |
|--------|-------|--------|
| `fpga-scorer/` | The anomaly-scoring "brain": Python model → quantized → Verilog, verified + latency-characterized. | ✅ working & simulated |
| `gateway/` | Raspberry Pi bridge: parses node frames, checks CRC, quantizes, asks the FPGA for a verdict. | ✅ working (sim backend) |
| `sensor-node/` | MSP432 firmware (C): samples sensors, builds authenticated frames. | ✅ framing built & cross-verified; board firmware skeleton ready |
| `knowledge-graph/` | Topology graph the AI agent reasons over (downstream/blast-radius). | ✅ local + Cypher; needs a fresh Aura instance to go live |
| `control-plane/` | FastAPI + SQLite system of record: ingest, incidents, graph-backed impact API. | ✅ working (runs on the `.venv`) |
| `agent/` | LangGraph AI agent: investigates anomalies via tools + runbook RAG, proposes remediation behind a human-approval gate. | ✅ working; 5/5 golden evals pass |
| `dashboard/` | React + TS + Vite security-ops UI: topology, anomaly feed, approval queue (approve/reject). | ✅ working; verified in browser |
| `Dockerfile` / `docker-compose.yml` | Containerized control plane. | ✅ `docker compose up --build` |
| `.github/workflows/ci.yml` | CI: control-plane tests, RTL sims, C↔Python protocol, Docker build. | ✅ green |
| `PROTOCOL.md` | The shared binary frame format (C ⇄ Python). | ✅ |

## Run with Docker

```bash
docker compose up --build      # control plane on http://localhost:8000
# then, for the UI:
cd dashboard && npm install && npm run dev   # http://localhost:5174
```

## CI

Every push runs three jobs (see `.github/workflows/ci.yml`):
1. **Control plane** — `verify_approvals`, `verify_auth`, `verify_mfa` (approval
   workflow, SPOF guardrail, auth/RBAC/audit, TOTP MFA), plus `e2e_pipeline.py`
   (a synthetic attack driven node-frame → gateway → scorer → incident →
   quarantine, with the guardrail protecting the gateway).
2. **FPGA + embedded** — trains the model, generates `scorer.v`, runs the model
   [evaluation report](fpga-scorer/EVAL_REPORT.md) (regression-gated), the RTL
   correctness + latency sims (Icarus Verilog), and the C↔Python protocol test.
3. **Docker** — builds the control-plane image.

Model quality (`fpga-scorer/eval_report.py`): **99.7% accuracy, 99.6% recall,
F1 0.997, 0.30% false-positive rate**, per-attack recall ~100%.

## Run everything (from PowerShell, with `C:\mingw64\bin` on PATH for gcc)

```powershell
# 1. Train + quantize + generate the FPGA Verilog
python fpga-scorer\build.py

# 2. (Verilog sims — git-bash is fine for iverilog)
#    iverilog -o s.vvp fpga-scorer\scorer.v fpga-scorer\tb_correctness.v ; vvp s.vvp

# 3. Accuracy-vs-hardware tradeoff sweep
python fpga-scorer\tune.py

# 4. Pi gateway demo (node -> CRC -> quantize -> chip verdict)
python gateway\pi_bridge.py

# 5. C-node ⇄ Python-gateway cross-language proof
python integration_test.py
```

## Proven results (résumé-ready)

- **Same model, two expressions** (Python + Verilog), verified **bit-exact** across 500 vectors.
- **Deterministic latency: 20 ns / 2 cycles @ 100 MHz, zero jitter.**
- **99.6% accuracy** at the knee of the accuracy-vs-area curve (5 comparators).
- **Cross-language protocol**: C firmware and Python gateway produce identical frames; CRC rejects corruption.

## Next

- **Basys 3 / Vivado**: synthesize `scorer.v` for real fmax + resource utilization.
- AI agent + MCP tools over the gateway; control plane (FastAPI/SQLite); dashboard.
