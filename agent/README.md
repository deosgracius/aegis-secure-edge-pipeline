# AEGIS — AI Security Agent (LangGraph + Anthropic)

The AI tier. When the FPGA flags an anomaly, this agent investigates by calling
tools over the running system, grounds its reasoning in a runbook corpus, and
proposes a remediation that a **human must approve** before anything happens.

## Files

| File | Role |
|------|------|
| `agent.py` | The LangGraph state machine: investigate → propose → approval gate → execute. |
| `tools.py` | Tools the agent can call (telemetry, blast-radius, runbook search, devices). |
| `rag.py` | Keyword retrieval over the runbook corpus (explainable; swap for embeddings later). |
| `runbooks/` | The knowledge the agent reasons with — one markdown file per incident type. |
| `evals.py` | Golden-incident eval harness (attack signature → expected action). |

## Safety model (the important part)

- **The agent cannot act on its own.** There is no "quarantine" tool. The agent
  can only emit a `propose_remediation` call, which the harness routes to a
  human approval gate — a real node in the graph, not a prompt instruction.
- **Hard guardrail in `execute`:** even after human approval, it re-checks the
  knowledge graph and refuses to quarantine a single point of failure.
- The agent must call `get_device_impact` before it may propose a quarantine.

## Run

> Use the venv (has anthropic + langgraph): `..\..\.venv\Scripts\python.exe`
> Reads `ANTHROPIC_API_KEY` from the project's `.env.txt` automatically.

```powershell
# Golden-incident evals (no human needed; auto-approver policy)
..\..\.venv\Scripts\python.exe evals.py

# Interactive: seed data, investigate one incident, approve at the prompt
..\..\.venv\Scripts\python.exe agent.py
```

## Result

**5/5 golden incidents handled correctly** (model: claude-opus-4-8):

| incident | signature | agent's action |
|----------|-----------|----------------|
| flood | high pkt_rate | quarantine sn1 |
| replay | large seq_gap | quarantine sn2 |
| timing_burst | high iat_var | quarantine sn1 |
| undersized | tiny pkt_size | quarantine sn2 |
| gateway_spof | anomaly on the gateway | **notify_operator** (refused to quarantine a SPOF) |

## Next

- Persist the investigation transcript + decision back to the control plane as
  an audit record (RBAC/audit-log tie-in).
- Serve the transcript + approval queue to the React dashboard.
