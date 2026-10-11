"""Tests for rilevatori.py on invented trajectories only (no dataset, no model, no network).

    python -m unittest test_rilevatori
"""

import json
import unittest

import rilevatori as R

OK = "The file /a.py has been edited. Here's the result of running `cat -n` on a snippet of /a.py:\n     1\tz = 0"
NOOP = "ERROR:\nNo replacement was performed. `new_str` and `old_str` must be different."
FAILED = "FAILED test_a.py::test_x - AssertionError\n[The command completed with exit code 1.]"


def call(name, args, text=""):
    return {"role": "assistant", "content": text,
            "tool_calls": [{"id": "c", "function": {"name": name, "arguments": json.dumps(args)}}]}


def res(content):
    return {"role": "tool", "content": content}


def edit(old, new, result=OK, text=""):
    return [call("str_replace_editor", {"command": "str_replace", "path": "/a.py", "old_str": old, "new_str": new},
                 text), res(result)]


def view(numbered):
    return [call("str_replace_editor", {"command": "view", "path": "/a.py"}),
            res("Here's the result of running `cat -n` on /a.py:\n" + numbered)]


def missing(s):
    return edit(s, "unused = 0", f"ERROR:\nNo replacement was performed, old_str `{s}` did not appear verbatim in /a.py.")


def bash(command, result):
    return [call("execute_bash", {"command": command}), res(result)]


class Calls(unittest.TestCase):
    def test_unreadable_or_non_object_arguments_are_skipped(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [{"id": "1", "function": {"name": "x",
                                                                                            "arguments": "not json"}}]},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "2", "function": {"name": "y",
                                                                                            "arguments": "[1, 2]"}}]}]
        self.assertEqual(list(R.calls(msgs)), [])


class EditFailures(unittest.TestCase):
    def kinds(self, msgs):
        return [(e["error"], e.get("kind")) for e in R.edit_failures(msgs)]

    def test_missing_text_classes(self):
        self.assertEqual(self.kinds(view("     1\tx = 1\n     2\ty = 3") + edit("x = 1", "x = 2") + missing("x = 1")),
                         [("missing", "stale")])
        self.assertEqual(self.kinds(missing("zzz_value = 9")), [("missing", "never_seen")])
        self.assertEqual(self.kinds(view("     1\ta  =  1") + missing("a = 1")), [("missing", "copy_error")])
        self.assertEqual(self.kinds(view("     1\tq = 1") + missing("q = 1")), [("missing", "seen_not_modified")])

    def test_noop_is_typed(self):
        self.assertEqual(self.kinds(edit("w = 1", "w = 1", NOOP)), [("noop", None)])


class Noops(unittest.TestCase):
    def test_causes_in_order(self):
        found = R.noops(edit("x = 1", "x = 2") + edit("x = 2", "x = 2", NOOP))
        self.assertEqual([(f["kind"], f["cost"], f["fate"]) for f in found], [("already_applied", None, "never")])
        found = R.noops(edit("k = 0", "k = 0", NOOP) + edit("k = 0", "k = 0", NOOP))
        self.assertEqual([f["kind"] for f in found], ["other", "repeat_attempt"])

    def test_after_a_failed_command_and_fixed_at_the_same_spot(self):
        msgs = (bash("python t.py", "Traceback (most recent call last):") +
                edit("value = compute(a)", "value = compute(a)", NOOP) +
                edit("value = compute(a)\nreturn value", "value = compute(b)\nreturn value"))
        self.assertEqual([(f["kind"], f["cost"], f["fate"]) for f in R.noops(msgs)], [("after_failure", 1, "same_spot")])


class Reverts(unittest.TestCase):
    def test_flip_flop_debug_whitespace_and_undo(self):
        msgs = (edit("alpha = 1", "alpha = 2") + edit("alpha = 2", "alpha = 1") +
                edit("beta = 1", "beta = 1\nprint(beta)") + edit("beta = 1\nprint(beta)", "beta = 1") +
                edit("gamma = 1", "gamma  = 1") +
                [call("str_replace_editor", {"command": "undo_edit", "path": "/a.py"}),
                 res("Last edit to /a.py undone successfully.")])
        out = R.reverts(msgs)
        self.assertEqual([(x["kind"], x["turns"]) for x in out["reverts"]], [("flip_flop", 1), ("debug", 1)])
        self.assertEqual((out["str_replace_ok"], out["whitespace_only"], out["undo"]), (5, 1, 1))


class Revisits(unittest.TestCase):
    def test_back_to_original_then_a_known_bad_retry_removed_again(self):
        a, b, c = "result = old_compute(x)", "result = new_compute(x)", "result = third_compute(x)"
        msgs = edit(a, b) + bash("pytest -q", FAILED) + edit(b, a) + edit(a, b) + edit(b, c)
        ev = R.revisits(msgs)
        self.assertEqual([(e["kind"], e["step"], e["tested"], e["again"]) for e in ev],
                         [("back_to_original", 4, False, None), ("retry_own", 6, True, 1)])
        self.assertIsNone(ev[0]["known_bad"])
        self.assertEqual(ev[1]["known_bad"], (1, True, "FAILED test_a.py::test_x - AssertionError"))
        self.assertEqual([R.remembers(msgs, e) for e in ev], [None, False])
        self.assertEqual([e["replaced_bad"] for e in ev], [(1, True, "FAILED test_a.py::test_x - AssertionError"), None])
        said = edit(a, b) + bash("pytest -q", FAILED) + edit(b, a) + edit(a, b, text="Back to the AssertionError one")
        self.assertTrue(R.remembers(said, R.revisits(said)[1]))
        self.assertEqual([(e["removed_at"], e["known_bad_kind"], e["project_changed"]) for e in ev],
                         [(0, None, False), (4, "application", False)])

    def test_infrastructure_failures_and_changes_elsewhere_are_marked(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        other = [call("str_replace_editor", {"command": "str_replace", "path": "/b.py", "old_str": "y = 1",
                                             "new_str": "y = 2"}), res(OK)]
        msgs = (edit(a, b) + bash("python t.py", "ModuleNotFoundError: No module named 'lib'\n"
                                                 "[The command completed with exit code 1.]") +
                edit(b, a) + other + edit(a, b))
        retry = R.revisits(msgs)[-1]
        self.assertEqual((retry["kind"], retry["known_bad_kind"], retry["project_changed"]),
                         ("retry_own", "infra", True))


class Intent(unittest.TestCase):
    def test_declared_undeclared_and_silent(self):
        msgs = (bash("ls", "a.py") +
                [call("think", {"thought": "Let me revert my change to check that the test fails"}),
                 res("Your thought has been logged.")] +
                edit("a1 = 1", "a1 = 2") + edit("a1 = 2", "a1 = 3", text="Now fix the parser") + edit("a1 = 3", "a1 = 4"))
        self.assertEqual([R.intent(msgs, i) for i in (4, 6, 8)], ["declared", "undeclared", "silent"])



class Version2(unittest.TestCase):
    """Checks for the points raised by Codex's review of 09/10 (B1, B2, B3, B7)."""

    def test_results_are_paired_by_id_and_missing_results_are_unknown(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [
                    {"id": "x", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "ls"})}},
                    {"id": "y", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "pwd"})}}]},
                {"role": "tool", "content": "from y", "tool_call_id": "y"},
                {"role": "tool", "content": "from x", "tool_call_id": "x"},
                call("str_replace_editor", {"command": "str_replace", "path": "/a.py", "old_str": "a", "new_str": "b"})]
        self.assertEqual([obs for i, n, a, obs in R.calls(msgs)], ["from x", "from y", ""])
        self.assertEqual(R.result_kind("str_replace", ""), "unknown")
        self.assertEqual(R.result_kind("str_replace", "File created successfully at: /a.py"), "unknown")
        self.assertEqual(R.result_kind("create", "File created successfully at: /a.py"), "ok")
        self.assertEqual([e["error"] for e in R.edit_failures(msgs)], ["unknown"])

    def test_a_first_bash_read_counts_as_seen(self):
        msgs = bash("cat /a.py", "x = 1\ny = 2") + missing("x = 1")
        self.assertEqual([e.get("kind") for e in R.edit_failures(msgs)], ["seen_not_modified"])

    def test_after_failure_uses_the_exit_code(self):
        msgs = bash("python t.py", "\n[The command completed with exit code 1.]") + edit("k = 0", "k = 0", NOOP)
        self.assertEqual([f["kind"] for f in R.noops(msgs)], ["after_failure"])

    def test_descriptor_copies_are_not_writes_but_unknown_writes_make_provenance_uncertain(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        clean = bash("python t.py 2>&1 | tail -5", "ok") + edit(a, b) + edit(b, a)
        self.assertEqual([(e["kind"], e["life_certain"]) for e in R.revisits(clean)], [("back_to_original", True)])
        dirty = bash("sed -i 's/x/y/' setup.cfg", "") + edit(a, b) + edit(b, a)
        self.assertEqual([(e["kind"], e["life_certain"]) for e in R.revisits(dirty)],
                         [("uncertain_provenance", False)])

    def test_a_mixed_block_has_uncertain_provenance_and_no_known_failure(self):
        a1, a9, b = "alpha = compute(1)", "alpha = compute(9)", "beta = compute(2)"
        msgs = (edit(a1, a9) + bash("pytest -q", FAILED) + edit(a9 + "\n" + b, "gamma = compute(0)") +
                edit("gamma = compute(0)", a9 + "\n" + b))
        ev = R.revisits(msgs)
        self.assertEqual([(e["kind"], e["life_certain"], e["known_bad"]) for e in ev],
                         [("uncertain_provenance", False, None)])

    def test_an_insert_ends_the_certain_presence_of_blocks_in_that_file(self):
        a, b, c = "result = old_compute(x)", "result = new_compute(x)", "result = third_compute(x)"
        insert = [call("str_replace_editor", {"command": "insert", "path": "/a.py", "insert_line": 1,
                                              "new_str": "import os"}), res(OK)]
        msgs = edit(a, b) + bash("pytest -q", FAILED) + insert + edit(b, c) + edit(c, b)
        retry = R.revisits(msgs)[-1]
        self.assertEqual((retry["kind"], retry["life_certain"], retry["known_bad"]), ("retry_own", False, None))

    def test_an_original_block_stays_original_after_the_agent_writes_it_again(self):
        a, b, c = "result = old_compute(x)", "result = new_compute(x)", "result = third_compute(x)"
        msgs = edit(a, b) + edit(b, a) + edit(a, c) + edit(c, a)
        self.assertEqual([e["kind"] for e in R.revisits(msgs)], ["back_to_original", "back_to_original"])

    def test_names_are_matched_as_whole_words(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        failing = "FAILED tests/test_x.py::test_foobar - AssertionError\n[The command completed with exit code 1.]"
        msgs = (edit(a, b) + bash("pytest -q", failing) + edit(b, a) +
                edit(a, b, text="test_foo and AssertionErrors are unrelated"))
        retry = R.revisits(msgs)[-1]
        self.assertEqual(R.names_in(retry["known_bad"][2]), {"test_x", "test_foobar", "AssertionError"})
        self.assertFalse(R.remembers(msgs, retry))


class Version3(unittest.TestCase):
    """Checks for the second review by Codex (09/10, 22:30)."""

    def test_any_other_change_of_the_file_ends_the_certain_presence(self):
        a, b, c = "result = old_compute(x)", "result = new_compute(x)", "result = third_compute(x)"
        elsewhere = edit("tail = abcdefghXYZ", "tail = ZZZABC")
        msgs = edit(a, b) + elsewhere + bash("pytest -q", FAILED) + edit(b, c) + edit(c, b)
        retry = R.revisits(msgs)[-1]
        self.assertEqual((retry["kind"], retry["life_certain"], retry["known_bad"]), ("retry_own", False, None))

    def test_the_most_recent_tested_life_decides(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        passing = "1 passed\n[The command completed with exit code 0.]"
        failed_then_untested = (edit(a, b) + bash("pytest -q", FAILED) + edit(b, a) + edit(a, b) + edit(b, a) +
                                edit(a, b))
        self.assertEqual(R.revisits(failed_then_untested)[-1]["known_bad"][2],
                         "FAILED test_a.py::test_x - AssertionError")
        failed_then_passed = (edit(a, b) + bash("pytest -q", FAILED) + edit(b, a) + edit(a, b) +
                              bash("pytest -q", passing) + edit(b, a) + edit(a, b))
        self.assertIsNone(R.revisits(failed_then_passed)[-1]["known_bad"])

    def test_calls_in_one_message_keep_their_order(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        one = {"role": "assistant", "content": "", "tool_calls": [
            {"id": "", "function": {"name": "str_replace_editor", "arguments": json.dumps(
                {"command": "str_replace", "path": "/a.py", "old_str": a, "new_str": b})}},
            {"id": "", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "pytest -q"})}},
            {"id": "", "function": {"name": "str_replace_editor", "arguments": json.dumps(
                {"command": "str_replace", "path": "/a.py", "old_str": b, "new_str": a})}}]}
        msgs = [one, res(OK), res(FAILED), res(OK)] + edit(a, b)
        retry = R.revisits(msgs)[-1]
        self.assertEqual((retry["kind"], retry["known_bad"][0]), ("retry_own", 1))

    def test_duplicate_ids_fall_back_to_position(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [
                    {"id": "same", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "ls"})}},
                    {"id": "same", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "pwd"})}}]},
                {"role": "tool", "content": "first", "tool_call_id": "same"},
                {"role": "tool", "content": "second", "tool_call_id": "same"}]
        self.assertEqual([obs for i, n, a, obs in R.calls(msgs)], ["first", "second"])
        self.assertEqual(R.pairing_counts(msgs), {"position_after_duplicate_ids": 2})

    def test_a_bash_write_on_the_same_file_counts_as_a_project_change(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        msgs = edit(a, b) + edit(b, a) + bash("sed -i 's/q/r/' /a.py", "") + edit(a, b)
        self.assertTrue(R.revisits(msgs)[-1]["project_changed"])

    def test_unidentified_writes_and_numbered_reads_in_edit_failures(self):
        stale = view("     1\tx = 1") + bash("sed -i 's/1/2/' conf", "") + missing("x = 1")
        self.assertEqual([e.get("kind") for e in R.edit_failures(stale)], ["stale"])
        numbered = bash("cat -n /a.py", "     1\tq = 1\n     2\tr = 2") + missing("q = 1\nr = 2")
        self.assertEqual([e.get("kind") for e in R.edit_failures(numbered)], ["seen_not_modified"])

    def test_error_names_leave_out_tests(self):
        self.assertEqual(R.error_names_in("FAILED test_a.py::test_b - AssertionError"), {"AssertionError"})


class Version4(unittest.TestCase):
    """Checks for the third review by Codex (10/10, 18:26)."""

    def test_a_redirect_to_a_variable_cannot_be_identified(self):
        self.assertIsNone(R.write_targets('echo x >> "$P"', ['/a.py']))
        self.assertEqual(R.write_targets('echo x > "out.txt"', ['/a.py']), {'out.txt'})
        self.assertEqual(R.write_targets('python t.py 2>&1 > /dev/null', ['/a.py']), set())

    def test_changed_lines_count_repeated_lines(self):
        self.assertEqual(R.changed_lines('x = 1' + chr(10) + 'print(x)' + chr(10) + 'print(x)', 'x = 1' + chr(10) + 'print(x)'),
                         ['print(x)'])


if __name__ == "__main__":
    unittest.main()
