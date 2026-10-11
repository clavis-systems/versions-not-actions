"""EXPLORATORY (11/10/2026, not part of any frozen premise): quick checks of three candidate ideas for the paper.

    python -I esplora_idee.py dev|swebench [--limit N]

  anatomy    For each "never seen" failed str_replace whose old_str is a near copy (difflib >= 0.8, lines compared
             stripped) of text the agent saw earlier in the same file: how does the agent's copy differ from the real
             lines? Each differing line pair gets one class: blank_indent (a blank line with spaces on one side),
             indent, trailing_ws, inner_space (only spaces inside the line), quotes (only ' versus "), comment,
             identifier (same skeleton, other names), literal (other numbers or strings), other; plus lines only in
             the copy (added) or only in the file (dropped).
  repeat     For each failed str_replace: was the identical call (same path, old_str, new_str) already sent and failed
             earlier in the run, with no successful edit of that path in between (the same version, as far as the
             log shows)? And: is the call right after a failure an identical repeat?
  regress    For each run: did a test command (pytest, unittest, tox... not any python script) pass at some point and the same command fail later, with an
             edit in between, and was the last run of that command a failure (a passing state lost)?

Only data is read; nothing from the runs is executed.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

NEAR = 0.8
STRICT_TEST = re.compile(r"pytest|unittest|\btox\b|\bnose|make test|npm test|go test|cargo test|runtests|manage\.py test")
WORD = re.compile(r"[A-Za-z_]\w*")
NUM_STR = re.compile(r"\d+(\.\d+)?|'[^']*'|\"[^\"]*\"")


def stripped(lines):
    return [x.strip() for x in lines]


def best_raw_window(s, texts):
    """(ratio, raw lines of the best window) over the texts seen, comparing stripped lines, blank lines kept."""
    want = s.strip("\n").splitlines()
    key = "\n".join(stripped(want))
    best, found = 0.0, None
    for t in texts:
        lines = t.splitlines()
        for start in range(0, max(1, len(lines) - len(want) + 1)):
            window = lines[start:start + len(want)]
            m = difflib.SequenceMatcher(None, key, "\n".join(stripped(window)), autojunk=False)
            if m.real_quick_ratio() <= best or m.quick_ratio() <= best:
                continue
            r = m.ratio()
            if r > best:
                best, found = r, window
    return best, found, want


def line_class(real, copy):
    if real.strip() == copy.strip():
        if not real.strip():
            return "blank_indent"
        if real.lstrip() == copy.lstrip() and real != copy and real.rstrip() == real and copy.rstrip() == copy:
            return "indent"
        if real.rstrip() == copy.rstrip():
            return "trailing_ws"
        return "indent"
    if real.replace(" ", "").replace("\t", "") == copy.replace(" ", "").replace("\t", ""):
        return "inner_space"
    if real.replace('"', "'") == copy.replace('"', "'"):
        return "quotes"
    if "#" in real or "#" in copy:
        if real.split("#")[0].strip() == copy.split("#")[0].strip():
            return "comment"
    if WORD.sub("N", NUM_STR.sub("L", real)).strip() == WORD.sub("N", NUM_STR.sub("L", copy)).strip():
        return "identifier" if WORD.findall(real) != WORD.findall(copy) else "literal"
    if NUM_STR.sub("L", real).strip() == NUM_STR.sub("L", copy).strip():
        return "literal"
    return "other"


def anatomy(real_lines, copy_lines, seen=frozenset()):
    """Differing line classes; a copied line that differs and is found elsewhere in the text the agent saw of that
    file is marked _from_elsewhere (spliced), otherwise it is new (not seen anywhere)."""
    out = collections.Counter()
    sm = difflib.SequenceMatcher(None, real_lines, copy_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        real, copy = real_lines[i1:i2], copy_lines[j1:j2]
        for a, b in zip(real, copy):
            kind = line_class(a, b)
            if kind == "other":
                kind = "other_from_elsewhere" if b.strip() in seen else "other_new"
            out[kind] += 1
        if len(copy) > len(real):
            extra = copy[len(real):]
            for x in extra:
                out["added_blank" if not x.strip() else "added_from_elsewhere" if x.strip() in seen else "added_new"] += 1
        if len(real) > len(copy):
            gone = real[len(copy):]
            out["dropped_blank" if all(not x.strip() for x in gone) else "dropped"] += len(gone)
    return out


def run_checks(messages):
    texts = collections.defaultdict(list)
    never = {e["call"] for e in R.edit_failures(messages) if e.get("kind") == "never_seen"}
    failed_since_edit = collections.defaultdict(set)      # path -> {(old, new)} failed since the last good edit
    anat, cases = collections.Counter(), collections.Counter()
    rep = collections.Counter()
    tests = collections.defaultdict(list)                 # command -> [(call, failed)]
    edits_at = []
    prev_failed = False
    for k, (i, name, a, obs) in enumerate(R.calls(messages)):
        if name == "execute_bash":
            cmd = a.get("command") or ""
            if R.READS.search(cmd):
                for p in R.PATHS.findall(cmd):
                    texts[p].append(R.LINE_NO.sub("", obs or ""))
            if STRICT_TEST.search(cmd) and obs:
                tests[cmd.strip()].append((k, R.failed(obs)))
            prev_failed = False
            continue
        if name != "str_replace_editor":
            prev_failed = False
            continue
        cmd, p = a.get("command"), a.get("path")
        kind = R.result_kind(cmd, obs)
        if cmd == "str_replace" and kind in ("noop", "missing", "multiple"):
            pair = (a.get("old_str") or "", a.get("new_str") or "")
            same = pair in failed_since_edit[p]
            rep["failed"] += 1
            rep["identical_repeat_same_version"] += same
            if prev_failed:
                rep["right_after_a_failure"] += 1
                rep["right_after_a_failure_identical"] += same
            failed_since_edit[p].add(pair)
            if k in never and texts[p]:
                recent = list(dict.fromkeys(texts[p]))[-6:]
                ratio, window, want = best_raw_window(pair[0], recent)
                if window is not None and ratio >= NEAR:
                    cases["near_copy"] += 1
                    seen = {x.strip() for t in texts[p] for x in t.splitlines() if x.strip()}
                    found = anatomy(window, want, seen)
                    anat.update(found)
                    if found and set(found) <= {"blank_indent", "indent", "trailing_ws", "inner_space",
                                                "added_blank", "dropped_blank"}:
                        cases["whitespace_only"] += 1
            prev_failed = True
        else:
            prev_failed = False
        if kind == "ok":
            if cmd == "view":
                texts[p].append(R.LINE_NO.sub("", obs or ""))
            elif cmd == "create":
                texts[p].append(a.get("file_text") or "")
            elif cmd in ("str_replace", "insert"):
                texts[p] += [a.get("new_str") or "", R.LINE_NO.sub("", obs or "")]
                failed_since_edit[p].clear()
                edits_at.append(k)
    regress = None
    for cmd, seq in tests.items():
        passed = [c for c, f in seq if not f]
        if passed and seq[-1][1] and any(passed[0] < e < seq[-1][0] for e in edits_at):
            regress = True
            break
        if passed:
            regress = regress or False
    return anat, cases, rep, regress


def main():
    p = argparse.ArgumentParser()
    p.add_argument("part", choices=("dev", "swebench"))
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args()
    if a.part == "dev":
        sources = [("swehero_dev", formati.swehero(misura.PARTS["dev"][0][2]))]
    else:
        sources = [(name, formati.openhands_events(where[0], formati.load_outcomes(where[1])))
                   for name, kind, where in misura.PARTS["heldout"] if kind == "openhands"]
    for name, runs in sources:
        anat, cases, rep = collections.Counter(), collections.Counter(), collections.Counter()
        reg = collections.Counter()
        for n, run in enumerate(runs):
            if a.limit is not None and n >= a.limit:
                break
            x, c, r, g = run_checks(run["messages"])
            anat.update(x)
            cases.update(c)
            rep.update(r)
            reg["runs"] += 1
            if g is not None:
                reg["runs_with_a_passing_test"] += 1
                reg["lost_a_passing_state"] += g
                if run.get("outcome") is not None:
                    reg[f"lost_and_resolved={run['outcome']}"] += g
        total = sum(anat.values()) or 1
        print(f"== {name}")
        print("  near copies:", dict(cases))
        print("  differing lines:", {k: f"{v} ({100 * v / total:.0f}%)" for k, v in anat.most_common()})
        print("  repeats:", dict(rep))
        print("  regressions:", dict(reg), flush=True)


if __name__ == "__main__":
    main()
