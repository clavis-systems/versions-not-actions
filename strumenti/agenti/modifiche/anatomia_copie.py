"""Idea 2, "anatomy of copy errors": how does an agent's old_str differ from the real text when an edit fails?

    python -I anatomia_copie.py swebench [--limit N]          # OpenHands Qwen3-Coder 30B and 480B (already seen)
    python -I anatomia_copie.py swehero dev|heldout [--limit N]
    python -I anatomia_copie.py gemma <folder>                 # runs of agente_gemma.py

Cases: str_replace calls that failed with "did not appear verbatim" (missing), whose old_str is not verbatim in any
text the agent saw of that file, nor (stripped) in any earlier tool output of the run, whatever the tool (that would
be a stale view, possibly through a read we do not reconstruct, not a copy error), and is a near copy of such a text:
the best window with EXACTLY as many lines as old_str (blank lines, empty or only spaces, at its edges are ignored;
lines compared without their spaces at the ends) has difflib
similarity >= 0.8. Texts seen: editor views, snippets after edits, own created files and new_str, and clean bash
reads: the WHOLE command, on one line, is cat/nl [-flags], head/tail [-n N] or sed -n 'A,Bp' followed by exactly
one absolute path and nothing else (CLEAN_READ). Earlier tool output means every tool message before the current
model response. A model response's results, and its bash commands, count only after all the calls of that
response. The window is searched in the 6 most recent distinct texts.
Each case gets ONE class:
  whitespace_only every difference is in whitespace or blank lines (not always harmless: indentation is code);
  lines_only      the copy has non-blank lines added or dropped, the lines in common are equal;
  content         at least one line pair differs in words or symbols (names, literals, quotes, comments, code).
Each differing non-blank line of the copy that is not in the real window is: seen_line if an equal line of 12+
characters appears anywhere in the texts the agent saw of that file (a lexical match, which does not prove where
it was copied from), unseen_line if not, trivial if shorter than 12 characters.
possibly_seen_otherwise: an earlier bash command that is not a clean single-file read but prints content (cat, head,
tail, nl, sed, awk, grep, rg, less, more, python, git diff/show/log -p) mentions the file name, so the agent may
have seen text we cannot reconstruct; A1 is also reported without these cases.
Only data is read; nothing from the runs is executed.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

NEAR, TRIVIAL = 0.8, 12
PRINTS = re.compile(r"\b(cat|head|tail|nl|sed|awk|grep|rg|less|more|python3?|git\s+(diff|show|log\s+-p))\b")
# a clean read: the WHOLE command is one of these forms, on one line, with one absolute path and nothing else
CLEAN_READ = re.compile(r"^[ \t]*(?:(?:cat|nl)(?:[ \t]+-[A-Za-z]+)*"
                        r"|(?:head|tail)(?:[ \t]+-[nc][ \t]*\+?\d+|[ \t]+-\d+)?"
                        r"|sed[ \t]+-n[ \t]+['\"]?\d+(?:,\d+)?p['\"]?)[ \t]+(/[\w./-]+)[ \t]*$")


def best_window(s, texts):
    """Best window with exactly as many lines as old_str (texts with fewer lines are skipped)."""
    want = s.splitlines()
    while want and not want[0].strip():                  # blank lines at the edges (empty or only spaces)
        want.pop(0)
    while want and not want[-1].strip():
        want.pop()
    key = "\n".join(x.strip() for x in want)
    best, found = 0.0, None
    for t in texts:
        lines = t.splitlines()
        for start in range(0, len(lines) - len(want) + 1):
            window = lines[start:start + len(want)]
            m = difflib.SequenceMatcher(None, key, "\n".join(x.strip() for x in window), autojunk=False)
            if m.real_quick_ratio() <= best or m.quick_ratio() <= best:
                continue
            r = m.ratio()
            if r > best:
                best, found = r, window
    return best, found, want


def squeeze(line):
    return "".join(line.split())


def classify(real, copy, seen):
    """(case class, Counter of the copy's differing non-blank lines: seen_line / unseen_line / trivial)."""
    prov = collections.Counter()
    words_differ = lines_differ = False
    sm = difflib.SequenceMatcher(None, [x.strip() for x in real], [x.strip() for x in copy], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        a, b = real[i1:i2], copy[j1:j2]
        nonblank_a = [x for x in a if x.strip()]
        nonblank_b = [x for x in b if x.strip()]
        if [squeeze(x) for x in nonblank_a] == [squeeze(x) for x in nonblank_b]:
            continue                                   # only whitespace or blank lines differ here
        if tag == "replace" and nonblank_a and nonblank_b:
            words_differ = True
        else:
            lines_differ = True
        for x in nonblank_b:
            if squeeze(x) in {squeeze(y) for y in nonblank_a}:
                continue
            t = x.strip()
            prov["trivial" if len(t) < TRIVIAL else "seen_line" if t in seen else "unseen_line"] += 1
    if words_differ:
        return "content", prov
    if lines_differ:
        return "lines_only", prov
    return "whitespace_only", prov


def cases(messages):
    """[(case class, provenance Counter, possibly_seen_otherwise)]. The texts seen by the agent grow only after the
    whole model response that produced them: calls of one response cannot see each other's results."""
    texts = collections.defaultdict(list)
    other_mentions = []                                # bash commands that print content we do not reconstruct
    pending, out = [], []
    tool_results = [(j, R.LINE_NO.sub("", m.get("content") or "")) for j, m in enumerate(messages)
                    if m.get("role") == "tool" and isinstance(m.get("content"), str)]
    response_start, last_message = -1, None

    pending_mentions = []

    def flush():
        for p, t in pending:
            texts[p].append(t)
        pending.clear()
        other_mentions.extend(pending_mentions)          # also known only after the response
        pending_mentions.clear()

    for k, (i, name, a, obs) in enumerate(R.calls(messages)):
        # a new model response starts at a new assistant message, unless that message continues the previous
        # response (meta.shared_response); calls of the same message are always the same response
        if i != last_message and not (messages[i].get("meta") or {}).get("shared_response"):
            flush()
            response_start = i
        last_message = i
        if name == "execute_bash":
            command = a.get("command") or ""
            clean = CLEAN_READ.match(command)
            if clean:
                pending.append((clean.group(1), R.LINE_NO.sub("", obs or "")))
            elif PRINTS.search(command):
                pending_mentions.append(command)   # prints file content in a way we do not reconstruct
            continue
        if name != "str_replace_editor":
            continue
        cmd, p = a.get("command"), a.get("path")
        kind = R.result_kind(cmd, obs)
        old = a.get("old_str") or ""
        # verbatim in a text seen of this file, or in ANY earlier tool output (a read we do not reconstruct):
        # a stale view, not a copy error from memory
        stale = any(old in t for t in texts[p]) or \
            any(old.strip() in t for j, t in tool_results if j < response_start)
        if cmd == "str_replace" and kind == "missing" and texts[p] and old.strip() and not stale:
            recent = list(dict.fromkeys(reversed(texts[p])))[:6]     # the 6 most recent distinct texts
            ratio, window, want = best_window(old, recent)
            if window is not None and ratio >= NEAR:
                seen = {x.strip() for t in texts[p] for x in t.splitlines() if len(x.strip()) >= TRIVIAL}
                base = os.path.basename(p or "") or "<no path>"
                maybe = any(base in c for c in other_mentions)
                cls, prov = classify(window, want, seen)
                out.append((cls, prov, maybe))
        if kind == "ok":
            if cmd == "view":
                pending.append((p, R.LINE_NO.sub("", obs or "")))
            elif cmd == "create":
                pending.append((p, a.get("file_text") or ""))
            elif cmd in ("str_replace", "insert"):
                pending += [(p, a.get("new_str") or ""), (p, R.LINE_NO.sub("", obs or ""))]
    return out


def sources(a):
    if a.source == "swebench":
        for name, kind, where in misura.PARTS["heldout"]:
            if kind == "openhands":
                yield name, formati.openhands_events(where[0], formati.load_outcomes(where[1]))
    elif a.source == "swehero":
        if a.where not in ("dev", "heldout"):
            raise SystemExit("swehero needs dev or heldout")
        part = misura.PARTS["dev"][0] if a.where == "dev" else misura.PARTS["heldout"][0]
        yield part[0], formati.swehero(part[2])
    else:
        if not a.where or not os.path.isdir(a.where):
            raise SystemExit("gemma needs the folder of the runs")
        runs = []
        for path in sorted(glob.glob(os.path.join(a.where, "*.json"))):
            with open(path, encoding="utf-8") as fh:
                run = json.load(fh)
            if "messages" in run:
                runs.append(run)
        for cond in (False, True):
            yield f"gemma_{'on' if cond else 'off'}", [r for r in runs if r["guard"] == cond]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", choices=("swebench", "swehero", "gemma"))
    p.add_argument("where", nargs="?", help="swehero: dev or heldout; gemma: the folder of the runs")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    report = {}
    for name, runs in sources(a):
        classes, prov, n, per_run, maybe = collections.Counter(), collections.Counter(), 0, [], collections.Counter()
        for k, run in enumerate(runs):
            if a.limit is not None and k >= a.limit:
                break
            n += 1
            rc, rp, rc_clean = collections.Counter(), collections.Counter(), collections.Counter()
            for cls, pr, possibly_seen in cases(run["messages"]):
                rc[cls] += 1
                rp.update(pr)
                maybe[cls] += possibly_seen
                if not possibly_seen:
                    rc_clean[cls] += 1
            classes.update(rc)
            prov.update(rp)
            if rc:
                per_run.append((rc, rp, rc_clean))
        report[name] = {
            "runs": n, "runs_with_cases": len(per_run), "near_copies": sum(classes.values()),
            "classes": dict(classes), "possibly_seen_otherwise": dict(maybe), "copy_lines_not_in_file": dict(prov),
            "A1_whitespace_only": misura.rate([c["whitespace_only"] for c, _, _ in per_run],
                                              [sum(c.values()) for c, _, _ in per_run]),
            "A1_sensitivity_without_possibly_seen": misura.rate([c["whitespace_only"] for _, _, c in per_run],
                                                                [sum(c.values()) for _, _, c in per_run]),
            "A2_seen_lines": misura.rate([q["seen_line"] for _, q, _ in per_run],
                                         [q["seen_line"] + q["unseen_line"] for _, q, _ in per_run])}
        r = report[name]
        print(json.dumps({"set": name, "runs": n, "near_copies": r["near_copies"], "classes": r["classes"],
                          "possibly_seen_otherwise": r["possibly_seen_otherwise"], "lines": r["copy_lines_not_in_file"],
                          **{k: {f: r[k][f] for f in ("num", "den", "value", "ci95", "invalid_replicates")}
                             for k in ("A1_whitespace_only", "A1_sensitivity_without_possibly_seen",
                                       "A2_seen_lines")}}), flush=True)
    if a.out:
        with open(a.out, "x", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)


if __name__ == "__main__":
    main()
