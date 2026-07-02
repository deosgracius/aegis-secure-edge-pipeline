"""
topology.py -- the AEGIS network topology (single source of truth).

A knowledge graph is just "things" (devices) and "how they connect" (links).
We describe both here as plain Python. Everything else (the dependency queries,
the Cypher for Neo4j) is generated from this one definition -- the same
"one model, two expressions" pattern we used for the Python tree -> Verilog.

An edge  A -> B  means "A FEEDS B": A provides data/service that B depends on.
So if A degrades, B (and anything downstream of B) is affected.
"""

# Each device: id -> attributes the agent can reason about.
DEVICES = {
    "sn1":  {"name": "sensor-node-1", "type": "sensor",       "criticality": "low"},
    "sn2":  {"name": "sensor-node-2", "type": "sensor",       "criticality": "low"},
    "pi":   {"name": "pi-gateway",    "type": "gateway",      "criticality": "high"},
    "fpga": {"name": "fpga-scorer",   "type": "accelerator",  "criticality": "medium"},
    "cp":   {"name": "control-plane", "type": "server",       "criticality": "high"},
    "dash": {"name": "dashboard",     "type": "ui",           "criticality": "low"},
}

# Directed "FEEDS" edges: (provider, consumer, what flows).
LINKS = [
    ("sn1",  "pi",   "telemetry"),
    ("sn2",  "pi",   "telemetry"),
    ("pi",   "fpga", "feature-vectors"),
    ("pi",   "cp",   "telemetry-sync"),
    ("fpga", "cp",   "verdicts"),
    ("cp",   "dash", "dashboard-data"),
]

# Devices with no provider are the data SOURCES (the sensors).
SOURCES = [d for d in DEVICES if not any(c == d for _, c, _ in LINKS)]
