# AEGIS Scorer on the Basys 3 (Vivado)

Everything needed to synthesize the anomaly scorer for the real Artix-7 and get
the two numbers interviewers ask for: **fmax** and **resource utilization**.
Prepared and simulation-verified ahead of time — tomorrow is just running it.

Part: **xc7a35tcpg236-1** (Basys 3).

## Files here

| File | What it is |
|------|------------|
| `scorer_top.v` | Board wrapper: switches pick a preset message, LEDs show the verdict + score. |
| `scorer.xdc` | Basys 3 pin constraints (100 MHz clock, sw[2:0], led[15:0]). |
| `build_vivado.tcl` | One-command synth + implement + reports + bitstream. |

It instantiates `../scorer_pipe.v` → `../scorer.v` (the pipeline and the tree).

## On-board demo (verified in simulation)

Flip the 3 rightmost switches to pick a message; watch the LEDs:

| sw[2:0] | message | led[0] (verdict) | led[8:1] (score) |
|---------|---------|------------------|-------------------|
| 000 | normal | off | 0 |
| 001 | flood (high packet rate) | **on** | 255 |
| 010 | replay (big sequence gap) | **on** | 255 |
| 011 | bursty timing | **on** | 255 |
| 100 | undersized packets | **on** | 255 |

`led[15]` blinks as the pipeline's heartbeat.

## Fast path — batch build (recommended)

From this folder, in a terminal with Vivado on PATH:

```powershell
vivado -mode batch -source build_vivado.tcl
```

It prints the timing summary and utilization to the console and writes
`vivado_out/utilization.rpt`, `vivado_out/timing.rpt`, and `vivado_out/scorer_top.bit`.

## GUI path (if you prefer clicking)

1. Vivado → **Create Project** → RTL project, do not specify sources yet.
2. Board/part: pick part **xc7a35tcpg236-1** (or the Basys 3 board file).
3. **Add Sources** → add `../scorer.v`, `../scorer_pipe.v`, `scorer_top.v`.
4. **Add Constraints** → add `scorer.xdc`.
5. Set `scorer_top` as top. Run **Synthesis**, then **Implementation**.
6. Open **Report Timing Summary** and **Report Utilization**.
7. To run on the board: **Generate Bitstream** → **Open Hardware Manager** →
   connect the Basys 3 → **Program Device**. Then flip the switches.

## The two numbers to record

- **fmax** = 1 / (10 ns − WNS), where **WNS** (Worst Negative Slack) is at the
  100 MHz constraint in the timing summary. Positive WNS → the design meets
  100 MHz with room to spare; the fmax formula tells you the real ceiling.
  *(If WNS is large and positive, this tiny combinational tree will clock far
  above 100 MHz — that's the expected, and quotable, result.)*
- **Utilization**: LUTs, FFs, and slices used (expect a tiny fraction of the
  35T — a great "fits with room for many more cores" talking point).

## Résumé line you earn tomorrow

> Synthesized the anomaly scorer on an Artix-7 (Basys 3): met timing at 100 MHz
> with **[WNS] ns** slack (fmax **[X] MHz**), using **[N] LUTs / [M] FFs**
> (<1% of the device).
