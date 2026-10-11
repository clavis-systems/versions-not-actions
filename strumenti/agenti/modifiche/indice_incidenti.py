"""Public incident index (resource): pointers only, no text of the trajectories.

    python -I indice_incidenti.py --out-dir <folder> [--sources swehero|all] [--limit N]

For every set with messages (SWE-Hero dev and held-out shards; OpenHands + Qwen3-Coder 30B and 480B on SWE-bench
Verified) the frozen detectors (rilevatori.py v3) are run, with the same six categories as the audit sample
(campione_verifica.py): noop, multiple, stale, never_seen, known_bad_retry, circle. Each incident is one JSON line:

    {"set", "run", "task", "category", "message", "call", ...}

"message" is the index in the common message shape made by formati.py, and "call" is the call number, so anyone can
rebuild the trajectory from the public source and find the spot. Revisit categories also give the message where the
block was removed and the call numbers of the failing tests (never their text). A manifest records the sources with
their SHA-256, the code with its SHA-256, and the counts. Files are written with mode "x".

Licences (Codex C7, 11/10/2026): SWE-Hero is CC BY 4.0, so its pointers can be published with attribution. No reuse
licence was found for the SWE-bench/experiments trajectories, so by default only SWE-Hero is indexed; `--sources all`
adds the two SWE-bench sets for local use. The Claude Opus 4.5 set has only observations (no calls) and is not
indexed.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import formati  # noqa: E402
import misura  # noqa: E402
import rilevatori as R  # noqa: E402

SOURCES = {"swehero": "https://huggingface.co/datasets/nvidia/SWE-Hero-openhands-trajectories (CC-BY-4.0)",
           "openhands": "https://github.com/SWE-bench/experiments (evaluation/verified)"}
CODE = ("formati.py", "rilevatori.py", "misura.py", "indice_incidenti.py")


def incidents(set_name, run):
    """Pointer records of one run, in the categories of the audit sample."""
    msgs, out = run["messages"], []
    base = {"set": set_name, "run": run["id"], "task": run["task"]}
    for f in R.edit_failures(msgs):
        category = f["error"] if f["error"] in ("noop", "multiple") else f.get("kind")
        if category in ("noop", "multiple", "stale", "never_seen"):
            out.append({**base, "category": category, "message": f["step"], "call": f["call"]})
    for e in R.revisits(msgs):
        pointer = {**base, "message": e["step"], "call": e["call"], "removed_at_message": e["removed_at"],
                   "failing_test_call": e["known_bad"][0] if e["known_bad"] else None,
                   "replaced_failing_test_call": e["replaced_bad"][0] if e["replaced_bad"] else None}
        if e["kind"] == "retry_own" and e["known_bad_kind"] == "application" and R.names_in(e["known_bad"][2]):
            out.append({**pointer, "category": "known_bad_retry"})
        if e["known_bad_kind"] == "application" and e["replaced_bad"] and \
                R.failure_kind(e["replaced_bad"]) == "application":
            out.append({**pointer, "category": "circle"})
    return out


def sets(sources="swehero"):
    for part in ("dev", "heldout"):
        for set_name, kind, where in misura.PARTS[part]:
            if kind != "swehero" and sources != "all":
                continue
            if kind == "swehero":
                yield set_name, kind, lambda w=where: formati.swehero(w), where
            elif kind == "openhands":
                yield set_name, kind, lambda w=where: formati.openhands_events(w[0], formati.load_outcomes(w[1])), \
                    [w for w in where]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--sources", choices=("swehero", "all"), default="swehero",
                   help="swehero (CC BY 4.0, publishable) or all (adds SWE-bench sets: licence unclear, local use)")
    p.add_argument("--limit", type=int, default=None, help="runs per set, for a quick check only")
    a = p.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    counts, runs = collections.defaultdict(collections.Counter), collections.Counter()
    with open(os.path.join(a.out_dir, "incidenti.jsonl"), "x", encoding="utf-8") as fh:
        for set_name, kind, load, where in sets(a.sources):
            for n, run in enumerate(load()):
                if a.limit is not None and n >= a.limit:
                    break
                runs[set_name] += 1
                for inc in incidents(set_name, run):
                    counts[set_name][inc["category"]] += 1
                    fh.write(json.dumps(inc, ensure_ascii=False) + "\n")
            print(set_name, runs[set_name], dict(counts[set_name]), flush=True)
    used = [f for part in ("dev", "heldout") for f in misura.inputs(part)
            if a.sources == "all" or "SWE-Hero" in f]
    manifest = {
        "limit": a.limit, "sources_option": a.sources, "runs": dict(runs),
        "incidents": {s: dict(c) for s, c in counts.items()},
        "input_files": [{"path": os.path.relpath(f, misura.ROOT)
                         .replace(os.sep, "/"), "bytes": os.path.getsize(f), "sha256": sha(f)} for f in used],
        "sources": SOURCES,
        "code_sha256": {f: sha(os.path.join(HERE, f)) for f in CODE},
        "categories": ["noop", "multiple", "stale", "never_seen", "known_bad_retry", "circle"],
    }
    with open(os.path.join(a.out_dir, "manifest.json"), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
