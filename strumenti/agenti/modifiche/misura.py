"""Final measurement of failed and wasted edits, as fixed in PREMESSA_MODIFICHE.md.

    python -I misura.py dev       # SWE-Hero shards 0-3 (development data): tests the runner, gives the dev values
    python -I misura.py heldout   # SWE-Hero shards 4-13 and three SWE-bench Verified submissions: run ONCE

Before opening any input file the runner writes strumenti/risultati/modifiche/misura_<part>.started (mode "x"),
with the time and the SHA-256 of the code. It refuses to start if that file exists, so a second held-out run cannot
happen without a trace. Then it writes the SHA-256 of every input file (for the held-out part, misura_dev.json
first) to misura_<part>.inputs.json, and the results to misura_<part>.json, both opened with mode "x". Read only:
the trajectories are data and nothing in them is executed.
"""

import collections
import datetime
import glob
import hashlib
import json
import math
import os
import re
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import rilevatori as R  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXT = os.path.join(ROOT, "esterni")
OUT_DIR = os.path.join(ROOT, "strumenti", "risultati", "modifiche")
REPS, SEED, CHUNK = 2000, 20261009, 100
TYPES = ("noop", "missing", "multiple", "other")
CLASSES = ("stale", "copy_error", "seen_not_modified", "never_seen")
CAUSES = ("already_applied", "repeat_attempt", "after_failure", "other")
FATES = ("same_spot", "elsewhere", "never")
QWEN_SETS = ("swehero_heldout", "openhands_qwen3_coder_30b", "openhands_qwen3_coder_480b")
EXPECTED_RUNS = {"swehero_dev": 10000, "swehero_heldout": 24269, "openhands_qwen3_coder_30b": 500,
                 "openhands_qwen3_coder_480b": 500, "openhands_claude_opus_4_5": 489}
REPLICATED = ("failed_str_replace_per_call", "noop_share_of_failures", "runs_with_noop", "runs_with_circle")
SWEBENCH_ID = re.compile(r"^[\w.-]+__[\w.-]+-\d+$")


def shard(k):
    return os.path.join(EXT, "SWE-Hero-openhands-trajectories", "data", f"train-{k:05d}-of-00014.parquet")


def swebench(trajs, results):
    return os.path.join(EXT, "swebench-trajs", trajs), os.path.join(EXT, "swebench-results", results, "results.json")


PARTS = {
    "dev": [("swehero_dev", "swehero", [shard(k) for k in range(4)])],
    "heldout": [
        ("swehero_heldout", "swehero", [shard(k) for k in range(4, 14)]),
        ("openhands_qwen3_coder_30b", "openhands",
         swebench("20250805-openhands-Qwen3-Coder-30B-A3B-Instruct", "20250805_openhands-Qwen3-Coder-30B-A3B-Instruct")),
        ("openhands_qwen3_coder_480b", "openhands",
         swebench("20250805-openhands-Qwen3-Coder-480B-A35B-Instruct",
                  "20250805_openhands-Qwen3-Coder-480B-A35B-Instruct")),
        ("openhands_claude_opus_4_5", "observations",
         swebench("20251127_openhands_claude-opus-4-5", "20251127_openhands_claude-opus-4-5")),
    ],
}


# ---------- per-run counts ----------

def token_shares(msgs):
    """{message index: tokens of ONE of its calls}. A response's prompt + completion tokens are split evenly among
    all the calls of the response: the calls of its first message and of the following messages marked
    shared_response."""
    shares, group, spent = {}, [], 0

    def close():
        n = sum(len(msgs[i]["tool_calls"]) for i in group)
        for i in group:
            shares[i] = spent / n

    for i, m in enumerate(msgs):
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        meta = m.get("meta") or {}
        if meta.get("shared_response") and group:
            group.append(i)
            continue
        if group:
            close()
        t = meta.get("tokens")
        group, spent = ([i], (t.get("prompt") or 0) + (t.get("completion") or 0)) if t else ([], 0)
    if group:
        close()
    return shares


def record(run):
    """Per-run counts for a run with messages."""
    msgs = run["messages"]
    calls = list(R.calls(msgs))
    sr = [(i, R.result_kind("str_replace", o)) for i, n, a, o in calls
          if n == "str_replace_editor" and a.get("command") == "str_replace"]
    failed_calls = collections.Counter(i for i, k in sr if k in TYPES)
    fails = R.edit_failures(msgs)
    types = collections.Counter(f["error"] for f in fails)
    noops = R.noops(msgs)
    revs = R.revisits(msgs)
    rv = R.reverts(msgs)
    editor = collections.Counter(formati.editor_outcome(o) for i, n, a, o in calls if n == "str_replace_editor")
    own = [e for e in revs if e["kind"] == "retry_own"]
    retry_all = [e for e in own if e["known_bad"]]
    retry_bad = [e for e in retry_all if e["known_bad_kind"] == "application"]
    remembered = [R.remembers(msgs, e) for e in retry_bad]
    same = [x for x, e in zip(remembered, retry_bad) if not e["project_changed"]]
    excluded = {"uncertain_presence": sum(not e["life_certain"] for e in own),
                "never_tested": sum(e["life_certain"] and not e["tested"] for e in own),
                "tested_and_passed": sum(e["tested"] and not e["known_bad"] for e in own),
                "infra_or_unknown_failure": len(retry_all) - len(retry_bad),
                "no_names": sum(x is None for x in remembered)}
    circles = [e for e in revs if e["known_bad_kind"] == "application" and e["replaced_bad"]
               and R.failure_kind(e["replaced_bad"]) == "application"]
    two = [e for e in circles if R.error_names_in(e["known_bad"][2]) and R.error_names_in(e["replaced_bad"][2])
           and not R.error_names_in(e["known_bad"][2]) & R.error_names_in(e["replaced_bad"][2])]
    both = []
    for e in two:
        w = R.window(msgs, e["step"])
        both.append(any(R.mentions(w, x) for x in R.error_names_in(e["known_bad"][2])) and
                    any(R.mentions(w, x) for x in R.error_names_in(e["replaced_bad"][2])))
    shares = token_shares(msgs)
    calls_in = {i: len(m["tool_calls"]) for i, m in enumerate(msgs) if m.get("tool_calls")}
    receipt = run["receipt"]
    return {
        "id": run["id"], "task": run["task"], "collection": run["collection"], "outcome": run["outcome"],
        "balanced": formati.balanced(receipt),
        "receipt": {k: receipt[k] for k in ("events", "written", "calls", "calls_rebuilt", "edits_checked",
                                            "edits_differing", "exit_lines_restored", "malformed_calls",
                                            "results_kept_raw")},
        "set_aside": dict(receipt["set_aside"]),
        "framework_versions": dict(receipt.get("framework_versions") or {}),
        "str_replace": sum(k != "unknown" for i, k in sr), "str_replace_unknown": sum(k == "unknown" for i, k in sr),
        "failed": sum(types[t] for t in TYPES), "types": {t: types[t] for t in TYPES},
        "classes": {c: sum(1 for f in fails if f.get("kind") == c) for c in CLASSES},
        "editor": {k: editor[k] for k in ("edited", "noop", "missing", "multiple")},
        "noops": len(noops), "causes": {c: sum(n["kind"] == c for n in noops) for c in CAUSES},
        "fates": {f: sum(n["fate"] == f for n in noops) for f in FATES},
        "noop_costs": [n["cost"] for n in noops if n["cost"] is not None],
        "revisits": collections.Counter(e["kind"] for e in revs),
        "revisits_life_uncertain": sum(not e["life_certain"] for e in revs),
        "retry_bad": len(retry_bad), "retry_bad_infra_or_unknown": len(retry_all) - len(retry_bad),
        "retry_bad_with_names": sum(x is not None for x in remembered), "retry_bad_named": sum(x is True for x in remembered),
        "retry_bad_project_changed": sum(e["project_changed"] for e in retry_bad),
        "retry_bad_same_with_names": sum(x is not None for x in same), "retry_bad_same_named": sum(x is True for x in same),
        "retry_own_excluded_from_h3": excluded, "pairing": R.pairing_counts(msgs),
        "circles": len(circles), "circles_two_errors": len(two), "circles_both_named": sum(both),
        "flip_flop": sum(x["kind"] == "flip_flop" for x in rv["reverts"]),
        "debug_reverts": sum(x["kind"] == "debug" for x in rv["reverts"]),
        "str_replace_ok": rv["str_replace_ok"], "whitespace_only": rv["whitespace_only"], "undo": rv["undo"],
        "malformed": sum(1 for m in msgs if m.get("role") == "error"),
        "tokens_all": sum(v * calls_in[i] for i, v in shares.items()),
        "tokens_failed_str_replace": sum(v * failed_calls[i] for i, v in shares.items()),
    }


def record_observations(run):
    """Per-run counts for an observation-only run: only the editor's results can be read."""
    editor = collections.Counter(formati.editor_outcome(t) for tool, t in run["observations"]
                                 if tool in ("file_editor", "str_replace_editor"))
    receipt = run["receipt"]
    return {"id": run["id"], "task": run["task"], "collection": run["collection"], "outcome": run["outcome"],
            "balanced": formati.balanced(receipt), "set_aside": dict(receipt["set_aside"]),
            "receipt": {"events": receipt["events"], "written": receipt["written"],
                        "results_kept_raw": receipt["results_kept_raw"]},
            "editor": {k: editor[k] for k in ("edited", "noop", "missing", "multiple")}}


# ---------- statistics ----------

def resamples(n, seed=SEED):
    """Bootstrap index chunks (numpy default_rng(seed).integers): the same sequence for every statistic of a set."""
    rng = np.random.default_rng(seed)
    for start in range(0, REPS, CHUNK):
        yield rng.integers(0, n, size=(min(CHUNK, REPS - start), n))


def quantiles(vals):
    return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))] if len(vals) else None


def rate(num, den):
    """Ratio of sums over runs, with a percentile bootstrap 95% interval (runs resampled, numpy linear quantiles).
    Replicates whose denominator is zero are dropped and counted."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    total = den.sum()
    out = {"num": int(num.sum()), "den": int(total), "value": float(num.sum() / total) if total else None,
           "ci95": None, "invalid_replicates": 0}
    if not total:
        return out
    vals = []
    for idx in resamples(len(num)):
        d = den[idx].sum(axis=1)
        ok = d > 0
        out["invalid_replicates"] += int((~ok).sum())
        vals.extend((num[idx].sum(axis=1)[ok] / d[ok]).tolist())
    out["ci95"] = quantiles(vals)
    return out


def binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                                 + i * math.log(p) + (n - i) * math.log(1 - p)) for i in range(k + 1)))


def clopper_pearson(k, n):
    """Exact two-sided 95% interval for k successes in n (bisection on the binomial distribution)."""
    if n == 0:
        return None
    lower, upper = 0.0, 1.0
    if k > 0:
        lo, hi = 0.0, k / n
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if 1 - binom_cdf(k - 1, n, mid) < 0.025 else (lo, mid)
        lower = lo
    if k < n:
        lo, hi = k / n, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if binom_cdf(k, n, mid) > 0.025 else (lo, mid)
        upper = hi
    return [lower, upper]


def per_run(named, eligible):
    """Runs with at least one eligible case; success = the agent named the error in at least one of them."""
    n = sum(1 for e in eligible if e > 0)
    k = sum(1 for x, e in zip(named, eligible) if e > 0 and x > 0)
    return {"runs": n, "runs_with_a_naming": k, "value": k / n if n else None, "ci95_clopper_pearson": clopper_pearson(k, n)}


def difference(res, group):
    """Resolution rate of runs in the group minus the rate of the others, with a bootstrap 95% interval."""
    res, group = np.asarray(res, float), np.asarray(group, bool)
    out = {"value": None, "ci95": None, "n_group": int(group.sum()), "n_other": int((~group).sum()),
           "invalid_replicates": 0}
    if group.all() or not group.any():
        return out
    vals = []
    for idx in resamples(len(res)):
        r, g = res[idx], group[idx]
        ng, no = g.sum(axis=1), (~g).sum(axis=1)
        ok = (ng > 0) & (no > 0)
        out["invalid_replicates"] += int((~ok).sum())
        vals.extend(((r * g).sum(axis=1)[ok] / ng[ok] - (r * ~g).sum(axis=1)[ok] / no[ok]).tolist())
    out.update(value=float(res[group].mean() - res[~group].mean()), ci95=quantiles(vals),
               rate_group=float(res[group].mean()), rate_other=float(res[~group].mean()))
    return out


def paired_difference(a, b):
    """Failure rate per str_replace call, set a minus set b, on the tasks both sets ran (tasks resampled)."""
    ta, tb = {r["task"]: r for r in a}, {r["task"]: r for r in b}
    tasks = sorted(set(ta) & set(tb))
    fa, ca = (np.asarray([ta[t][k] for t in tasks], float) for k in ("failed", "str_replace"))
    fb, cb = (np.asarray([tb[t][k] for t in tasks], float) for k in ("failed", "str_replace"))
    out = {"tasks": len(tasks), "value": None, "ci95": None, "invalid_replicates": 0}
    if not tasks or not ca.sum() or not cb.sum():
        return out
    vals = []
    for idx in resamples(len(tasks)):
        da, db = ca[idx].sum(axis=1), cb[idx].sum(axis=1)
        ok = (da > 0) & (db > 0)
        out["invalid_replicates"] += int((~ok).sum())
        vals.extend((fa[idx].sum(axis=1)[ok] / da[ok] - fb[idx].sum(axis=1)[ok] / db[ok]).tolist())
    out.update(value=float(fa.sum() / ca.sum() - fb.sum() / cb.sum()), ci95=quantiles(vals))
    return out


# ---------- summaries ----------

def summary(recs, observations=False):
    ones = [1] * len(recs)
    s = {"runs": len(recs), "receipts_balanced": all(r["balanced"] for r in recs),
         "runs_not_balanced": sum(not r["balanced"] for r in recs)}
    totals = collections.Counter()
    aside = collections.Counter()
    for r in recs:
        totals.update(r["receipt"])
        aside.update(r["set_aside"])
    s["receipt_totals"], s["set_aside"] = dict(totals), dict(aside)
    e = [r["editor"] for r in recs]
    s["editor_failure_rate"] = rate([x["noop"] + x["missing"] + x["multiple"] for x in e],
                                    [x["edited"] + x["noop"] + x["missing"] + x["multiple"] for x in e])
    s["editor_noop_share"] = rate([x["noop"] for x in e], [x["noop"] + x["missing"] + x["multiple"] for x in e])
    s["runs_with_noop"] = rate([int(x["noop"] > 0) for x in e], ones)
    if not observations:
        failed = [r["failed"] for r in recs]
        s["failed_str_replace_per_call"] = rate(failed, [r["str_replace"] for r in recs])
        s["str_replace_unknown_outcome"] = int(sum(r["str_replace_unknown"] for r in recs))
        s["failure_type_share"] = {t: rate([r["types"][t] for r in recs], failed) for t in TYPES}
        s["noop_share_of_failures"] = s["failure_type_share"]["noop"]
        missing = [r["types"]["missing"] for r in recs]
        s["missing_class_share"] = {c: rate([r["classes"][c] for r in recs], missing) for c in CLASSES}
        s["runs_with_noop"] = rate([int(r["noops"] > 0) for r in recs], ones)
        noops = [r["noops"] for r in recs]
        s["noop_cause_share"] = {c: rate([r["causes"][c] for r in recs], noops) for c in CAUSES}
        s["noop_fate_share"] = {f: rate([r["fates"][f] for r in recs], noops) for f in FATES}
        costs = [c for r in recs for c in r["noop_costs"]]
        s["noop_calls_to_next_good_edit"] = {"n_fixed": len(costs), "n_never": int(sum(noops)) - len(costs),
                                             "median": statistics.median(costs) if costs else None}
        revisit_kinds = collections.Counter()
        for r in recs:
            revisit_kinds.update(r["revisits"])
        s["revisits"] = dict(revisit_kinds)
        s["revisits_life_uncertain"] = int(sum(r["revisits_life_uncertain"] for r in recs))
        s["runs_with_known_bad_retry"] = rate([int(r["retry_bad"] > 0) for r in recs], ones)
        s["known_bad_retry_error_named"] = rate([r["retry_bad_named"] for r in recs],
                                                [r["retry_bad_with_names"] for r in recs])
        s["known_bad_retry_error_named_per_run"] = per_run([r["retry_bad_named"] for r in recs],
                                                           [r["retry_bad_with_names"] for r in recs])
        s["known_bad_retry_error_named_same_conditions"] = rate([r["retry_bad_same_named"] for r in recs],
                                                                [r["retry_bad_same_with_names"] for r in recs])
        s["known_bad_retry_project_changed"] = rate([r["retry_bad_project_changed"] for r in recs],
                                                    [r["retry_bad"] for r in recs])
        excluded, pairing = collections.Counter(), collections.Counter()
        for r in recs:
            excluded.update(r["retry_own_excluded_from_h3"])
            pairing.update(r["pairing"])
        s["retry_own_excluded_from_h3"] = dict(excluded)
        s["retry_own_eligible_for_h3"] = int(sum(r["retry_bad_with_names"] for r in recs))
        s["pairing"] = dict(pairing)
        s["runs_with_circle"] = rate([int(r["circles"] > 0) for r in recs], ones)
        s["circles_two_errors_both_named"] = rate([r["circles_both_named"] for r in recs],
                                                  [r["circles_two_errors"] for r in recs])
        s["circles_two_errors_both_named_per_run"] = per_run([r["circles_both_named"] for r in recs],
                                                             [r["circles_two_errors"] for r in recs])
        s["runs_with_flip_flop"] = rate([int(r["flip_flop"] > 0) for r in recs], ones)
        s["whitespace_only_share"] = rate([r["whitespace_only"] for r in recs], [r["str_replace_ok"] for r in recs])
        s["counts"] = {k: int(sum(r[k] for r in recs)) for k in (
            "str_replace", "str_replace_unknown", "failed", "noops", "retry_bad", "retry_bad_infra_or_unknown",
            "circles", "circles_two_errors", "flip_flop", "debug_reverts", "undo", "malformed")}
        versions = collections.Counter()
        for r in recs:
            versions.update(r["framework_versions"])
        s["framework_versions"] = dict(versions)
        if any(r["tokens_all"] for r in recs):
            s["token_share_in_failed_str_replace_calls"] = rate([r["tokens_failed_str_replace"] for r in recs],
                                                                [r["tokens_all"] for r in recs])
    graded = [r for r in recs if r["outcome"] in ("resolved", "unresolved")]
    if graded:
        res = [int(r["outcome"] == "resolved") for r in graded]
        noop = [(r["noops"] if "noops" in r else r["editor"]["noop"]) > 0 for r in graded]
        s["outcome"] = {"graded_runs": len(graded), "resolved_rate": float(np.mean(res)),
                        "not_graded": len(recs) - len(graded), "with_vs_without_noop": difference(res, noop)}
        if not observations:
            s["outcome"]["with_vs_without_circle"] = difference(res, [r["circles"] > 0 for r in graded])
    return s


def reconcile(recs, outcomes):
    ids = [r["id"] for r in recs]
    return {"runs": len(ids), "unique_ids": len(set(ids)), "ids_not_like_swebench": sum(not SWEBENCH_ID.match(i) for i in ids),
            "listed_in_results": len(outcomes), "listed_without_a_run": len(set(outcomes) - set(ids)),
            "runs_not_listed_counted_unresolved": len(set(ids) - set(outcomes))}


def structural_problems(sets_recs, sets_outcomes, conflicts=None):
    """Checks that must pass before the hypotheses are evaluated."""
    problems = [f"{k}: {len(v)} ids in more than one list of results.json" for k, v in (conflicts or {}).items() if v]
    for name, recs in sets_recs.items():
        if name in EXPECTED_RUNS and len(recs) != EXPECTED_RUNS[name]:
            problems.append(f"{name}: {len(recs)} runs instead of {EXPECTED_RUNS[name]}")
        bad = sum(not r["balanced"] for r in recs)
        if bad:
            problems.append(f"{name}: {bad} receipts not balanced")
        differing = sum(r["receipt"].get("edits_differing", 0) for r in recs)
        if differing:
            problems.append(f"{name}: {differing} str_replace calls differ from the recorded action")
        if len({r["id"] for r in recs}) != len(recs):
            problems.append(f"{name}: duplicate run ids")
    small, large = "openhands_qwen3_coder_30b", "openhands_qwen3_coder_480b"
    if small in sets_recs and large in sets_recs:
        ids = {k: {r["id"] for r in sets_recs[k]} for k in sets_recs if sets_outcomes.get(k) is not None}
        universe = ids[small] | ids[large]
        if ids[small] != ids[large]:
            problems.append("the 30B and 480B submissions do not cover the same tasks")
        for k in ids:
            if ids[k] - universe:
                problems.append(f"{k}: {len(ids[k] - universe)} run ids outside the shared task list")
            if set(sets_outcomes[k]) - universe:
                problems.append(f"{k}: {len(set(sets_outcomes[k]) - universe)} ids in results.json outside the "
                                "shared task list")
    return problems


def status(evaluable, supported):
    return "not_evaluable" if not evaluable else "supported" if supported else "not_supported"


def hypotheses(sets, recs, dev):
    h = {}
    q = [sets[k] for k in QWEN_SETS]
    h1 = []
    for s in q:
        shares = {t: s["failure_type_share"][t]["value"] for t in TYPES}
        h1.append(s["failure_type_share"]["noop"]["den"] > 0 and
                  all(shares["noop"] > shares[t] for t in TYPES if t != "noop"))
    h["H1"] = {"rule": "in each Qwen set, failures > 0 and the noop share strictly above every other type",
               "per_set": dict(zip(QWEN_SETS, h1)),
               "status": status(all(s["failure_type_share"]["noop"]["den"] > 0 for s in q), all(h1))}
    d = paired_difference(recs["openhands_qwen3_coder_30b"], recs["openhands_qwen3_coder_480b"])
    h["H2"] = {"rule": "failed str_replace per call, 30B minus 480B on the shared tasks (tasks resampled): "
                       "95% interval above 0", "difference": d,
               "status": status(d["ci95"] is not None, d["ci95"] is not None and d["ci95"][0] > 0)}
    for key, field in (("H3", "known_bad_retry_error_named_per_run"), ("H4", "circles_two_errors_both_named_per_run")):
        per_set = {k: sets[k][field] for k in QWEN_SETS}
        evaluable = {k: v for k, v in per_set.items() if v["runs"] >= 30}
        h[key] = {"rule": f"{field}: in every Qwen set with at least 30 eligible runs, the Clopper-Pearson 95% upper "
                          "bound is below 0.10 (at least one such set)", "evaluable_sets": sorted(evaluable),
                  "status": status(bool(evaluable), all(v["ci95_clopper_pearson"][1] < 0.10 for v in evaluable.values()))}
    h5 = {k: sets[k].get("outcome", {}).get("with_vs_without_noop", {}) for k in QWEN_SETS[1:]}
    h["H5"] = {"rule": "resolution rate with a no-op minus without, 95% interval below 0, in both OpenHands Qwen sets",
               "status": status(all(v.get("ci95") for v in h5.values()),
                                all(v.get("ci95") and v["ci95"][1] < 0 for v in h5.values()))}
    r2e = sets["swehero_heldout"]["by_collection"].get("R2E-Gym/R2E-Gym-Subset")
    ok = bool(r2e) and all(r2e[k]["ci95"] is not None and dev[k]["value"] is not None for k in REPLICATED)
    h["H6"] = {"rule": "dev point estimate inside the 95% interval of the held-out R2E-Gym runs, for " + ", ".join(REPLICATED),
               "dev": {k: dev[k]["value"] for k in REPLICATED},
               "held_out_r2e": {k: (r2e[k]["value"], r2e[k]["ci95"]) if r2e else None for k in REPLICATED},
               "status": status(ok, ok and all(r2e[k]["ci95"][0] <= dev[k]["value"] <= r2e[k]["ci95"][1]
                                               for k in REPLICATED))}
    return h


# ---------- run ----------

def inputs(part):
    files = []
    for name, kind, where in PARTS[part]:
        if kind == "swehero":
            files += where
        else:
            trajs, results = where
            files += sorted(glob.glob(os.path.join(trajs, "**", "*.json"), recursive=True)) + [results]
    return files


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite(v) for v in x]
    return x


def read(kind, where):
    """(records, outcomes, conflicting ids in results.json)."""
    if kind == "swehero":
        return [record(run) for run in formati.swehero(where)], None, []
    trajs, results = where
    outcomes, conflicts = formati.outcomes_and_conflicts(results)
    if kind == "openhands":
        return [record(run) for run in formati.openhands_events(trajs, outcomes)], outcomes, conflicts
    return [record_observations(run) for run in formati.observation_logs(trajs, outcomes)], outcomes, conflicts


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else ""
    if part not in PARTS:
        sys.exit("usage: python -I misura.py dev|heldout")
    os.makedirs(OUT_DIR, exist_ok=True)
    started, out_path = (os.path.join(OUT_DIR, f"misura_{part}.{x}") for x in ("started", "json"))
    if os.path.exists(started) or os.path.exists(out_path):
        sys.exit(f"misura_{part} was already started: a new run needs a declared deviation")
    code = {f: sha(os.path.join(HERE, f)) for f in ("formati.py", "rilevatori.py", "misura.py")}
    dev_path = os.path.join(OUT_DIR, "misura_dev.json")
    marker = {"part": part, "started": datetime.datetime.now().isoformat(timespec="seconds"), "code_sha256": code}
    with open(started, "x", encoding="utf-8") as fh:
        json.dump(marker, fh, indent=1)
    print("started", started, flush=True)
    files = ([dev_path] if part == "heldout" else []) + inputs(part)
    manifest = [{"path": os.path.relpath(f, ROOT), "bytes": os.path.getsize(f), "sha256": sha(f)} for f in files]
    with open(os.path.join(OUT_DIR, f"misura_{part}.inputs.json"), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    dev = None
    if part == "heldout":
        with open(dev_path, encoding="utf-8") as fh:
            dev = json.load(fh)["sets"]["swehero_dev"]
    sets, recs, all_outcomes, conflicts = {}, {}, {}, {}
    for name, kind, where in PARTS[part]:
        recs[name], outcomes, conflicts[name] = read(kind, where)
        all_outcomes[name] = outcomes
        sets[name] = summary(recs[name], observations=(kind == "observations"))
        if outcomes is not None:
            sets[name]["reconciliation"] = reconcile(recs[name], outcomes)
        if kind == "swehero":
            groups = collections.defaultdict(list)
            for r in recs[name]:
                groups[r["collection"]].append(r)
            sets[name]["by_collection"] = {c: summary(g) for c, g in sorted(groups.items())}
        print(name, sets[name]["runs"], "runs", flush=True)
    problems = structural_problems(recs, all_outcomes, conflicts)
    result = {"part": part, "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "bootstrap": {"replicates": REPS, "seed": SEED, "unit": "run (task for H2)"},
              "code_sha256": code, "structural_problems": problems, "sets": sets}
    if part == "heldout":
        result["hypotheses"] = (hypotheses(sets, recs, dev) if not problems else
                                "not evaluated: structural checks failed")
    with open(out_path, "x", encoding="utf-8") as fh:
        json.dump(finite(result), fh, indent=1, allow_nan=False)
    print("written", out_path, "| structural problems:", problems or "none")


if __name__ == "__main__":
    main()
