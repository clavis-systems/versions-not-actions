"""Audit sample of PREMESSA_MODIFICHE.md §7.4, drawn only after the held-out run.

    python -I campione_verifica.py

Six categories, from the three Qwen held-out sets together: noop, stale, never_seen, multiple, known_bad_retry (own
version written again with a certain presence interval, an application failure and at least one error or test
name) and circle (both versions failed with application errors, certain presence). Incidents are sorted by (set,
run id, step) and 20 per category are drawn with random.Random(20261010), categories in this order. Each item has
the call, its result and the messages around it, cut to 400 characters each, so that Claude and Codex can judge
separately whether the detector is right. The file is written with mode "x"; the program refuses to run before
misura_heldout.json exists.
"""

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

SEED, PER_CATEGORY, CUT = 20261010, 20, 400
CATEGORIES = ("noop", "stale", "never_seen", "multiple", "known_bad_retry", "circle")


def cut(text):
    text = text if isinstance(text, str) else json.dumps(text)
    return text if len(text) <= CUT else text[:CUT] + " [...]"


def around(msgs, step, before=6, after=2):
    out = []
    for j in range(max(0, step - before), min(len(msgs), step + after)):
        m = msgs[j]
        calls = [cut(c["function"]["name"] + " " + c["function"]["arguments"]) for c in m.get("tool_calls") or []]
        out.append({"index": j, "role": m.get("role"), "content": cut(m.get("content") or ""), "calls": calls})
    return out


def incidents(set_name, run):
    msgs = run["messages"]
    found = []
    for f in R.edit_failures(msgs):
        if f["error"] in ("noop", "multiple"):
            found.append((f["error"], f["step"], {}))
        elif f.get("kind") in ("stale", "never_seen"):
            found.append((f["kind"], f["step"], {}))
    for e in R.revisits(msgs):
        detail = {"kind": e["kind"], "removed_at": e["removed_at"],
                  "known_bad": e["known_bad"], "replaced_bad": e["replaced_bad"]}
        if e["kind"] == "retry_own" and e["known_bad_kind"] == "application" and R.names_in(e["known_bad"][2]):
            found.append(("known_bad_retry", e["step"], detail))
        if e["known_bad_kind"] == "application" and e["replaced_bad"] and \
                R.failure_kind(e["replaced_bad"]) == "application":
            found.append(("circle", e["step"], detail))
    return [(category, set_name, run["id"], step, detail) for category, step, detail in found]


def main():
    out_path = os.path.join(misura.OUT_DIR, "verifica_campione.json")
    if not os.path.exists(os.path.join(misura.OUT_DIR, "misura_heldout.json")):
        sys.exit("the held-out run has not been made yet: the audit sample comes after it")
    pool = {c: [] for c in CATEGORIES}
    messages = {}
    for set_name, kind, where in misura.PARTS["heldout"]:
        if set_name not in misura.QWEN_SETS:
            continue
        runs = (formati.swehero(where) if kind == "swehero" else
                formati.openhands_events(where[0], formati.load_outcomes(where[1])))
        for run in runs:
            found = incidents(set_name, run)
            for category, s, run_id, step, detail in found:
                pool[category].append((s, run_id, step, detail))
            if found:
                messages[(set_name, run["id"])] = run["messages"]
    rnd = random.Random(SEED)
    items = []
    for category in CATEGORIES:
        candidates = sorted(pool[category], key=lambda x: (x[0], x[1], x[2]))
        for s, run_id, step, detail in rnd.sample(candidates, min(PER_CATEGORY, len(candidates))):
            msgs = messages[(s, run_id)]
            item = {"n": len(items) + 1, "category": category, "set": s, "run": run_id, "step": step,
                    "detail": detail, "around": around(msgs, step)}
            if "removed_at" in detail:
                item["around_removal"] = around(msgs, detail["removed_at"])
            items.append(item)
    with open(out_path, "x", encoding="utf-8") as fh:
        json.dump({"seed": SEED, "pool_sizes": {c: len(v) for c, v in pool.items()}, "items": items}, fh,
                  ensure_ascii=False, indent=1)
    print("written", out_path, {c: len(v) for c, v in pool.items()})


if __name__ == "__main__":
    main()
