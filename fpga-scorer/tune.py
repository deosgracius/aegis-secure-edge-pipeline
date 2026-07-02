"""
tune.py -- the accuracy-vs-hardware tradeoff sweep.

A deeper tree fits the data better (higher accuracy) but costs more on the chip
(more comparators, deeper logic). This sweeps tree depth and prints the tradeoff,
so you can pick a sweet spot AND talk about the tradeoff in an interview.

Run:  python tune.py
"""

import tree_model as tm


def evaluate(depth, Xtr, ytr, Xte, yte):
    tree = tm.build_tree(Xtr, ytr, max_depth=depth, min_samples=8)

    # accuracy on unseen data (float model)
    correct = sum(1 for k in range(len(yte))
                  if tm.predict_float(tree, Xte[k])[0] == yte[k])
    acc = 100.0 * correct / len(yte)

    # quantize and check the integer (chip) model still agrees + its accuracy
    qparams = tm.fit_quantizer(Xtr)
    tree_q = tm.quantize_tree(tree, qparams)
    agree = 0
    qcorrect = 0
    for k in range(len(yte)):
        xq = tm.quantize_sample(Xte[k], qparams)
        cls_f, _ = tm.predict_float(tree, Xte[k])
        cls_q, _ = tm.predict_quant(tree_q, xq)
        if cls_f == cls_q:
            agree += 1
        if cls_q == yte[k]:
            qcorrect += 1
    agreement = 100.0 * agree / len(yte)
    qacc = 100.0 * qcorrect / len(yte)

    return {
        "depth": depth,
        "comparators": tm.count_decision_nodes(tree),
        "leaves": tm.count_leaves(tree),
        "logic_depth": tm.tree_height(tree),
        "acc": acc,
        "qacc": qacc,
        "agreement": agreement,
    }


def main():
    Xtr, ytr = tm.generate_dataset(1500, seed=1)
    Xte, yte = tm.generate_dataset(500, seed=99)

    print("=" * 72)
    print("Accuracy vs. hardware-cost sweep (deeper tree = smarter but bigger)")
    print("=" * 72)
    print("%-6s %-12s %-7s %-12s %-9s %-9s %-10s" %
          ("depth", "comparators", "leaves", "logic_depth",
           "test_acc", "chip_acc", "agreement"))
    print("-" * 72)
    for depth in range(1, 9):
        r = evaluate(depth, Xtr, ytr, Xte, yte)
        print("%-6d %-12d %-7d %-12d %-8.1f%% %-8.1f%% %-9.1f%%" %
              (r["depth"], r["comparators"], r["leaves"], r["logic_depth"],
               r["acc"], r["qacc"], r["agreement"]))
    print("-" * 72)
    print("comparators = 16-bit '<=' units on the FPGA (the main area cost)")
    print("logic_depth = longest compare chain (lower = can clock faster)")
    print("agreement   = float-brain vs integer-brain match (must stay 100%)")


if __name__ == "__main__":
    main()
