// AEGIS topology -- auto-generated from topology.py
// load into Neo4j Aura:  copy-paste into the Browser, or use neo4j_load.py
MATCH (n) DETACH DELETE n;

CREATE (sn1:Device {id:'sn1', name:'sensor-node-1', type:'sensor', criticality:'low'});
CREATE (sn2:Device {id:'sn2', name:'sensor-node-2', type:'sensor', criticality:'low'});
CREATE (pi:Device {id:'pi', name:'pi-gateway', type:'gateway', criticality:'high'});
CREATE (fpga:Device {id:'fpga', name:'fpga-scorer', type:'accelerator', criticality:'medium'});
CREATE (cp:Device {id:'cp', name:'control-plane', type:'server', criticality:'high'});
CREATE (dash:Device {id:'dash', name:'dashboard', type:'ui', criticality:'low'});

MATCH (x:Device {id:'sn1'}),(y:Device {id:'pi'}) CREATE (x)-[:FEEDS {flow:'telemetry'}]->(y);
MATCH (x:Device {id:'sn2'}),(y:Device {id:'pi'}) CREATE (x)-[:FEEDS {flow:'telemetry'}]->(y);
MATCH (x:Device {id:'pi'}),(y:Device {id:'fpga'}) CREATE (x)-[:FEEDS {flow:'feature-vectors'}]->(y);
MATCH (x:Device {id:'pi'}),(y:Device {id:'cp'}) CREATE (x)-[:FEEDS {flow:'telemetry-sync'}]->(y);
MATCH (x:Device {id:'fpga'}),(y:Device {id:'cp'}) CREATE (x)-[:FEEDS {flow:'verdicts'}]->(y);
MATCH (x:Device {id:'cp'}),(y:Device {id:'dash'}) CREATE (x)-[:FEEDS {flow:'dashboard-data'}]->(y);

// Example queries the agent runs:
//   downstream of the pi gateway (what it affects):
//   MATCH (:Device {id:'pi'})-[:FEEDS*]->(d) RETURN DISTINCT d.name;
//   what the control-plane depends on (root-cause search):
//   MATCH (d)-[:FEEDS*]->(:Device {id:'cp'}) RETURN DISTINCT d.name;
