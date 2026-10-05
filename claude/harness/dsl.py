"""Expression-tree DSL used by the proposer to generate candidate solvers.

A genome maps each task id to an expression tree. Trees are JSON-friendly:
  terminals: "x", "y", or an int constant
  nodes:     [op, child] for unary ops, [op, a, b] for binary ops
"""
import random

BINARY = {"add": "({} + {})", "sub": "({} - {})", "mul": "({} * {})",
          "max": "max({}, {})", "min": "min({}, {})"}
UNARY = {"neg": "(-{})"}
CONSTS = list(range(-3, 6))
MAX_DEPTH = 6
MAX_SIZE = 31


def evaluate(tree, x, y):
    if isinstance(tree, int):
        return tree
    if tree == "x":
        return x
    if tree == "y":
        return y
    op = tree[0]
    if op == "neg":
        return -evaluate(tree[1], x, y)
    a, b = evaluate(tree[1], x, y), evaluate(tree[2], x, y)
    return {"add": a + b, "sub": a - b, "mul": a * b,
            "max": max(a, b), "min": min(a, b)}[op]


def render(tree):
    if isinstance(tree, int):
        return f"({tree})" if tree < 0 else str(tree)
    if isinstance(tree, str):
        return tree
    if tree[0] in UNARY:
        return UNARY[tree[0]].format(render(tree[1]))
    return BINARY[tree[0]].format(render(tree[1]), render(tree[2]))


def size(tree):
    return 1 if not isinstance(tree, list) else 1 + sum(size(c) for c in tree[1:])


def depth(tree):
    return 1 if not isinstance(tree, list) else 1 + max(depth(c) for c in tree[1:])


def random_tree(rng, max_depth):
    if max_depth <= 1 or rng.random() < 0.3:
        r = rng.random()
        return "x" if r < 0.4 else "y" if r < 0.8 else rng.choice(CONSTS)
    if rng.random() < 0.1:
        return ["neg", random_tree(rng, max_depth - 1)]
    op = rng.choice(sorted(BINARY))
    return [op, random_tree(rng, max_depth - 1), random_tree(rng, max_depth - 1)]


def _paths(tree, path=()):
    yield path
    if isinstance(tree, list):
        for i, c in enumerate(tree[1:], start=1):
            yield from _paths(c, path + (i,))


def _get(tree, path):
    for i in path:
        tree = tree[i]
    return tree


def _set(tree, path, sub):
    if not path:
        return sub
    tree = list(tree)
    tree[path[0]] = _set(tree[path[0]], path[1:], sub)
    return tree


def mutate(tree, rng, donors=()):
    """Apply one structural mutation. Returns a new tree (input untouched)."""
    paths = list(_paths(tree))
    p = rng.choice(paths)
    kind = rng.random()
    if kind < 0.45:                                  # subtree replacement
        new = _set(tree, p, random_tree(rng, 3))
    elif kind < 0.65:                                # point mutation
        node = _get(tree, p)
        if isinstance(node, list) and node[0] in BINARY:
            new = _set(tree, p, [rng.choice(sorted(BINARY))] + node[1:])
        else:
            new = _set(tree, p, random_tree(rng, 1))
    elif kind < 0.80 and donors:                     # crossover
        donor = rng.choice(donors)
        new = _set(tree, p, _get(donor, rng.choice(list(_paths(donor)))))
    elif kind < 0.90:                                # wrap node in a new op
        node = _get(tree, p)
        op = rng.choice(sorted(BINARY))
        other = random_tree(rng, 2)
        new = _set(tree, p, [op, node, other] if rng.random() < .5 else [op, other, node])
    else:                                            # hoist a subtree
        new = _get(tree, rng.choice(paths))
    if depth(new) > MAX_DEPTH or size(new) > MAX_SIZE:
        return tree
    return new


def render_solver(genome):
    lines = ['"""Auto-generated candidate solver. Do not edit by hand."""', "",
             "", "def solve(task, x, y):"]
    for task in sorted(genome):
        lines.append(f"    if task == {task!r}:")
        lines.append(f"        return {render(genome[task])}")
    lines.append("    return 0")
    return "\n".join(lines) + "\n"


def genome_size(genome):
    return sum(size(t) for t in genome.values())
