"""Does the agent know it is going back? A local model reads the agent's own words around a revisit.

Development test of 09/10/2026 (see rapporto/PIANO_GEMMA_PAPER.md). For each item (see campione_ritorni.py) the model
reads what the agent wrote when it removed a block and when it writes the block again, and answers YES (the words
show a deliberate undo or restore) or NO. Temperature 0, seed 1.
- Prompt v1 tells the model that the block is the same one; v2 does not, and asks it to judge only from the words.
- --think lets the model reason before it answers.

    python -I giudice.py <items.json> <out.json> --prompt v2 --think [--model gemma4:e4b-it-qat]

It needs the GPU lock (strumenti/risultati/.gpu_lock) and a running Ollama server on this PC.
"""

import argparse
import json
import urllib.request

PROMPTS = {
    "v1": """You will read two short notes written by a coding agent while it edits a file. Earlier the agent REMOVED a block of code from the file. Now it is WRITING THE SAME BLOCK BACK.

Note written when it removed the block:
<<<
{removal}
>>>

Note written now, when it writes the block back:
<<<
{rewrite}
>>>

Question: do the agent's own words show that it is deliberately undoing or restoring its own earlier change (for example: revert, restore, re-apply, re-enable, go back, change back, remove the debug code or the duplicate it added, temporarily disable)? If there are no words, answer NO. Answer with one word: YES or NO.""",
    "v2": """Below are two short notes written by a coding agent, in its own words.

Note A (written at an earlier edit):
<<<
{removal}
>>>

Note B (written just before the current edit):
<<<
{rewrite}
>>>

Question: in these notes, does the agent itself say that the current edit undoes, reverts or restores something it did earlier (for example: revert, restore, re-apply, re-enable, go back, change back, put back, remove the debug code or the duplicate it added)? Judge only from the words. If the notes do not say so, or are empty, answer NO. Answer with one word: YES or NO.""",
}


def ask(model, text, think, num_predict):
    body = {"model": model, "messages": [{"role": "user", "content": text}], "stream": False, "think": think,
            "options": {"temperature": 0, "seed": 1, "num_predict": num_predict}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["message"]["content"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("items")
    p.add_argument("out")
    p.add_argument("--prompt", choices=sorted(PROMPTS), default="v2")
    p.add_argument("--think", action="store_true")
    p.add_argument("--model", default="gemma4:e4b-it-qat")
    a = p.parse_args()
    num_predict = 1500 if a.think else 8
    with open(a.items, encoding="utf-8") as fh:
        items = json.load(fh)
    out = {}
    for it in items:
        raw = ask(a.model, PROMPTS[a.prompt].format(removal=it["removal_text"] or "(no words)",
                                                    rewrite=it["rewrite_text"] or "(no words)"), a.think, num_predict)
        word = raw.strip().strip(".*").split()[0].upper() if raw.strip() else ""
        out[str(it["n"])] = {"label": word if word in ("YES", "NO") else "INVALID", "raw": raw[:60]}
        print(it["n"], out[str(it["n"])]["label"], flush=True)
    with open(a.out, "x", encoding="utf-8") as fh:
        json.dump({"model": a.model, "prompt": PROMPTS[a.prompt],
                   "options": f"temperature 0, seed 1, num_predict {num_predict}, think {str(a.think).lower()}",
                   "judgements": out}, fh, indent=1)


if __name__ == "__main__":
    main()
