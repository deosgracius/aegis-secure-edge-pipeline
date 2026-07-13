"""
tree_model.py  --  The "scoring brain" for the AEGIS FPGA anomaly scorer.

Plain-English summary
---------------------
This file does ONE job: it builds a tiny decision tree that looks at a few
numbers describing a network message and decides "normal" (0) or "suspicious" (1).

A decision tree is just a flowchart of yes/no questions like:
    "is the packet rate above 812?"  ->  yes go left, no go right  ->  ... -> verdict

We train it on FLOAT numbers (the kind a laptop loves). But an FPGA chip can't do
messy decimals cheaply -- it loves whole numbers. So we also "quantize" the tree:
we convert every feature and every threshold into fixed-size whole numbers (here,
16-bit integers, i.e. 0..65535). The flowchart shape stays identical; only the
number format changes. Because our quantization keeps numbers in the same ORDER,
the integer flowchart makes the same yes/no choices as the float one.

No external libraries. Pure standard-library Python so it runs anywhere.

The four features we use (made up, but network-flavored):
    f0  pkt_rate   packets per second coming from a node
    f1  pkt_size   average packet size in bytes
    f2  seq_gap    jump in the message sequence number (big = injected/lost msgs)
    f3  iat_var    variance of time-between-packets (jittery timing)
"""

import math
import random

FEATURE_NAMES = ["pkt_rate", "pkt_size", "seq_gap", "iat_var"]
N_FEATURES = len(FEATURE_NAMES)

# 16-bit unsigned integers: every feature gets squeezed into 0..65535 on the chip.
QUANT_BITS = 16
QUANT_MAX = (1 << QUANT_BITS) - 1          # 65535
SCORE_BITS = 8                             # suspicion score 0..255


# ---------------------------------------------------------------------------
# 1. FAKE DATA  --  make a pile of "normal" and "anomalous" examples
# ---------------------------------------------------------------------------
def generate_dataset(n, seed=0):
    """Return (X, y). X is a list of [f0,f1,f2,f3] floats, y is a list of 0/1.

    Normal nodes: modest packet rate, normal size, tiny seq gaps, low jitter.
    Anomalies:    pick one or more "attack-ish" knobs and crank them.
    """
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        if rng.random() < 0.5:
            # ----- NORMAL -----
            pkt_rate = rng.gauss(300, 60)      # ~300 pps
            pkt_size = rng.gauss(512, 80)      # ~512 bytes
            seq_gap  = abs(rng.gauss(1, 0.7))  # gaps of ~1
            iat_var  = abs(rng.gauss(5, 2))    # low timing jitter
            label = 0
        else:
            # ----- ANOMALOUS: crank one or two knobs -----
            pkt_rate = rng.gauss(300, 60)
            pkt_size = rng.gauss(512, 80)
            seq_gap  = abs(rng.gauss(1, 0.7))
            iat_var  = abs(rng.gauss(5, 2))
            knob = rng.randint(0, 3)
            if knob == 0:
                pkt_rate = rng.gauss(1100, 200)   # flood / DDoS-ish
            elif knob == 1:
                seq_gap = rng.gauss(40, 12)        # injected/replayed messages
            elif knob == 2:
                iat_var = rng.gauss(80, 25)        # very bursty timing
            else:
                pkt_size = rng.gauss(60, 15)       # tiny weird packets
            label = 1
        X.append([pkt_rate, pkt_size, seq_gap, iat_var])
        y.append(label)
    return X, y


# Same distributions as generate_dataset, but also returns the attack TYPE per
# sample (for per-attack-type recall in the eval report). Separate function so
# the trained model is never affected.
ATTACK_KINDS = ["flood", "replay", "bursty-timing", "undersized"]


def generate_typed_dataset(n, seed=0):
    """Return (X, y, kinds). kinds[i] in {'normal', *ATTACK_KINDS}."""
    rng = random.Random(seed)
    X, y, kinds = [], [], []
    for _ in range(n):
        pkt_rate = rng.gauss(300, 60)
        pkt_size = rng.gauss(512, 80)
        seq_gap = abs(rng.gauss(1, 0.7))
        iat_var = abs(rng.gauss(5, 2))
        if rng.random() < 0.5:
            kind, label = "normal", 0
        else:
            knob = rng.randint(0, 3)
            if knob == 0:
                pkt_rate = rng.gauss(1100, 200); kind = "flood"
            elif knob == 1:
                seq_gap = rng.gauss(40, 12); kind = "replay"
            elif knob == 2:
                iat_var = rng.gauss(80, 25); kind = "bursty-timing"
            else:
                pkt_size = rng.gauss(60, 15); kind = "undersized"
            label = 1
        X.append([pkt_rate, pkt_size, seq_gap, iat_var])
        y.append(label)
        kinds.append(kind)
    return X, y, kinds


# ---------------------------------------------------------------------------
# 2. TRAIN  --  grow a small decision tree (the CART algorithm, by hand)
# ---------------------------------------------------------------------------
def _gini(y):
    """Impurity: 0 means a pure group (all same label), 0.5 is a 50/50 mix."""
    n = len(y)
    if n == 0:
        return 0.0
    p = sum(y) / n
    return 1.0 - (p * p + (1 - p) * (1 - p))


def _best_split(X, y):
    """Find the (feature, threshold) that best separates 0s from 1s."""
    n = len(y)
    best = None  # (gain, feature_index, threshold)
    parent = _gini(y)
    for f in range(N_FEATURES):
        # candidate thresholds = midpoints between sorted unique feature values
        vals = sorted(set(row[f] for row in X))
        for i in range(len(vals) - 1):
            thr = (vals[i] + vals[i + 1]) / 2.0
            ly = [y[k] for k in range(n) if X[k][f] <= thr]
            ry = [y[k] for k in range(n) if X[k][f] > thr]
            if not ly or not ry:
                continue
            # weighted impurity after the split; we want this small
            child = (len(ly) * _gini(ly) + len(ry) * _gini(ry)) / n
            gain = parent - child
            if best is None or gain > best[0]:
                best = (gain, f, thr)
    return best


def build_tree(X, y, max_depth=3, min_samples=8, depth=0):
    """Return a nested dict describing the tree.

    Leaf node:     {"leaf": True, "cls": 0/1, "score": 0..255, "n": count}
    Internal node: {"leaf": False, "f": idx, "thr": float, "left": .., "right": ..}
    """
    pos = sum(y)
    n = len(y)
    prob = pos / n if n else 0.0
    leaf = {
        "leaf": True,
        "cls": 1 if prob >= 0.5 else 0,
        "score": int(round(prob * (2 ** SCORE_BITS - 1))),  # suspicion 0..255
        "n": n,
    }
    # stop growing if pure, too deep, or too few samples
    if depth >= max_depth or n < 2 * min_samples or pos == 0 or pos == n:
        return leaf
    split = _best_split(X, y)
    if split is None or split[0] <= 0:
        return leaf
    _, f, thr = split
    lX, ly, rX, ry = [], [], [], []
    for k in range(n):
        if X[k][f] <= thr:
            lX.append(X[k]); ly.append(y[k])
        else:
            rX.append(X[k]); ry.append(y[k])
    if len(ly) < min_samples or len(ry) < min_samples:
        return leaf
    return {
        "leaf": False,
        "f": f,
        "thr": thr,
        "left": build_tree(lX, ly, max_depth, min_samples, depth + 1),
        "right": build_tree(rX, ry, max_depth, min_samples, depth + 1),
    }


def predict_float(node, x):
    """Walk the FLOAT tree for one sample x -> (cls, score)."""
    while not node["leaf"]:
        node = node["left"] if x[node["f"]] <= node["thr"] else node["right"]
    return node["cls"], node["score"]


# ---------------------------------------------------------------------------
# 3. QUANTIZE  --  turn the float tree into a whole-number (chip-friendly) tree
# ---------------------------------------------------------------------------
def fit_quantizer(X):
    """Learn how to squeeze each feature into 0..65535 using the training range.

    Returns per-feature {"lo":.., "hi":..}. We map lo->0 and hi->65535 linearly.
    Linear + increasing => ORDER is preserved => compares behave identically.
    """
    params = []
    for f in range(N_FEATURES):
        col = [row[f] for row in X]
        lo, hi = min(col), max(col)
        span = hi - lo
        pad = span * 0.02 if span > 0 else 1.0   # small margin so edges don't clip
        params.append({"lo": lo - pad, "hi": hi + pad})
    return params


def quantize_value(x, p):
    """Float feature value -> 16-bit integer 0..65535."""
    lo, hi = p["lo"], p["hi"]
    if hi <= lo:
        return 0
    q = round((x - lo) / (hi - lo) * QUANT_MAX)
    return max(0, min(QUANT_MAX, int(q)))


def quantize_threshold(thr, p):
    """Float threshold -> integer threshold using the SAME mapping.

    We floor so that 'x <= thr' (float) matches 'q(x) <= q(thr)' (int).
    """
    lo, hi = p["lo"], p["hi"]
    if hi <= lo:
        return 0
    q = math.floor((thr - lo) / (hi - lo) * QUANT_MAX)
    return max(0, min(QUANT_MAX, int(q)))


def quantize_tree(node, qparams):
    """Copy the tree, replacing float thresholds with integer thresholds."""
    if node["leaf"]:
        return dict(node)
    return {
        "leaf": False,
        "f": node["f"],
        "thr_q": quantize_threshold(node["thr"], qparams[node["f"]]),
        "left": quantize_tree(node["left"], qparams),
        "right": quantize_tree(node["right"], qparams),
    }


def quantize_sample(x, qparams):
    """Float feature vector -> integer feature vector (what the chip receives)."""
    return [quantize_value(x[f], qparams[f]) for f in range(N_FEATURES)]


def predict_quant(node_q, xq):
    """Walk the INTEGER tree for one integer sample xq -> (cls, score)."""
    while not node_q["leaf"]:
        node_q = node_q["left"] if xq[node_q["f"]] <= node_q["thr_q"] else node_q["right"]
    return node_q["cls"], node_q["score"]


# ---------------------------------------------------------------------------
# 4. HARDWARE COST  --  how big does this tree become on the chip?
# ---------------------------------------------------------------------------
def count_decision_nodes(node):
    """Number of internal nodes = number of '<=' comparators in the circuit.

    This is the main 'area' cost on the FPGA: each decision node is one
    16-bit comparator plus a little select logic.
    """
    if node["leaf"]:
        return 0
    return 1 + count_decision_nodes(node["left"]) + count_decision_nodes(node["right"])


def count_leaves(node):
    if node["leaf"]:
        return 1
    return count_leaves(node["left"]) + count_leaves(node["right"])


def tree_height(node):
    """Longest chain of compares = the combinational logic depth (affects fmax)."""
    if node["leaf"]:
        return 0
    return 1 + max(tree_height(node["left"]), tree_height(node["right"]))


# ---------------------------------------------------------------------------
# 5. THE CANONICAL MODEL  --  one trained tree shared by everything.
# ---------------------------------------------------------------------------
# build.py (which writes scorer.v) and pi_bridge.py (which emulates the chip)
# must use the SAME model, or the bridge's "golden" verdict won't match the
# hardware. This function is that single source of truth.
CANON_SEED = 1
CANON_DEPTH = 4
CANON_MIN_SAMPLES = 8


def canonical_model():
    """Return (tree, qparams) for the exact model that becomes scorer.v."""
    Xtr, ytr = generate_dataset(1500, seed=CANON_SEED)
    tree = build_tree(Xtr, ytr, max_depth=CANON_DEPTH, min_samples=CANON_MIN_SAMPLES)
    qparams = fit_quantizer(Xtr)
    return tree, qparams
