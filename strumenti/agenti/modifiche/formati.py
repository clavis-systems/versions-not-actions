"""Translate coding-agent trajectories ("diaries") from three public formats into one common shape.

Read only: nothing in a trajectory is executed. The shape is described in FORMATO_COMUNE.md. In short, one run is
    {"id", "task", "collection", "source", "model", "outcome", "patch", "messages", "observations", "receipt"}
and its messages are the ones of the SWE-Hero dataset, each tool result right after the call that asked for it:
    {"role": "assistant", "content": str, "tool_calls": [{"id": str, "function": {"name": str, "arguments": str}}]}
    {"role": "tool", "content": str, "tool_call_id": str}
A message may carry margin notes in "meta" when its source keeps them: "time" (ISO timestamp), "tokens" (prompt and
completion tokens of the model response, on its first call only), "shared_response" (true on the later calls of a
response with several calls, which repeat the response's text), "file_before" and "file_after" (the whole file
around a successful edit). Every run comes with a receipt that accounts for each event of the source: written into
a message, or set aside with its reason.

Sources:
- SWE-Hero (NVIDIA, parquet shards): already in this shape; the cover keeps the final patch.
- OpenHands event lists (SWE-bench Verified submissions, `<set>/<instance>/trajectory.json`): rebuilt from the
  tool-call metadata of each result, which keeps the model's raw call; each str_replace call is checked against
  the action that the agent framework recorded. A command result gets back the exit-code line that the model saw,
  which the event list keeps apart. An error raised before any tool ran (for example a call without a required
  argument) has no call to attach to, so it is kept as {"role": "error", "content": ...}.
- Observation-only logs (the Claude Opus 4.5 submission, `<set>/<instance>.json`): the actions were not saved
  ("Action: unknown"), so only tool results can be read, as (tool, text) pairs; `editor_outcome` sorts them.
"""

import ast
import collections
import glob
import json
import os
import re

# Action arguments kept when a call has to be rebuilt from the action (the model's raw call is missing).
KEEP = ("command", "path", "old_str", "new_str", "file_text", "insert_line", "view_range", "is_input")
TOOL_PREFIX = re.compile(r"\[(\w+)\] (.*)", re.S)
VIEW = re.compile(r"Here's the (result of running `cat -n`|files and directories)")


def new_receipt():
    return {"events": 0, "written": 0, "set_aside": collections.Counter(), "calls": 0, "calls_rebuilt": 0,
            "edits_checked": 0, "edits_differing": 0, "exit_lines_restored": 0, "malformed_calls": 0,
            "results_kept_raw": 0, "models": collections.Counter(), "framework_versions": collections.Counter()}


def balanced(receipt):
    """True when every event of the source is either written or set aside."""
    return receipt["written"] + sum(receipt["set_aside"].values()) == receipt["events"]


def load_outcomes(path):
    """{instance id: "resolved" | "no_generation" | "no_logs"} from a SWE-bench results.json."""
    return outcomes_and_conflicts(path)[0]


def outcomes_and_conflicts(path):
    """The outcome of every listed instance, and the ids that appear in more than one list (a conflict that the
    caller must report; the last list read, "resolved", wins)."""
    with open(path, encoding="utf-8") as fh:
        lists = json.load(fh)
    out, conflicts = {}, set()
    for label in ("no_generation", "no_logs", "resolved"):
        for instance in lists.get(label) or []:
            if instance in out and out[instance] != label:
                conflicts.add(instance)
            out[instance] = label
    return out, sorted(conflicts)


def outcome(outcomes, instance):
    """The task outcome of a run; an instance in no list is unresolved; None without a results file."""
    return None if outcomes is None else outcomes.get(instance, "unresolved")


def raw_call(tcm):
    """(response key, response text, tool name, raw JSON arguments) of the call named in the tool-call metadata.
    The response key is the response id, or, when it is missing, the tuple of the response's call ids, so that the
    calls of one response share it."""
    resp = tcm.get("model_response") or {}
    choices = resp.get("choices") or [{}]
    msg = (choices[0] or {}).get("message") or {}
    calls = msg.get("tool_calls") or []
    key = resp.get("id") or (("calls",) + tuple(c.get("id") for c in calls) if calls else None)
    for c in calls:
        if c.get("id") == tcm.get("tool_call_id"):
            return key, msg.get("content"), c["function"]["name"], c["function"]["arguments"]
    return key, msg.get("content"), None, None


def rebuilt_arguments(action):
    args = {k: v for k, v in (action.get("args") or {}).items() if k in KEEP}
    if action.get("action") == "read":
        args.setdefault("command", "view")
    return json.dumps(args)


def check_edit(arguments, action, receipt):
    """Count a str_replace call whose raw arguments disagree with the action the framework recorded."""
    try:
        a = json.loads(arguments)
    except (ValueError, TypeError):
        return
    if not isinstance(a, dict) or a.get("command") != "str_replace":
        return
    receipt["edits_checked"] += 1
    recorded = action.get("args") or {}
    receipt["edits_differing"] += action.get("action") != "edit" or \
        any(a.get(k) != recorded.get(k) for k in ("path", "old_str", "new_str"))


def with_meta(message, **notes):
    notes = {k: v for k, v in notes.items() if v is not None}
    if notes:
        message["meta"] = notes
    return message


def translate_events(events):
    """(messages, receipt) for one OpenHands event list."""
    events = events if isinstance(events, list) else []
    by_id = {e.get("id"): e for e in events if isinstance(e, dict)}
    answered = {e.get("cause") for e in events if isinstance(e, dict) and e.get("observation")
                and (e.get("tool_call_metadata") or {}).get("tool_call_id")}
    out, said, r = [], set(), new_receipt()
    for e in events:
        r["events"] += 1
        if not isinstance(e, dict):
            r["set_aside"]["not an event"] += 1
            continue
        kind, args = e.get("action"), e.get("args") or {}
        if kind == "system":
            out.append({"role": "system", "content": args.get("content") or ""})
            r["written"] += 1
            if args.get("openhands_version"):
                r["framework_versions"][f"OpenHands {args['openhands_version']}"] += 1
        elif kind == "message":
            role = "user" if e.get("source") == "user" else "assistant"
            out.append(with_meta({"role": role, "content": args.get("content") or ""}, time=e.get("timestamp")))
            r["written"] += 1
        elif kind:
            if e.get("id") in answered:
                r["written"] += 1                # written together with its result
            else:
                r["set_aside"][f"action: {kind}"] += 1
        elif e.get("observation"):
            tcm = e.get("tool_call_metadata") or {}
            if not tcm.get("tool_call_id"):
                if e.get("observation") == "error" and e.get("source") == "agent":
                    out.append(with_meta({"role": "error", "content": e.get("content") or ""},
                                         time=e.get("timestamp")))
                    r["written"] += 1
                    r["malformed_calls"] += 1
                else:
                    r["set_aside"][f"result: {e.get('observation')}"] += 1
                continue
            action = by_id.get(e.get("cause")) or {}
            rid, text, name, arguments = raw_call(tcm)
            if arguments is None:
                name, arguments = tcm.get("function_name"), rebuilt_arguments(action)
                r["calls_rebuilt"] += 1
            else:
                check_edit(arguments, action, r)
            resp = tcm.get("model_response") or {}
            first = rid is None or rid not in said
            if not isinstance(text, str) or not text:
                text = (action.get("args") or {}).get("thought") or ""
            said.add(rid)
            if resp.get("model") and first:
                r["models"][resp["model"]] += 1
            usage = resp.get("usage") or {}
            tokens = ({"prompt": usage.get("prompt_tokens"), "completion": usage.get("completion_tokens")}
                      if first and usage else None)
            result = e.get("content") if isinstance(e.get("content"), str) else ""
            extras = e.get("extras") or {}
            if e.get("observation") == "run":
                meta = extras.get("metadata") or {}
                prefix, suffix = meta.get("prefix") or "", meta.get("suffix") or ""
                restored = False
                if prefix and not result.startswith(prefix):
                    result, restored = prefix + result, True
                if suffix and not result.endswith(suffix):
                    result, restored = result + suffix, True
                r["exit_lines_restored"] += restored
            files = {}
            if e.get("observation") == "edit" and extras.get("old_content") is not None \
                    and extras.get("new_content") is not None:
                files = {"file_before": extras["old_content"], "file_after": extras["new_content"]}
            out.append(with_meta({"role": "assistant", "content": text, "tool_calls": [
                {"id": tcm["tool_call_id"], "function": {"name": name, "arguments": arguments}}]},
                time=action.get("timestamp") or e.get("timestamp"), tokens=tokens,
                shared_response=None if first else True))
            out.append(with_meta({"role": "tool", "content": result, "tool_call_id": tcm["tool_call_id"]},
                                 time=e.get("timestamp"), **files))
            r["written"] += 1
            r["calls"] += 1
        else:
            r["set_aside"]["unknown event"] += 1
    return out, r


def events_to_messages(events):
    return translate_events(events)[0]


def run_record(run_id, source, messages=None, observations=None, receipt=None, model=None, outcome_label=None,
               patch=None, task=None, collection=None):
    receipt = receipt or new_receipt()
    if model is None and receipt["models"]:
        model = receipt["models"].most_common(1)[0][0]
    return {"id": run_id, "task": task or run_id, "collection": collection, "source": source, "model": model,
            "outcome": outcome_label,
            "patch": patch, "messages": messages, "observations": observations, "receipt": receipt}


def swehero(paths, model=None):
    """Runs from SWE-Hero parquet shards (no task outcomes: the dataset does not include them)."""
    import pyarrow.parquet as pq

    for path in paths:
        table = pq.read_table(path, columns=["trajectory_id", "instance_id", "dataset", "trajectory", "model_patch"])
        for row in table.to_pylist():
            msgs = row["trajectory"]
            r = new_receipt()
            r["events"] = r["written"] = len(msgs)
            r["calls"] = sum(len(m.get("tool_calls") or []) for m in msgs)
            yield run_record(row["trajectory_id"], "swehero", messages=msgs, receipt=r, model=model,
                             patch=row["model_patch"], task=row["instance_id"], collection=row["dataset"])


def openhands_events(set_dir, outcomes=None):
    """Runs from every `<set_dir>/<instance>/trajectory.json`."""
    for f in sorted(glob.glob(os.path.join(set_dir, "*", "trajectory.json"))):
        instance = os.path.basename(os.path.dirname(f))
        with open(f, encoding="utf-8") as fh:
            msgs, r = translate_events(json.load(fh))
        yield run_record(instance, "openhands_events", messages=msgs, receipt=r,
                         outcome_label=outcome(outcomes, instance), collection="SWE-bench Verified")


def result_text(rest):
    """The text inside a stored tool result such as "[{'type': 'text', 'text': '...'}]" (a Python literal), or
    None when the literal cannot be read."""
    try:
        parts = ast.literal_eval(rest)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    if isinstance(parts, list):
        return "".join(p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str))
    return None


def read_observation_log(messages):
    """([(tool, text)], receipt) for an observation-only log."""
    out, r = [], new_receipt()
    for m in messages if isinstance(messages, list) else []:
        r["events"] += 1
        s = m.get("content") if isinstance(m, dict) else None
        found = TOOL_PREFIX.match(s) if isinstance(s, str) else None
        if found:
            text = result_text(found.group(2))
            if text is None:
                text = found.group(2)
                r["results_kept_raw"] += 1
            out.append((found.group(1), text))
            r["written"] += 1
        elif isinstance(s, str) and s.startswith("Action:"):
            r["set_aside"]["action not recorded"] += 1
        elif isinstance(m, dict) and m.get("role") in ("system", "user"):
            r["set_aside"]["prompt"] += 1
        else:
            r["set_aside"]["other message"] += 1
    return out, r


def observation_log(messages):
    return read_observation_log(messages)[0]


def observation_logs(set_dir, outcomes=None):
    """Runs from every `<set_dir>/<instance>.json` of an observation-only submission."""
    for f in sorted(glob.glob(os.path.join(set_dir, "*.json"))):
        instance = os.path.basename(f)[:-len(".json")]
        with open(f, encoding="utf-8") as fh:
            obs, r = read_observation_log(json.load(fh))
        yield run_record(instance, "observations_only", observations=obs, receipt=r,
                         outcome_label=outcome(outcomes, instance), collection="SWE-bench Verified")


def editor_outcome(text):
    """Sort one file-editor result: noop, missing, multiple, other_error, edited, created, undo, view or other.
    Checked in this order; "other" includes empty and unrecognized results."""
    t = (text or "").lstrip()
    if t.startswith(("ERROR", "Invalid", "No replacement", "Ran into")):
        if "must be different" in t:
            return "noop"
        if "did not appear verbatim" in t:
            return "missing"
        if re.search(r"[Mm]ultiple occurrences", t):
            return "multiple"
        return "other_error"
    if "has been edited" in t[:300]:
        return "edited"
    if t.startswith("File created successfully"):
        return "created"
    if t.startswith("Last edit to") and "undone" in t[:300]:
        return "undo"
    if VIEW.search(t[:400]):
        return "view"
    return "other"
