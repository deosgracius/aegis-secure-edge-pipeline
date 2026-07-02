"""
build_kg.py -- demo the knowledge-graph queries, and emit Cypher for Neo4j.

Run:  python build_kg.py

Prints the answers the AI agent will need (downstream impact, blast radius,
single points of failure), then writes topology.cypher so you can load the exact
same graph into your Neo4j Aura instance.
"""

import os

import topology as topo
import kg

HERE = os.path.dirname(os.path.abspath(__file__))


def names(ids):
    return ", ".join(sorted(topo.DEVICES[i]["name"] for i in ids)) or "(none)"


def emit_cypher():
    """Generate CREATE statements for Neo4j -- the same graph, Cypher edition."""
    lines = ["// AEGIS topology -- auto-generated from topology.py",
             "// load into Neo4j Aura:  copy-paste into the Browser, or use neo4j_load.py",
             "MATCH (n) DETACH DELETE n;", ""]
    for did, a in topo.DEVICES.items():
        lines.append(
            "CREATE (%s:Device {id:'%s', name:'%s', type:'%s', criticality:'%s'});"
            % (did, did, a["name"], a["type"], a["criticality"]))
    lines.append("")
    for a, b, flow in topo.LINKS:
        lines.append(
            "MATCH (x:Device {id:'%s'}),(y:Device {id:'%s'}) "
            "CREATE (x)-[:FEEDS {flow:'%s'}]->(y);" % (a, b, flow))
    lines += [
        "",
        "// Example queries the agent runs:",
        "//   downstream of the pi gateway (what it affects):",
        "//   MATCH (:Device {id:'pi'})-[:FEEDS*]->(d) RETURN DISTINCT d.name;",
        "//   what the control-plane depends on (root-cause search):",
        "//   MATCH (d)-[:FEEDS*]->(:Device {id:'cp'}) RETURN DISTINCT d.name;",
    ]
    path = os.path.join(HERE, "topology.cypher")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def main():
    print("=" * 68)
    print("AEGIS knowledge graph")
    print("=" * 68)
    print("Devices: %d   Links: %d   Sources: %s"
          % (len(topo.DEVICES), len(topo.LINKS),
             ", ".join(topo.DEVICES[s]["name"] for s in topo.SOURCES)))

    print("\n--- The topology (who feeds whom) ---")
    for a, b, flow in topo.LINKS:
        print("  %-14s --%s--> %-14s"
              % (topo.DEVICES[a]["name"], flow, topo.DEVICES[b]["name"]))

    print("\n--- Agent question 1: 'if the Pi gateway degrades, what's affected?' ---")
    print("  downstream of pi-gateway:", names(kg.downstream("pi")))

    print("\n--- Agent question 2: 'where could a control-plane problem come from?' ---")
    print("  upstream of control-plane:", names(kg.upstream("cp")))

    print("\n--- Agent question 3: 'what truly BREAKS if we quarantine X?' ---")
    for d in ("sn1", "pi", "fpga"):
        impacted = kg.impact_of_failure(d)
        print("  quarantine %-14s -> breaks: %s"
              % (topo.DEVICES[d]["name"], names(impacted)))
    print("  (note: losing one sensor breaks nothing -- the Pi still has the other.")
    print("   losing the Pi cascades through the whole stack. That's redundancy.)")

    print("\n--- Agent question 4: 'which devices are single points of failure?' ---")
    for d, impacted in kg.single_points_of_failure().items():
        print("  %-14s is a SPOF -> %d device(s) downstream depend on it"
              % (topo.DEVICES[d]["name"], len(impacted)))

    path = emit_cypher()
    print("\nWrote %s (load this into Neo4j Aura)." % os.path.basename(path))
    print("=" * 68)


if __name__ == "__main__":
    main()
