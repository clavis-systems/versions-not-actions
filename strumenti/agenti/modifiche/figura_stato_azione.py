"""Figure of idea 1: the same run drawn as an action graph and as a version graph.

    python -I figura_stato_azione.py find [--limit N]              # candidate runs (480B, test part)
    python -I figura_stato_azione.py draw <instance id> <path> --out figure.svg

Only the edits of one file are drawn (str_replace, insert, create, undo_edit), in order.
  Action graph   one node per distinct call (tool + its arguments), arrows in time order: a call identical to an
                 earlier one is drawn as an arrow back to that node; a new call is a new node.
  Version graph  one node per content of the file (SHA-256), arrows for successful edits, loops for failed ones; a
                 return to an earlier content is an arrow back to that node.
Only data is read; nothing from the runs is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import formati  # noqa: E402
import misura  # noqa: E402
import stato_azione as S  # noqa: E402

INK, MUTED, BG, RET, FAIL = "#1d2430", "#5b6472", "#fbfaf7", "#c2410c", "#b3412e"


def runs_480b():
    name, kind, where = next(x for x in misura.PARTS["heldout"] if x[0] == "openhands_qwen3_coder_480b")
    for n, run in enumerate(formati.openhands_events(where[0], formati.load_outcomes(where[1]))):
        if n >= S.DEV_RUNS:                                   # test part only, as in the frozen premise
            yield run


def edit_events(calls, path):
    """[(action key, outcome, before, after)] for the edits of one file."""
    out = []
    for name, args, result, meta in calls:
        if S.label(name, args) != "EDIT" or args.get("path") != path:
            continue
        outcome = formati.editor_outcome(result or "")
        after = meta.get("file_after")
        if after is None and args.get("command") == "create":
            after = args.get("file_text")
        out.append((S.action_key(name, args), outcome, meta.get("file_before"), after))
    return out


def graphs(events):
    actions, action_edges, states, state_edges, loops = [], [], [], [], {}
    prev_a = prev_s = None
    for key, outcome, before, after in events:
        if key not in actions:
            actions.append(key)
        a = actions.index(key)
        if prev_a is not None:
            action_edges.append((prev_a, a))
        prev_a = a
        if outcome in S.FAILED:
            if prev_s is not None:
                loops[prev_s] = loops.get(prev_s, 0) + 1
            continue
        if after is None:
            continue
        hb = hashlib.sha256(before.encode()).hexdigest() if before is not None else None
        if hb is not None and hb not in states:
            states.append(hb)
        if hb is not None:
            prev_s = states.index(hb)
        ha = hashlib.sha256(after.encode()).hexdigest()
        if ha not in states:
            states.append(ha)
        s = states.index(ha)
        if prev_s is not None and prev_s != s:
            state_edges.append((prev_s, s))
        prev_s = s
    return actions, action_edges, states, state_edges, loops


def find(limit):
    for k, run in enumerate(runs_480b()):
        if limit and k >= limit:
            break
        calls = S.calls_with_results(run["messages"])
        paths = {a.get("path") for n, a, r, m in calls if S.label(n, a) == "EDIT"}
        for path in paths:
            ev = edit_events(calls, path)
            actions, aedges, states, sedges, loops = graphs(ev)
            back_s = [e for e in sedges if e[1] < e[0]]
            back_a = [e for e in aedges if e[1] <= e[0]]
            if back_s and not back_a and 3 <= len(states) <= 5 and len(ev) <= 7:
                print(run["id"], path, f"edits {len(ev)} states {len(states)} actions {len(actions)}",
                      f"state returns {len(back_s)} action back-edges {len(back_a)} outcome {run.get('outcome')}")


def node(x, y, label, fill, r=22):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>'
            f'<text x="{x}" y="{y + 5}" font-size="14" font-weight="700" text-anchor="middle" fill="#fff">{label}</text>')


def arrow(x1, y1, x2, y2, color, back=False, label=""):
    if not back and abs(x2 - x1) > 130:                      # a jump forward over other nodes: an arc above
        mid, lift = (x1 + x2) / 2, 20 + abs(x1 - x2) / 10
        return (f'<path d="M {x1} {y1 - 24} Q {mid} {y1 - 24 - 2 * lift} {x2} {y2 - 26}" fill="none" '
                f'stroke="{color}" stroke-width="2.2" marker-end="url(#a)"/>')
    if not back:
        return (f'<line x1="{x1 + 24}" y1="{y1}" x2="{x2 - 28}" y2="{y2}" stroke="{color}" stroke-width="2.2" '
                f'marker-end="url(#a)"/>')
    mid, lift = (x1 + x2) / 2, 40 + abs(x1 - x2) / 5
    return (f'<path d="M {x1} {y1 + 24} Q {mid} {y1 + 24 + 2 * lift} {x2} {y2 + 26}" fill="none" stroke="{color}" '
            f'stroke-width="2.6" marker-end="url(#ar)"/>')


def draw(instance, path, out):
    run = next(r for r in runs_480b() if r["id"] == instance)
    ev = edit_events(S.calls_with_results(run["messages"]), path)
    actions, aedges, states, sedges, loops = graphs(ev)
    gap, W = 120, 140 + 120 * max(len(actions), len(states))
    parts = [f'<rect width="100%" height="100%" fill="{BG}"/>',
             '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
             f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{MUTED}"/></marker>'
             '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
             f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{RET}"/></marker></defs>',
             f'<text x="20" y="34" font-size="18" font-weight="700" fill="{INK}">One run, two drawings '
             f'({html.escape(instance)}, Qwen3-Coder-480B)</text>',
             f'<text x="20" y="80" font-size="15" font-weight="700" fill="{INK}">Action graph</text>',
             f'<text x="140" y="80" font-size="13" fill="{MUTED}">a node per distinct call: every edit is new, '
             f'so no cycle appears</text>']
    y = 130
    for i, _ in enumerate(actions):
        parts.append(node(70 + i * gap, y, f"a{i + 1}", MUTED))
    for s, t in aedges:
        parts.append(arrow(70 + s * gap, y, 70 + t * gap, y, MUTED, back=t <= s, label="repeat"))
    y2 = 330
    parts += [f'<text x="20" y="{y2 - 130}" font-size="15" font-weight="700" fill="{INK}">Version graph</text>',
              f'<text x="150" y="{y2 - 130}" font-size="13" fill="{MUTED}">a node per content of '
              f'{html.escape(os.path.basename(path))}; red arcs: returns to an earlier content</text>']
    for i, _ in enumerate(states):
        parts.append(node(70 + i * gap, y2, f"v{i}", INK))
        if loops.get(i):
            parts.append(f'<text x="{70 + i * gap}" y="{y2 - 32}" font-size="12" text-anchor="middle" '
                         f'fill="{FAIL}">{loops[i]} failed</text>')
    for s, t in sedges:
        parts.append(arrow(70 + s * gap, y2, 70 + t * gap, y2, RET if t < s else MUTED, back=t < s,
                           label="back to v%d" % t))
    H = y2 + 140
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'font-family="Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="The same run as an action graph and as a version graph">' + "".join(parts) + "</svg>")
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(svg)
    print("edits", len(ev), "actions", len(actions), "states", len(states), "state edges", sedges)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("find", "draw"))
    p.add_argument("instance", nargs="?")
    p.add_argument("path", nargs="?")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out")
    a = p.parse_args()
    if a.mode == "find":
        find(a.limit)
    else:
        draw(a.instance, a.path, a.out)


if __name__ == "__main__":
    main()
