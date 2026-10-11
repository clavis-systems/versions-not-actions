"""Tests for grafo_versioni.py on a scripted run of agente_gemma.py (fake model, fake test runner).

    python -m unittest test_grafo_versioni
"""

import unittest

import agente_gemma as A
import grafo_versioni as G
from test_agente_gemma import TASK, call
from test_analisi_prova_gemma import FIX, scripted


class Replay(unittest.TestCase):
    def test_versions_loops_tests_and_a_back_edge(self):
        run = scripted(True, [call("str_replace", path=A.FILE, old_str="return a * b", new_str="x"),
                              call("str_replace", path=A.FILE, old_str=FIX[0], new_str=FIX[1]),
                              call("run_tests"),
                              call("str_replace", path=A.FILE, old_str=FIX[1], new_str=FIX[0]),
                              call("run_tests"), call("finish")])
        g = G.replay(run, TASK["files"][A.FILE])
        self.assertEqual(len(g["nodes"]), 2)
        self.assertEqual([(e["from"], e["to"], e["step"], e["back"]) for e in g["edges"]],
                         [(0, 1, 2, False), (1, 0, 4, True)])
        self.assertEqual([a["type"] for a in g["nodes"][0]["attempts"]], ["missing"])
        self.assertTrue(g["nodes"][0]["attempts"][0]["note"].startswith("The closest text"))
        self.assertEqual([t["passed"] for t in g["nodes"][1]["tests"]], [True])
        self.assertEqual([t["passed"] for t in g["nodes"][0]["tests"]], [False])
        self.assertEqual(g["final"], 0)
        svg = G.figure([g], "test")
        self.assertTrue(svg.startswith("<svg") and "back to v0" in svg and "×1 missing" in svg)

    def test_a_replay_that_does_not_match_stops(self):
        run = scripted(False, [call("str_replace", path=A.FILE, old_str=FIX[0], new_str=FIX[1]), call("finish")])
        with self.assertRaises(ValueError):
            G.replay(run, TASK["files"][A.FILE].replace("return a - b", "return a - c", 1))


if __name__ == "__main__":
    unittest.main()
