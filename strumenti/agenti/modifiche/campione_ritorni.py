"""Development test of 09/10/2026 (SWE-Hero dev shards 0-3 only): a fixed sample of revisits for the "does the agent know it goes back?"
test. For each revisit: the reasoning window when the block was last removed and when it is written again.
Writes items.json (texts only, for labelling and for the judge) and hidden.json (kind, known bad, removed again,
keyword label), so labels are made from the texts alone.
Usage: python -I campione_ritorni.py <out_dir> <shard.parquet>...

The sample of 09/10 (items e2b46d10..., hidden e4266dda...) was drawn with rilevatori version 1, commit f121a5a. With
rilevatori version 2 (provenance and certain presence intervals) the same seed gives a different sample: to
reproduce the 09/10 sample, run this script from commit f121a5a."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formati  # noqa: E402
import rilevatori as R  # noqa: E402

out_dir, shards = sys.argv[1], sys.argv[2:]
pools = {"retry_known_bad": [], "retry_not_known_bad": [], "back_to_original": []}
for run in formati.swehero(shards):
    msgs = run["messages"]
    events = R.revisits(msgs)
    if not events:
        continue
    removals = [(i, a.get("path"), R.norm(a.get("old_str") or ""), R.norm(a.get("new_str") or ""))
                for i, name, a, obs in R.calls(msgs)
                if name == "str_replace_editor" and a.get("command") == "str_replace" and R.error_type(obs) is None]
    for e in events:
        k = max((i for i, p, old, new in removals if p == e["path"] and i < e["step"] and e["block"] in old
                 and e["block"] not in new), default=None)
        if k is None:
            continue
        item = {"run": run["id"], "step": e["step"], "removed_at": k,
                "removal_text": R.window(msgs, k)[-600:], "rewrite_text": R.window(msgs, e["step"])[-600:]}
        hidden = {"kind": e["kind"], "known_bad": e["known_bad"] is not None, "again": e["again"],
                  "keyword": R.intent(msgs, e["step"])}
        pool = ("back_to_original" if e["kind"] == "back_to_original" else
                "retry_known_bad" if hidden["known_bad"] else "retry_not_known_bad")
        pools[pool].append((item, hidden))
random.seed(20261009)
chosen = (random.sample(pools["retry_known_bad"], 12) + random.sample(pools["retry_not_known_bad"], 12) +
          random.sample(pools["back_to_original"], 16))
random.shuffle(chosen)
items = [dict(item, n=n + 1) for n, (item, _) in enumerate(chosen)]
hidden = [dict(h, n=n + 1) for n, (_, h) in enumerate(chosen)]
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as fh:
    json.dump(items, fh, ensure_ascii=False, indent=1)
with open(os.path.join(out_dir, "hidden.json"), "w", encoding="utf-8") as fh:
    json.dump(hidden, fh, indent=1)
print({k: len(v) for k, v in pools.items()}, "-> sample", len(items))
