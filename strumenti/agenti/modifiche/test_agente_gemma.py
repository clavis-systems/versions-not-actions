"""Tests for agente_gemma.py: a scripted fake model and a fake test runner, plus one check in the real WASM sandbox
(skipped if the sandbox or the dataset is missing). No model, no GPU, no network.

    python -m unittest test_agente_gemma
"""

import json
import os
import re
import tempfile
import unittest

import agente_gemma as A

TASK = {"id": "T/0", "entry_point": "add", "files": {A.FILE: (
    "def helper(x):\n    return x + 1\n\n\ndef add(a, b):\n    \"\"\"Return a + b.\"\"\"\n    return a - b\n\n\n"
    "def other(a, b):\n    return a - b\n")},
    "visible_test": "def check(f):\n    assert f(2, 3) == 5\n", "hidden_test": "def check(f):\n    assert f(1, 1) == 2\n",
    "test_setup": "", "statement": "Fix add."}


def fake_runner(program, files):
    ok = "return a + b" in files[A.FILE]
    passed = re.search(r"print\('(.*PASSED.*)'\)", program).group(1)
    return ok, (passed if ok else "Traceback (most recent call last):\n    assert f(2, 3) == 5\nAssertionError")


def call(name, **args):
    return {"message": {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]},
            "prompt_eval_count": 10, "eval_count": 2}


class Tools(unittest.TestCase):
    def test_plain_messages(self):
        ws = A.Workspace(TASK, guard=False, runner=fake_runner)
        self.assertTrue(ws.view(A.FILE).startswith("Here's the result of running `cat -n` on solution.py:\n     1\tdef"))
        self.assertIn("must be different", ws.str_replace(A.FILE, "x", "x"))
        self.assertIn("did not appear verbatim", ws.str_replace(A.FILE, "return a * b", "return a + b"))
        self.assertIn("Multiple occurrences of old_str `return a - b` in lines [7, 11]",
                      ws.str_replace(A.FILE, "return a - b", "return a + b"))
        self.assertNotIn("[Host note]", ws.str_replace(A.FILE, "return a * b", "y"))
        ok = ws.str_replace(A.FILE, '    """Return a + b."""\n    return a - b', '    """Return a + b."""\n    return a + b')
        self.assertTrue(ok.startswith("The file solution.py has been edited."))
        self.assertIn("exit code 0", ws.run_tests())

    def test_guard_notes(self):
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)

        def replace(old, new):
            return ws.call("str_replace", {"path": A.FILE, "old_str": old, "new_str": new})

        self.assertIn("[Host note] The closest text in the file is at lines",
                      replace("    return a -  b  # sum", "    return a + b"))
        self.assertIn("The text appears at:\n- line 7, in function `add`:\n    return a - b\n"
                      "- line 11, in function `other`:\n    return a - b\nAdd nearby lines",
                      replace("return a - b", "return a + b"))
        replace('"""Return a + b."""\n    return a - b', '"""Return a + b."""\n    return a + b')
        self.assertIn("You already made this change at step 3", replace("return a + b", "return a + b"))
        self.assertIn("old_str and new_str are identical", replace("nothing = 1", "nothing = 1"))

    def test_revisit_note_recalls_the_failing_test(self):
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)

        def replace(old, new):
            return ws.call("str_replace", {"path": A.FILE, "old_str": old, "new_str": new})

        wrong = '"""Return a + b."""\n    return b - a + 0'
        replace('"""Return a + b."""\n    return a - b', wrong)
        ws.call("run_tests", {})
        replace(wrong, '"""Return a + b."""\n    return a * b')
        note = replace('"""Return a + b."""\n    return a * b', wrong)
        self.assertIn("identical to a version that was already in the file at step 2", note)
        self.assertIn("assert f(2, 3) == 5 / AssertionError", note)

    def test_a_repeated_edit_is_named_not_sent_back_to_copy(self):
        """The smoke-test scene (task 1, guard on): the same successful edit sent again."""
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)
        edit = {"path": A.FILE, "old_str": '"""Return a + b."""\n    return a - b',
                "new_str": '"""Return a + b."""\n    return a + b'}
        self.assertTrue(ws.call("str_replace", edit).startswith("The file solution.py has been edited."))
        note = ws.call("str_replace", edit)
        self.assertIn("You already made this exact edit at step 1", note)
        self.assertIn("your new_str is now at lines 6-7", note)
        self.assertNotIn("Copy old_str", note)

    def test_text_removed_by_an_earlier_edit(self):
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)
        ws.call("str_replace", {"path": A.FILE, "old_str": "def helper(x):\n    return x + 1",
                                "new_str": "def helper(x):\n    return x + 2"})
        note = ws.call("str_replace", {"path": A.FILE, "old_str": "def helper(x):\n    return x + 1",
                                       "new_str": "def helper(x):\n    return x + 3"})
        self.assertIn("old_str was in the file until your edit at step 1 changed it", note)
        self.assertIn("The closest text in the file is at lines 1-2", note)

    def test_a_near_copy_shows_where_it_differs(self):
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)
        note = ws.call("str_replace", {"path": A.FILE, "old_str": "    return x + 1\n    \n\ndef add(a, b):",
                                       "new_str": "    return x + 1\n\n\ndef add(a, b, c=0):"})
        self.assertIn("It differs from your old_str only in spaces at line 3: the file has '', your old_str has "
                      "'    '", note)
        note = ws.call("str_replace", {"path": A.FILE, "old_str": "def add(a, b):\n    \"\"\"Return a+b.\"\"\"",
                                       "new_str": "def add(a, b):\n    \"\"\"Sum.\"\"\""})
        self.assertIn("It differs from your old_str at line 6: the file has '    \"\"\"Return a + b.\"\"\"', your "
                      "old_str has '    \"\"\"Return a+b.\"\"\"'", note)
        off = A.Workspace(TASK, guard=False, runner=fake_runner)
        self.assertNotIn("[Host note]", off.call("str_replace", {"path": A.FILE, "old_str": "    return x + 1\n    \n",
                                                                  "new_str": "    return x + 2\n"}))

    def test_a_repeated_failed_call_is_named_first(self):
        """Dev task 15: the same non-unique old_str sent again and again."""
        on, off = A.Workspace(TASK, guard=True, runner=fake_runner), A.Workspace(TASK, guard=False, runner=fake_runner)
        same = {"path": A.FILE, "old_str": "return a - b", "new_str": "return a + b"}
        first, second, third = (on.call("str_replace", same) for _ in range(3))
        self.assertNotIn("already sent", first)
        self.assertIn("[Host note] You already sent this exact call at step 1, on this same version of the file", second)
        self.assertIn("at steps 1, 2,", third)
        self.assertLess(third.index("already sent"), third.index("The text appears at"))
        for _ in range(3):
            self.assertNotIn("[Host note]", off.call("str_replace", same))
        on.call("str_replace", {"path": A.FILE, "old_str": "def helper(x):", "new_str": "def helper(y):"})
        self.assertNotIn("already sent", on.call("str_replace", same))      # another version of the file

    def test_edge_cases_of_the_notes(self):
        """Codex review 2: noop attribution, every occurrence of new_str, and the advice for a repeated noop."""
        ws = A.Workspace(TASK, guard=True, runner=fake_runner)
        self.assertIn("old_str and new_str are identical", ws.call("str_replace", {
            "path": A.FILE, "old_str": "return x + 1", "new_str": "return x + 1"}))       # in the file from the start
        ws.call("str_replace", {"path": A.FILE, "old_str": "def helper(x):\n    return x + 1",
                                "new_str": "def helper(x):\n    return x * 1"})
        self.assertIn("You already made this change at step 2", ws.call("str_replace", {
            "path": A.FILE, "old_str": "return x * 1", "new_str": "return x * 1"}))
        repeat = ws.call("str_replace", {"path": A.FILE, "old_str": "return x * 1", "new_str": "return x * 1"})
        self.assertIn("Repeating it cannot work: change new_str.", repeat)
        self.assertEqual(A.line_spans("a\nb\nc\nb\nc\n", "b\nc"), "2-3, 4-5")
        self.assertEqual(A.line_spans("a\nb\n", "\nb"), "2")

    def test_suspicious_additions_are_listed(self):
        before = TASK["files"][A.FILE]
        after = before.replace("    return a - b\n\n\ndef other", "    import sys; sys.exit(0)\n\n\ndef other")
        self.assertEqual(A.suspicious_additions(before, after), ["exit(", "sys."])
        self.assertEqual(A.suspicious_additions(before, before.replace("a - b", "a + b", 1)), [])

    def test_hidden_outcome_needs_the_nonce(self):
        self.assertEqual(A.hidden_outcome(True, "HIDDEN TESTS PASSED ab12\n", "ab12"), "passed")
        self.assertEqual(A.hidden_outcome(True, "HIDDEN TESTS PASSED\n", "ab12"), "unclear")
        self.assertEqual(A.hidden_outcome(True, "", "ab12"), "unclear")
        self.assertEqual(A.hidden_outcome(False, "Traceback (most recent call last):\n  ...", "ab12"), "failed")
        self.assertEqual(A.hidden_outcome(False, "Timeout: limite di esecuzione superato.", "ab12"), "failed")


class Loop(unittest.TestCase):
    def test_a_scripted_run_is_logged_in_the_common_shape(self):
        script = iter([call("view", path=A.FILE),
                       call("str_replace", path=A.FILE, old_str='"""Return a + b."""\n    return a - b',
                            new_str='"""Return a + b."""\n    return a + b'),
                       call("run_tests"), call("finish")])
        out = A.run_task(TASK, guard=False, chat=lambda messages: next(script), runner=fake_runner)
        self.assertEqual((out["solved"], out["finished"], out["calls"]), (True, True, 4))
        names = [json.loads(m["tool_calls"][0]["function"]["arguments"]).get("command")
                 for m in out["messages"] if m.get("tool_calls")]
        self.assertEqual(names[:3], ["view", "str_replace", "python -m pytest (example tests)"])
        self.assertEqual([m["role"] for m in out["messages"][:4]], ["system", "user", "assistant", "tool"])

    def test_text_without_tools_is_nudged_and_counted(self):
        replies = iter([{"message": {"content": "I think the bug is the minus."}}, call("finish")])
        out = A.run_task(TASK, guard=True, chat=lambda m: next(replies), runner=fake_runner)
        self.assertEqual((out["calls"], out["finished"], out["solved"]), (2, True, False))

    def test_the_call_budget_is_never_exceeded(self):
        three = {"message": {"content": "", "tool_calls": [
            {"function": {"name": "view", "arguments": {"path": A.FILE}}}] * 3}}
        replies = iter([call("view", path=A.FILE), three])
        out = A.run_task(TASK, guard=False, chat=lambda m: next(replies), runner=fake_runner, max_calls=2)
        self.assertEqual((out["calls"], out["dropped_calls"], out["finished"]), (2, 2, False))
        self.assertEqual(sum(1 for m in out["messages"] if m["role"] == "tool"), 2)

    def test_a_test_file_that_was_not_removed_stops_the_run(self):
        """Codex review 3: if the hidden-test file cannot be deleted, the solution never runs and nothing is scored."""
        program = A.test_program("def check(f):\n    pass\n", "add", "HIDDEN TESTS", "", "n0nce", hide=True)
        self.assertLess(program.index("raise SystemExit(3)"), program.index("from solution import *"))
        compile(program, "program.py", "exec")

        def stuck(program, files):
            if "HIDDEN TESTS" in program:
                return False, f"{A.NOT_REMOVED} [Errno 63] read-only\n"
            return fake_runner(program, files)
        out = A.run_task(TASK, guard=True, chat=lambda m: call("finish"), runner=stuck)
        self.assertEqual((out["solved"], out["hidden"]), (None, None))
        self.assertIn("could not be removed", out["infra_error"])

    def test_an_infrastructure_error_is_recorded_not_scored(self):
        def broken(messages):
            raise A.InfraError("ollama: URLError: refused")
        out = A.run_task(TASK, guard=True, chat=broken, runner=fake_runner)
        self.assertEqual((out["solved"], out["hidden"], out["infra_error"]), (None, None, "ollama: URLError: refused"))


class Runs(unittest.TestCase):
    def test_results_are_saved_whole_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "000_on.json")
            A.save_result(path, {"task": "T/0", "guard": True, "config": {"a": 1}})
            with self.assertRaises(SystemExit):
                A.save_result(path, {"task": "T/0"})
            self.assertEqual(os.listdir(d), ["000_on.json"])
            A.check_existing(path, {"a": 1}, "T/0", True)
            for args in (({"a": 2}, "T/0", True), ({"a": 1}, "T/1", True), ({"a": 1}, "T/0", False)):
                with self.assertRaises(SystemExit):
                    A.check_existing(path, *args)

    def test_the_order_of_conditions_depends_only_on_seed_and_task(self):
        self.assertEqual(A.condition_order(20261011, 5), A.condition_order(20261011, 5))
        orders = {tuple(A.condition_order(20261011, i)) for i in range(20)}
        self.assertEqual(orders, {("off", "on"), ("on", "off")})


@unittest.skipUnless(os.path.exists(A.DATA), "dataset not downloaded")
class RealData(unittest.TestCase):
    def test_tasks_and_the_sandbox(self):
        rows = A.load_rows()
        task = A.build_task(rows, 0)
        text = task["files"][A.FILE]
        self.assertEqual(text.count("def has_close_elements("), 1)
        self.assertEqual(text.count(rows[0]["buggy_solution"].strip()), 1)
        try:
            ws = A.Workspace(task, guard=False)
            self.assertIn("exit code 1", ws.run_tests())
        except A.InfraError as exc:                                 # sandbox not installed
            self.skipTest(f"sandbox unavailable: {exc}")
        fixed = text.replace(rows[0]["buggy_solution"].rstrip("\n"), rows[0]["canonical_solution"].rstrip("\n"))
        program = A.test_program(task["hidden_test"], task["entry_point"], "HIDDEN TESTS", task["test_setup"], "n0nce",
                                 hide=True)
        ok, out = A.sandbox_run(program, {A.FILE: fixed})
        self.assertEqual(A.hidden_outcome(ok, out, "n0nce"), "passed", out)
        ok, out = A.sandbox_run(program, {A.FILE: text})
        self.assertEqual(A.hidden_outcome(ok, out, "n0nce"), "failed", out)
        spy = fixed + ("\ntry:\n    open('/sandbox/program.py').read()\n    print('SPY READ THE TESTS')\n"
                       "except OSError:\n    print('SPY FOUND NOTHING')\n")
        ok, out = A.sandbox_run(program, {A.FILE: spy})
        self.assertIn("SPY FOUND NOTHING", out)
        self.assertEqual(A.hidden_outcome(ok, out, "n0nce"), "passed", out)


if __name__ == "__main__":
    unittest.main()
