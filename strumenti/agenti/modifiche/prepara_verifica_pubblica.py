"""Public copies of the audit files (PREMESSA_MODIFICHE §7.4) for the repository versions-not-actions.

    python -I prepara_verifica_pubblica.py <output folder>

The SWE-Hero trajectories are CC BY 4.0; the OpenHands SWE-bench trajectories have no reuse licence that I found, so
for the 13 sampled items that come from them no verbatim trajectory text is published:
- verifica_campione.json: no message windows (n, category, set, run id, step, detail). The windows ("around",
  "around_removal") are removed for every item; for SWE-bench items the failing lines in known_bad and replaced_bad
  are replaced by null (the call numbers stay). SWE-Hero items keep their failing lines.
- verifica_aggiudicazione.json: for SWE-bench items the fields "command" and "examples_never_shown" are removed.
Copied unchanged: Claude's criterion, Claude's labels, Codex's labels and the comparison. Claude's labels (repeated
in the comparison) quote at most a few words of the logs, as a reviewer would.
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "..", "risultati", "modifiche")
CODEX = os.path.join(HERE, "..", "..", "esperimenti_codex", "verifica_etichette_codex.json")
SWEHERO = "swehero_heldout"


def main():
    out = sys.argv[1]
    res_out = os.path.join(out, "strumenti", "risultati", "modifiche")
    codex_out = os.path.join(out, "strumenti", "esperimenti_codex")
    os.makedirs(res_out, exist_ok=True)
    os.makedirs(codex_out, exist_ok=True)
    with open(os.path.join(RES, "verifica_campione.json"), encoding="utf-8") as fh:
        sample = json.load(fh)
    swebench = set()
    items = []
    for it in sample["items"]:
        detail = dict(it.get("detail") or {})
        if it["set"] != SWEHERO:
            swebench.add(it["n"])
            for key in ("known_bad", "replaced_bad"):
                if detail.get(key):
                    detail[key] = [detail[key][0], detail[key][1], None]
        items.append({k: it[k] for k in ("n", "category", "set", "run", "step")} | {"detail": detail})
    public_sample = {"seed": sample["seed"], "pool_sizes": sample["pool_sizes"],
                     "note": "No message windows; for SWE-bench items the failing lines are removed too. Rebuild "
                             "the full sample with campione_verifica.py from the public sources (move this file "
                             "away first).",
                     "items": items}
    with open(os.path.join(res_out, "verifica_campione.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(public_sample, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(RES, "verifica_aggiudicazione.json"), encoding="utf-8") as fh:
        adj = json.load(fh)
    for row in adj["items"]:
        if row["n"] in swebench:
            row.pop("examples_never_shown", None)
            for key in ("known_bad", "replaced_bad"):
                if row.get(key):
                    row[key].pop("command", None)
    with open(os.path.join(res_out, "verifica_aggiudicazione.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(adj, fh, ensure_ascii=False, indent=1)
    for name in ("verifica_criterio_claude.md", "verifica_etichette_claude.jsonl", "verifica_confronto.json"):
        shutil.copyfile(os.path.join(RES, name), os.path.join(res_out, name))
    shutil.copyfile(CODEX, os.path.join(codex_out, "verifica_etichette_codex.json"))
    print("SWE-bench items:", sorted(swebench))
    print("written to", os.path.normpath(out))


if __name__ == "__main__":
    main()
