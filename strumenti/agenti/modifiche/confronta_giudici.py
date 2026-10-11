"""Development test of 09/10/2026: compare judges with the reference labels (YES = deliberate return). UNCLEAR references are left out.
Usage: python -I confronta_giudici.py <dir> <judgement files...>
(<dir> holds etichette_claude.json, hidden.json and the judgement files.)"""
import collections
import json
import os
import sys

d = sys.argv[1]
ref = json.load(open(os.path.join(d, "etichette_claude.json"), encoding="utf-8"))["labels"]
hidden = {str(h["n"]): h for h in json.load(open(os.path.join(d, "hidden.json"), encoding="utf-8"))}
judges = {"keywords": {n: ("YES" if h["keyword"] == "declared" else "NO") for n, h in hidden.items()}}
for f in sys.argv[2:]:
    j = json.load(open(os.path.join(d, f), encoding="utf-8"))
    judges[f] = {n: v["label"] for n, v in j["judgements"].items()}


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa = collections.Counter(a for a, _ in pairs)
    pb = collections.Counter(b for _, b in pairs)
    pe = sum(pa[k] * pb[k] for k in ("YES", "NO")) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


keep = [n for n, v in ref.items() if v in ("YES", "NO")]
print(f"reference: {collections.Counter(ref.values())}")
by_stratum = collections.Counter()
for n in keep:
    h = hidden[n]
    s = "back_to_original" if h["kind"] == "back_to_original" else "retry_known_bad" if h["known_bad"] else "retry_not_known_bad"
    by_stratum[(s, ref[n])] += 1
print("reference by stratum:", dict(by_stratum))
for name, lab in judges.items():
    pairs = [(ref[n], lab.get(n, "INVALID")) for n in keep]
    cm = collections.Counter(pairs)
    no_ref = [n for n in keep if ref[n] == "NO"]
    print(f"\n{name}: agreement {sum(a == b for a, b in pairs)}/{len(pairs)} | kappa {kappa(pairs):.2f}")
    print(f"  ref YES -> judge YES {cm[('YES', 'YES')]}, NO {cm[('YES', 'NO')]} | ref NO -> judge NO {cm[('NO', 'NO')]}, "
          f"YES {cm[('NO', 'YES')]} | invalid {sum(v == 'INVALID' for _, v in pairs)}")
    print(f"  on the reference NO cases {sorted(no_ref, key=int)}: {[lab.get(n) for n in sorted(no_ref, key=int)]}")
