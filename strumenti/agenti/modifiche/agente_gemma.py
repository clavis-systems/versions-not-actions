"""Gemma as a coding agent on HumanEvalFix, with the host guard ON or OFF (live test).

    python -I agente_gemma.py --tasks 0-19 --guard off --out <folder>     # needs Ollama and the GPU lock

Each task is a file solution.py holding the buggy function of one HumanEvalFix item (declaration, docstring and
buggy body) among a few correct HumanEval functions used as context, so that edits have room to go wrong. The agent
has four tools:
  view(path, view_range)              the file with line numbers, as `cat -n` (OpenHands wording);
  str_replace(path, old_str, new_str) OpenHands semantics: old_str must occur exactly once, and differ from new_str;
  run_tests()                         the item's visible example tests, run in the WASM sandbox only;
  finish()                            ends the task.
At the end the item's full hidden tests run in the sandbox: the task is solved if they pass.

Guard OFF returns the plain OpenHands-style messages. Guard ON adds, after the same message, a note from the host:
  repeat    first, for any failed str_replace: the same call already failed at step N on this same version of the
            file, so repeating it cannot work;
  noop      it was already applied at step N, or old and new are identical, so the new text must say what changes;
  missing   if this exact edit was already made at step N: say so, and where its new text is now (no other advice);
            if an earlier edit removed old_str: at which step; then the closest real text in the file, with its line
            numbers (most "never seen" text is a near copy) and, for a near copy, the first lines that differ, with
            spaces made visible;
  multiple  every occurrence: its line number, the function that encloses it, and the whole line;
  revisit   after a successful edit: this block was already in the file at step N, and while it was there the
            tests failed with <line>; if the block it replaces had failed too with another error, both errors.
Nothing else differs between the two conditions. The Python code of the model and of the dataset runs only in the
sandbox; Ollama and the reading of the dataset file run on the host.

The hidden tests count as passed only with exit code 0 and a marker that carries a random nonce of the run. A failure
of Ollama or of the sandbox is an infrastructure error: the result records it, the task is excluded from the
comparison, and the run stops. Every result records the configuration (model digest, versions, file hashes); a resumed
run refuses results written by another configuration.
"""

from __future__ import annotations

import argparse
import difflib
import glob
import hashlib
import http.client
import json
import os
import random
import re
import secrets
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "strumenti", "valutazione"))

DATA = os.path.join(ROOT, "esterni", "humanevalpack", "python", "test-00000-of-00001.parquet")
RUNTIME = os.path.join(ROOT, "strumenti", "valutazione", "runtime")
LOCK = os.path.join(ROOT, "strumenti", "risultati", ".gpu_lock")
OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA = OLLAMA_BASE + "/api/chat"
MODEL = "gemma4:e4b-it-qat"
OPTIONS = {"temperature": 0, "seed": 1, "num_ctx": 16384, "num_predict": 1024}
NOT_REMOVED = "TEST FILE NOT REMOVED"
LOCK_MAX_AGE = 24 * 3600         # seconds: an older lock file is stale
FILE = "solution.py"
CONTEXT_FUNCTIONS = 6
MAX_CALLS = 20
SNIPPET = 4
OUTPUT_CUT = 2500
NEAR = 0.8                       # difflib similarity of a near copy, as in the trajectory study

SYSTEM = """You are a careful coding agent. Your job: fix the bug in one function of solution.py.
Tools:
- view(path, view_range): shows the file with line numbers. view_range = [first, last] is optional.
- str_replace(path, old_str, new_str): replaces old_str with new_str. old_str must match the file EXACTLY, once,
  without the line numbers that view shows.
- run_tests(): runs the example tests of the function.
- finish(): call it when the tests pass.
Change only the buggy function. Do not change the docstring or the other functions."""

TOOLS = [
    {"type": "function", "function": {
        "name": "view", "description": "Show a file with line numbers.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "view_range": {"type": "array", "items": {"type": "integer"}}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "str_replace", "description": "Replace one exact occurrence of old_str with new_str in a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}},
            "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run the example tests.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "finish", "description": "End the task.", "parameters": {"type": "object", "properties": {}}}},
]


# ---------- tasks ----------

def load_rows(path=DATA):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def split_imports(prompt):
    """(import lines, the rest) of a HumanEval prompt."""
    imports, rest = [], []
    for line in prompt.splitlines():
        (imports if re.match(r"^(from \S+ import |import )", line) and not rest else rest).append(line)
    return imports, "\n".join(rest).strip("\n")


def build_task(rows, index, n_context=CONTEXT_FUNCTIONS):
    """solution.py for item `index`: the buggy function in the middle of n_context correct ones."""
    target = rows[index]
    others, j = [], 1
    while len(others) < n_context:
        other = rows[(index + 7 * j) % len(rows)]
        j += 1
        if other["entry_point"] != target["entry_point"] and \
                all(o["entry_point"] != other["entry_point"] for o in others):
            others.append(other)
    imports, blocks = [], []
    for k, row in enumerate(others[:n_context // 2] + [target] + others[n_context // 2:]):
        imp, body = split_imports(row["prompt"])
        imports += [x for x in imp if x not in imports]
        code = row["buggy_solution"] if row is target else row["canonical_solution"]
        blocks.append(body + "\n" + code.rstrip("\n"))
    text = "\n".join(imports) + ("\n\n\n" if imports else "") + "\n\n\n".join(blocks) + "\n"
    return {"id": target["task_id"], "entry_point": target["entry_point"], "files": {FILE: text},
            "visible_test": target["example_test"], "hidden_test": target["test"],
            "test_setup": target.get("test_setup") or "",
            "statement": f"The function `{target['entry_point']}` in {FILE} has a bug: it does not do what its "
                         f"docstring says. Fix it. Use run_tests to check your fix, then call finish."}


def test_program(test_code, entry_point, label, setup="", nonce="", hide=False):
    """The test program. With hide=True it deletes its own file before importing the solution, so that the
    candidate code cannot read the tests or the nonce from the disk (it still could from memory: see the premise).
    If the file cannot be deleted, the solution is never run: the program prints NOT_REMOVED and stops."""
    marker = f"{label} PASSED" + (f" {nonce}" if nonce else "")
    head = (f"import os\ntry:\n    os.remove(__file__)\nexcept OSError as exc:\n    print('{NOT_REMOVED}', exc)\n"
            "    raise SystemExit(3)\n") if hide else ""
    return (head + "import sys, traceback\nsys.path.insert(0, '/sandbox/progetto')\nfrom solution import *\n"
            + setup + "\n" + test_code + "\n"
            + f"try:\n    check({entry_point})\n    print('{marker}')\n"
            + "except Exception:\n    traceback.print_exc()\n    raise SystemExit(1)\n")


class InfraError(RuntimeError):
    """Ollama or the sandbox failed: not the agent's doing."""


def sandbox_run(program, files, timeout=20):
    import sandbox_wasm
    try:
        ok, out, err = sandbox_wasm.run(program, "python", timeout=timeout, files=files)
    except sandbox_wasm.SandboxUnavailable as exc:
        raise InfraError(f"sandbox: {exc}") from exc
    return ok, (out or "") + (err or "")


def hidden_outcome(ok, out, nonce):
    """passed (exit code 0 and the marker with this run's nonce), failed (a Python traceback, or the sandbox's time
    or output limit), or unclear (anything else, e.g. exit code 0 without the marker): unclear is excluded."""
    if ok and f"HIDDEN TESTS PASSED {nonce}" in out:
        return "passed"
    if "Traceback (most recent call last)" in out or out.startswith(("Timeout:", "Output troppo grande")):
        return "failed"
    return "unclear"


SUSPICIOUS = re.compile(r"\bopen\(|__main__|sys\.modules|_getframe|\binspect\b|\bglobals\(|program\.py|\bexit\(|"
                        r"_exit\(|SystemExit|PASSED|__import__|importlib|\beval\(|\bexec\(|\bos\.|\bsys\.")


def suspicious_additions(initial, final):
    """Tokens in the lines the agent added that could read the tests or fake their outcome (listed, not judged)."""
    added = [x[2:] for x in difflib.ndiff(initial.splitlines(), final.splitlines()) if x.startswith("+ ")]
    return sorted({m.group(0) for line in added for m in SUSPICIOUS.finditer(line)})


# ---------- the workspace and its tools ----------

def numbered(text, first=1):
    return "\n".join(f"{n:6d}\t{line}" for n, line in enumerate(text.splitlines(), first))


def enclosing_function(lines, index):
    for j in range(index, -1, -1):
        m = re.match(r"\s*def (\w+)", lines[j])
        if m:
            return m.group(1)
    return None


def norm(text):
    return "\n".join(x.rstrip() for x in text.strip("\n").splitlines())


def line_spans(text, part):
    """'first-last' lines of every occurrence of `part` in `text`, leading and trailing line breaks aside."""
    lead, core, spans = len(part) - len(part.lstrip("\n")), part.strip("\n"), []
    for m in re.finditer(re.escape(part), text):
        first = text[:m.start() + lead].count("\n") + 1
        last = first + core.count("\n")
        spans.append(f"{first}" if last == first else f"{first}-{last}")
    return ", ".join(spans)


def shown(lines):
    """Lines with their spaces made visible, as Python string literals."""
    if not lines:
        return "nothing"
    text = " ".join(repr(x) for x in lines[:3]) + (" ..." if len(lines) > 3 else "")
    return text if len(text) <= 200 else text[:200] + " ..."


def differences(found, want, first, limit=2):
    """The first `limit` places where the file lines `found` (starting at line `first`) differ from `want`."""
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, found, want, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        where = (f"line {first + i1}" if i2 - i1 == 1 else f"lines {first + i1}-{first + i2 - 1}" if i2 > i1
                 else f"after line {first + i1 - 1}")
        out.append(f"{where}: the file has {shown(found[i1:i2])}, your old_str has {shown(want[j1:j2])}")
        if len(out) == limit:
            break
    return out


class Workspace:
    def __init__(self, task, guard, runner=sandbox_run):
        self.task, self.guard, self.runner = task, guard, runner
        self.files = dict(task["files"])
        self.edits = []              # (step, old_str, new_str, text before, text after) of each successful edit
        self.tests = []              # (step, file text at that time, failed, failing line)
        self.failed_calls = {}       # (path, old_str, new_str, file text) -> steps of the failed str_replace calls
        self.step = 0

    def call(self, name, args):
        self.step += 1
        try:
            if name == "view":
                return self.view(args.get("path", FILE), args.get("view_range"))
            if name == "str_replace":
                return self.str_replace(args.get("path", FILE), args.get("old_str"), args.get("new_str"))
            if name == "run_tests":
                return self.run_tests()
            if name == "finish":
                return "Task finished."
            return f"ERROR:\nUnknown tool {name!r}."
        except (TypeError, ValueError) as exc:
            return f"ERROR:\nInvalid arguments: {exc}"

    def view(self, path, view_range=None):
        if path not in self.files:
            return f"ERROR:\nInvalid `path` parameter: {path}. The path {path} does not exist."
        lines = self.files[path].splitlines()
        first, last = 1, len(lines)
        if view_range:
            first, last = int(view_range[0]), int(view_range[-1]) if int(view_range[-1]) > 0 else len(lines)
        body = "\n".join(numbered("\n".join(lines[first - 1:last]), first).splitlines())
        return f"Here's the result of running `cat -n` on {path}:\n{body}\n"

    def str_replace(self, path, old, new):
        if path not in self.files:
            return f"ERROR:\nInvalid `path` parameter: {path}. The path {path} does not exist."
        if old is None or new is None:
            raise ValueError("old_str and new_str are required")
        text = self.files[path]
        key = (path, old, new, text)
        if old == new:
            msg = (f"ERROR:\nInvalid `new_str` parameter: {new}. No replacement was performed. `new_str` and "
                   "`old_str` must be different.")
            return msg + self.guard_repeat(key, "change new_str") + self.guard_noop(old) if self.guard else \
                self.failure(key, msg)
        count = text.count(old)
        if count == 0:
            msg = f"ERROR:\nNo replacement was performed, old_str `{old}` did not appear verbatim in {path}."
            return msg + self.guard_repeat(key, "change old_str") + self.guard_missing(text, old, new) if self.guard else \
                self.failure(key, msg)
        if count > 1:
            lines = [text[:m.start()].count("\n") + 1 for m in re.finditer(re.escape(old), text)]
            msg = (f"ERROR:\nNo replacement was performed. Multiple occurrences of old_str `{old}` in lines "
                   f"{lines}. Please ensure it is unique.")
            return msg + self.guard_repeat(key, "change old_str") + self.guard_multiple(text, lines) if self.guard else \
                self.failure(key, msg)
        before = text
        start_line = text[:text.index(old)].count("\n")
        self.files[path] = text.replace(old, new, 1)
        self.edits.append((self.step, old, new, before, self.files[path]))
        lines = self.files[path].splitlines()
        first = max(0, start_line - SNIPPET)
        last = min(len(lines), start_line + new.count("\n") + 1 + SNIPPET)
        msg = (f"The file {path} has been edited. Here's the result of running `cat -n` on a snippet of {path}:\n"
               + numbered("\n".join(lines[first:last]), first + 1)
               + "\nReview the changes and make sure they are as expected. Edit the file again if necessary.")
        return msg + self.guard_revisit(before, old, new) if self.guard else msg

    def run_tests(self):
        program = test_program(self.task["visible_test"], self.task["entry_point"], "TESTS",
                               self.task.get("test_setup", ""))
        ok, out = self.runner(program, dict(self.files))
        failed = not ok
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        failing = ""
        if failed:
            asserts = [x for x in lines if x.startswith("assert ")]
            errors = [x for x in lines if re.search(r"Error|Exception", x)]
            failing = " / ".join(([asserts[-1]] if asserts else []) + ([errors[-1]] if errors else []))
        self.tests.append((self.step, self.files[FILE], failed, failing[:160]))
        out = out if len(out) <= OUTPUT_CUT else out[:OUTPUT_CUT] + "\n[output cut]"
        return out + f"\n[The command completed with exit code {1 if failed else 0}.]"

    def failure(self, key, msg):
        """Records a failed str_replace (in both conditions; only the guard speaks about it)."""
        self.failed_calls.setdefault(key, []).append(self.step)
        return msg

    # ---------- the guard ----------

    def guard_repeat(self, key, fix):
        """The same call on the same version of the file fails in the same way: say so first."""
        steps = list(self.failed_calls.get(key, []))
        self.failure(key, "")
        if not steps:
            return ""
        when = ("step " if len(steps) == 1 else "steps ") + ", ".join(str(s) for s in steps)
        return (f"\n[Host note] You already sent this exact call at {when}, on this same version of the file, and it "
                f"failed in the same way. Repeating it cannot work: {fix}.")

    def guard_noop(self, old):
        """"Already made" only if an edit of the agent put this text in the file (it was not there before that edit)
        and the text is still there."""
        target = norm(old)
        made = [e for e in self.edits if target and target in norm(e[4]) and target not in norm(e[3])]
        if made and target in norm(self.files[FILE]):
            return (f"\n[Host note] You already made this change at step {made[-1][0]}: your edit then put this text "
                    "in the file, and it is still there. If the tests still fail, the bug is somewhere else.")
        return ("\n[Host note] old_str and new_str are identical, so nothing would change. Put in new_str the lines "
                "as they must become after your fix.")

    def guard_missing(self, text, old, new):
        gone = next((e for e in reversed(self.edits) if old and old in e[3] and old not in e[4]), None)
        if gone and (gone[1], gone[2]) == (old, new):
            if new.strip("\n") and new in text:
                return (f"\n[Host note] You already made this exact edit at step {gone[0]}: it replaced old_str, so "
                        f"old_str is no longer in the file, and your new_str is now at lines {line_spans(text, new)}. "
                        "Do not repeat it: run the tests, or view the file.")
            return (f"\n[Host note] You already made this exact edit at step {gone[0]}, and a later edit changed that "
                    "text again. View the file before you edit it.")
        note = "\n[Host note] "
        if gone:
            note += f"old_str was in the file until your edit at step {gone[0]} changed it. "
        return note + self.closest(text, old)

    @staticmethod
    def closest(text, old):
        """The window of the file most similar to old_str (lines compared without their spaces at the ends), and,
        for a near copy, the first lines where it differs."""
        lines, want = text.splitlines(), old.strip("\n").splitlines()
        key, size, best, where = [x.strip() for x in want], max(1, len(want)), -1.0, 0
        for start in range(0, max(1, len(lines) - size + 1)):
            window = [x.strip() for x in lines[start:start + size]]
            ratio = difflib.SequenceMatcher(None, "\n".join(key), "\n".join(window), autojunk=False).ratio()
            if ratio > best:
                best, where = ratio, start
        found = lines[where:where + size]
        note = (f"The closest text in the file is at lines {where + 1}-{where + len(found)}:\n" + "\n".join(found)
                + "\n")
        if best >= NEAR:
            diffs = differences(found, want, where + 1)
            if not diffs:
                note += "It matches old_str line by line: check the line breaks at the start and end of old_str.\n"
            else:
                only = "only in spaces " if [x.strip() for x in found] == key else ""
                note += f"It differs from your old_str {only}at " + "; ".join(diffs) + ".\n"
        return note + "Copy old_str exactly from the file."

    def guard_multiple(self, text, line_numbers):
        lines = text.splitlines()
        where = "".join(f"\n- line {n}, in function `{enclosing_function(lines, n - 1)}`:\n{lines[n - 1]}"
                        for n in line_numbers)
        return (f"\n[Host note] The text appears at:{where}\nAdd nearby lines to old_str so that it is unique, for "
                "example the whole line you want to change.")

    def failure_while_present(self, block, before_step):
        """The last test that failed while `block` was in the file, before `before_step`, if the block was
        removed after it."""
        hits = [t for t in self.tests if t[2] and t[0] < before_step and block and block in norm(t[1])]
        return hits[-1] if hits else None

    def guard_revisit(self, before, old, new):
        block, gone = norm(new), norm(old)
        if not any(len(x.strip()) >= 8 for x in block.splitlines()) or block in norm(before):
            return ""
        earlier = self.failure_while_present(block, self.step)
        if not earlier:
            return ""
        note = (f"\n[Host note] This text is identical to a version that was already in the file at step "
                f"{earlier[0]}. While it was there, the tests failed with: {earlier[3]}")
        other = self.failure_while_present(gone, self.step)
        if other and other[3] != earlier[3]:
            note += (f"\nThe version you just replaced also failed, with: {other[3]}. A correct fix must avoid both "
                     "errors.")
        return note


# ---------- the agent loop ----------

def ollama_chat(messages, think=False, model=MODEL):
    body = {"model": model, "messages": messages, "tools": TOOLS, "stream": False, "think": think,
            "options": OPTIONS}
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            reply = json.load(r)
    except (OSError, ValueError, http.client.HTTPException) as exc:     # connection, HTTP status, timeout, bad JSON
        raise InfraError(f"ollama: {type(exc).__name__}: {exc}") from exc
    if not isinstance(reply, dict) or not isinstance(reply.get("message"), dict):
        raise InfraError(f"ollama: reply without a message: {str(reply)[:200]}")
    return reply


def run_task(task, guard, chat=ollama_chat, runner=sandbox_run, max_calls=MAX_CALLS):
    """Trajectory in the common message shape of formati.py, plus the outcome. Never more than max_calls calls:
    tool calls of one reply beyond the budget are not executed (counted in dropped_calls)."""
    ws = Workspace(task, guard, runner)
    sent = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["statement"]}]
    log = [dict(m) for m in sent]
    calls, finished, started, dropped = 0, False, time.time(), 0
    hidden, out, infra = None, "", None
    try:
        while calls < max_calls and not finished:
            t0 = time.time()
            reply = chat(sent)
            msg = reply.get("message") or {}
            tokens = {"prompt": reply.get("prompt_eval_count"), "completion": reply.get("eval_count")}
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                sent.append({"role": "assistant", "content": msg.get("content") or ""})
                log.append({"role": "assistant", "content": msg.get("content") or "",
                            "meta": {"tokens": tokens, "seconds": round(time.time() - t0, 2)}})
                nudge = "Use the tools. Call finish when the tests pass."
                sent.append({"role": "user", "content": nudge})
                log.append({"role": "user", "content": nudge})
                calls += 1
                continue
            sent.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
            for n, tc in enumerate(tool_calls):
                if calls >= max_calls:
                    dropped += len(tool_calls) - n
                    break
                fn = tc.get("function") or {}
                name, args = fn.get("name"), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                raw_name = "str_replace_editor" if name in ("view", "str_replace") else (
                    "execute_bash" if name == "run_tests" else name)
                raw_args = dict(args, command=name) if name in ("view", "str_replace") else (
                    {"command": "python -m pytest (example tests)"} if name == "run_tests" else args)
                call_id = f"c{calls}_{n}"
                result = ws.call(name, args)
                sent.append({"role": "tool", "content": result})
                meta = {"seconds": round(time.time() - t0, 2)}
                if n == 0:
                    meta["tokens"] = tokens
                else:
                    meta["shared_response"] = True
                log.append({"role": "assistant", "content": msg.get("content") or "", "meta": meta,
                            "tool_calls": [{"id": call_id, "function": {"name": raw_name,
                                                                        "arguments": json.dumps(raw_args)}}]})
                log.append({"role": "tool", "content": result, "tool_call_id": call_id})
                calls += 1
                if name == "finish":
                    finished = True
                    break
        nonce = secrets.token_hex(8)
        program = test_program(task["hidden_test"], task["entry_point"], "HIDDEN TESTS", task.get("test_setup", ""),
                               nonce, hide=True)
        ok, out = runner(program, dict(ws.files))
        if out.lstrip().startswith(NOT_REMOVED):
            raise InfraError(f"sandbox: the test file could not be removed: {out.strip()[:200]}")
        hidden = hidden_outcome(ok, out, nonce)
    except InfraError as exc:
        infra = str(exc)
    return {"task": task["id"], "guard": guard,
            "solved": hidden == "passed" if hidden in ("passed", "failed") else None,
            "hidden": hidden, "infra_error": infra, "finished": finished, "calls": calls, "dropped_calls": dropped,
            "seconds": round(time.time() - started, 1), "hidden_test_output": out[-400:],
            "suspicious_additions": suspicious_additions(task["files"][FILE], ws.files[FILE]),
            "final_file": ws.files[FILE], "messages": log}


# ---------- runs: configuration, saving, resuming ----------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ollama_get(path):
    with urllib.request.urlopen(OLLAMA_BASE + path, timeout=30) as r:
        return json.load(r)


def run_config(seed):
    """Everything that must be equal across the results of one run."""
    import sandbox_wasm
    sandbox_wasm.preflight({"python"})        # prepares the precompiled interpreter and the standard library once
    tags = ollama_get("/api/tags").get("models", [])
    wasmtime = sorted(glob.glob(os.path.join(RUNTIME, "wasmtime", "**", "wasmtime.exe"), recursive=True))
    return {"model": MODEL, "model_digest": next((m.get("digest") for m in tags if m.get("name") == MODEL), None),
            "ollama_version": ollama_get("/api/version").get("version"), "options": OPTIONS, "think": False,
            "max_calls": MAX_CALLS, "context_functions": CONTEXT_FUNCTIONS, "seed": seed,
            "agent_sha256": sha256_file(os.path.abspath(__file__)), "dataset_sha256": sha256_file(DATA),
            "sandbox_sha256": sha256_file(os.path.abspath(sandbox_wasm.__file__)),
            "wasmtime": os.path.relpath(wasmtime[0], ROOT).replace(os.sep, "/") if wasmtime else None,
            "wasmtime_sha256": sha256_file(wasmtime[0]) if wasmtime else None,
            "python_wasm_sha256": sha256_file(os.path.join(RUNTIME, "python", "python.wasm")),
            "python_cwasm_sha256": sha256_file(os.path.join(RUNTIME, "python.cwasm")),
            "stdlib_zip_sha256": {os.path.basename(p): sha256_file(p)
                                  for p in sorted(glob.glob(os.path.join(RUNTIME, "python3*.zip")))}}


def check_existing(path, config, task_id, guard):
    """A result already written by this same configuration, for this task and condition; anything else stops."""
    with open(path, encoding="utf-8") as fh:
        old = json.load(fh)
    if old.get("config") != config or old.get("task") != task_id or old.get("guard") != guard:
        raise SystemExit(f"{path}: written by another configuration or for another task: do not mix runs")
    return old


def save_result(path, result):
    """Written whole to a side file, then renamed: a final file is always complete, and never overwritten."""
    if os.path.exists(path):
        raise SystemExit(f"{path} already exists")
    part = f"{path}.{os.getpid()}.part"
    with open(part, "x", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(part, path)                     # on Windows this also refuses a `path` that appeared meanwhile


def condition_order(seed, index):
    """The order of the two conditions for one task: fixed by the seed and the task, whatever range is run."""
    order = ["off", "on"]
    random.Random(f"{seed}-{index}").shuffle(order)
    return order


def parse_range(text):
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True, help="item indices, e.g. 0-19")
    p.add_argument("--guard", choices=("on", "off", "both"), required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=20261011, help="order of the conditions in --guard both")
    a = p.parse_args()
    if not os.path.exists(LOCK) or "agente_gemma" not in open(LOCK, encoding="utf-8", errors="replace").read() \
            or time.time() - os.path.getmtime(LOCK) > LOCK_MAX_AGE:
        raise SystemExit("The GPU lock strumenti/risultati/.gpu_lock must exist, name agente_gemma and be less than "
                         "24 hours old (CLAUDE.md).")
    config = run_config(a.seed)
    if not config["model_digest"]:
        raise SystemExit(f"{MODEL} is not in Ollama")
    print(json.dumps(config, indent=1), flush=True)
    rows = load_rows()
    os.makedirs(a.out, exist_ok=True)
    for index in parse_range(a.tasks):
        task = build_task(rows, index)
        conditions = condition_order(a.seed, index) if a.guard == "both" else [a.guard]
        for position, cond in enumerate(conditions):
            path = os.path.join(a.out, f"{index:03d}_{cond}.json")
            if os.path.exists(path):
                check_existing(path, config, task["id"], cond == "on")
                continue
            result = run_task(task, cond == "on")
            result.update(config=config, position=position)
            save_result(path, result)
            print(f"{task['id']} guard {cond}: solved {result['solved']}, calls {result['calls']}, "
                  f"{result['seconds']} s", flush=True)
            if result["infra_error"]:
                raise SystemExit(f"Stopped by an infrastructure error: {result['infra_error']}")


if __name__ == "__main__":
    main()
