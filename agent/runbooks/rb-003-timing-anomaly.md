# RB-003: Bursty Timing (inter-arrival variance)

**Symptoms:** iat_var far above the ~5 baseline (often 50+). Message contents
look normal.

**Likely causes:** network congestion between node and gateway, a node CPU
starving its network task, or an attacker shaping traffic to evade rate
detection (sending in bursts).

**Investigation steps:**
1. Check whether other nodes on the same link also show high iat_var
   (congestion is shared; a compromised node is alone).
2. Correlate with pkt_rate: bursty AND high-rate suggests evasive flooding.
3. Bursty but normal-rate on one node suggests local device trouble.

**Remediation:** Shared burstiness → network issue, no quarantine, notify
operators. Single node bursty + rate anomaly → treat as evasive attack and
quarantine if safe.
