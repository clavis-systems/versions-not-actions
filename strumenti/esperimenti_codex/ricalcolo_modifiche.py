"""Ricalcolo indipendente dello studio sulle modifiche, senza producer Claude."""

from __future__ import annotations

from collections import Counter, defaultdict
import ast
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "strumenti/risultati/modifiche/misura_heldout.inputs.json"
SEME = 20261009
N_BOOT = 2_000
FAILURES = {"noop", "missing", "multiple", "other"}
TEST_RE = re.compile(r"pytest|python|unittest|tox|nose|make test|npm test|go test|cargo test", re.I)
FAIL_RE = re.compile(r"Traceback|FAILED|AssertionError|Error:|error:|Exception")
INFRA_RE = re.compile(
    r"ModuleNotFoundError|No module named|command not found|[Tt]imed? ?out|Killed|Permission denied|"
    r"No such file or directory|ConnectionError|MemoryError"
)
NAMES_RE = re.compile(r"\b[A-Z]\w*(?:Error|Exception)\b|\btest_\w+")
READ_RE = re.compile(r"^\s*(?:cat|head|tail|sed\s+-n|nl)\b", re.I)
PATH_RE = re.compile(r"(/[\w.\-/]+\.\w+)")
WRITE_TARGET_RE = re.compile(r">> ?([^\s|;&<>]+)")
WRITE_ACTION_RE = re.compile(
    r"sed\s+-i|\btee\b|\bmv\b|\bcp\b|git\s+(?:checkout|stash|apply|reset|restore|pull|merge)|"
    r"\bpatch\b|open\([^)]*['\"][wa]|write_text|\bperl\s+-pi|\bblack\b|\bisort\b|\bautopep8\b"
)


def norm(text: str) -> str:
    text = str(text).strip("\n")
    return "\n".join(line.rstrip(" ") for line in text.split("\n"))


def large(text: str) -> bool:
    return any(len(line.strip()) >= 8 for line in norm(text).splitlines())


def text_lines(text: str) -> set[str]:
    return {line.strip() for line in norm(text).splitlines() if len(line.strip()) >= 8}


def squash(text: str) -> str:
    return "\n".join(re.sub(r" +", " ", line) for line in norm(text).splitlines()).strip()


def strip_line_numbers(text: str) -> str:
    return re.sub(r"^ *\d+\t", "", str(text), flags=re.M)


def editor_outcome(output: str) -> str:
    """Classifica l'osservazione secondo l'ordine congelato in §9."""
    output = str(output).lstrip()
    low = output.lower()
    if output.startswith(("ERROR", "Invalid", "No replacement", "Ran into")):
        if "must be different" in low:
            return "noop"
        if "did not appear verbatim" in low:
            return "missing"
        if re.search(r"multiple occurrences", output, re.I):
            return "multiple"
        return "other"
    if "has been edited" in output[:300]:
        return "edited"
    if output.startswith("File created successfully"):
        return "created"
    if output.startswith("Last edit to") and "undone" in output[:300]:
        return "undo"
    if re.search(r"Here's the (?:result of running `cat -n`|files and directories)", output[:400]):
        return "view"
    return "unknown"


@dataclass
class Call:
    n: int
    name: str
    args: dict[str, Any]
    output: str = ""
    method: str = "none"
    result: str = "unknown"
    path: str = ""
    command: str = ""
    old: str = ""
    new: str = ""
    context: str = ""

    @property
    def editor(self) -> bool:
        return self.name == "str_replace_editor" and self.args.get("command") == "str_replace"


@dataclass
class Run:
    dataset: str
    task: str
    calls: list[Call]
    resolved: bool | None = None
    pairing: Counter = field(default_factory=Counter)
    duplicate_ids: int = 0


def _json_args(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        value = raw
    else:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
    return value if isinstance(value, dict) else None


def _assistant_context(messages: list[dict[str, Any]], index: int, args: Mapping[str, Any]) -> str:
    chunks = [str(messages[index].get("content") or "")]
    thought = args.get("thought")
    if thought:
        chunks.append(str(thought))
    added = 0
    for prior in reversed(messages[:index]):
        if prior.get("role") != "assistant":
            continue
        calls = prior.get("tool_calls") or []
        names = [((c.get("function") or {}).get("name")) for c in calls]
        if any(name != "think" for name in names):
            break
        if prior.get("content"):
            chunks.insert(0, str(prior["content"]))
        for call in calls:
            p_args = _json_args((call.get("function") or {}).get("arguments")) or {}
            if p_args.get("thought"):
                chunks.insert(0, str(p_args["thought"]))
        added += 1
        if added >= 3:
            break
    return " ".join(chunks)


def parse_swehero_run(task: str, trajectory: list[dict[str, Any]]) -> Run:
    calls: list[Call] = []
    pairing = Counter()
    duplicate_ids = 0
    i = 0
    while i < len(trajectory):
        message = trajectory[i]
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            i += 1
            continue
        valid: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for raw_call in message.get("tool_calls") or []:
            fn = raw_call.get("function") or {}
            args = _json_args(fn.get("arguments"))
            if args is not None:
                valid.append((raw_call, {"name": str(fn.get("name") or ""), **args}))
        j = i + 1
        outputs = []
        while j < len(trajectory) and trajectory[j].get("role") == "tool":
            outputs.append(trajectory[j])
            j += 1
        ids = [call.get("id") for call, _ in valid]
        out_ids = [out.get("tool_call_id") for out in outputs]
        if ids and all(ids) and len(set(ids)) != len(ids):
            duplicate_ids += 1
        if ids and all(ids) and out_ids and all(out_ids) and len(set(ids)) == len(ids) and len(set(out_ids)) == len(out_ids):
            by_id = {out.get("tool_call_id"): out for out in outputs}
            matched = [by_id.get(call.get("id")) for call, _ in valid]
            pairing["id"] += sum(out is not None for out in matched)
            pairing["missing"] += sum(out is None for out in matched)
        elif len(outputs) == len(valid):
            matched = outputs
            pairing["position"] += len(valid)
        else:
            matched = [None] * len(valid)
            pairing["missing"] += len(valid)
        for k, (raw_call, packed) in enumerate(valid):
            args = dict(packed)
            name = str(args.pop("name", ""))
            output = str((matched[k] or {}).get("content") or "")
            call = Call(
                n=len(calls), name=name, args=args, output=output,
                method="position" if matched[k] is not None and not (out_ids and all(out_ids)) else ("id" if matched[k] is not None else "none"),
                path=str(args.get("path") or ""), command=str(args.get("command") or ""),
                old=str(args.get("old_str") or ""), new=str(args.get("new_str") or ""),
                context=_assistant_context(trajectory, i, args),
            )
            call.result = editor_outcome(output) if name == "str_replace_editor" else "unknown"
            calls.append(call)
        i = j
    return Run("swehero", task, calls, pairing=pairing, duplicate_ids=duplicate_ids)


def parse_openhands(dataset: str, task: str, events: list[dict[str, Any]], resolved: bool | None) -> Run:
    outputs_by_id: dict[str, dict[str, Any]] = {}
    outputs_by_cause: dict[Any, dict[str, Any]] = {}
    for event in events:
        metadata = event.get("tool_call_metadata") or {}
        tool_id = metadata.get("tool_call_id")
        # OpenHands salva spesso l'osservazione con source="agent": l'output
        # è comunque in content e si riconosce dal tool_call_id/cause.
        if tool_id or event.get("cause") is not None:
            if not event.get("content"):
                continue
        else:
            continue
        if tool_id:
            outputs_by_id[str(tool_id)] = event
        if event.get("cause") is not None:
            outputs_by_cause[event["cause"]] = event
    calls: list[Call] = []
    pairing = Counter()
    duplicate_ids = 0
    prior_thoughts: list[str] = []
    for event in events:
        if event.get("source") != "agent" or not event.get("action"):
            continue
        args = _json_args(event.get("args"))
        if args is None:
            continue
        meta = event.get("tool_call_metadata") or {}
        name = str(meta.get("function_name") or event.get("action") or "")
        if name == "edit":
            name = "str_replace_editor"
        call_id = meta.get("tool_call_id")
        observation = outputs_by_id.get(str(call_id)) if call_id else None
        if observation is None:
            observation = outputs_by_cause.get(event.get("id"))
        if observation is not None:
            pairing["id" if call_id else "position"] += 1
        else:
            pairing["missing"] += 1
        output = str((observation or {}).get("content") or "")
        act = str(event.get("action") or "")
        cmd = str(args.get("command") or "")
        if act == "edit":
            args.setdefault("command", cmd)
        context_parts = []
        if meta.get("model_response"):
            choices = meta["model_response"].get("choices") or []
            if choices:
                context_parts.append(str((choices[0].get("message") or {}).get("content") or ""))
        if args.get("thought"):
            context_parts.append(str(args["thought"]))
        context_parts = prior_thoughts[-3:] + context_parts
        call = Call(
            n=len(calls), name=name, args=args, output=output,
            method="id" if call_id and observation is not None else ("position" if observation is not None else "none"),
            path=str(args.get("path") or ""), command=cmd,
            old=str(args.get("old_str") or ""), new=str(args.get("new_str") or ""),
            context=" ".join(context_parts),
        )
        if name == "str_replace_editor":
            call.result = editor_outcome(output)
        elif act == "edit" and cmd == "str_replace":
            call.result = editor_outcome(output)
        elif name == "str_replace_editor" and args.get("command") == "str_replace":
            call.result = editor_outcome(output)
        calls.append(call)
        if act == "think" and args.get("thought"):
            prior_thoughts.append(str(args["thought"]))
    return Run(dataset, task, calls, resolved=resolved, pairing=pairing, duplicate_ids=duplicate_ids)


def result_members(path: Path) -> tuple[set[str], set[str], set[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    no_generation = set(data.get("no_generation") or [])
    no_logs = set(data.get("no_logs") or [])
    resolved = set(data.get("resolved") or [])
    return no_generation, no_logs, resolved


def parse_openhands_set(root: Path, name: str) -> list[Run]:
    dataset_dirs = [
        name.replace("-openhands-", "_openhands-", 1),
        name.replace("-openhands-", "_openhands_", 1),
    ]
    traj_candidates = [root / "esterni/swebench-trajs" / name] + [
        root / "esterni/swebench-trajs" / item for item in dataset_dirs
    ]
    traj_root = next((item for item in traj_candidates if item.is_dir()), traj_candidates[0])
    result_candidates = [root / "esterni/swebench-results" / item / "results.json" for item in dataset_dirs]
    result_path = next((item for item in result_candidates if item.is_file()), result_candidates[0])
    if not result_path.is_file():
        raise FileNotFoundError(result_path)
    no_gen, no_logs, resolved_ids = result_members(result_path)
    outcomes = (no_gen | no_logs | resolved_ids)
    def outcome(task: str) -> bool | None:
        if task in no_gen or task in no_logs:
            return None
        return task in resolved_ids
    files = sorted(set(traj_root.glob("**/trajectory.json")) | set(traj_root.glob("*.json")))
    runs: list[Run] = []
    for path in files:
        task = path.parent.name if path.name == "trajectory.json" else path.stem
        events = json.loads(path.read_text(encoding="utf-8"))
        if "claude-opus" in name.lower():
            runs.append(parse_opus_observations(name, task, events, outcome(task)))
        else:
            runs.append(parse_openhands(name, task, events, outcome(task)))
    seen = {run.task for run in runs}
    # Missing trajectory files still appear as runs with no calls for task-outcome reconciliation.
    for task in sorted(outcomes - seen):
        runs.append(Run(name, task, [], outcome(task)))
    runs.sort(key=lambda run: run.task)
    return runs


def parse_opus_observations(dataset: str, task: str, messages: list[dict[str, Any]], resolved: bool | None) -> Run:
    """Estrae gli esiti dalla serializzazione Opus priva di chiamate/ID."""
    calls = []
    for message in messages:
        content = str(message.get("content") or "")
        prefix = "[file_editor] "
        if message.get("role") != "assistant" or not content.startswith(prefix):
            continue
        try:
            payload = ast.literal_eval(content[len(prefix):])
        except (ValueError, SyntaxError):
            continue
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            continue
        output = str(payload[0].get("text") or "")
        result = editor_outcome(output)
        # La raccolta conserva solo le osservazioni: riconosciamo gli esiti
        # meccanici espliciti e le modifiche riuscite, senza inventare gli ID.
        if result not in {"edited", "noop", "missing", "multiple"}:
            continue
        calls.append(Call(
            n=len(calls), name="str_replace_editor",
            args={"command": "str_replace"}, output=output,
            method="none", result=result,
        ))
    return Run(dataset, task, calls, resolved=resolved)


def parse_swehero(root: Path) -> list[Run]:
    import pyarrow.parquet as pq
    data_root = root / "esterni/SWE-Hero-openhands-trajectories/data"
    runs = []
    for shard in range(4, 14):
        path = data_root / f"train-{shard:05d}-of-00014.parquet"
        parquet = pq.ParquetFile(path)
        for group in range(parquet.num_row_groups):
            id_table = parquet.read_row_group(group, columns=["instance_id", "dataset"])
            ids = id_table.column("dataset").to_pylist()
            if "R2E-Gym/R2E-Gym-Subset" not in ids:
                continue
            table = parquet.read_row_group(group, columns=["instance_id", "dataset", "trajectory"])
            for row in table.to_pylist():
                if row.get("dataset") != "R2E-Gym/R2E-Gym-Subset":
                    continue
                runs.append(parse_swehero_run(str(row["instance_id"]), row["trajectory"] or []))
    return runs


def verify_input_manifest(root: Path = ROOT, manifest: Path = INPUTS) -> dict[str, Any]:
    """Verifica le impronte degli input raw; non apre mai misura_dev.json."""
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    checked, skipped = 0, []
    for item in entries:
        rel = str(item["path"]).replace("\\", "/")
        if rel == "strumenti/risultati/modifiche/misura_dev.json":
            skipped.append(rel)
            continue
        path = root / rel
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Dimensione input discordante: {rel}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError(f"SHA-256 input discordante: {rel}")
        checked += 1
    return {"controllati": checked, "saltati_per_perimetro": skipped}


def _ratio(n: float, d: float) -> float | None:
    return n / d if d else None


def _bootstrap_ratio(num: np.ndarray, den: np.ndarray, seed: int = SEME, reps: int = N_BOOT) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n = len(num)
    ix = rng.integers(0, n, size=(reps, n))
    ns = num[ix].sum(axis=1)
    ds = den[ix].sum(axis=1)
    valid = ds != 0
    vals = ns[valid] / ds[valid]
    if not len(vals):
        return {"ic95": None, "repliche_scartate": reps}
    return {"ic95": [float(np.quantile(vals, .025)), float(np.quantile(vals, .975))], "repliche_scartate": int(reps - len(vals))}


def _bootstrap_diff_ratio(a_num: np.ndarray, a_den: np.ndarray, b_num: np.ndarray, b_den: np.ndarray, seed: int = SEME) -> dict[str, Any]:
    if len(a_num) != len(b_num) or len(a_num) == 0:
        raise ValueError("Bootstrap appaiato richiede vettori non vuoti e della stessa lunghezza")
    rng = np.random.default_rng(seed)
    n = len(a_num)
    ix = rng.integers(0, n, size=(N_BOOT, n))
    an, ad, bn, bd = (x[ix].sum(axis=1) for x in (a_num, a_den, b_num, b_den))
    valid = (ad != 0) & (bd != 0)
    vals = an[valid] / ad[valid] - bn[valid] / bd[valid]
    return {
        "media": float(a_num.sum() / a_den.sum() - b_num.sum() / b_den.sum()),
        "ic95": [float(np.quantile(vals, .025)), float(np.quantile(vals, .975))] if len(vals) else None,
        "repliche_scartate": int(N_BOOT - valid.sum()),
    }


def _test_failed(call: Call) -> tuple[bool, bool, str, set[str]]:
    command = call.command
    if not TEST_RE.search(command):
        return False, False, "", set()
    output = call.output
    matches = re.findall(r"exit code (-?\d+)", output)
    failed = int(matches[-1]) != 0 if matches else bool(FAIL_RE.search(output))
    line = next((line.strip()[:120] for line in reversed(output.splitlines()) if FAIL_RE.search(line)), "") if failed else ""
    infra = bool(INFRA_RE.search(line)) if failed else False
    return True, failed, line, set(NAMES_RE.findall(line))


def _shell_write(command: str, known_paths: set[str]) -> tuple[bool, set[str]]:
    cleaned = re.sub(r"\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/null", "", command)
    targets: set[str] = set()
    for target in WRITE_TARGET_RE.findall(cleaned):
        target = target.strip("'\"")
        if not target or any(c in target for c in "$`*?{["):
            return True, set()
        for path in known_paths:
            if target == path or path.endswith("/" + target.removeprefix("./")):
                targets.add(path)
    if WRITE_ACTION_RE.search(cleaned):
        for path in known_paths:
            if path in cleaned or Path(path).name in cleaned:
                targets.add(path)
        if not targets:
            return True, set()
    return bool(targets), targets


def _read_targets(command: str, known_paths: set[str]) -> set[str]:
    if not READ_RE.search(command):
        return set()
    targets = set(PATH_RE.findall(command))
    targets.update(path for path in known_paths if path in command)
    return targets


@dataclass
class Life:
    text: str
    start: int
    provenance: str
    certain: bool
    tested: list[tuple[int, bool, bool, str, set[str]]] = field(default_factory=list)
    removed: int = -1

    @property
    def last_test(self):
        return self.tested[-1] if self.tested else None

    @property
    def failed_program(self) -> bool:
        test = self.last_test
        return bool(self.certain and test and test[1] and not test[2])

    @property
    def error_names(self) -> set[str]:
        test = self.last_test
        return test[4] if self.failed_program and test else set()


def analyze_returns(run: Run) -> dict[str, Any]:
    """Ricostruisce vite certe, fallimenti, ritorni e conteggi H3/H4 per esecuzione."""
    history: dict[str, dict[str, list[Life]]] = defaultdict(lambda: defaultdict(list))
    present: dict[str, Life] = {}
    changed_files: set[str] = set()
    unknown_write = False
    h3_cases, h3_named, h4_cases, h4_named = 0, 0, 0, 0
    h3_exclusions = Counter()
    circles = 0
    null_modifications = 0
    file_paths = {c.path for c in run.calls if c.path}
    views: dict[str, list[tuple[int, str]]] = defaultdict(list)
    test_calls = []
    for call in run.calls:
        if call.name in ("view", "read", "str_replace_editor") and call.args.get("command") in (None, "view"):
            for path in _read_targets(call.command, file_paths):
                views[path].append((call.n, strip_line_numbers(call.output)))
        did_test, failed, line, names = _test_failed(call)
        if did_test:
            test_calls.append((call.n, failed, bool(INFRA_RE.search(line)) if failed else False, line, names))
            for life in present.values():
                if life.start < call.n:
                    life.tested.append((call.n, failed, bool(INFRA_RE.search(line)) if failed else False, line, names))
        if call.name == "execute_bash" or call.command and call.name in ("run", "execute_bash"):
            is_write, targets = _shell_write(call.command, file_paths)
            if is_write:
                if not targets:
                    unknown_write = True
                    for path, life in list(present.items()):
                        life.certain = False
                        present.pop(path, None)
                else:
                    for path in targets:
                        changed_files.add(path)
                        if path in present:
                            present[path].certain = False
                            present.pop(path, None)
        if not call.editor:
            if call.name == "str_replace_editor" and call.result == "noop":
                null_modifications += 1
            command = str(call.args.get("command") or "")
            if call.name == "str_replace_editor" and command in {"insert", "create", "undo_edit"}:
                if call.result in {"edited", "created", "undo"} or call.result == "unknown":
                    if call.path:
                        changed_files.add(call.path)
                        present.pop(call.path, None)
                    else:
                        unknown_write = True
                        for path in list(present):
                            present.pop(path, None)
            continue
        if call.result == "noop":
            null_modifications += 1
        if call.result != "edited":
            continue
        path = call.path
        old, new = norm(call.old), norm(call.new)
        old_life = present.get(path)
        if large(old):
            if old_life is not None and old_life.text == old:
                old_life.removed = call.n
                life = old_life
            else:
                prior_history = history[path].get(old, [])
                if path not in changed_files and not unknown_write and not prior_history:
                    life = Life(old, -1, "originale", True, removed=call.n)
                else:
                    life = Life(old, call.n, "incerta", False, removed=call.n)
            history[path][old].append(life)
        if old_life is not None:
            old_life.removed = call.n
        present.pop(path, None)
        if large(new) and new in history[path]:
            new_lives = history[path][new]
            latest = next((life for life in reversed(new_lives) if life.certain and life.tested), None)
            if latest and latest.provenance == "agente" and latest.certain and latest.tested:
                if latest.failed_program and latest.error_names:
                    h3_cases += 1
                    if any(re.search(rf"\b{re.escape(name)}\b", call.context) for name in latest.error_names):
                        h3_named += 1
                elif latest.last_test and latest.last_test[2]:
                    h3_exclusions["infrastruttura"] += 1
                elif latest.last_test and not latest.last_test[1]:
                    h3_exclusions["superata"] += 1
                elif latest.last_test:
                    h3_exclusions["nessun_nome"] += 1
            elif latest and not latest.certain:
                h3_exclusions["presenza_incerta"] += 1
            elif latest and not latest.tested:
                h3_exclusions["mai_provata"] += 1
            elif latest and latest.provenance != "agente":
                h3_exclusions["provenienza_non_propria"] += 1
            if old_life and old_life.failed_program and latest and latest.failed_program:
                left_errors, right_errors = old_life.error_names, latest.error_names
                if left_errors and right_errors and left_errors.isdisjoint(right_errors):
                    circles += 1
                    h4_cases += 1
                    named_left = any(re.search(rf"\b{re.escape(name)}\b", call.context) for name in left_errors)
                    named_right = any(re.search(rf"\b{re.escape(name)}\b", call.context) for name in right_errors)
                    if named_left and named_right:
                        h4_named += 1
        if large(new):
            provenance = history[path][new][-1].provenance if history[path].get(new) else "agente"
            present[path] = Life(new, call.n, provenance, True)
        changed_files.add(path)
    return {
        "h3_casi": h3_cases,
        "h3_nominati": h3_named,
        "h3_esclusioni": dict(h3_exclusions),
        "h4_cerchi": h4_cases,
        "h4_nominati_entrambi": h4_named,
        "cerchi": circles,
        "modifiche_nulle": null_modifications,
    }


def aggregate_editor(runs: Iterable[Run]) -> dict[str, Any]:
    counts = Counter()
    for run in runs:
        for call in run.calls:
            if call.editor:
                counts[call.result] += 1
    denominator = sum(counts[k] for k in ("edited", "noop", "missing", "multiple"))
    return {
        "esiti": dict(sorted(counts.items())),
        "fallimenti_per_chiamata": _ratio(sum(counts[k] for k in FAILURES), denominator),
        "quota_noop": _ratio(counts["noop"], denominator),
        "denominatore": denominator,
    }


def mcnemar_exact(wins: int, losses: int) -> float:
    n = wins + losses
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / (2**n))


def clopper_pearson(successes: int, total: int, alpha: float = .05) -> list[float] | None:
    """Intervallo binomiale esatto bilaterale tramite bisezione della CDF."""
    if total <= 0:
        return None

    def cdf(k: int, probability: float) -> float:
        if probability <= 0:
            return 1.0
        if probability >= 1:
            return 1.0 if k >= total else 0.0
        return sum(
            math.comb(total, i) * probability**i * (1 - probability)**(total - i)
            for i in range(k + 1)
        )

    def inverse_cdf(k: int, target: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(100):
            middle = (low + high) / 2
            if cdf(k, middle) > target:
                low = middle
            else:
                high = middle
        return (low + high) / 2

    lower = 0.0 if successes == 0 else inverse_cdf(successes - 1, 1 - alpha / 2)
    upper = 1.0 if successes == total else inverse_cdf(successes, alpha / 2)
    return [lower, upper]


def _h34_decision(items: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    eligible_key = "h3_casi" if prefix == "h3" else "h4_cerchi"
    success_key = "h3_nominati" if prefix == "h3" else "h4_nominati_entrambi"
    eligible_runs = sum(item[eligible_key] > 0 for item in items)
    success_runs = sum(item[success_key] > 0 for item in items)
    interval = clopper_pearson(success_runs, eligible_runs)
    status = "non valutabile" if eligible_runs < 30 or interval is None else (
        "sostenuta" if interval[1] < .10 else "non sostenuta"
    )
    return {
        "esecuzioni_ammesse": eligible_runs,
        "successi_per_esecuzione": success_runs,
        "ic95_clopper_pearson": interval,
        "stato": status,
        "casi_descrittivi": sum(item[eligible_key] for item in items),
        "casi_con_nome": sum(item[success_key] for item in items),
    }


def summarize_sets(swehero: list[Run], qwen30: list[Run], qwen480: list[Run], opus: list[Run] | None = None) -> dict[str, Any]:
    sets = {"swehero_r2e_heldout": swehero, "openhands_30b": qwen30, "openhands_480b": qwen480}
    result: dict[str, Any] = {"insiemi_qwen": {}, "h1": {}, "h2_30b_meno_480b": None, "h5": {}, "h6_swehero": None, "h3_h4": {}}
    for name, runs in sets.items():
        result["insiemi_qwen"][name] = aggregate_editor(runs)
        per_run = [analyze_returns(run) for run in runs]
        result["h3_h4"][name] = {
            "esecuzioni": len(runs),
            "h3": _h34_decision(per_run, "h3"),
            "h4": _h34_decision(per_run, "h4"),
            "h3_esecuzioni_con_caso": sum(x["h3_casi"] > 0 for x in per_run),
            "h3_esecuzioni_con_nome": sum(x["h3_nominati"] > 0 for x in per_run),
            "h4_esecuzioni_con_cerchio": sum(x["h4_cerchi"] > 0 for x in per_run),
            "h4_esecuzioni_con_entrambi_nominati": sum(x["h4_nominati_entrambi"] > 0 for x in per_run),
            "conteggi_per_esecuzione": [
                {"indice": index, "task": run.task, **item}
                for index, (run, item) in enumerate(zip(runs, per_run))
            ],
        }
    result["h1"] = {
        name: {
            "fallimenti_presenti": sum(result["insiemi_qwen"][name]["esiti"].get(kind, 0) for kind in FAILURES) > 0,
            "noop_primo": (
                result["insiemi_qwen"][name]["esiti"].get("noop", 0)
                > max((result["insiemi_qwen"][name]["esiti"].get(kind, 0) for kind in FAILURES if kind != "noop"), default=0)
            ),
        }
        for name in sets
    }
    result["h1"]["stato"] = "sostenuta" if all(
        value["fallimenti_presenti"] and value["noop_primo"]
        for key, value in result["h1"].items() if key != "stato"
    ) else "non sostenuta"
    a = {run.task: run for run in qwen30}
    b = {run.task: run for run in qwen480}
    common = sorted(a.keys() & b.keys())
    af = np.array([sum(c.editor and c.result in FAILURES for c in a[t].calls) for t in common], dtype=float)
    ad = np.array([sum(c.editor and c.result in ("edited", *FAILURES) for c in a[t].calls) for t in common], dtype=float)
    bf = np.array([sum(c.editor and c.result in FAILURES for c in b[t].calls) for t in common], dtype=float)
    bd = np.array([sum(c.editor and c.result in ("edited", *FAILURES) for c in b[t].calls) for t in common], dtype=float)
    result["h2_30b_meno_480b"] = {"compiti_comuni": len(common), **_bootstrap_diff_ratio(af, ad, bf, bd)}
    for name, runs in (("openhands_30b", qwen30), ("openhands_480b", qwen480)):
        eligible_runs = [r for r in runs if r.resolved is not None]
        resolved = np.array([int(r.resolved is True) for r in eligible_runs], dtype=float)
        with_null = np.array([any(c.editor and c.result == "noop" for c in r.calls) for r in eligible_runs], dtype=bool)
        both = [resolved[with_null], resolved[~with_null]]
        if len(both[0]) and len(both[1]):
            rng = np.random.default_rng(SEME)
            samples = []
            for _ in range(N_BOOT):
                indices = rng.integers(0, len(eligible_runs), size=len(eligible_runs))
                sampled_null = with_null[indices]
                sampled_resolved = resolved[indices]
                if not sampled_null.any() or sampled_null.all():
                    continue
                x = sampled_resolved[sampled_null].mean()
                y = sampled_resolved[~sampled_null].mean()
                samples.append(x-y)
            result["h5"][name] = {
                "con_nulla": {"risolti": int(both[0].sum()), "totale": len(both[0])},
                "senza_nulla": {"risolti": int(both[1].sum()), "totale": len(both[1])},
                "esclusi_senza_esito": len(runs) - len(eligible_runs),
                "differenza_quote": float(both[0].mean()-both[1].mean()),
                "ic95": [float(np.quantile(samples,.025)),float(np.quantile(samples,.975))] if samples else None,
                "repliche_scartate": N_BOOT - len(samples),
                "stato": ("non valutabile" if not samples else
                          "sostenuta" if np.quantile(samples, .975) < 0 else "non sostenuta"),
            }
        else:
            result["h5"][name] = {"non_valutabile": "manca uno dei due gruppi"}
    # H6: le quattro misure della coorte SWE-Hero heldout, con bootstrap per esecuzione.
    run_metrics = []
    for run in swehero:
        c = Counter(call.result for call in run.calls if call.editor)
        measured = c["edited"] + sum(c[k] for k in FAILURES)
        ret = analyze_returns(run)
        run_metrics.append((
            sum(c[k] for k in FAILURES), measured,
            c["noop"], sum(c[k] for k in FAILURES),
            int(c["noop"] > 0), 1,
            int(ret["cerchi"] > 0), 1,
        ))
    arr = np.asarray(run_metrics, dtype=float)
    h6 = {}
    for label, ncol, dcol in (("fallimenti_per_chiamata",0,1),("quota_noop_fra_fallimenti",2,3),("esecuzioni_con_nulla",4,5),("esecuzioni_con_cerchio",6,7)):
        h6[label] = {"stima": _ratio(float(arr[:,ncol].sum()),float(arr[:,dcol].sum())), **_bootstrap_ratio(arr[:,ncol],arr[:,dcol])}
    result["h6_swehero"] = {"n_esecuzioni": len(swehero), "misure": h6}
    if opus is not None:
        result["opus_editor_rate"] = aggregate_editor(opus)
        result["opus_editor_rate"]["limite"] = (
            "Le traiettorie Opus contengono solo osservazioni: non sono disponibili ID o argomenti. "
            "Il tasso usa output file_editor riconosciuti come edited/noop/missing/multiple; il comando originale non è verificabile."
        )
    return result


def main() -> None:
    inputs = verify_input_manifest()
    swehero = parse_swehero(ROOT)
    qwen30 = parse_openhands_set(ROOT, "20250805-openhands-Qwen3-Coder-30B-A3B-Instruct")
    qwen480 = parse_openhands_set(ROOT, "20250805-openhands-Qwen3-Coder-480B-A35B-Instruct")
    opus = parse_openhands_set(ROOT, "20251127-openhands-claude-opus-4-5")
    result = summarize_sets(swehero, qwen30, qwen480, opus)
    result["input_manifest"] = inputs
    output = ROOT / "strumenti/esperimenti_codex/RICALCOLO_MODIFICHE_codex.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    print(json.dumps({k:v for k,v in result.items() if k != "h3_h4"}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
