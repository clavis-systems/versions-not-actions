"""Idea 1, "state, not action": what an action graph misses that a version graph sees, on the same runs.

    python -I stato_azione.py swebench --part dev|test [--out file.json]
    python -I stato_azione.py gemma <folder> [--out file.json]

Split (PREMESSA_STATO_AZIONE.md): in each SWE-bench set the runs are sorted by instance id; dev = the first 50,
test = the other 450. The definitions were fixed on dev only.

A run is read as a sequence of tool calls. Two identities are compared:
  action    the call itself: tool name plus its semantic arguments (for the editor: command, path, old_str, new_str,
            file_text, insert_line; for bash: the command). Graphs of agent trajectories in prior work use actions
            as nodes (concrete: the call; abstract: its type).
  state     the content of the edited file, as a SHA-256 of its text, for every file the agent edits. Sources: the
            file before and after each successful edit (OpenHands logs keep both), or an exact replay (agente_gemma
            runs, which start from a known file). A file content seen before an edit that differs from the last known
            one means something else changed it (bash, another tool): it is an untracked change, recorded as such.

Edits are the editor commands str_replace, insert, create and undo_edit. A failed edit never changes the file; a
create without stored contents takes its file_text as the new content; an edit whose content cannot be known is
counted (edits_without_state) and the replay of that file restarts from its next known content.

Counts, per set of runs:
  returns          successful edits that bring a file back to a content it already had earlier in the run (a cycle
                   in the version graph). not_recurrence = the call was not identical to any earlier call of the run:
                   in a graph whose nodes are concrete actions (type + arguments) the return is not a recurrence of a
                   node, so it is not shown as a cycle (the graph may still keep the outcomes and observations).
  stuck_attempts   failed edits (noop, missing, multiple), the file staying at the same content: self-loops of the
                   version graph. not_recurrence = the call was new.
  type_cycles      the abstract projection gives each call one label (EDIT for every edit of any file, VIEW, BASH, or
                   the tool name); every EDIT after the first one is a recurrence of the label, a cycle of the abstract
                   graph. Its edit is: progress (a new content), return (an earlier content), failed, no_change (a
                   successful edit that leaves the same content), or unknown (content not known).
                   known = progress + return + failed + no_change.
Also: calls without a result message or with an empty result, undo edits without a known content (for example
the undo of a create, after which the file is absent), untracked changes and those that go back to an earlier content, undo edits, runs with
at least one return, and, where the outcome is known, resolved runs with and without returns (an association, not a
cause). Only data is read; nothing from the runs is executed.
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402

EDITOR_KEYS = ("command", "path", "old_str", "new_str", "file_text", "insert_line")
FAILED = ("noop", "missing", "multiple")


def h(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def action_key(name, args):
    if name in ("str_replace_editor", "file_editor", "edit_file"):
        return json.dumps([name] + [args.get(k) for k in EDITOR_KEYS], ensure_ascii=False)
    if name in ("execute_bash", "bash"):
        return json.dumps([name, (args.get("command") or "").strip()], ensure_ascii=False)
    return json.dumps([name, args], sort_keys=True, ensure_ascii=False, default=str)


def calls_with_results(messages):
    """[(name, args, result text, result meta)] in order, from the common message shape."""
    results = {m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"}
    out = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            res = results.get(tc.get("id"))
            content = None if res is None else (res.get("content") or "")    # None: no result message at all
            out.append((fn.get("name"), args if isinstance(args, dict) else {}, content, (res or {}).get("meta") or {}))
    return out


MODIFY = ("str_replace", "insert", "create", "undo_edit")
EDITORS = ("str_replace_editor", "file_editor", "edit_file")


def label(name, args):
    """The abstract projection: one label per action type, editor modifications of any file all being EDIT."""
    if name in EDITORS:
        return "EDIT" if args.get("command") in MODIFY else "VIEW" if args.get("command") == "view" else "EDITOR"
    if name in ("execute_bash", "bash"):
        return "BASH"
    return str(name)


def measure(calls, start_states=None):
    """Counters for one run. start_states: {path: initial text} when known (replays); otherwise the first
    file_before of a path is its first known state."""
    c = collections.Counter()
    seen_actions = set()
    current = {p: h(t) for p, t in (start_states or {}).items()}
    history = {p: [s] for p, s in current.items()}
    texts = dict(start_states or {})
    edits_seen = 0
    for name, args, result, meta in calls:
        key = action_key(name, args)
        repeat = key in seen_actions
        seen_actions.add(key)
        if result is None:
            c["calls_without_result_message"] += 1
            result = ""
        elif not result:
            c["calls_with_empty_result"] += 1      # also when the result message has metadata (e.g. its time)
        if label(name, args) != "EDIT":
            continue
        edits_seen += 1
        cycle = edits_seen > 1                    # the EDIT label recurs: a cycle of the abstract graph
        cmd, path = args.get("command"), args.get("path")
        outcome = formati.editor_outcome(result)
        if outcome in FAILED:                     # the file does not change: a self-loop of the version graph
            c["stuck_attempts"] += 1
            c["stuck_not_recurrence"] += not repeat
            c["type_cycles_failed"] += cycle
            continue
        before = meta.get("file_before")
        after = meta.get("file_after")
        if after is None and outcome == "created" and cmd == "create" and args.get("file_text") is not None:
            after = args["file_text"]             # a created file: its content is the file_text of the call
        if after is None and outcome not in ("edited", "created", "undo"):
            c["edits_unrecognised"] += 1
            c["type_cycles_unknown"] += cycle
            continue
        if after is None and path in texts and cmd == "str_replace" and                 texts[path].count(args.get("old_str") or "") == 1:
            before, after = texts[path], texts[path].replace(args.get("old_str") or "", args.get("new_str") or "", 1)
        if after is None:
            c["edits_without_state"] += 1
            c["undo_without_state"] += cmd == "undo_edit"        # e.g. undoing a create: the file is absent
            c["type_cycles_unknown"] += cycle
            current.pop(path, None)
            texts.pop(path, None)
            continue
        if before is not None:
            hb = h(before)
            if path in current and current[path] != hb:
                c["untracked_changes"] += 1
                c["untracked_returns"] += hb in history.get(path, [])     # e.g. git checkout of the file
            if hb not in history.setdefault(path, []):
                history[path].append(hb)
            current[path] = hb
        ha = h(after)
        c["edits_with_state"] += 1
        c["undo_edits"] += cmd == "undo_edit"
        unchanged = ha == current.get(path)
        returned = ha in history.get(path, []) and not unchanged
        c["edits_no_change"] += unchanged
        if cycle:
            c["type_cycles_no_change" if unchanged else "type_cycles_return" if returned
              else "type_cycles_progress"] += 1
        if returned:
            c["returns"] += 1
            c["returns_not_recurrence"] += not repeat
        history.setdefault(path, []).append(ha)
        current[path] = ha
        texts[path] = after
    c["type_cycles_known"] = (c["type_cycles_progress"] + c["type_cycles_return"] + c["type_cycles_failed"]
                              + c["type_cycles_no_change"])
    return c


DEV_RUNS = 50


def runs_swebench(part):
    """openhands_events yields runs sorted by instance id (sorted glob): dev = the first DEV_RUNS, test = the rest."""
    for name, kind, where in misura.PARTS["heldout"]:
        if kind != "openhands":
            continue
        for n, run in enumerate(formati.openhands_events(where[0], formati.load_outcomes(where[1]))):
            if (part == "dev") != (n < DEV_RUNS):
                continue
            yield name, run.get("outcome"), calls_with_results(run["messages"]), None


def runs_gemma(folder):
    import agente_gemma as A
    rows = A.load_rows()
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            run = json.load(fh)
        if "messages" not in run:
            continue
        start = A.build_task(rows, int(run["task"].split("/")[1]))["files"][A.FILE]
        name = "gemma_" + ("on" if run["guard"] else "off")
        outcome = "resolved" if run.get("solved") else "unresolved"
        yield name, outcome, calls_with_results(run["messages"]), {A.FILE: start}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", choices=("swebench", "gemma"))
    p.add_argument("folder", nargs="?")
    p.add_argument("--part", choices=("dev", "test"), default=None)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    if a.source == "swebench" and a.part is None:
        raise SystemExit("--part dev|test is required for swebench")
    runs = runs_swebench(a.part) if a.source == "swebench" else runs_gemma(a.folder)
    totals = collections.defaultdict(collections.Counter)
    per_run = collections.defaultdict(list)
    for set_name, outcome, calls, start in runs:
        c = measure(calls, start)
        per_run[set_name].append(c)
        t = totals[set_name]
        t.update(c)
        t["runs"] += 1
        t["runs_with_return"] += c["returns"] > 0
        if outcome in ("resolved", "unresolved"):
            t[f"{'with' if c['returns'] else 'without'}_return_{outcome}"] += 1
    report = {}
    for s, t in totals.items():
        rs = per_run[s]
        report[s] = {**dict(t),
                     "S1_returns_not_recurrence": misura.rate([r["returns_not_recurrence"] for r in rs],
                                                              [r["returns"] for r in rs]),
                     "S2_stuck_not_recurrence": misura.rate([r["stuck_not_recurrence"] for r in rs],
                                                            [r["stuck_attempts"] for r in rs]),
                     "S3_type_cycles_progress": misura.rate([r["type_cycles_progress"] for r in rs],
                                                            [r["type_cycles_known"] for r in rs])}
        print(s, json.dumps(report[s]), flush=True)
    if a.out:
        with open(a.out, "x", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)


if __name__ == "__main__":
    main()
