"""
rag.py -- tiny retrieval over the runbook corpus.

The agent grounds its diagnosis in runbooks instead of free-associating. This
is deliberately simple, explainable retrieval: score each runbook by weighted
keyword overlap with the query, return the top matches. No embeddings needed
at this corpus size (5 docs) -- and you can explain every ranking decision in
an interview, which beats a black box.

Swap in vector embeddings later if the corpus grows; the interface stays the same.
"""

import os
import re

RUNBOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runbooks")

# words that carry signal for this domain get a boost over generic overlap
DOMAIN_TERMS = {
    "flood": 3.0, "rate": 2.0, "pkt_rate": 3.0, "ddos": 3.0,
    "sequence": 3.0, "seq_gap": 3.0, "gap": 2.0, "replay": 3.0, "injection": 3.0,
    "timing": 2.0, "iat_var": 3.0, "bursty": 3.0, "variance": 2.0, "jitter": 2.0,
    "size": 2.0, "pkt_size": 3.0, "undersized": 3.0, "small": 1.5, "tiny": 2.0,
    "gateway": 3.0, "infrastructure": 2.0, "quarantine": 1.5, "probe": 2.0,
}

_WORD = re.compile(r"[a-z_]+")


def _tokens(text):
    return _WORD.findall(text.lower())


def load_corpus():
    """Return [{'id':..., 'title':..., 'text':...}] for every runbook."""
    docs = []
    for fname in sorted(os.listdir(RUNBOOK_DIR)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(RUNBOOK_DIR, fname), encoding="utf-8") as fh:
            text = fh.read()
        title = text.splitlines()[0].lstrip("# ").strip()
        docs.append({"id": fname[:-3], "title": title, "text": text})
    return docs


def retrieve(query, k=2):
    """Return the k best-matching runbooks for a query string, with scores."""
    qtokens = set(_tokens(query))
    scored = []
    for doc in load_corpus():
        dtokens = _tokens(doc["text"])
        dset = set(dtokens)
        score = 0.0
        for tok in qtokens:
            if tok in dset:
                score += DOMAIN_TERMS.get(tok, 1.0)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda s: -s[0])
    return [{"id": d["id"], "title": d["title"], "text": d["text"], "score": s}
            for s, d in scored[:k]]
