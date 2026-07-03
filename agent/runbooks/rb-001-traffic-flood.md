# RB-001: Traffic Flood (high packet rate)

**Symptoms:** pkt_rate far above the ~300 pps baseline (often 800+); other
features may look normal. FPGA scorer flags with high suspicion.

**Likely causes:** DDoS-style flood from a compromised node, a stuck firmware
loop retransmitting, or a misconfigured sample period.

**Investigation steps:**
1. Compare the node's recent pkt_rate history to its baseline (~300 pps).
2. Check whether OTHER sensors show the same spike (network-wide event) or
   just one node (compromised/faulty node).
3. Check the device's blast radius before acting.

**Remediation:** If a single node is flooding and it is safe to isolate
(redundant coverage exists), quarantine the node. If several nodes spike at
once, suspect an upstream issue — do NOT quarantine sensors; escalate to a
human operator.
