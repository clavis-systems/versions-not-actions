"""Append audit labels to verifica_etichette_claude.jsonl (one JSON line per case; a case can be labelled once).

    python -I registra_etichette.py "<n>|<corretto|sbagliato|incerto>|<reason>" [...]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "risultati", "modifiche", "verifica_etichette_claude.jsonl")
LABELS = ("corretto", "sbagliato", "incerto")


def main():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            done = {json.loads(line)["n"] for line in fh if line.strip()}
    with open(OUT, "a", encoding="utf-8") as fh:
        for arg in sys.argv[1:]:
            n, label, reason = arg.split("|", 2)
            n = int(n)
            if label not in LABELS:
                raise SystemExit(f"bad label {label!r} for case {n}")
            if n in done:
                raise SystemExit(f"case {n} is already labelled")
            fh.write(json.dumps({"n": n, "label": label, "reason": reason.strip()}, ensure_ascii=False) + "\n")
            done.add(n)
    print("labelled cases:", len(done))


if __name__ == "__main__":
    main()
