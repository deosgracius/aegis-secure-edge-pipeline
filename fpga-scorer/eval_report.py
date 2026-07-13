"""
eval_report.py -- the data-tier evaluation report for the anomaly scorer.

Runs the quantized (chip) model on a fresh, attack-typed test set and computes
the metrics an ML/security reviewer expects: confusion matrix, accuracy,
precision, recall, F1, and per-attack-type recall (does it catch each attack?).
Writes EVAL_REPORT.md.

Pure standard library -- no numpy/sklearn needed.  Run:  python eval_report.py
"""

import os

import tree_model as tm

HERE = os.path.dirname(os.path.abspath(__file__))


def confusion(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    return tp, tn, fp, fn


def main():
    tree, qparams = tm.canonical_model()
    tree_q = tm.quantize_tree(tree, qparams)

    X, y, kinds = tm.generate_typed_dataset(2000, seed=1234)
    preds = [tm.predict_quant(tree_q, tm.quantize_sample(x, qparams))[0] for x in X]

    tp, tn, fp, fn = confusion(y, preds)
    n = len(y)
    acc = (tp + tn) / n
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    # per-attack-type recall
    per_kind = {}
    for kind in tm.ATTACK_KINDS:
        idx = [i for i in range(n) if kinds[i] == kind]
        caught = sum(1 for i in idx if preds[i] == 1)
        per_kind[kind] = (caught, len(idx))
    # false-positive rate on normal traffic
    normal_idx = [i for i in range(n) if kinds[i] == "normal"]
    normal_fp = sum(1 for i in normal_idx if preds[i] == 1)

    lines = []
    w = lines.append
    w("# AEGIS Anomaly Scorer - Evaluation Report\n")
    w("Model: quantized depth-%d decision tree (the exact model in `scorer.v`), "
      "evaluated on %d unseen, attack-typed messages.\n" % (tm.CANON_DEPTH, n))

    w("## Headline metrics\n")
    w("| metric | value |")
    w("|--------|-------|")
    w("| accuracy | %.1f%% |" % (100 * acc))
    w("| precision | %.1f%% |" % (100 * prec))
    w("| recall (attack detection) | %.1f%% |" % (100 * rec))
    w("| F1 | %.3f |" % f1)
    w("")

    w("## Confusion matrix\n")
    w("| | predicted normal | predicted suspicious |")
    w("|--|--|--|")
    w("| **actual normal** | %d (TN) | %d (FP) |" % (tn, fp))
    w("| **actual attack** | %d (FN) | %d (TP) |" % (fn, tp))
    w("")
    w("False-positive rate on normal traffic: %.2f%% (%d / %d).\n"
      % (100 * normal_fp / len(normal_idx), normal_fp, len(normal_idx)))

    w("## Per-attack-type recall\n")
    w("| attack type | caught | total | recall |")
    w("|-------------|--------|-------|--------|")
    for kind in tm.ATTACK_KINDS:
        caught, total = per_kind[kind]
        r = 100 * caught / total if total else 0.0
        w("| %s | %d | %d | %.1f%% |" % (kind, caught, total, r))
    w("")

    w("## Hardware cost & timing\n")
    w("- comparators (16-bit): **%d**, leaves: %d, logic depth: %d"
      % (tm.count_decision_nodes(tree), tm.count_leaves(tree), tm.tree_height(tree)))
    w("- latency: **2 cycles = 20 ns @ 100 MHz, zero jitter** (see `tb_latency.v`)")
    w("- float vs quantized agreement: 100% (see `build.py` / `tb_correctness.v`)")
    w("")

    report = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "EVAL_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report)

    # console summary
    print("Evaluation on %d messages:" % n)
    print("  accuracy %.1f%%  precision %.1f%%  recall %.1f%%  F1 %.3f"
          % (100 * acc, 100 * prec, 100 * rec, f1))
    print("  per-attack recall:", {k: "%d/%d" % per_kind[k] for k in tm.ATTACK_KINDS})
    print("  false positives on normal: %d/%d" % (normal_fp, len(normal_idx)))
    print("Wrote EVAL_REPORT.md")

    # regression gate for CI: fail if the model degrades badly
    import sys
    if acc < 0.95 or rec < 0.95:
        print(">>> FAIL: model quality regressed (acc %.3f, recall %.3f)" % (acc, rec))
        sys.exit(1)


if __name__ == "__main__":
    main()
