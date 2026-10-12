"""Declared step after the blind labels of PREMESSA_MODIFICHE §7.4: objective facts from the FULL logs of the sampled
incidents, where the 400-character window of the sample was not enough. No judgement here, only facts.

    python -I aggiudica_campione.py

- noop: whether the full editor message says "must be different".
- never_seen: where the searched text S (the failed old_str) or its lines appeared before the call, anywhere in the
  log: in full in an earlier tool output of any tool and path (line numbers removed), in an earlier text the agent
  wrote successfully (new_str, file_text), or as an earlier failed old_str of the same file; and the lines of S of at
  least 8 characters that never appeared before in a tool output or a written text.
- known_bad_retry and circle: the message index and command of the failing call named by known_bad and replaced_bad,
  whether its full result contains the failing line, and the kind of command: "repo_tests" (runtests.py, or pytest or
  unittest naming a path with test/ or tests/), "inline" (python -c, one line or more), "agent_script" (a .py file
  that the agent created earlier in the run with the editor) or "other" (any other Python command, such as a module
  run with -m or an example program).
Writes verifica_aggiudicazione.json next to the sample, with a summary, with "\\n" line ends on every system.
"""

import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

SAMPLE = os.path.join(misura.OUT_DIR, "verifica_campione.json")
OUT = os.path.join(misura.OUT_DIR, "verifica_aggiudicazione.json")


def load_runs(wanted):
    """{(set, run id): messages} for the wanted pairs only."""
    found = {}
    for set_name, kind, where in misura.PARTS["heldout"]:
        if not any(s == set_name for s, _ in wanted):
            continue
        runs = (formati.swehero(where) if kind == "swehero" else
                formati.openhands_events(where[0], formati.load_outcomes(where[1])))
        for run in runs:
            if (set_name, run["id"]) in wanted:
                found[(set_name, run["id"])] = run["messages"]
                if all(w in found for w in wanted if w[0] == set_name):
                    break
    return found


def edit_call(msgs, step, category):
    for f in R.edit_failures(msgs):
        if f["step"] == step and category in (f["error"], f.get("kind")):
            return f["call"]
    return None


def never_seen_facts(cl, k):
    _, _, args, _ = cl[k]
    s, p = args.get("old_str") or "", args.get("path")
    outputs, written, failed_old = [], [], []
    for _, name, a, obs in cl[:k]:
        outputs.append(R.LINE_NO.sub("", obs or ""))
        if name != "str_replace_editor":
            continue
        cmd = a.get("command")
        ok = R.result_kind(cmd, obs) == "ok"
        if ok and cmd in ("str_replace", "insert"):
            written.append(a.get("new_str") or "")
        elif ok and cmd == "create":
            written.append(a.get("file_text") or "")
        elif cmd == "str_replace" and a.get("path") == p:
            failed_old.append(a.get("old_str") or "")
    texts = outputs + written
    seen = set().union(*(R.lines(x) for x in texts)) if texts else set()
    unseen = sorted(R.lines(s) - seen)
    return {"in_tool_output": any(s in x for x in outputs), "in_written": any(s in x for x in written),
            "squashed_in_tool_output_or_written": any(R.squash(s) in R.squash(x) for x in texts),
            "same_as_earlier_failed_old_str": s in failed_old, "lines": len(R.lines(s)),
            "lines_never_shown_before": len(unseen), "examples_never_shown": [x[:100] for x in unseen[:3]]}


SCRIPT = re.compile(r"(?:python[0-9.]*|pytest)\s+(?:-m\s+pytest\s+)?(?:\S*/)?([\w.-]+\.py)\b")


def command_kind(command, created):
    if "runtests.py" in command or (re.search(r"pytest|unittest", command) and re.search(r"tests?/", command)):
        return "repo_tests"
    if re.search(r"python[0-9.]*\s+-c\b", command):
        return "inline"
    script = SCRIPT.search(command)
    return "agent_script" if script and script.group(1) in created else "other"


def failure_facts(cl, bad):
    if not bad:
        return None
    i, _, args, obs = cl[bad[0]]
    command = str(args.get("command", ""))
    created = {os.path.basename(a.get("path") or "") for _, name, a, o in cl[:bad[0]]
               if name == "str_replace_editor" and a.get("command") == "create" and R.result_kind("create", o) == "ok"}
    return {"message": i, "command": command[:160], "kind": command_kind(command, created),
            "line_in_result": bad[2] in (obs or "")}


def summary(out):
    ns = [r for r in out if r["category"] == "never_seen"]
    bad = [r for r in out if r["category"] in ("known_bad_retry", "circle")]
    return {
        "noop_must_be_different": sum(r["must_be_different"] for r in out if r["category"] == "noop"),
        "multiple_message": sum(r["multiple_occurrences"] for r in out if r["category"] == "multiple"),
        "never_seen": {"cases": len(ns),
                       "seen_in_full_anywhere": sum(r["in_tool_output"] or r["in_written"] for r in ns),
                       "all_lines_shown_before": sum(r["lines_never_shown_before"] == 0 and not
                                                     (r["in_tool_output"] or r["in_written"]) for r in ns),
                       "some_line_never_shown": sum(r["lines_never_shown_before"] > 0 for r in ns)},
        "failure_lines_found": sum(r[x]["line_in_result"] for r in bad for x in ("known_bad", "replaced_bad") if r[x]),
        "known_bad_kind": dict(collections.Counter(r["known_bad"]["kind"] for r in bad)),
        "replaced_bad_kind": dict(collections.Counter(r["replaced_bad"]["kind"] for r in bad if r["replaced_bad"])),
        "project_changed": sum(r["project_changed"] for r in bad),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(SAMPLE, encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    runs = load_runs({(it["set"], it["run"]) for it in items})
    out = []
    for it in items:
        msgs = runs[(it["set"], it["run"])]
        cl = list(R.calls(msgs))
        row = {"n": it["n"], "category": it["category"]}
        if it["category"] in ("known_bad_retry", "circle"):
            ev = next(e for e in R.revisits(msgs) if e["step"] == it["step"])
            row["known_bad"] = failure_facts(cl, ev["known_bad"])
            row["replaced_bad"] = failure_facts(cl, ev["replaced_bad"])
            row["project_changed"] = ev["project_changed"]
        else:
            k = edit_call(msgs, it["step"], it["category"])
            obs = cl[k][3] or ""
            if it["category"] == "noop":
                row["must_be_different"] = "must be different" in obs
            elif it["category"] == "multiple":
                row["multiple_occurrences"] = "ultiple occurrences" in obs
            elif it["category"] == "never_seen":
                row.update(never_seen_facts(cl, k))
            elif it["category"] == "stale":
                row["did_not_appear_verbatim"] = "did not appear verbatim" in obs
        out.append(row)
    result = {"summary": summary(out), "items": out}
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    for row in out:
        if row["category"] in ("known_bad_retry", "circle"):
            print(row["n"], row["category"], "known_bad:", row["known_bad"]["kind"], row["known_bad"]["command"][:90],
                  "| replaced_bad:", row["replaced_bad"] and row["replaced_bad"]["kind"])
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    print("written", OUT)


if __name__ == "__main__":
    main()
