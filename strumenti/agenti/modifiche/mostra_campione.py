"""Compact view of the audit sample (verifica_campione.json) for a human or AI judge: only the information the plan
gives the judges (category, detail, the messages around the incident and around the removal), shortened.

    python -I mostra_campione.py <first n> <last n>
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "..", "risultati", "modifiche", "verifica_campione.json")


def short(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n] + "…"


def show_window(msgs, step, near=400, far=220):
    for m in msgs:
        mark = ">>" if m["index"] == step or m["index"] == step + 1 else "  "
        width = near if mark == ">>" else far
        body = short(m.get("content"), width)
        calls = " | ".join(short(c, width) for c in m.get("calls") or [])
        print(f"   {mark}{m['index']:4d} {m['role'][:4]}: {body}" + (f"  CALLS: {calls}" if calls else ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    first, last = int(sys.argv[1]), int(sys.argv[2])
    with open(PATH, encoding="utf-8") as fh:
        items = json.load(fh)["items"]
    for it in items:
        if not first <= it["n"] <= last:
            continue
        if "around" not in it:
            sys.exit("this sample has no message windows (public copy): rebuild the full one with campione_verifica.py")
        d = it.get("detail") or {}
        print(f"== #{it['n']} {it['category']} | {it['set']} | step {it['step']}")
        if d:
            kb, rb = d.get("known_bad"), d.get("replaced_bad")
            print(f"   detail: kind={d.get('kind')} removed_at={d.get('removed_at')}"
                  f" known_bad={short(json.dumps(kb), 260) if kb else None}"
                  f" replaced_bad={short(json.dumps(rb), 200) if rb else None}")
        show_window(it["around"], it["step"])
        if it.get("around_removal"):
            print("   -- around removal:")
            show_window(it["around_removal"], d.get("removed_at"), near=260, far=160)


if __name__ == "__main__":
    main()
