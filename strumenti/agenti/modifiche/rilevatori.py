"""Detectors of failed and wasted edits in coding-agent trajectories, version 3 (read only, nothing is executed).

Every detector reads one trajectory in the common message shape of formati.py and only looks at tool calls and
their results. A path P is a file as the agent names it. Order is the call number: calls with JSON-object arguments
counted from 0 in message order and, within a message, in call order ("step" is the message index, kept for
reading the context). Costs are counted in calls.

Results (pair()). When every call and every following tool message has an id and the ids are unique, results are
paired by id; otherwise the k-th tool message goes with the k-th call when their numbers match; otherwise every
result is missing. An editor result is "ok" only when the editor's success message matches the command (edited for
str_replace and insert, created, view, undone); the errors are noop ("must be different"), missing ("did not
appear verbatim"), multiple ("Multiple occurrences") and other; anything else, including a missing result, is
"unknown" and is counted apart, never as a success.

1. edit_failures: every str_replace that is not ok (an unknown outcome is listed with error "unknown"). For a
   missing old_str S, the evidence on what the agent had seen of P: texts(P) are the earlier successful views of P
   (line numbers removed), the snippets shown after its edits, bash reads of P (cat, head, tail, sed -n, nl with P
   named in the command, also when P was never seen before, unless the command may also write; line numbers
   removed) and every text the agent wrote into P. P counts as modified by its own edits, by changes of P with an
   unknown outcome, by bash commands that may write it (write_targets), and by bash writes that cannot be
   identified (all known paths).
     stale              S is in an earlier text of P, and P was modified after the last text containing S;
     copy_error         S is in no earlier text, but it is once the whitespace of every line is normalized;
     seen_not_modified  S is in an earlier text and P was not modified since;
     never_seen         none of the above ("not observed in the log", which does not mean invented).
2. noops: every no-op str_replace on P with text S, by cause, checked in this order
     already_applied  S equals the new_str of an earlier successful str_replace of P;
     repeat_attempt   the same (P, S) no-op was attempted before;
     after_failure    the last bash command before it had failed (failed());
     other.
   Cost: tool calls after the no-op up to the next successful str_replace, insert or create of P, that call
   included (None if there is none). Fate: same_spot if a later successful str_replace of P has an old_str sharing a
   line of at least 8 characters with S, elsewhere if P is edited later only at other spots, never otherwise.
3. reverts: a successful str_replace that undoes an earlier successful one of P, exactly or inside a larger
   window; "debug" when every changed line is a print, log or debugger line, else "flip_flop". Also counted:
   successful str_replace calls, the ones that only change whitespace, and undo_edit calls.
4. revisits (version memory). A block is the text of a successful str_replace's old_str or new_str after norm(),
   with a line of at least 8 characters; its identity is that text within one path.
   - Presence is certain (prudent rule) from the call at which the agent wrote the block with a successful
     str_replace until the next change of P of any kind: any other successful str_replace, insert, create or
     undo_edit of P, a change of P with an unknown outcome, a bash command that may write P, or a bash write that
     cannot be identified. A block removed by the first change of a path that nothing had changed before is
     original text, present with certainty since the start. Any other removed block has an uncertain interval.
   - Provenance is fixed at the first sighting: original, agent, or uncertain. A later return to an original block
     stays back_to_original even after the agent wrote it again.
   - Every removal of a block adds one presence interval (a "life") to its history.
   - A successful edit whose new block equals a block removed earlier from the same path is a revisit:
     back_to_original, retry_own or uncertain_provenance.
   - known_bad: take the most recent certain life in which a test-like command (TESTLIKE) ran; known_bad is the
     last failing one of those commands (failed()), or None if they all passed. Its failing line is the last result
     line matching FAIL, cut to 120 characters. The failure is "infra" if that line matches INFRA, "unknown" if the
     line is empty, else "application".
   - replaced_bad: the same for the block that the revisit removes. project_changed: between the last removal of
     the block and the revisit there was a bash command that may write (any target), or a change of another path.
   - again (retry_own): calls until a later successful str_replace of P removes the block again.
5. intent: the reasoning window of a call (window()) and whether it declares a deliberate return (DECLARED).
6. remembers: for a revisit with a known_bad line, whether the window names, as a whole word, an error
   (FooError, FooException) or a test (test_foo) of that line. None when there is no such name.
"""

import collections
import json
import re

from formati import editor_outcome

FAIL = re.compile(r"Traceback|FAILED|AssertionError|Error:|error:|Exception")
LINE_NO = re.compile(r"^ *\d+\t", re.M)
OTHER_WRITES = re.compile(r"sed\s+-i|\btee\b|\bmv\b|\bcp\b|git\s+(checkout|stash|apply|reset|restore|pull|merge)|"
                          r"\bpatch\b|open\([^)]*['\"][wa]|write_text|\bperl\s+-pi|\bblack\b|\bisort\b|\bautopep8\b")
FD_DUP = re.compile(r"\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/null")
READS = re.compile(r"^\s*(cat|head|tail|sed\s+-n|nl)\b")
PATHS = re.compile(r"(/[\w.\-/]+\.\w+)")
REDIRECT = re.compile(r">>?\s*([^\s|;&<>]+)")
DEBUG = re.compile(r"^\s*(print\(|logging\.|logger\.|log\.|import pdb|pdb\.|breakpoint\(|sys\.std(err|out)\.write"
                   r"|console\.log|#\s*DEBUG|traceback\.print)")
TESTLIKE = re.compile(r"pytest|python|unittest|tox|nose|make test|npm test|go test|cargo test")
EXIT = re.compile(r"exit code (-?\d+)")
DECLARED = re.compile(
    r"\brevert|\bundo|\bundid|\brestor|roll(ing|ed)? ?back|go(ing)? back|went back|\bback to (the |my |our )?"
    r"(original|previous|old|earlier|initial|prior)|(original|previous|old|earlier|initial|prior) (code|version|"
    r"implementation|approach|fix|logic|behaviou?r|state|change|condition|line)|(put|change|switch|move|add|bring)"
    r"(ing|ed)? (it |this |that |them |these |those )?back|re-?appl|temporar", re.I)
ERRORS = {"noop": "noop", "missing": "missing", "multiple": "multiple", "other_error": "other"}
OK_RESULT = {"str_replace": "edited", "insert": "edited", "create": "created", "view": "view", "undo_edit": "undo"}
ERROR_NAMES = re.compile(r"\b[A-Z]\w*(?:Error|Exception)\b|\btest_\w+")
INFRA = re.compile(r"ModuleNotFoundError|No module named|command not found|[Tt]imed? ?out|Killed|Permission denied|"
                   r"No such file or directory|ConnectionError|MemoryError")
CHANGES = ("create", "insert", "str_replace", "undo_edit")


def pair(messages, i):
    """The results of the calls of message i, in call order, and how they were paired: "id" when every call and
    every following tool message has an id and the ids are unique, else "position" when the numbers match, else
    "none" (every result missing)."""
    tcs = messages[i].get("tool_calls") or []
    results, j = [], i + 1
    while j < len(messages) and messages[j].get("role") == "tool":
        results.append(messages[j])
        j += 1
    result_ids, call_ids = [r.get("tool_call_id") for r in results], [c.get("id") for c in tcs]
    with_ids = all(result_ids) and all(call_ids)
    if with_ids and len(set(result_ids)) == len(results) and len(set(call_ids)) == len(tcs):
        by_id = dict(zip(result_ids, results))
        return [by_id.get(c) for c in call_ids], "id"
    if len(results) == len(tcs):
        return results, "position_after_duplicate_ids" if with_ids else "position"
    return [None] * len(tcs), "none"


def calls(messages):
    """(index, tool name, arguments, result text) for every tool call whose arguments are a JSON object, in message
    order and, within a message, in call order. The result text is "" when no result can be paired with the call."""
    for i, m in enumerate(messages):
        tcs = m.get("tool_calls") or []
        if not tcs:
            continue
        paired, _ = pair(messages, i)
        for c, r in zip(tcs, paired):
            try:
                args = json.loads(c["function"]["arguments"])
            except (ValueError, TypeError):
                continue
            if not isinstance(args, dict):
                continue
            obs = (r or {}).get("content")
            yield i, c["function"]["name"], args, obs if isinstance(obs, str) else ("" if obs is None else json.dumps(obs))


def pairing_counts(messages):
    """How the calls of a trajectory were paired with their results: {"id": n, "position": n, "none": n}."""
    out = collections.Counter()
    for i, m in enumerate(messages):
        if m.get("tool_calls"):
            out[pair(messages, i)[1]] += len(m["tool_calls"])
    return dict(out)


def result_kind(cmd, obs):
    """ok, noop, missing, multiple, other or unknown, for an editor call with this command."""
    e = editor_outcome(obs or "")
    if e in ERRORS:
        return ERRORS[e]
    return "ok" if OK_RESULT.get(cmd) == e else "unknown"


def error_type(obs):
    """noop, missing, multiple or other for an editor error message, else None (also for unknown results)."""
    return ERRORS.get(editor_outcome(obs or ""))


def squash(text):
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def norm(text):
    return "\n".join(x.rstrip() for x in text.strip("\n").splitlines())


def lines(text):
    return {x.strip() for x in text.splitlines() if len(x.strip()) >= 8}


def big(text):
    return any(len(x.strip()) >= 8 for x in text.splitlines())


def changed_lines(a, b):
    """The lines of a and b that the other one lacks, counting repeated lines (multiset difference)."""
    ca, cb = collections.Counter(a.splitlines()), collections.Counter(b.splitlines())
    return list((ca - cb).elements()) + list((cb - ca).elements())


def failed(obs):
    codes = EXIT.findall(obs or "")
    return codes[-1] != "0" if codes else bool(FAIL.search(obs or ""))


def names_in(line):
    return set(ERROR_NAMES.findall(line or ""))


def error_names_in(line):
    """Only the error names (FooError, FooException) of a line, without test names."""
    return {x for x in names_in(line) if not x.startswith("test_")}


def mentions(text, name):
    return re.search(r"\b" + re.escape(name) + r"\b", text or "") is not None


def write_targets(command, known):
    """Paths that a bash command may write, or None when it may write files that cannot be identified.
    Descriptor copies (2>&1) and writes to /dev/null are not writes. A redirect writes its target (quotes removed),
    matched to a known path when possible; a target with a variable, a substitution or a pattern ($ ` * ? { [) cannot
    be identified. Other writing commands (OTHER_WRITES: sed -i, tee, mv, cp, git checkout, patch, open(..., 'w'),
    ...) may write any absolute path they name and any known path named in full or by file name."""
    clean = FD_DUP.sub(" ", command)
    redirects = [t.strip("'\"") for t in REDIRECT.findall(clean)]
    other = OTHER_WRITES.search(clean)
    targets = set()
    for t in redirects:
        if not t or any(ch in t for ch in "$`*?{["):
            return None
        targets |= {p for p in known if p == t or p.endswith("/" + t.lstrip("./"))} or {t}
    if other:
        named = set(PATHS.findall(clean)) | {p for p in known if p and (p in clean or p.rsplit("/", 1)[-1] in clean)}
        if not named:
            return None
        targets |= named
    return targets


def edit_failures(messages):
    texts = collections.defaultdict(list)       # path -> [(call number, text)]
    modified = collections.defaultdict(list)    # path -> [call number]
    events = []
    for k, (i, name, args, obs) in enumerate(calls(messages)):
        if name == "str_replace_editor":
            cmd, p = args.get("command"), args.get("path")
            kind = result_kind(cmd, obs)
            if kind == "ok":
                if cmd == "view":
                    texts[p].append((k, LINE_NO.sub("", obs)))
                elif cmd == "create":
                    texts[p].append((k, args.get("file_text") or ""))
                    modified[p].append(k)
                elif cmd == "str_replace":
                    texts[p] += [(k, args.get("new_str") or ""), (k, LINE_NO.sub("", obs))]
                    modified[p].append(k)
                elif cmd in ("insert", "undo_edit"):
                    texts[p].append((k, (args.get("new_str") or "") + "\n" + LINE_NO.sub("", obs)))
                    modified[p].append(k)
            elif cmd in CHANGES and kind == "unknown":
                modified[p].append(k)
                if cmd == "str_replace":
                    events.append({"step": i, "call": k, "path": p, "error": "unknown"})
            elif cmd == "str_replace":
                s = args.get("old_str") or ""
                ev = {"step": i, "call": k, "path": p, "error": kind}
                if kind == "missing":
                    hits = [t for t, x in texts[p] if s and s in x]
                    if hits:
                        ev["kind"] = "stale" if any(t > max(hits) for t in modified[p]) else "seen_not_modified"
                    elif s and any(squash(s) in squash(x) for _, x in texts[p]):
                        ev["kind"] = "copy_error"
                    else:
                        ev["kind"] = "never_seen"
                events.append(ev)
        elif name == "execute_bash":
            command = args.get("command") or ""
            targets = write_targets(command, list(texts))
            for p in (list(texts) if targets is None else targets):
                modified[p].append(k)
            if targets == set() and READS.search(command):
                for p in set(PATHS.findall(command)) | {q for q in texts if q and q in command}:
                    texts[p].append((k, LINE_NO.sub("", obs)))
    return events


def noops(messages):
    applied = collections.defaultdict(set)      # path -> new_str of successful str_replace
    good = collections.defaultdict(list)        # path -> [(call number, old_str or None)] of successful edits
    tried, found = set(), []
    last_failed = False
    for k, (i, name, a, obs) in enumerate(calls(messages)):
        if name == "str_replace_editor":
            cmd, p = a.get("command"), a.get("path")
            kind = result_kind(cmd, obs)
            old, new = a.get("old_str") or "", a.get("new_str") or ""
            if cmd == "str_replace" and kind == "noop":
                cause = ("already_applied" if old in applied[p] else "repeat_attempt" if (p, old) in tried
                         else "after_failure" if last_failed else "other")
                tried.add((p, old))
                found.append({"step": i, "call": k, "path": p, "text": old, "kind": cause})
            elif cmd == "str_replace" and kind == "ok":
                applied[p].add(new)
                good[p].append((k, old))
            elif cmd in ("insert", "create") and kind == "ok":
                good[p].append((k, None))
        if name == "execute_bash":
            last_failed = failed(obs)
    for f in found:
        later = [(k, o) for k, o in good[f["path"]] if k > f["call"]]
        f["cost"] = later[0][0] - f["call"] if later else None
        f["fate"] = ("same_spot" if any(o is not None and lines(o) & lines(f["text"]) for _, o in later)
                     else "elsewhere" if later else "never")
    return found


def reverts(messages):
    done = collections.defaultdict(list)        # path -> [(index, old, new)] of successful str_replace
    out = {"reverts": [], "str_replace_ok": 0, "whitespace_only": 0, "undo": 0}
    for i, name, a, obs in calls(messages):
        if name != "str_replace_editor":
            continue
        cmd, p = a.get("command"), a.get("path")
        old, new = a.get("old_str") or "", a.get("new_str") or ""
        if cmd == "undo_edit":
            out["undo"] += 1
        if cmd != "str_replace" or result_kind(cmd, obs) != "ok":
            continue
        out["str_replace_ok"] += 1
        out["whitespace_only"] += old != new and old.split() == new.split()
        for j, o1, n1 in done[p]:
            exact = norm(old) == norm(n1) and norm(new) == norm(o1)
            window = bool(n1) and n1 in old and old.replace(n1, o1, 1) == new
            if exact or window:
                ch = changed_lines(o1, n1)
                kind = "debug" if ch and all(DEBUG.match(x) for x in ch) else "flip_flop"
                out["reverts"].append({"step": i, "path": p, "kind": kind, "turns": (i - j) // 2})
                break
        done[p].append((i, old, new))
    return out


def failure_kind(bad):
    if bad is None:
        return None
    return "unknown" if not bad[2] else "infra" if INFRA.search(bad[2]) else "application"


def last_tested(history):
    """The failing test of the most recent certain life in which a test-like command ran (None if it passed, or if
    no certain life was tested)."""
    tested = [x for x in history if x["certain"] and x["tested"]]
    return tested[-1]["bad"] if tested else None


def revisits(messages):
    present = collections.defaultdict(dict)       # path -> block -> call number from which its presence is certain
    origin = collections.defaultdict(dict)        # path -> block -> original | agent | uncertain (first sighting)
    lives = collections.defaultdict(dict)         # path -> block -> [presence intervals, once removed]
    touched = set()                               # paths that something may have changed
    tests, changes, events = [], [], []           # tests: (call, failed, line); changes: (call, path, source)
    unidentified_write = False
    for k, (i, name, a, obs) in enumerate(calls(messages)):
        if name == "execute_bash":
            command = str(a.get("command", ""))
            if TESTLIKE.search(command):
                f = failed(obs)
                line = next((x.strip() for x in obs.splitlines()[::-1] if FAIL.search(x)), "") if f else ""
                tests.append((k, f, line[:120]))
            targets = write_targets(command, list(touched | set(present) | set(lives)))
            if targets is None:
                unidentified_write = True
                present.clear()
            for t in targets or ():
                present[t].clear()
                touched.add(t)
            if targets is None or targets:
                changes.append((k, None, "bash"))
            continue
        if name != "str_replace_editor":
            continue
        cmd, p = a.get("command"), a.get("path")
        kind = result_kind(cmd, obs)
        if (cmd in CHANGES and kind == "unknown") or (cmd in CHANGES and cmd != "str_replace" and kind == "ok"):
            present[p].clear()
            touched.add(p)
            changes.append((k, p, "editor"))
            continue
        if kind != "ok" or cmd != "str_replace":
            continue
        old, new = norm(a.get("old_str") or ""), norm(a.get("new_str") or "")
        for e in events:
            if e["kind"] == "retry_own" and e["path"] == p and e["again"] is None and e["block"] in old \
                    and e["block"] not in new:
                e["again"] = k - e["call"]
        if big(old):
            if old in present[p]:
                start = present[p][old]
            elif p not in touched and not unidentified_write:
                start = -1
                origin[p].setdefault(old, "original")
            else:
                start = None
                origin[p].setdefault(old, "uncertain")
            during = [t for t in tests if start is not None and start < t[0] < k]
            lives[p].setdefault(old, []).append({
                "bad": next((t for t in reversed(during) if t[1]), None) if start is not None else None,
                "tested": bool(during), "removed_at": i, "removed_call": k, "certain": start is not None})
        present[p].clear()
        touched.add(p)
        changes.append((k, p, "editor"))
        if big(new):
            if new in lives[p]:
                history = lives[p][new]
                last = history[-1]
                bad = last_tested(history)
                events.append({
                    "step": i, "call": k, "path": p, "block": new, "removed": old,
                    "removed_at": last["removed_at"], "removed_call": last["removed_call"],
                    "kind": {"original": "back_to_original", "agent": "retry_own"}.get(origin[p].get(new),
                                                                                     "uncertain_provenance"),
                    "life_certain": any(x["certain"] for x in history), "known_bad": bad,
                    "tested": any(x["certain"] and x["tested"] for x in history),
                    "known_bad_kind": failure_kind(bad),
                    "replaced_bad": last_tested(lives[p][old]) if big(old) else None,
                    "project_changed": any(last["removed_call"] < s < k and (src == "bash" or q != p)
                                           for s, q, src in changes),
                    "again": None})
            origin[p].setdefault(new, "agent")
            present[p][new] = k
    return events


def thoughts_of(m):
    out = []
    for c in m.get("tool_calls") or []:
        if c["function"]["name"] == "think":
            try:
                out.append(json.loads(c["function"]["arguments"]).get("thought") or "")
            except (ValueError, TypeError, AttributeError):
                pass
    return " ".join(x for x in out if x)


def text_of(m):
    content = m.get("content") if isinstance(m.get("content"), str) else ""
    return " ".join(x for x in (content, thoughts_of(m)) if x)


def window(messages, i):
    """The reasoning before call message i: the thoughts of the earlier calls of the same response (messages marked
    shared_response, back to the response's first message), the text of message i, and the text of at most 3 earlier
    assistant messages that only hold think calls."""
    first = i
    while (messages[first].get("meta") or {}).get("shared_response"):
        j = first - 1
        while j >= 0 and messages[j].get("role") != "assistant":
            j -= 1
        if j < 0:
            break
        first = j
    same = [thoughts_of(messages[j]) for j in range(first, i) if messages[j].get("role") == "assistant"]
    parts, seen = [x for x in same if x] + [text_of(messages[i])], 0
    for j in range(first - 1, -1, -1):
        m = messages[j]
        if m.get("role") != "assistant":
            continue
        if {c["function"]["name"] for c in m.get("tool_calls") or []} - {"think"} or seen >= 3:
            break
        parts.insert(0, text_of(m))
        seen += 1
    return " ".join(p for p in parts if p).strip()


def intent(messages, i):
    """'silent' (no text), 'declared' (a deliberate return is stated) or 'undeclared'."""
    w = window(messages, i)
    return "silent" if not w else "declared" if DECLARED.search(w) else "undeclared"


def remembers(messages, event):
    """For a revisit with a known_bad line: does the reasoning window name, as a whole word, an error or a test of
    that line? None when there was no failure, or when the failing line names nothing."""
    if not event.get("known_bad"):
        return None
    found = names_in(event["known_bad"][2])
    if not found:
        return None
    w = window(messages, event["step"])
    return any(mentions(w, n) for n in found)
