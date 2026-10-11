"""Tests for analisi_prova_gemma.py on scripted runs of agente_gemma.py (fake model, fake test runner).

    python -m unittest test_analisi_prova_gemma
"""

import unittest

import agente_gemma as A
import analisi_prova_gemma as S
from test_agente_gemma import TASK, call, fake_runner

FIX = ('"""Return a + b."""\n    return a - b', '"""Return a + b."""\n    return a + b')


def scripted(guard, replies):
    script = iter(replies)
    return A.run_task(TASK, guard=guard, chat=lambda m: next(script), runner=fake_runner)


class OneRun(unittest.TestCase):
    def test_calls_outcomes_recovery_and_repeats(self):
        run = scripted(True, [call("view", path=A.FILE),
                              call("str_replace", path=A.FILE, old_str="return a * b", new_str="return a + b"),
                              {"message": {"content": "Let me look again."}},
                              call("str_replace", path=A.FILE, old_str="return a / b", new_str="return a + b"),
                              call("str_replace", path=A.FILE, old_str=FIX[0], new_str=FIX[1]),
                              call("str_replace", path=A.FILE, old_str=FIX[0], new_str=FIX[1]),
                              call("run_tests"), call("finish")])
        seq = S.turns(run["messages"])
        self.assertEqual(seq, [("view", None), ("str_replace", "missing"), ("text", None), ("str_replace", "missing"),
                               ("str_replace", "edited"), ("str_replace", "missing"), ("run_tests", None),
                               ("finish", None)])
        self.assertEqual(len(seq), run["calls"])
        self.assertEqual(S.recovery_calls(seq), 3 + 2)       # text, missing, edited; then run_tests, finish
        self.assertEqual(S.repeated_failures(seq), 1)        # missing after missing; the last one follows an edit
        self.assertEqual(S.notes(run["messages"]), {"closest": 2, "already_made_edit": 1})
        self.assertTrue(run["solved"])


class Statistics(unittest.TestCase):
    def test_mcnemar_exact(self):
        self.assertEqual(S.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(S.mcnemar_exact(9, 1), 22 / 1024)
        self.assertAlmostEqual(S.mcnemar_exact(15, 5), 2 * 21700 / 2 ** 20)
        self.assertAlmostEqual(S.mcnemar_exact(5, 15), S.mcnemar_exact(15, 5))
        self.assertEqual(S.min_wins_needed(20), 15)
        self.assertEqual(S.min_wins_needed(10), 9)
        self.assertIsNone(S.min_wins_needed(4))

    def test_bootstrap_is_seeded(self):
        a, b = S.bootstrap_mean([1, 0, -1, 2]), S.bootstrap_mean([1, 0, -1, 2])
        self.assertEqual(a, b)
        self.assertEqual(a["mean"], 0.5)
        self.assertLessEqual(a["low"], a["mean"])
        self.assertGreaterEqual(a["high"], a["mean"])


class WholeTest(unittest.TestCase):
    def test_pairs_exclusions_and_wins(self):
        solve = [call("str_replace", path=A.FILE, old_str=FIX[0], new_str=FIX[1]), call("finish")]
        give_up = [call("finish")]
        broken = dict(scripted(False, give_up), solved=None, infra_error="ollama: URLError: refused")
        runs = {0: {"off": scripted(False, give_up), "on": scripted(True, solve)},
                1: {"off": scripted(False, solve), "on": scripted(True, solve)},
                2: {"off": broken, "on": scripted(True, solve)},
                3: {"off": scripted(False, solve), "on": None}}
        out = S.analyse(runs)
        self.assertEqual((out["tasks_total"], out["tasks_compared"]), (4, 2))
        self.assertEqual([e["task"] for e in out["excluded"]], [2, 3])
        self.assertEqual(out["excluded"][0]["why"], ["off: ollama: URLError: refused"])
        l1 = out["L1"]
        self.assertEqual((l1["solved_off"], l1["solved_on"], l1["wins"], l1["losses"]), (1, 2, 1, 0))
        self.assertEqual((l1["p"], l1["supported"]), (1.0, False))
        self.assertEqual((out["solved_on_not_off"], out["solved_off_not_on"]), ([0], []))
        self.assertEqual(out["describe"]["on"]["str_replace_outcomes"], {"edited": 2})
        self.assertIsNone(out["L1_sensitivity_suspicious_as_unsolved"])


if __name__ == "__main__":
    unittest.main()
