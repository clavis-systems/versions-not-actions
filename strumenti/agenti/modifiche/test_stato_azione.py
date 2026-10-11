"""Tests for stato_azione.py on made-up calls.

    python -m unittest test_stato_azione
"""

import unittest

import stato_azione as S

ED = "str_replace_editor"
OK = "The file /a.py has been edited. Here's the result of running `cat -n` on a snippet of /a.py:"
MISSING = "ERROR:\nNo replacement was performed, old_str `x` did not appear verbatim in /a.py."
UNDO = "Last edit to /a.py undone successfully. Here's the result of running `cat -n` on /a.py:"


def edit(old, new, before, after, result=OK):
    return (ED, {"command": "str_replace", "path": "/a.py", "old_str": old, "new_str": new}, result,
            {"file_before": before, "file_after": after} if after is not None else {})


def bash(cmd):
    return ("execute_bash", {"command": cmd}, "ok\n[The command completed with exit code 0.]", {})


class Measure(unittest.TestCase):
    def test_returns_loops_and_type_cycles(self):
        calls = [edit("a", "b", "a\n", "b\n"),                    # v0 -> v1 (first EDIT: no cycle)
                 edit("x", "y", None, None, MISSING),               # loop, new action; type cycle: failed
                 bash("pytest"),
                 edit("x", "y", None, None, MISSING),               # loop, repeated action; type cycle: failed
                 edit("b", "a", "b\n", "a\n"),                     # back to v0, new action; type cycle: return
                 edit("a", "b", "a\n", "b\n"),                     # back to v1, repeated action; type cycle: return
                 edit("b", "c", "b\n", "c\n")]                     # progress
        c = S.measure(calls)
        self.assertEqual((c["returns"], c["returns_not_recurrence"]), (2, 1))
        self.assertEqual((c["stuck_attempts"], c["stuck_not_recurrence"]), (2, 1))
        self.assertEqual((c["type_cycles_progress"], c["type_cycles_return"], c["type_cycles_failed"],
                          c["type_cycles_known"]), (1, 2, 2, 5))

    def test_undo_is_a_return(self):
        calls = [edit("a", "b", "a\n", "b\n"),
                 (ED, {"command": "undo_edit", "path": "/a.py"}, UNDO, {"file_before": "b\n", "file_after": "a\n"})]
        c = S.measure(calls)
        self.assertEqual((c["undo_edits"], c["returns"], c["returns_not_recurrence"]), (1, 1, 1))

    def test_untracked_change_and_return(self):
        calls = [edit("a", "b", "a\n", "b\n"), bash("git checkout /a.py"), edit("a", "z", "a\n", "z\n")]
        c = S.measure(calls)
        self.assertEqual((c["untracked_changes"], c["untracked_returns"], c["returns"]), (1, 1, 0))

    def test_unknown_content_restarts_the_replay(self):
        calls = [(ED, {"command": "str_replace", "path": "f", "old_str": "1", "new_str": "2"}, OK, {}),
                 (ED, {"command": "str_replace", "path": "f", "old_str": "zz", "new_str": "q"}, OK, {}),
                 (ED, {"command": "str_replace", "path": "f", "old_str": "2", "new_str": "1"}, OK, {})]
        c = S.measure(calls, {"f": "x = 1\n"})
        self.assertEqual((c["edits_with_state"], c["edits_without_state"], c["returns"]), (1, 2, 0))
        self.assertEqual(c["type_cycles_unknown"], 2)

    def test_replay_from_a_known_start_and_calls_without_result(self):
        calls = [(ED, {"command": "str_replace", "path": "f", "old_str": "1", "new_str": "2"}, OK, {}),
                 (ED, {"command": "str_replace", "path": "f", "old_str": "2", "new_str": "1"}, OK, {}),
                 ("execute_bash", {"command": "ls"}, "", {}),
                 ("execute_bash", {"command": "pwd"}, None, {})]
        c = S.measure(calls, {"f": "x = 1\n"})
        self.assertEqual((c["edits_with_state"], c["returns"], c["returns_not_recurrence"]), (2, 1, 1))
        self.assertEqual((c["calls_with_empty_result"], c["calls_without_result_message"]), (1, 1))

    def test_an_edit_that_changes_nothing_is_not_progress(self):
        calls = [edit("a", "b", "a\n", "b\n"),
                 (ED, {"command": "insert", "path": "/a.py", "new_str": "", "insert_line": 1}, OK,
                  {"file_before": "b\n", "file_after": "b\n"})]
        c = S.measure(calls)
        self.assertEqual((c["edits_no_change"], c["type_cycles_no_change"], c["type_cycles_progress"],
                          c["returns"]), (1, 1, 0, 0))


if __name__ == "__main__":
    unittest.main()
