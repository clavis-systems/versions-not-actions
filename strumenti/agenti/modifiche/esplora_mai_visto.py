"""EXPLORATORY, after the frozen run (not part of PREMESSA_MODIFICHE.md): where does the "never seen" text come from?

For every str_replace that fails with "did not appear verbatim" and whose old_str S was never observed in the log
(rilevatori.edit_failures kind never_seen), one origin is assigned, checked in this order:
  own_failed_edit  norm(S) is inside the new_str of an earlier FAILED str_replace of the same file: the agent acts
                   as if its failed edit had been applied;
  from_issue       at least half of the lines of S (with 8+ characters) appear in the first user message, the task
                   description;
  near_copy        some earlier text of the file (views, snippets, bash reads, own writes) has a window of as many
                   lines whose similarity with S (difflib ratio, lines stripped) is at least 0.8: written from memory;
  file_never_seen  the file was never viewed or written before;
  other.
For near_copy the best window is also the hint a host could show ("the closest text is lines ...").

    python -I esplora_mai_visto.py dev               # SWE-Hero shards 0-3
    python -I esplora_mai_visto.py swebench          # the two OpenHands Qwen sets, exploratory after the run
"""

import collections
import difflib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

THRESHOLD = 0.8


def strip_lines(text):
    return [x.strip() for x in text.splitlines() if x.strip()]


def best_window(s, texts):
    target = strip_lines(s)
    if not target:
        return 0.0
    joined, n, best = "\n".join(target), len(target), 0.0
    for t in texts:
        lines = strip_lines(t)
        for start in range(0, max(1, len(lines) - n + 1)):
            window = "\n".join(lines[start:start + n])
            m = difflib.SequenceMatcher(None, joined, window, autojunk=False)
            if m.real_quick_ratio() <= best or m.quick_ratio() <= best:
                continue
            best = max(best, m.ratio())
    return best


def origins(messages):
    issue = next((m.get("content") for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
    issue_lines = set(strip_lines(issue))
    texts = collections.defaultdict(list)
    failed_new = collections.defaultdict(list)
    out = []
    events = {e["call"]: e for e in R.edit_failures(messages) if e.get("kind") == "never_seen"}
    for k, (i, name, a, obs) in enumerate(R.calls(messages)):
        if name != "str_replace_editor":
            if name == "execute_bash" and R.READS.search(a.get("command") or ""):
                for p in R.PATHS.findall(a.get("command") or ""):
                    texts[p].append(R.LINE_NO.sub("", obs))
            continue
        cmd, p = a.get("command"), a.get("path")
        kind = R.result_kind(cmd, obs)
        if k in events:
            s = a.get("old_str") or ""
            long = [x for x in strip_lines(s) if len(x) >= 8]
            if any(R.norm(s) and R.norm(s) in R.norm(n) for n in failed_new[p]):
                origin = "own_failed_edit"
            elif long and sum(x in issue_lines for x in long) * 2 >= len(long):
                origin = "from_issue"
            elif texts[p] and best_window(s, texts[p]) >= THRESHOLD:
                origin = "near_copy"
            elif not texts[p]:
                origin = "file_never_seen"
            else:
                origin = "other"
            out.append(origin)
        if kind == "ok":
            if cmd == "view":
                texts[p].append(R.LINE_NO.sub("", obs))
            elif cmd == "create":
                texts[p].append(a.get("file_text") or "")
            elif cmd in ("str_replace", "insert"):
                texts[p] += [a.get("new_str") or "", R.LINE_NO.sub("", obs)]
        elif cmd == "str_replace" and kind in ("missing", "multiple", "other"):
            failed_new[p].append(a.get("new_str") or "")
    return out


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else ""
    if part == "dev":
        sources = [("swehero_dev", formati.swehero(misura.PARTS["dev"][0][2]))]
    elif part == "swebench":
        sources = [(name, formati.openhands_events(where[0], formati.load_outcomes(where[1])))
                   for name, kind, where in misura.PARTS["heldout"] if kind == "openhands"]
    else:
        sys.exit("usage: python -I esplora_mai_visto.py dev|swebench")
    for name, runs in sources:
        c = collections.Counter()
        for run in runs:
            c.update(origins(run["messages"]))
        total = sum(c.values())
        print(f"{name}: {total} never-seen failures |", {k: f"{v} ({100 * v / total:.0f}%)" for k, v in c.most_common()})


if __name__ == "__main__":
    main()
