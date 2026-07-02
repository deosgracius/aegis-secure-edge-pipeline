"""
neo4j_load.py -- push the AEGIS topology into the real Neo4j Aura instance,
then run a live query to prove it's there.

Reads credentials from the Neo4j-*.txt file Aura gave you (kept in the project
root, NOT in this repo folder, so secrets stay out of the code).

    pip install neo4j
    python neo4j_load.py

If the driver isn't installed or Aura is paused/unreachable, it says so clearly
and exits -- the local graph (kg.py / build_kg.py) still works without any of this.
"""

import glob
import os
import sys

import topology as topo
import kg

# the Aura credentials file lives at the SummerProject root (two levels up)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_credentials():
    matches = glob.glob(os.path.join(ROOT, "Neo4j-*.txt"))
    if not matches:
        sys.exit("No Neo4j-*.txt credentials file found in %s" % ROOT)
    creds = {}
    with open(matches[0]) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds


def main():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        sys.exit("neo4j driver not installed.  Run:  pip install neo4j")

    creds = load_credentials()
    uri = creds["NEO4J_URI"]
    user = creds["NEO4J_USERNAME"]
    pwd = creds["NEO4J_PASSWORD"]
    db = creds.get("NEO4J_DATABASE", "neo4j")

    print("Connecting to %s ..." % uri)
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    print("Connected.")

    with driver.session(database=db) as s:
        # wipe + rebuild so re-running is idempotent
        s.run("MATCH (n) DETACH DELETE n")
        for did, a in topo.DEVICES.items():
            s.run("CREATE (:Device {id:$id, name:$name, type:$type, criticality:$crit})",
                  id=did, name=a["name"], type=a["type"], crit=a["criticality"])
        for a, b, flow in topo.LINKS:
            s.run("MATCH (x:Device {id:$a}),(y:Device {id:$b}) "
                  "CREATE (x)-[:FEEDS {flow:$flow}]->(y)", a=a, b=b, flow=flow)
        print("Loaded %d devices, %d links." % (len(topo.DEVICES), len(topo.LINKS)))

        # live query: what does the Pi gateway affect? (compare to kg.downstream)
        rows = s.run("MATCH (:Device {id:'pi'})-[:FEEDS*]->(d) "
                     "RETURN DISTINCT d.name AS name ORDER BY name")
        live = [r["name"] for r in rows]
        print("\nLive Neo4j query -- downstream of pi-gateway:")
        print("  ", ", ".join(live))
        local = sorted(topo.DEVICES[i]["name"] for i in kg.downstream("pi"))
        print("Local kg.downstream('pi') agrees:", live == local)

    driver.close()


if __name__ == "__main__":
    main()
