# RB-005: Gateway / Infrastructure Degradation

**Symptoms:** anomalies reported simultaneously across MANY nodes, or the
control plane stops receiving telemetry from all sensors at once.

**Likely causes:** the Pi gateway degrading (it is a single point of failure
for the whole pipeline), broker overload, or an upstream network outage.

**Investigation steps:**
1. Query the topology: if the common ancestor of all affected devices is the
   gateway, suspect the gateway, not the sensors.
2. Check the gateway's blast radius — it feeds the FPGA, control plane, and
   dashboard.

**Remediation:** NEVER quarantine the gateway automatically — its blast radius
covers the entire downstream stack. Escalate to a human operator with the
evidence. Individual sensors should not be quarantined for a gateway-wide
event.
