# AEGIS — Knowledge Graph

The AI agent's "map of the system": which devices feed which, and what depends on
what. It lets the agent reason about **consequences** ("if I quarantine the Pi,
what breaks?") instead of seeing each anomaly in isolation.

Same pattern as the rest of AEGIS: **one model, two expressions** — a pure-Python
graph that runs today, plus generated Cypher for the real Neo4j Aura database.

## Files

| File | Role |
|------|------|
| `topology.py` | The topology: devices + `FEEDS` links. Single source of truth. |
| `kg.py` | Graph queries: `downstream`, `upstream`, `impact_of_failure`, `single_points_of_failure`. |
| `build_kg.py` | Demo + writes `topology.cypher`. **Run this first.** |
| `neo4j_load.py` | Loads the graph into a live Neo4j Aura instance (needs `pip install neo4j`). |
| `topology.cypher` | Generated Neo4j load script (paste into the Aura Browser). |

## Run (local, no database needed)

```bash
python build_kg.py
```

Shows the headline result: quarantining one **sensor** breaks nothing (the Pi has
a second one), but quarantining the **Pi** cascades to the FPGA, control-plane,
and dashboard — true blast-radius reasoning that accounts for redundancy.

## Putting it in real Neo4j

The original Aura Free instance (created 2026-06-19) was **auto-deleted** after
inactivity — Aura Free tears instances down after a few idle days. To go live:

1. Create a new free instance at https://console.neo4j.io and save its
   `Neo4j-*.txt` credentials file into the project root.
2. `pip install neo4j` then `python neo4j_load.py` — it loads the graph and runs a
   live query, checking the database's answer matches the local `kg.py`.
   (Or just paste `topology.cypher` into the Aura Browser.)

## Where this fits

This is the reasoning ground for the **AI tier** (LangGraph agent). It's built
early, risk-first, so it's ready when the agent arrives — the agent will call
these same queries via an MCP tool to decide whether a remediation is safe.
