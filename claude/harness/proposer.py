"""Candidate generator: (1 + lambda) genetic programming on TRAIN cases only.

The proposer never touches holdout data and never decides acceptance; it only
suggests the most promising mutant. The judge (evaluator + selection) decides.
"""
import random

from . import dsl, tasks

TRAIN = [(x, y) for (x, y) in tasks.TRAIN_INPUTS]


def task_fitness(task, tree):
    """(exact matches, -mean abs error, -size): higher is better."""
    hits, err = 0, 0
    for x, y in TRAIN:
        diff = abs(dsl.evaluate(tree, x, y) - tasks.expected(task, x, y))
        hits += diff == 0
        err += min(diff, 10**6)
    return (hits, -err / len(TRAIN), -dsl.size(tree))


def reject_streaks(history):
    """history: chronological [(focus_task, decision)] of earlier proposer attempts.
    Returns {task: consecutive REJECTs since that task's last ACCEPT}."""
    streak = {t: 0 for t in tasks.TASK_IDS}
    for focus, decision in history:
        if focus in streak:
            streak[focus] = 0 if decision == "ACCEPT" else streak[focus] + 1
    return streak


def propose(genome, seed, lam=300, history=()):
    """Return (candidate_genome, note, params). Deterministic for (genome, seed, history).

    Self-adaptation driven by the judge's past decisions (never by holdout data):
      * tasks whose candidates keep being rejected get exponentially lower focus weight;
      * search effort (lambda) doubles with the focus task's reject streak (cap 8x);
      * after 3 straight rejects half of the offspring restart from fresh random trees,
        escaping local optima that overfit the train set.
    """
    rng = random.Random(seed)
    genome = {t: genome.get(t, 0) for t in tasks.TASK_IDS}
    scored = {t: task_fitness(t, genome[t]) for t in tasks.TASK_IDS}
    streak = reject_streaks(history)
    pool = [t for t in tasks.TASK_IDS if scored[t][0] < len(TRAIN)] or tasks.TASK_IDS
    weights = [0.5 ** min(streak[t], 10) for t in pool]
    focus = rng.choices(pool, weights=weights)[0]
    effort = lam * 2 ** min(streak[focus], 3)
    restart = streak[focus] >= 3
    donors = [genome[t] for t in tasks.TASK_IDS if isinstance(genome[t], list)]
    best_tree, best_fit = genome[focus], scored[focus]
    for i in range(effort):
        tree = dsl.random_tree(rng, 4) if restart and i % 2 else genome[focus]
        for _ in range(rng.randint(1, 3)):
            tree = dsl.mutate(tree, rng, donors)
        fit = task_fitness(focus, tree)
        if fit > best_fit:
            best_tree, best_fit = tree, fit
    candidate = dict(genome, **{focus: best_tree})
    params = {"focus": focus, "lambda": effort, "restart": restart,
              "reject_streak": streak[focus]}
    note = (f"focus={focus} train_hits {scored[focus][0]}->{best_fit[0]}/{len(TRAIN)} "
            f"size {dsl.size(genome[focus])}->{dsl.size(best_tree)}")
    return candidate, note, params
