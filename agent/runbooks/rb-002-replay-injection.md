# RB-002: Message Injection / Replay (sequence gap)

**Symptoms:** seq_gap far above the normal ~1 (jumps of tens or hundreds).
Packet rate and size may be normal.

**Likely causes:** an attacker injecting or replaying frames (sequence numbers
jump), heavy packet loss on the link, or a node reboot resetting its counter.

**Investigation steps:**
1. Check if the gaps are one-time (reboot) or sustained (injection/loss).
2. A reboot shows one large gap then normal increments; injection shows
   repeated irregular gaps.
3. CRC failures alongside gaps strengthen the tampering hypothesis.

**Remediation:** Sustained irregular gaps on one node indicate tampering —
quarantine the node if its blast radius is safe. A single gap after downtime
is benign; acknowledge the incident without quarantine.
