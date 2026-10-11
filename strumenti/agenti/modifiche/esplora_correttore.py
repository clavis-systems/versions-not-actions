"""EXPLORATORY (11/10/2026, not part of any frozen premise): the "proofreader effect".

    python -I esplora_correttore.py <folder of agente_gemma.py results> [...]

Idea: when the agent copies the buggy code into old_str, does it copy the code as it SHOULD be (the fix it expects)
instead of as it IS? HumanEvalFix gives the truth: each task has the buggy body and the canonical correct body.
For every str_replace that failed with "did not appear verbatim", the old_str is checked against two files:
  - the file as it was when the call was made (replayed), where it is missing by definition;
  - the same file with the buggy body replaced by the canonical one (the "fixed" file).
  proofread   old_str is in the fixed file, but not in the file: the agent quoted the correct code as if it were
              already there, so its copy "fixed" the bug while reading;
  other       anything else.
Also reported: for proofread cases, whether the run later solved the task. Only data is read.
"""

from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agente_gemma as A  # noqa: E402
import formati  # noqa: E402


def check(run, rows):
    index = int(run["task"].split("/")[1])
    task = A.build_task(rows, index)
    text = task["files"][A.FILE]
    buggy, canon = rows[index]["buggy_solution"].rstrip("\n"), rows[index]["canonical_solution"].rstrip("\n")
    results = {m.get("tool_call_id"): m.get("content") or "" for m in run["messages"] if m.get("role") == "tool"}
    out = []
    for m in run["messages"]:
        for tc in m.get("tool_calls") or []:
            args = json.loads(tc["function"].get("arguments") or "{}")
            if args.get("command") != "str_replace":
                continue
            res = formati.editor_outcome(results.get(tc.get("id")))
            old, new = args.get("old_str") or "", args.get("new_str") or ""
            if res == "missing":
                fixed = text.replace(buggy, canon, 1) if buggy in text else None
                kind = "proofread" if fixed is not None and old and old in fixed and old not in text else "other"
                out.append({"kind": kind, "old": old, "buggy_present": buggy in text})
            elif res == "edited" and text.count(old) == 1:
                text = text.replace(old, new, 1)
    return out


def main():
    rows = A.load_rows()
    for folder in sys.argv[1:]:
        c = collections.Counter()
        solved = collections.Counter()
        examples = []
        for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
            with open(path, encoding="utf-8") as fh:
                run = json.load(fh)
            if "messages" not in run:
                continue
            found = check(run, rows)
            for f in found:
                c[f["kind"]] += 1
                c["missing_while_buggy_present"] += f["buggy_present"]
            if any(f["kind"] == "proofread" for f in found):
                c["runs_with_proofread"] += 1
                solved[run.get("solved")] += 1
                if len(examples) < 3:
                    examples.append((os.path.basename(path), next(f["old"] for f in found if f["kind"] == "proofread")))
            c["runs"] += 1
        print(f"== {folder}\n  {dict(c)}\n  runs with proofread, solved: {dict(solved)}")
        for name, old in examples:
            print(f"  e.g. {name}: {old[:160]!r}")


if __name__ == "__main__":
    main()
