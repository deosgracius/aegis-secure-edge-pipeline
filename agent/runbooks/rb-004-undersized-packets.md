# RB-004: Undersized Packets (tiny payloads)

**Symptoms:** pkt_size well below the ~512-byte baseline (often under 200).
Rate and timing may look normal.

**Likely causes:** protocol-scanning or probing traffic (small probes), a
truncation bug after a bad firmware update, or covert-channel exfiltration
using minimal frames.

**Investigation steps:**
1. Check if the size drop coincides with a firmware update (benign truncation).
2. Small packets + rising pkt_rate looks like scanning — treat as hostile.
3. Persistent small frames at normal rate could be a covert channel — inspect
   payload entropy if capture is available.

**Remediation:** Probing/scanning or suspected covert channel → quarantine the
node if its blast radius is safe. Known-bad firmware rollout → schedule a
rollback instead; quarantine only if it cannot be rolled back promptly.
