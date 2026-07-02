"""
kg.py -- the tiny graph "brain" the AI agent will lean on.

These are the questions the LangGraph agent needs answered when an anomaly fires:
  - downstream(x)        : everything that consumes x's output (what x affects)
  - upstream(x)          : everything x depends on (where to look for a root cause)
  - impact_of_failure(x) : what ACTUALLY breaks if x dies -- accounting for
                           redundancy (a consumer with another live provider survives)
  - single_points_of_failure() : devices whose loss cascades to others

Pure Python, no libraries. Operates on topology.DEVICES / topology.LINKS.
"""

import topology as topo


def _providers(node):
    """Who feeds `node` directly (its upstream neighbours)."""
    return [a for (a, b, _) in topo.LINKS if b == node]


def _consumers(node):
    """Who `node` feeds directly (its downstream neighbours)."""
    return [b for (a, b, _) in topo.LINKS if a == node]


def _reach(start, neighbours):
    """All nodes reachable from `start` (exclusive) using a neighbour function."""
    seen, stack = set(), list(neighbours(start))
    while stack:
        n = stack.pop()
        if n not in seen:
            seen.add(n)
            stack.extend(neighbours(n))
    return seen


def downstream(node):
    """Everything affected if `node` degrades (its consumers, transitively)."""
    return _reach(node, _consumers)


def upstream(node):
    """Everything `node` depends on (transitively) -- root-cause search space."""
    return _reach(node, _providers)


def impact_of_failure(node):
    """Devices that lose ALL their data paths if `node` is removed.

    This is the TRUE blast radius: a consumer survives if it still has at least
    one live provider after `node` is gone. Sensors are always 'alive' (they are
    sources). We propagate aliveness from the surviving sources to a fixpoint.
    """
    alive = set(s for s in topo.SOURCES if s != node)
    changed = True
    while changed:
        changed = False
        for d in topo.DEVICES:
            if d == node or d in alive:
                continue
            if any(p in alive for p in _providers(d)):
                alive.add(d)
                changed = True
    impacted = set(topo.DEVICES) - {node} - alive
    return impacted


def single_points_of_failure():
    """Devices whose failure breaks at least one OTHER device (true cascade)."""
    spofs = {}
    for d in topo.DEVICES:
        impacted = impact_of_failure(d)
        if impacted:
            spofs[d] = impacted
    return spofs
