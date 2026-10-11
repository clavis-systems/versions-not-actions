"""Tests for misura.py on invented data only (no dataset, no model, no network).

    python -m unittest test_misura
"""

import json
import unittest

import formati
import misura
from test_rilevatori import FAILED, NOOP, bash, edit


def run(messages, outcome=None):
    receipt = formati.new_receipt()
    receipt["events"] = receipt["written"] = len(messages)
    return formati.run_record("r", "swehero", messages=messages, receipt=receipt, outcome_label=outcome,
                              collection="invented")


class Rates(unittest.TestCase):
    def test_ratio_of_sums_with_an_interval_around_it(self):
        out = misura.rate([1, 0, 2, 1], [10, 10, 10, 10])
        self.assertEqual((out["num"], out["den"], out["value"]), (4, 40, 0.1))
        self.assertTrue(out["ci95"][0] <= 0.1 <= out["ci95"][1])
        self.assertIsNone(misura.rate([0, 0], [0, 0])["ci95"])

    def test_difference_of_resolution_rates(self):
        out = misura.difference([1, 1, 0, 0, 1, 0], [True, True, True, False, False, False])
        self.assertAlmostEqual(out["value"], 2 / 3 - 1 / 3)
        self.assertEqual((out["n_group"], out["n_other"]), (3, 3))
        self.assertIsNone(misura.difference([1, 0], [True, True])["value"])


class Records(unittest.TestCase):
    def test_counts_of_one_invented_run(self):
        a, b = "result = old_compute(x)", "result = new_compute(x)"
        msgs = (edit(a, b) + bash("pytest -q", FAILED) + edit(b, a) + edit(a, b) +
                edit("x = 1", "x = 1", NOOP) + edit("zzz_value = 9", "w = 0", "ERROR:\nNo replacement was performed, "
                                                                           "old_str `zzz_value = 9` did not appear "
                                                                           "verbatim in /a.py."))
        r = misura.record(run(msgs, "resolved"))
        self.assertEqual((r["str_replace"], r["failed"], r["types"]["noop"], r["types"]["missing"]), (5, 2, 1, 1))
        self.assertEqual((r["classes"]["never_seen"], r["noops"], r["causes"]["after_failure"]), (1, 1, 1))
        self.assertEqual((r["retry_bad"], r["retry_bad_with_names"], r["retry_bad_named"]), (1, 1, 0))
        self.assertEqual((r["editor"]["edited"], r["editor"]["noop"], r["editor"]["missing"]), (3, 1, 1))
        s = misura.summary([r, misura.record(run(edit(a, b), "unresolved"))])
        self.assertEqual(s["failed_str_replace_per_call"]["value"], 2 / 6)
        self.assertEqual(s["outcome"]["with_vs_without_noop"]["value"], 1.0)



class Version2(unittest.TestCase):
    """Checks for the points raised by Codex's review of 09/10 (B3, B5, B6, N1)."""

    def test_clopper_pearson_is_valid_at_zero(self):
        self.assertAlmostEqual(misura.clopper_pearson(0, 30)[1], 1 - 0.025 ** (1 / 30), places=6)
        self.assertLess(misura.clopper_pearson(0, 36)[1], 0.10)
        lo, hi = misura.clopper_pearson(5, 20)
        self.assertTrue(lo < 0.25 < hi)
        self.assertIsNone(misura.clopper_pearson(0, 0))

    def test_per_run_counts_runs_not_events(self):
        out = misura.per_run([0, 2, 0, 0], [3, 2, 0, 1])
        self.assertEqual((out["runs"], out["runs_with_a_naming"]), (3, 1))

    def test_paired_difference_uses_shared_tasks(self):
        a = [{"task": t, "failed": f, "str_replace": 10} for t, f in (("t1", 2), ("t2", 1), ("t3", 3))]
        b = [{"task": t, "failed": f, "str_replace": 10} for t, f in (("t1", 1), ("t2", 0), ("t4", 9))]
        out = misura.paired_difference(a, b)
        self.assertEqual(out["tasks"], 2)
        self.assertAlmostEqual(out["value"], 3 / 20 - 1 / 20)

    def test_tokens_of_a_response_are_split_among_its_calls(self):
        msgs = [{"role": "assistant", "tool_calls": [{}], "meta": {"tokens": {"prompt": 90, "completion": 10}}},
                {"role": "tool", "content": "a"},
                {"role": "assistant", "tool_calls": [{}], "meta": {"shared_response": True}},
                {"role": "tool", "content": "b"},
                {"role": "assistant", "tool_calls": [{}], "meta": {"tokens": {"prompt": 30, "completion": 0}}}]
        self.assertEqual(misura.token_shares(msgs), {0: 50.0, 2: 50.0, 4: 30.0})

    def test_non_finite_values_become_null(self):
        self.assertEqual(misura.finite({"a": float("nan"), "b": [1.0, float("inf")]}), {"a": None, "b": [1.0, None]})
        self.assertEqual(misura.status(False, True), "not_evaluable")


class Version3(unittest.TestCase):
    """Checks for the second review by Codex (09/10, 22:30)."""

    def test_tokens_split_among_the_calls_of_one_message(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [
                    {"id": "a", "function": {"name": "str_replace_editor", "arguments": json.dumps(
                        {"command": "str_replace", "path": "/a.py", "old_str": "x = 1", "new_str": "x = 1"})}},
                    {"id": "b", "function": {"name": "execute_bash", "arguments": json.dumps({"command": "ls"})}}],
                 "meta": {"tokens": {"prompt": 90, "completion": 10}}},
                {"role": "tool", "content": NOOP, "tool_call_id": "a"},
                {"role": "tool", "content": "a.py", "tool_call_id": "b"}]
        r = misura.record(run(msgs))
        self.assertEqual((r["tokens_all"], r["tokens_failed_str_replace"]), (100.0, 50.0))

    def test_two_errors_need_disjoint_error_names(self):
        a, b, c = "result = old_compute(x)", "result = new_compute(x)", "result = third_compute(x)"
        same_error = (edit(a, b) + bash("pytest -q", "FAILED test_a.py::test_a - AssertionError") + edit(b, c) +
                      bash("pytest -q", "FAILED test_a.py::test_b - AssertionError") + edit(c, b))
        r = misura.record(run(same_error))
        self.assertEqual((r["circles"], r["circles_two_errors"]), (1, 0))

    def test_ids_are_reconciled_between_submissions(self):
        recs = {"openhands_qwen3_coder_30b": [{"id": "x__y-1", "balanced": True, "receipt": {}}],
                "openhands_qwen3_coder_480b": [{"id": "x__y-2", "balanced": True, "receipt": {}}]}
        problems = misura.structural_problems(recs, {k: {} for k in recs})
        self.assertIn("the 30B and 480B submissions do not cover the same tasks", problems)


class Version4(unittest.TestCase):
    def test_expected_run_counts_are_checked(self):
        recs = {'openhands_claude_opus_4_5': [{'id': 'x__y-1', 'balanced': True, 'receipt': {}}]}
        self.assertIn('openhands_claude_opus_4_5: 1 runs instead of 489', misura.structural_problems(recs, {}))


if __name__ == "__main__":
    unittest.main()
