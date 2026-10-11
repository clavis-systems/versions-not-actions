"""Version graph of one agent run: the nodes are the versions of the edited file, not the agent's actions.

    python -I grafo_versioni.py --run <off.json> --run <on.json> --out <figure.svg>

A run of agente_gemma.py is replayed on its starting file (rebuilt from the dataset):
  - every successful str_replace makes a new version, or goes back to an earlier one (a back edge);
  - every failed str_replace is an attempt that leaves the file where it is (a loop on the node, by failure type);
  - every run_tests marks the version it ran on as passed or failed.
The host notes received after failed attempts are kept, so the figure can show what ended a loop. The replay must end
on the run's final file, otherwise it stops with an error. Only data is read: no model and no code from the runs.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agente_gemma as A  # noqa: E402
import formati  # noqa: E402

PASS, FAIL, NONE = "#2f7d4f", "#b3412e", "#8a8f98"


def replay(run, initial):
    """The version graph of a run: nodes (versions), edges (successful edits) and the attempts and tests per node."""
    nodes, index, edges = [], {}, []

    def node_of(text, step):
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key not in index:
            index[key] = len(nodes)
            nodes.append({"id": len(nodes), "sha256": key[:12], "first_step": step, "tests": [], "attempts": []})
        return index[key]

    text, step = initial, 0
    current = node_of(text, 0)
    results = {m.get("tool_call_id"): m.get("content") or "" for m in run["messages"] if m.get("role") == "tool"}
    for m in run["messages"]:
        if m.get("role") != "assistant":
            continue
        if not m.get("tool_calls"):
            step += 1                                    # a reply without tools counts as a call
            continue
        for tc in m["tool_calls"]:
            step += 1
            fn = tc.get("function") or {}
            args = json.loads(fn.get("arguments") or "{}")
            out = results.get(tc.get("id"), "")
            kind = args.get("command") if fn.get("name") == "str_replace_editor" else (
                "run_tests" if fn.get("name") == "execute_bash" else fn.get("name"))
            if kind == "str_replace":
                outcome = formati.editor_outcome(out)
                if outcome == "edited":
                    old, new = args["old_str"], args["new_str"]
                    if text.count(old) != 1:
                        raise ValueError(f"step {step}: the replay does not match the run")
                    text = text.replace(old, new, 1)
                    target = node_of(text, step)
                    edges.append({"from": current, "to": target, "step": step,
                                  "back": nodes[target]["first_step"] < step})
                    current = target
                else:
                    note = out.split("[Host note]", 1)[1].strip() if "[Host note]" in out else None
                    nodes[current]["attempts"].append({"step": step, "type": outcome, "note": note})
            elif kind == "run_tests":
                nodes[current]["tests"].append({"step": step, "passed": "exit code 0." in out[-60:]})
    if text != run["final_file"]:
        raise ValueError("the replay does not end on the run's final file")
    return {"task": run["task"], "guard": run["guard"], "solved": run["solved"], "calls": run["calls"],
            "nodes": nodes, "edges": edges, "final": current}


def initial_file(task_id, rows):
    return A.build_task(rows, int(task_id.split("/")[1]))["files"][A.FILE]


# ---------- drawing ----------

def esc(text):
    return html.escape(text, quote=True)


def short(text, n=74):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def color(node):
    return NONE if not node["tests"] else PASS if node["tests"][-1]["passed"] else FAIL


def panel(graph, top, width):
    """SVG elements of one run, drawn from y = top; returns (elements, height)."""
    gap, r, base = 128, 19, top + 112
    xs = [70 + i * gap for i in range(len(graph["nodes"]))]
    label = "notes ON" if graph["guard"] else "notes OFF"
    out = [f'<text x="16" y="{top + 22}" font-size="15" font-weight="700" fill="#1d2430">{label}</text>',
           f'<text x="{16 + 92}" y="{top + 22}" font-size="13" fill="#4a5361">{graph["calls"]} calls, '
           f'{"solved" if graph["solved"] else "not solved"}</text>']
    for e in graph["edges"]:
        x1, x2 = xs[e["from"]], xs[e["to"]]
        if e["back"] or abs(e["to"] - e["from"]) != 1:
            mid, lift = (x1 + x2) / 2, 30 + abs(x2 - x1) / 6
            out.append(f'<path d="M {x1} {base + r} Q {mid} {base + r + 2 * lift} {x2} {base + r}" fill="none" '
                       f'stroke="#4a5361" stroke-width="1.6" marker-end="url(#arrow)"/>')
            out.append(f'<text x="{mid}" y="{base + r + lift + 16}" font-size="12" text-anchor="middle" '
                       f'fill="#4a5361">step {e["step"]}: back to v{e["to"]}</text>')
        else:
            out.append(f'<line x1="{x1 + r}" y1="{base}" x2="{x2 - r - 3}" y2="{base}" stroke="#4a5361" '
                       f'stroke-width="1.6" marker-end="url(#arrow)"/>')
            out.append(f'<text x="{(x1 + x2) / 2}" y="{base - 8}" font-size="12" text-anchor="middle" '
                       f'fill="#4a5361">step {e["step"]}</text>')
    notes = []
    for node, x in zip(graph["nodes"], xs):
        out.append(f'<circle cx="{x}" cy="{base}" r="{r}" fill="{color(node)}"/>')
        out.append(f'<text x="{x}" y="{base + 5}" font-size="13" font-weight="700" text-anchor="middle" '
                   f'fill="#ffffff">v{node["id"]}</text>')
        if node["tests"]:
            marks = ", ".join(("tests passed" if t["passed"] else "tests failed") + f" at step {t['step']}"
                              for t in node["tests"])
            if len(node["tests"]) > 3:
                fails = sum(not t["passed"] for t in node["tests"])
                marks = f"tests: {fails} failed, {len(node['tests']) - fails} passed"
            out.append(f'<text x="{x}" y="{base + r + 18}" font-size="11" text-anchor="middle" '
                       f'fill="#4a5361">{esc(marks)}</text>')
        if node["attempts"]:
            n, types = len(node["attempts"]), sorted({a["type"] for a in node["attempts"]})
            out.append(f'<path d="M {x - 11} {base - r + 3} C {x - 34} {base - r - 46}, {x + 34} {base - r - 46}, '
                       f'{x + 11} {base - r + 3}" fill="none" stroke="{FAIL}" stroke-width="2" '
                       f'marker-end="url(#arrow-red)"/>')
            out.append(f'<text x="{x}" y="{base - r - 40}" font-size="12" font-weight="700" text-anchor="middle" '
                       f'fill="{FAIL}">×{n} {esc("/".join(types))}</text>')
            seen = []
            for a in node["attempts"]:
                kind = (a["note"] or "").split(":")[0].split(".")[0]
                if a["note"] and kind not in seen:
                    seen.append(kind)
                    text = a["note"]
                    for key in ("It differs", "You already"):
                        if key in text:
                            text = text[text.index(key):]
                            break
                    notes.append(f'v{node["id"]}, step {a["step"]}: “{short(text, 110)}”')
    y = base + 78
    for line in notes[:4]:
        out.append(f'<text x="16" y="{y}" font-size="12" fill="#1d2430">host note at {esc(line)}</text>')
        y += 18
    return out, y - top + 6


def figure(graphs, title):
    width = max(760, 140 + 128 * max(len(g["nodes"]) for g in graphs))
    parts, top = [], 52
    for g in graphs:
        body, height = panel(g, top, width)
        parts += body
        top += height + 12
    legend = (f'<circle cx="24" cy="{top + 8}" r="7" fill="{PASS}"/><text x="38" y="{top + 12}" font-size="12" '
              f'fill="#4a5361">last tests passed</text>'
              f'<circle cx="170" cy="{top + 8}" r="7" fill="{FAIL}"/><text x="184" y="{top + 12}" font-size="12" '
              f'fill="#4a5361">last tests failed</text>'
              f'<circle cx="310" cy="{top + 8}" r="7" fill="{NONE}"/><text x="324" y="{top + 12}" font-size="12" '
              f'fill="#4a5361">not tested</text>'
              f'<text x="420" y="{top + 12}" font-size="12" fill="{FAIL}">red loop: failed edits, file unchanged'
              f'</text>')
    height = top + 30
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'font-family="Helvetica, Arial, sans-serif" role="img" aria-label="{esc(title)}">'
            f'<rect width="100%" height="100%" fill="#fbfaf7"/>'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#4a5361"/></marker>'
            '<marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{FAIL}"/></marker></defs>'
            f'<text x="16" y="30" font-size="17" font-weight="700" fill="#1d2430">{esc(title)}</text>'
            + "".join(parts) + legend + "</svg>")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="append", required=True, help="a result file of agente_gemma.py (repeatable)")
    p.add_argument("--out", required=True, help="the SVG to write (never overwritten)")
    p.add_argument("--title", default=None)
    p.add_argument("--json", default=None, help="also write the graphs as JSON")
    a = p.parse_args()
    rows = A.load_rows()
    graphs = []
    for path in a.run:
        with open(path, encoding="utf-8") as fh:
            run = json.load(fh)
        graphs.append(replay(run, initial_file(run["task"], rows)))
    title = a.title or f"{graphs[0]['task']}: versions of solution.py"
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write(figure(graphs, title))
    if a.json:
        with open(a.json, "x", encoding="utf-8") as fh:
            json.dump(graphs, fh, ensure_ascii=False, indent=1)
    for g in graphs:
        print(f"{g['task']} guard {'on' if g['guard'] else 'off'}: {len(g['nodes'])} versions, {len(g['edges'])} "
              f"edits ({sum(e['back'] for e in g['edges'])} back), "
              f"{sum(len(n['attempts']) for n in g['nodes'])} failed attempts")


if __name__ == "__main__":
    main()
