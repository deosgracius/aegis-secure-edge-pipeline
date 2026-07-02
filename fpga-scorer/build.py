"""
build.py  --  Run the whole "scoring brain" pipeline and emit the chip's Verilog.

What this does, in order:
  1. Make fake data, split into train / test.
  2. Train the float decision tree (the laptop brain).
  3. Quantize it into a 16-bit integer tree (the chip brain).
  4. Run BOTH on the test set and prove they make the same decisions.
  5. Write scorer.v  (the Verilog that becomes the FPGA circuit),
     plus quant_params.json and test_vectors.txt for later FPGA simulation.

Run it:   python build.py
No external libraries required.
"""

import json
import os

import tree_model as tm

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Verilog generation: turn the integer tree into a combinational circuit.
# ---------------------------------------------------------------------------
def tree_to_verilog_expr(node, value_key):
    """Recursively build a nested-ternary Verilog expression for one output.

    value_key = "cls" gives the 0/1 verdict; "score" gives the 0..255 suspicion.
    Reads like:  (f0 <= 1234) ? (<left subtree>) : (<right subtree>)
    """
    if node["leaf"]:
        return str(node[value_key])
    fname = "f%d" % node["f"]
    cond = "(%s <= 16'd%d)" % (fname, node["thr_q"])
    left = tree_to_verilog_expr(node["left"], value_key)
    right = tree_to_verilog_expr(node["right"], value_key)
    return "(%s ? %s : %s)" % (cond, left, right)


def generate_verilog(tree_q):
    verdict_expr = tree_to_verilog_expr(tree_q, "cls")
    score_expr = tree_to_verilog_expr(tree_q, "score")
    inputs = "\n".join(
        "    input  wire [15:0] f%d,   // %s" % (i, tm.FEATURE_NAMES[i])
        for i in range(tm.N_FEATURES)
    )
    return """// scorer.v  -- AUTO-GENERATED from tree_model.py. Do not edit by hand.
//
// AEGIS Stage-4 anomaly scorer (combinational).
// Same decision tree as the Python model, expressed as hardware.
// Each feature arrives as a 16-bit unsigned integer (the quantized value).
//   verdict = 1 means "suspicious", 0 means "normal".
//   score   = 0..255 suspicion level (for the dashboard / threshold tuning).
//
// NOTE: this is purely combinational (no clock yet). Registering the inputs and
// the output turns this into the 2-stage pipeline we characterize for latency.

module scorer (
{inputs}
    output wire        verdict, // 1 = suspicious, 0 = normal
    output wire [7:0]  score    // 0..255 suspicion level
);

    assign verdict = {verdict};

    assign score = {score};

endmodule
""".format(inputs=inputs, verdict=verdict_expr, score=score_expr)


# ---------------------------------------------------------------------------
# Pretty-print the trained tree so a human can read the flowchart.
# ---------------------------------------------------------------------------
def print_tree(node, indent="  "):
    if node["leaf"]:
        verdict = "SUSPICIOUS" if node["cls"] else "normal"
        print("%s-> %s (score=%d, from %d samples)"
              % (indent, verdict, node["score"], node["n"]))
        return
    print("%sif %s <= %.2f:" % (indent, tm.FEATURE_NAMES[node["f"]], node["thr"]))
    print_tree(node["left"], indent + "    ")
    print("%selse:" % indent)
    print_tree(node["right"], indent + "    ")


def accuracy(tree, X, y, predict):
    correct = sum(1 for k in range(len(y)) if predict(tree, X[k])[0] == y[k])
    return correct / len(y)


def main():
    # 1. data ---------------------------------------------------------------
    Xtr, ytr = tm.generate_dataset(1500, seed=1)
    Xte, yte = tm.generate_dataset(500, seed=99)   # different seed = unseen data
    print("=" * 64)
    print("AEGIS FPGA scoring brain -- build report")
    print("=" * 64)
    print("Training samples: %d   Test samples: %d" % (len(ytr), len(yte)))
    print("Features: %s" % ", ".join(tm.FEATURE_NAMES))

    # 2. train float tree ---------------------------------------------------
    # depth 4 is the knee of the accuracy-vs-area curve (see tune.py):
    # ~99.6% accuracy for only 5 comparators; deeper buys nothing here.
    tree = tm.build_tree(Xtr, ytr, max_depth=4, min_samples=8)
    print("\n--- The trained decision tree (the flowchart) ---")
    print_tree(tree)
    print("Hardware cost: %d comparators, %d leaves, logic depth %d"
          % (tm.count_decision_nodes(tree), tm.count_leaves(tree),
             tm.tree_height(tree)))

    acc_float = accuracy(tree, Xte, yte, tm.predict_float)
    print("\nFloat tree accuracy on unseen test data: %.1f%%" % (100 * acc_float))

    # 3. quantize -----------------------------------------------------------
    qparams = tm.fit_quantizer(Xtr)
    tree_q = tm.quantize_tree(tree, qparams)

    # 4. prove float-brain and integer-brain AGREE --------------------------
    Xte_q = [tm.quantize_sample(x, qparams) for x in Xte]
    agree = 0
    acc_q_correct = 0
    for k in range(len(yte)):
        cls_f, _ = tm.predict_float(tree, Xte[k])
        cls_q, _ = tm.predict_quant(tree_q, Xte_q[k])
        if cls_f == cls_q:
            agree += 1
        if cls_q == yte[k]:
            acc_q_correct += 1
    agreement = 100.0 * agree / len(yte)
    acc_quant = 100.0 * acc_q_correct / len(yte)
    print("Integer (chip) tree accuracy on test data: %.1f%%" % acc_quant)
    print("AGREEMENT float-brain vs integer-brain:     %.1f%% (%d/%d)"
          % (agreement, agree, len(yte)))
    if agree == len(yte):
        print(">>> Perfect: the chip makes the EXACT same decisions as the laptop.")

    # 5. write artifacts ----------------------------------------------------
    verilog = generate_verilog(tree_q)
    with open(os.path.join(HERE, "scorer.v"), "w") as fh:
        fh.write(verilog)

    with open(os.path.join(HERE, "quant_params.json"), "w") as fh:
        json.dump({"features": tm.FEATURE_NAMES,
                   "quant_bits": tm.QUANT_BITS,
                   "params": qparams}, fh, indent=2)

    # test vectors: integer inputs + expected verdict/score, for FPGA sim later
    with open(os.path.join(HERE, "test_vectors.txt"), "w") as fh:
        fh.write("# f0 f1 f2 f3 expected_verdict expected_score\n")
        for k in range(len(yte)):
            cls_q, score_q = tm.predict_quant(tree_q, Xte_q[k])
            fh.write("%d %d %d %d %d %d\n"
                     % (Xte_q[k][0], Xte_q[k][1], Xte_q[k][2], Xte_q[k][3],
                        cls_q, score_q))

    print("\n--- Wrote artifacts ---")
    print("  scorer.v           the FPGA circuit (the same brain, as hardware)")
    print("  quant_params.json  how the Pi converts floats -> 16-bit before the chip")
    print("  test_vectors.txt   %d input/answer pairs to test the chip later" % len(yte))
    print("=" * 64)


if __name__ == "__main__":
    main()
