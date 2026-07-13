# AEGIS Anomaly Scorer - Evaluation Report

Model: quantized depth-4 decision tree (the exact model in `scorer.v`), evaluated on 2000 unseen, attack-typed messages.

## Headline metrics

| metric | value |
|--------|-------|
| accuracy | 99.7% |
| precision | 99.7% |
| recall (attack detection) | 99.6% |
| F1 | 0.997 |

## Confusion matrix

| | predicted normal | predicted suspicious |
|--|--|--|
| **actual normal** | 981 (TN) | 3 (FP) |
| **actual attack** | 4 (FN) | 1012 (TP) |

False-positive rate on normal traffic: 0.30% (3 / 984).

## Per-attack-type recall

| attack type | caught | total | recall |
|-------------|--------|-------|--------|
| flood | 238 | 238 | 100.0% |
| replay | 270 | 270 | 100.0% |
| bursty-timing | 262 | 266 | 98.5% |
| undersized | 242 | 242 | 100.0% |

## Hardware cost & timing

- comparators (16-bit): **5**, leaves: 6, logic depth: 4
- latency: **2 cycles = 20 ns @ 100 MHz, zero jitter** (see `tb_latency.v`)
- float vs quantized agreement: 100% (see `build.py` / `tb_correctness.v`)

