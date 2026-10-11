"""Tests for formati.py on invented data only (no dataset, no model, no network).

    python -m unittest test_formati
"""

import json
import tempfile
import unittest
from pathlib import Path

import formati

SUFFIX = "\n[The command completed with exit code 1.]"


def obs(i, cause, kind, content, call_id, name, args, text="", rid=None, extras=None, raw=True):
    call = {"id": call_id, "function": {"name": name, "arguments": json.dumps(args)}}
    message = {"content": text, "tool_calls": [call] if raw else []}
    return {"id": i, "cause": cause, "observation": kind, "content": content, "source": "agent",
            "extras": extras or {},
            "tool_call_metadata": {"function_name": name, "tool_call_id": call_id, "total_calls_in_response": 1,
                                   "model_response": {"id": rid or call_id, "choices": [{"message": message}]}}}


EDIT = {"command": "str_replace", "path": "/a.py", "old_str": "x = 1", "new_str": "x = 2"}
NOOP = {"command": "str_replace", "path": "/a.py", "old_str": "x = 2", "new_str": "x = 2"}
EVENTS = [
    {"id": 0, "action": "system", "source": "agent", "args": {"content": "system prompt"}},
    {"id": 1, "action": "message", "source": "user", "args": {"content": "fix the bug"}},
    {"id": 2, "action": "recall", "source": "user", "args": {}},
    {"id": 3, "observation": "recall", "cause": 2, "content": "Added workspace context", "extras": {}},
    {"id": 4, "action": "edit", "source": "agent", "args": dict(EDIT, thought="")},
    obs(5, 4, "edit", "The file /a.py has been edited.", "c1", "str_replace_editor", EDIT, text="I change x"),
    {"id": 6, "action": "run", "source": "agent", "args": {"command": "pytest"}},
    obs(7, 6, "run", "1 failed", "c2", "execute_bash", {"command": "pytest"},
        extras={"metadata": {"exit_code": 1, "prefix": "", "suffix": SUFFIX}}),
    {"id": 8, "action": "edit", "source": "agent", "args": dict(NOOP, thought="")},
    obs(9, 8, "edit", "ERROR:\nInvalid `new_str` parameter: x = 2. No replacement was performed. "
        "`new_str` and `old_str` must be different.", "c3", "str_replace_editor", NOOP),
]


class EventsToMessages(unittest.TestCase):
    def test_order_roles_calls_and_results(self):
        m = formati.events_to_messages(EVENTS)
        self.assertEqual([x["role"] for x in m],
                         ["system", "user", "assistant", "tool", "assistant", "tool", "assistant", "tool"])
        self.assertEqual(m[2]["content"], "I change x")
        call = m[2]["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "str_replace_editor")
        self.assertEqual(json.loads(call["function"]["arguments"]), EDIT)
        self.assertEqual(m[3]["tool_call_id"], "c1")
        self.assertEqual(m[5]["content"], "1 failed" + SUFFIX)
        self.assertTrue(m[7]["content"].startswith("ERROR") and "must be different" in m[7]["content"])

    def test_exit_code_line_is_not_added_twice(self):
        e = obs(1, 0, "run", "ok" + SUFFIX, "c", "execute_bash", {"command": "ls"},
                extras={"metadata": {"suffix": SUFFIX}})
        self.assertEqual(formati.events_to_messages([e])[1]["content"], "ok" + SUFFIX)

    def test_call_rebuilt_from_the_action_when_the_raw_call_is_missing(self):
        action = {"id": 0, "action": "read", "source": "agent",
                  "args": {"path": "/a.py", "view_range": [1, 5], "thought": "look", "start": 0}}
        e = obs(1, 0, "read", "Here's the result of running `cat -n` on /a.py", "c", "str_replace_editor", {},
                raw=False)
        call = formati.events_to_messages([action, e])[0]
        self.assertEqual(json.loads(call["tool_calls"][0]["function"]["arguments"]),
                         {"path": "/a.py", "view_range": [1, 5], "command": "view"})
        self.assertEqual(call["content"], "look")

    def test_a_malformed_call_is_kept_as_an_error_message(self):
        e = {"id": 1, "observation": "error", "source": "agent", "cause": None, "extras": {},
             "content": 'Missing required argument "command" in tool call str_replace_editor'}
        recall = {"id": 2, "observation": "recall", "source": "environment", "cause": 0, "content": "context"}
        self.assertEqual(formati.events_to_messages([e, recall]),
                         [{"role": "error", "content": e["content"]}])

    def test_every_call_of_a_response_keeps_its_text_and_later_calls_are_marked(self):
        a = obs(1, 0, "run", "a", "c1", "execute_bash", {"command": "ls"}, text="two things", rid="r")
        b = obs(2, 0, "run", "b", "c2", "execute_bash", {"command": "pwd"}, text="two things", rid="r")
        b["tool_call_metadata"]["model_response"]["choices"][0]["message"]["tool_calls"].append(
            {"id": "c2", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "pwd"})}})
        m = formati.events_to_messages([a, b])
        self.assertEqual([m[0]["content"], m[2]["content"]], ["two things", "two things"])
        self.assertEqual((m[0].get("meta"), m[2]["meta"]), (None, {"shared_response": True}))
        self.assertEqual(json.loads(m[2]["tool_calls"][0]["function"]["arguments"]), {"command": "pwd"})


class Receipts(unittest.TestCase):
    def test_every_event_is_written_or_set_aside_with_a_reason(self):
        msgs, r = formati.translate_events(EVENTS)
        self.assertTrue(formati.balanced(r))
        self.assertEqual((r["events"], r["written"], dict(r["set_aside"])),
                         (10, 8, {"action: recall": 1, "result: recall": 1}))
        self.assertEqual((r["calls"], r["calls_rebuilt"], r["edits_checked"], r["edits_differing"],
                          r["exit_lines_restored"], r["malformed_calls"]), (3, 0, 2, 0, 1, 0))

    def test_a_raw_call_that_disagrees_with_the_recorded_action_is_counted(self):
        action = {"id": 0, "action": "edit", "source": "agent", "args": dict(EDIT, old_str="x = 9")}
        _, r = formati.translate_events([action, obs(1, 0, "edit", "The file /a.py has been edited.", "c",
                                                     "str_replace_editor", EDIT)])
        self.assertEqual((r["edits_checked"], r["edits_differing"]), (1, 1))

    def test_observation_log_receipt(self):
        log, r = formati.read_observation_log([
            {"role": "system", "content": "s"}, {"role": "user", "content": "u"},
            {"role": "assistant", "content": "Action: unknown"},
            {"role": "assistant", "content": "[file_editor] [{'type': 'text', 'text': 'File created successfully'}]"},
            {"role": "assistant", "content": "[terminal] [{'type': 'text', 'text': 'unterminated"},
            {"role": "assistant", "content": "plain text"}])
        self.assertEqual(len(log), 2)
        self.assertTrue(formati.balanced(r))
        self.assertEqual(dict(r["set_aside"]), {"prompt": 2, "action not recorded": 1, "other message": 1})
        self.assertEqual(r["results_kept_raw"], 1)


class MarginNotes(unittest.TestCase):
    def test_time_tokens_model_and_file_states(self):
        action = {"id": 1, "action": "edit", "source": "agent", "timestamp": "2025-07-31T19:16:00", "args": dict(EDIT)}
        o = obs(2, 1, "edit", "The file /a.py has been edited.", "c1", "str_replace_editor", EDIT, text="t",
                extras={"old_content": "x = 1\n", "new_content": "x = 2\n"})
        o["timestamp"] = "2025-07-31T19:16:02"
        o["tool_call_metadata"]["model_response"].update(model="m1",
                                                         usage={"prompt_tokens": 100, "completion_tokens": 7})
        msgs, r = formati.translate_events([action, o])
        self.assertEqual(msgs[0]["meta"], {"time": "2025-07-31T19:16:00", "tokens": {"prompt": 100, "completion": 7}})
        self.assertEqual(msgs[1]["meta"], {"time": "2025-07-31T19:16:02", "file_before": "x = 1\n",
                                           "file_after": "x = 2\n"})
        self.assertEqual(dict(r["models"]), {"m1": 1})

    def test_tokens_of_a_response_are_counted_on_its_first_call_only(self):
        a = obs(1, 0, "run", "a", "c1", "execute_bash", {"command": "ls"}, rid="r")
        b = obs(2, 0, "run", "b", "c2", "execute_bash", {"command": "pwd"}, rid="r")
        for e in (a, b):
            e["tool_call_metadata"]["model_response"]["usage"] = {"prompt_tokens": 50, "completion_tokens": 5}
        b["tool_call_metadata"]["model_response"]["choices"][0]["message"]["tool_calls"].append(
            {"id": "c2", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "pwd"})}})
        msgs = formati.events_to_messages([a, b])
        self.assertEqual(msgs[0]["meta"]["tokens"], {"prompt": 50, "completion": 5})
        self.assertEqual(msgs[2]["meta"], {"shared_response": True})


class Covers(unittest.TestCase):
    def test_outcomes_and_runs_from_a_set_folder(self):
        root = Path(tempfile.mkdtemp())
        (root / "results.json").write_text(json.dumps({"resolved": ["t1"], "no_logs": ["t2"], "no_generation": []}),
                                           encoding="utf-8")
        outcomes = formati.load_outcomes(root / "results.json")
        self.assertEqual([formati.outcome(outcomes, t) for t in ("t1", "t2", "t3")],
                         ["resolved", "no_logs", "unresolved"])
        self.assertIsNone(formati.outcome(None, "t1"))
        (root / "set" / "t1").mkdir(parents=True)
        (root / "set" / "t1" / "trajectory.json").write_text(json.dumps(EVENTS), encoding="utf-8")
        runs = list(formati.openhands_events(root / "set", outcomes))
        self.assertEqual([(x["id"], x["collection"], x["source"], x["outcome"], len(x["messages"])) for x in runs],
                         [("t1", "SWE-bench Verified", "openhands_events", "resolved", 8)])


class ObservationLogs(unittest.TestCase):
    def test_stored_results_are_read_as_literals_and_bad_ones_kept_raw(self):
        log = formati.observation_log([
            {"role": "assistant", "content": "Action: unknown"},
            {"role": "assistant", "content": "[file_editor] [{'cache_prompt': False, 'type': 'text', "
                                             "'text': 'File created successfully at: /a.py'}]"},
            {"role": "assistant", "content": "[terminal] [{'type': 'text', 'text': 'unterminated"},
            {"role": "user", "content": None}])
        self.assertEqual(log, [("file_editor", "File created successfully at: /a.py"),
                               ("terminal", "[{'type': 'text', 'text': 'unterminated")])

    def test_editor_outcomes(self):
        cases = {
            "ERROR:\nInvalid `new_str` parameter: x. No replacement was performed. "
            "`new_str` and `old_str` must be different.": "noop",
            "Invalid `new_str` parameter: x. No replacement was performed. `new_str` and `old_str` must be "
            "different.": "noop",
            "No replacement was performed, old_str `y` did not appear verbatim in /a.py.": "missing",
            "ERROR:\nNo replacement was performed. Multiple occurrences of old_str `z` in lines [3, 9].": "multiple",
            "Ran into [Errno 13] Permission denied: '/a.py'": "other_error",
            "The file /a.py has been edited. Here's the result of running `cat -n` on a snippet": "edited",
            "File created successfully at: /a.py": "created",
            "Here's the result of running `cat -n` on /a.py:\n 1\tmsg = 'must be different'": "view",
            "Last edit to /a.py undone successfully. Here's the result of running `cat -n`": "undo",
            "Image file /a.png read successfully.": "other",
            "NOTE: We only show up to 417 since there're only 417 lines in this file.\n"
            "Here's the result of running `cat -n` on /a.py:": "view",
            "": "other",
        }
        for text, want in cases.items():
            self.assertEqual(formati.editor_outcome(text), want, text)


class Version3(unittest.TestCase):
    def test_a_raw_str_replace_recorded_as_another_action_is_counted_as_differing(self):
        action = {"id": 0, "action": "run", "source": "agent", "args": {"command": "ls"}}
        _, r = formati.translate_events([action, obs(1, 0, "edit", "The file /a.py has been edited.", "c",
                                                     "str_replace_editor", EDIT)])
        self.assertEqual((r["edits_checked"], r["edits_differing"]), (1, 1))


class Version4(unittest.TestCase):
    def test_ids_in_two_lists_are_reported(self):
        root = Path(tempfile.mkdtemp())
        (root / 'r.json').write_text(json.dumps({'resolved': ['t1'], 'no_generation': ['t1', 't2']}), encoding='utf-8')
        out, conflicts = formati.outcomes_and_conflicts(root / 'r.json')
        self.assertEqual((out['t1'], out['t2'], conflicts), ('resolved', 'no_generation', ['t1']))

    def test_calls_of_a_response_without_id_share_its_tokens(self):
        a = obs(1, 0, 'run', 'a', 'c1', 'execute_bash', {'command': 'ls'})
        b = obs(2, 0, 'run', 'b', 'c2', 'execute_bash', {'command': 'pwd'})
        both = [{'id': 'c1', 'function': {'name': 'execute_bash', 'arguments': json.dumps({'command': 'ls'})}},
                {'id': 'c2', 'function': {'name': 'execute_bash', 'arguments': json.dumps({'command': 'pwd'})}}]
        for e in (a, b):
            resp = e['tool_call_metadata']['model_response']
            del resp['id']
            resp['usage'] = {'prompt_tokens': 90, 'completion_tokens': 10}
            resp['choices'][0]['message']['tool_calls'] = both
        msgs = formati.events_to_messages([a, b])
        self.assertEqual((msgs[0]['meta']['tokens'], msgs[2]['meta']), ({'prompt': 90, 'completion': 10}, {'shared_response': True}))


if __name__ == "__main__":
    unittest.main()
