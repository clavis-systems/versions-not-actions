"""Audit of PREMESSA_MODIFICHE §7.4: detector precision per category and agreement between the two judges.

    python -I confronta_etichette.py

Inputs: verifica_campione.json (120 items, 20 per category), the Claude labels (verifica_etichette_claude.jsonl) and
the Codex labels (verifica_etichette_codex.json). Labels: corretto / sbagliato / incerto.
- Precision of a judge in a category: corretto / (corretto + sbagliato), with the exact Clopper-Pearson 95% interval;
  incerto is reported apart.
- Agreement: share of equal labels and Cohen's kappa (three labels), overall and per category.
Writes verifica_confronto.json next to the inputs.
"""

import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "..", "risultati", "modifiche")
CODEX = os.path.join(HERE, "..", "..", "esperimenti_codex", "verifica_etichette_codex.json")
LABELS = ("corretto", "sbagliato", "incerto")
CODEX_NAMES = {"rilevatore corretto": "corretto", "corretto": "corretto", "rilevatore sbagliato": "sbagliato",
               "sbagliato": "sbagliato", "incerto": "incerto"}


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k, n, alpha=0.05):
    """Exact two-sided interval by bisection (100 steps) on the binomial distribution."""
    if n == 0:
        return None
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    low = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) < alpha / 2)
    high = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > alpha / 2)
    return [round(low, 4), round(high, 4)]


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[x] * cb[x] for x in LABELS) / n ** 2
    return {"n": n, "agreement": round(po, 4), "kappa": None if pe == 1 else round((po - pe) / (1 - pe), 4)}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(os.path.join(RES, "verifica_campione.json"), encoding="utf-8") as fh:
        items = {it["n"]: it for it in json.load(fh)["items"]}
    with open(os.path.join(RES, "verifica_etichette_claude.jsonl"), encoding="utf-8") as fh:
        claude = {r["n"]: r for r in map(json.loads, filter(str.strip, fh))}
    with open(CODEX, encoding="utf-8") as fh:
        codex = {int(k): {"label": CODEX_NAMES[v["giudizio"]], "reason": v["motivo"]} for k, v in json.load(fh).items()}
    assert set(claude) == set(codex) == set(items) == set(range(1, 121))
    categories = list(dict.fromkeys(items[n]["category"] for n in sorted(items)))
    out = {"categories": {}, "overall": {}, "disagreements": []}
    for cat in categories + ["all"]:
        ns = [n for n in sorted(items) if cat == "all" or items[n]["category"] == cat]
        row = {}
        for judge, labels in (("claude", claude), ("codex", codex)):
            c = collections.Counter(labels[n]["label"] for n in ns)
            decided = c["corretto"] + c["sbagliato"]
            row[judge] = {**{x: c[x] for x in LABELS},
                          "precision": round(c["corretto"] / decided, 4) if decided else None,
                          "ci95": clopper_pearson(c["corretto"], decided)}
        both = sum(claude[n]["label"] == codex[n]["label"] == "corretto" for n in ns)
        row["both_corretto"] = both
        row["either_sbagliato"] = sum("sbagliato" in (claude[n]["label"], codex[n]["label"]) for n in ns)
        row["agreement"] = kappa([(claude[n]["label"], codex[n]["label"]) for n in ns])
        row["notes_claude"] = sum("Nota:" in claude[n]["reason"] for n in ns)
        (out["overall"] if cat == "all" else out["categories"]).update({cat: row} if cat != "all" else row)
    matrix = collections.Counter((claude[n]["label"], codex[n]["label"]) for n in items)
    out["overall"]["confusion_claude_rows_codex_cols"] = {a: {b: matrix[(a, b)] for b in LABELS} for a in LABELS}
    for n in sorted(items):
        if claude[n]["label"] != codex[n]["label"]:
            out["disagreements"].append({"n": n, "category": items[n]["category"], "claude": claude[n]["label"],
                                         "codex": codex[n]["label"], "claude_reason": claude[n]["reason"],
                                         "codex_reason": codex[n]["reason"]})
    path = os.path.join(RES, "verifica_confronto.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for cat, row in list(out["categories"].items()) + [("TUTTE", out["overall"])]:
        cl, cx = row["claude"], row["codex"]
        print(f"{cat:16s} Claude c/s/i {cl['corretto']:2d}/{cl['sbagliato']}/{cl['incerto']:2d} prec {cl['precision']}"
              f" {cl['ci95']} | Codex c/s/i {cx['corretto']:2d}/{cx['sbagliato']}/{cx['incerto']:2d} prec {cx['precision']}"
              f" {cx['ci95']} | entrambi corretto {row['both_corretto']:2d} | accordo {row['agreement']['agreement']}"
              f" kappa {row['agreement']['kappa']} | note Claude {row['notes_claude']}")
    print("matrice (righe Claude, colonne Codex):", out["overall"]["confusion_claude_rows_codex_cols"])
    print("disaccordi:", len(out["disagreements"]), "| scritto", os.path.normpath(path))


if __name__ == "__main__":
    main()
