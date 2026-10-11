"""Analysis of the live test (PREMESSA_PROVA_GEMMA.md §4): guard ON vs OFF on the same tasks, paired by task.

    python -I analisi_prova_gemma.py --dir <results folder> --tasks 20-163 --out <analysis.json>

A "call" is one unit of the agent's budget: a tool call, or a reply without tools. A str_replace call is sorted with
formati.editor_outcome: edited, or one of the failures noop / missing / multiple / other_error.

  L1 (primary)   solved tasks. Exact two-sided McNemar test on the discordant pairs; supported if p < 0.05 and the
                 guard wins more pairs than it loses. Also the bootstrap interval of the difference in solved share.
  L2 (secondary) recovery calls of a run: calls made while a failed str_replace is not yet followed by a successful
                 one (the successful one included; the failure that opens the stretch not). Supported if the 95%
                 bootstrap interval of the mean per-task difference (ON - OFF) lies entirely below 0.
  L3 (secondary) repeated failures of a run: str_replace failures whose previous str_replace call failed with the
                 same type. Same rule as L2.
L2 and L3 are secondary: no correction for multiplicity, and the paper says so.

A task is excluded from every comparison, descriptive parts included, if either run is missing, or has an
infrastructure error or an unclear hidden-test outcome; exclusions are counted and listed. The descriptive parts also
give the failures found by the study's detectors (rilevatori.edit_failures: error type / kind). Bootstrap: tasks resampled with replacement,
2,000 replicates, numpy default_rng(20261011), percentile interval. Runs whose added lines contain suspicious tokens
are listed; a sensitivity analysis counts their solved runs as unsolved.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import formati  # noqa: E402
import rilevatori  # noqa: E402

FAILURES = ("noop", "missing", "multiple", "other_error")
SEED, REPLICATES = 20261011, 2000
NOTES = [("repeated_call", "You already sent this exact call"),
         ("already_made_edit", "You already made this exact edit"), ("noop_applied", "You already made this change"),
         ("noop_identical", "old_str and new_str are identical"), ("removed_by_edit", "old_str was in the file until"),
         ("closest", "The closest text in the file"), ("multiple", "The text appears at"),
         ("revisit", "This text is identical to a version")]


# ---------- one run ----------

def turns(messages):
    """[(kind, outcome)] for every call of a run, in order: kind is the tool name ("text" for a reply without
    tools); outcome is editor_outcome for str_replace, else None."""
    out, results = [], {m.get("tool_call_id"): m.get("content") for m in messages if m.get("role") == "tool"}
    for m in messages:
        if m.get("role") != "assistant":
            continue
        if not m.get("tool_calls"):
            out.append(("text", None))
            continue
        for tc in m["tool_calls"]:
            fn = tc.get("function") or {}
            args = json.loads(fn.get("arguments") or "{}")
            kind = args.get("command") if fn.get("name") == "str_replace_editor" else (
                "run_tests" if fn.get("name") == "execute_bash" else fn.get("name"))
            outcome = formati.editor_outcome(results.get(tc.get("id"))) if kind == "str_replace" else None
            out.append((kind, outcome))
    return out


def recovery_calls(seq):
    stretch, n = False, 0
    for kind, outcome in seq:
        if stretch:
            n += 1
        if kind == "str_replace":
            if outcome == "edited":
                stretch = False
            elif outcome in FAILURES:
                stretch = True
    return n


def repeated_failures(seq):
    edits = [o for k, o in seq if k == "str_replace"]
    return sum(1 for a, b in zip(edits, edits[1:]) if b in FAILURES and b == a)


def notes(messages):
    """Host notes by kind; one tool result can carry more than one note."""
    counts = {}
    for m in messages:
        if m.get("role") != "tool":
            continue
        for part in (m.get("content") or "").split("[Host note]")[1:]:
            text = part.strip()
            kind = next((k for k, start in NOTES if text.startswith(start)), "other")
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def tokens(messages):
    total = {"prompt": 0, "completion": 0}
    for m in messages:
        t = (m.get("meta") or {}).get("tokens") or {}
        for k in total:
            total[k] += t.get(k) or 0
    return total


# ---------- statistics ----------

def mcnemar_exact(wins, losses):
    """Two-sided exact McNemar p-value: binomial test of `wins` among wins + losses discordant pairs, p = 1/2."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_mean(diffs, seed=SEED, replicates=REPLICATES):
    import numpy as np
    d = np.asarray(diffs, dtype=float)
    if len(d) == 0:
        return {"mean": None, "low": None, "high": None}
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(replicates, len(d)))].mean(axis=1)
    return {"mean": float(d.mean()), "low": float(np.percentile(means, 2.5)), "high": float(np.percentile(means, 97.5))}


def min_wins_needed(discordant):
    """The smallest number of guard wins among `discordant` pairs that gives p < 0.05 (None if none does)."""
    return next((w for w in range(discordant + 1) if w > discordant - w and
                 mcnemar_exact(w, discordant - w) < 0.05), None)


# ---------- the whole test ----------

def load(folder, index, cond):
    path = os.path.join(folder, f"{index:03d}_{cond}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def analyse(runs):
    """runs: {task index: {"off": result or None, "on": result or None}}."""
    kept, excluded, flagged = [], [], []
    for index in sorted(runs):
        pair = runs[index]
        reasons = [f"{c}: missing" for c in ("off", "on") if pair.get(c) is None]
        reasons += [f"{c}: {pair[c].get('infra_error') or 'hidden ' + str(pair[c].get('hidden'))}"
                    for c in ("off", "on") if pair.get(c) is not None and (
                        pair[c].get("solved") is None or pair[c].get("infra_error")
                        or pair[c].get("hidden") not in ("passed", "failed"))]
        if reasons:
            excluded.append({"task": index, "why": reasons})
            continue
        kept.append(index)
        if any(pair[c].get("suspicious_additions") for c in ("off", "on")):
            flagged.append({"task": index, **{c: pair[c].get("suspicious_additions") for c in ("off", "on")}})
    flagged_ids = {f["task"] for f in flagged}

    def l1(sensitivity=False):
        def solved(i, c):
            r = runs[i][c]
            return bool(r["solved"]) and not (sensitivity and r.get("suspicious_additions"))
        wins = sum(1 for i in kept if solved(i, "on") and not solved(i, "off"))
        losses = sum(1 for i in kept if solved(i, "off") and not solved(i, "on"))
        p = mcnemar_exact(wins, losses)
        return {"solved_off": sum(solved(i, "off") for i in kept), "solved_on": sum(solved(i, "on") for i in kept),
                "wins": wins, "losses": losses, "p": p, "supported": p < 0.05 and wins > losses,
                "difference": bootstrap_mean([solved(i, "on") - solved(i, "off") for i in kept])}

    seqs = {i: {c: turns(runs[i][c]["messages"]) for c in ("off", "on")} for i in kept}
    out = {"tasks_total": len(runs), "tasks_compared": len(kept), "excluded": excluded,
           "L1": l1(), "L1_sensitivity_suspicious_as_unsolved": l1(True) if flagged_ids else None}
    for name, measure in (("L2", recovery_calls), ("L3", repeated_failures)):
        per = {i: {c: measure(seqs[i][c]) for c in ("off", "on")} for i in kept}
        diff = bootstrap_mean([per[i]["on"] - per[i]["off"] for i in kept])
        out[name] = {"total_off": sum(per[i]["off"] for i in kept), "total_on": sum(per[i]["on"] for i in kept),
                     "difference": diff, "supported": diff["high"] is not None and diff["high"] < 0}
    describe = {}
    for c in ("off", "on"):
        types, note_counts, tok, detected = {}, {}, {"prompt": 0, "completion": 0}, {}
        for i in kept:
            for kind, outcome in seqs[i][c]:
                if kind == "str_replace":
                    types[outcome] = types.get(outcome, 0) + 1
            for f in rilevatori.edit_failures(runs[i][c]["messages"]):
                k = f"{f.get('error')}/{f.get('kind')}"
                detected[k] = detected.get(k, 0) + 1
            for k, v in notes(runs[i][c]["messages"]).items():
                note_counts[k] = note_counts.get(k, 0) + v
            for k, v in tokens(runs[i][c]["messages"]).items():
                tok[k] += v
        describe[c] = {"str_replace_outcomes": types, "detector_failures": detected, "host_notes": note_counts,
                       "tokens": tok,
                       "calls": sum(runs[i][c]["calls"] for i in kept),
                       "finished": sum(bool(runs[i][c]["finished"]) for i in kept),
                       "dropped_calls": sum(runs[i][c].get("dropped_calls", 0) for i in kept),
                       "seconds": round(sum(runs[i][c]["seconds"] for i in kept), 1)}
    out["describe"] = describe
    out["solved_off_not_on"] = [i for i in kept if runs[i]["off"]["solved"] and not runs[i]["on"]["solved"]]
    out["solved_on_not_off"] = [i for i in kept if runs[i]["on"]["solved"] and not runs[i]["off"]["solved"]]
    out["suspicious"] = flagged
    return out


def parse_range(text):
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--tasks", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    runs = {i: {c: load(a.dir, i, c) for c in ("off", "on")} for i in parse_range(a.tasks)}
    result = analyse(runs)
    with open(a.out, "x", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    l1 = result["L1"]
    print(f"compared {result['tasks_compared']} of {result['tasks_total']} tasks; excluded {len(result['excluded'])}")
    print(f"L1 solved: off {l1['solved_off']}, on {l1['solved_on']}; guard wins {l1['wins']}, loses {l1['losses']}; "
          f"McNemar p = {l1['p']:.4f}; supported {l1['supported']}")
    for name in ("L2", "L3"):
        d = result[name]["difference"]
        if d["mean"] is not None:
            print(f"{name}: off {result[name]['total_off']}, on {result[name]['total_on']}; mean difference "
                  f"{d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]; supported {result[name]['supported']}")


if __name__ == "__main__":
    main()
