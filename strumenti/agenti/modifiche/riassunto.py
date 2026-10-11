"""Print the key numbers of misura_heldout.json or misura_dev.json, for reading (it only reads the results file).

    python -I riassunto.py <misura_*.json>
"""

import json
import sys


def pct(x):
    if not x or x.get("value") is None:
        return "-"
    ci = x.get("ci95") or x.get("ci95_clopper_pearson")
    span = f" [{100 * ci[0]:.2f}, {100 * ci[1]:.2f}]" if ci else ""
    count = f" ({x['num']}/{x['den']})" if "num" in x else f" ({x.get('runs_with_a_naming')}/{x.get('runs')} runs)"
    return f"{100 * x['value']:.2f}%{span}{count}"


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print("part", d["part"], "| written", d["written"], "| structural problems:", d["structural_problems"] or "none")
    for name, s in d["sets"].items():
        print(f"\n== {name}: {s['runs']} runs, receipts balanced {s['receipts_balanced']}")
        for k in ("editor_failure_rate", "failed_str_replace_per_call", "noop_share_of_failures", "runs_with_noop",
                  "runs_with_circle", "runs_with_known_bad_retry", "known_bad_retry_error_named_per_run",
                  "circles_two_errors_both_named_per_run", "token_share_in_failed_str_replace_calls"):
            if k in s:
                print(f"  {k:42s} {pct(s[k])}")
        if "failure_type_share" in s:
            print("  types:", {t: round(100 * v["value"], 1) for t, v in s["failure_type_share"].items()
                               if v["value"] is not None})
            print("  missing classes:", {c: round(100 * v["value"], 1) for c, v in s["missing_class_share"].items()
                                         if v["value"] is not None})
            print("  noop causes:", {c: round(100 * v["value"], 1) for c, v in s["noop_cause_share"].items()
                                     if v["value"] is not None})
            print("  noop cost:", s["noop_calls_to_next_good_edit"], "| revisits:", s["revisits"])
            print("  counts:", s["counts"])
            print("  excluded from H3:", s.get("retry_own_excluded_from_h3"), "| eligible:",
                  s.get("retry_own_eligible_for_h3"), "| pairing:", s.get("pairing"))
        if "outcome" in s:
            o = s["outcome"]
            w = o["with_vs_without_noop"]
            print(f"  resolved {100 * o['resolved_rate']:.1f}% of {o['graded_runs']} graded | with a no-op minus "
                  f"without: {w['value']} {w['ci95']} (n {w['n_group']} vs {w['n_other']})")
            if "with_vs_without_circle" in o:
                c = o["with_vs_without_circle"]
                print(f"  with a circle minus without: {c['value']} {c['ci95']} (n {c['n_group']} vs {c['n_other']})")
        if "reconciliation" in s:
            print("  reconciliation:", s["reconciliation"])
        for c, g in (s.get("by_collection") or {}).items():
            print(f"  [{c}] runs {g['runs']} | failed per call {pct(g['failed_str_replace_per_call'])} | noop share "
                  f"{pct(g['noop_share_of_failures'])} | runs with a no-op {pct(g['runs_with_noop'])} | circle "
                  f"{pct(g['runs_with_circle'])}")
    if isinstance(d.get("hypotheses"), dict):
        print("\n== hypotheses")
        for k, v in d["hypotheses"].items():
            extra = v.get("difference") or v.get("per_set") or v.get("held_out_r2e") or v.get("evaluable_sets") or ""
            print(f"  {k}: {v['status']} | {extra}")


if __name__ == "__main__":
    main()
