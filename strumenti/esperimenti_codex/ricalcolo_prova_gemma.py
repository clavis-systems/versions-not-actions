"""Ricalcolo indipendente delle misure L1-L3 per la prova Gemma."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import numpy as np


CONDIZIONI = ("acceso", "spento")
FALLIMENTI = {"noop", "missing", "multiple", "other_error"}
ESITI_EDIT = FALLIMENTI | {"edited", "unknown"}
SEME_BOOTSTRAP = 20261011
N_BOOTSTRAP = 2_000
_SOSPETTO = re.compile(r"open\s*\(|sys\.|exit\s*\(|inspect", re.IGNORECASE)


def _esito_editor(output: str) -> str:
    """Classificazione del messaggio di str_replace definita nella premessa."""
    output = str(output).lstrip()
    low = output.lower()
    if output.startswith(("ERROR", "Invalid", "No replacement", "Ran into")):
        if "must be different" in low:
            return "noop"
        if "did not appear verbatim" in low:
            return "missing"
        if re.search(r"multiple occurrences", output, re.I):
            return "multiple"
        return "other_error"
    if "has been edited" in output[:300]:
        return "edited"
    return "unknown"


def _categorie_note_host(output: str) -> list[str]:
    """Classifica le note esplicite e gli esiti del tool che ne identificano il tipo."""
    text = str(output).lower()
    if "[host note]" not in text:
        return []
    result = _esito_editor(output)
    categories = []
    if "already sent this exact call" in text:
        categories.append("repeated_call")
    if "identical to a version that was already in the file" in text:
        categories.append("revisit")
    if result == "missing":
        if "already made this exact edit" in text or "already made this change" in text:
            categories.append("already_made_edit")
        elif "old_str was in the file until" in text:
            categories.append("removed_by_edit")
        elif "closest text in the file" in text:
            categories.append("closest")
    elif result == "noop":
        if "old_str and new_str are identical" in text:
            categories.append("noop_identical")
        elif "already made" in text or "still there" in text:
            categories.append("noop_applied")
    elif result == "multiple":
        categories.append("multiple")
    return categories


@dataclass(frozen=True)
class Coppia:
    compito: str
    acceso: Mapping[str, Any]
    spento: Mapping[str, Any]


def _chiave(riga: Mapping[str, Any]) -> tuple[str, str]:
    compito = str(riga.get("compito", ""))
    condizione = str(riga.get("condizione", ""))
    if not compito or condizione not in CONDIZIONI:
        raise ValueError("Ogni corsa deve avere compito e condizione acceso/spento")
    return compito, condizione


def valida_righe(righe: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Convalida record normalizzati e rifiuta duplicati o esiti non definiti."""
    indicizzate: dict[tuple[str, str], Mapping[str, Any]] = {}
    for riga in righe:
        chiave = _chiave(riga)
        if chiave in indicizzate:
            raise ValueError(f"Corsa duplicata: {chiave}")
        if not isinstance(riga.get("chiamate"), list):
            raise ValueError(f"Lista chiamate mancante: {chiave}")
        if riga.get("esito") not in ("risolto", "non_risolto", "incerto", "infrastruttura"):
            raise ValueError(f"Esito del compito non riconosciuto: {chiave}")
        for chiamata in riga["chiamate"]:
            if chiamata.get("tipo") == "str_replace" and chiamata.get("esito_editor") not in ESITI_EDIT:
                raise ValueError(f"Esito str_replace non riconosciuto: {chiave}")
        indicizzate[chiave] = riga
    return indicizzate


def conta_recupero(chiamate: Iterable[Mapping[str, Any]]) -> int:
    """Conta chiamate dopo il primo fallimento, inclusa la str_replace riuscita."""
    aperto = False
    conteggio = 0
    for chiamata in chiamate:
        tipo = chiamata.get("tipo")
        esito = chiamata.get("esito_editor") if tipo == "str_replace" else None
        if aperto:
            conteggio += 1
        if tipo == "str_replace" and esito in FALLIMENTI:
            aperto = True
        elif tipo == "str_replace" and esito == "edited":
            aperto = False
    return conteggio


def conta_fallimenti_ripetuti(chiamate: Iterable[Mapping[str, Any]]) -> int:
    """Conta fallimenti str_replace consecutivi dello stesso tipo di errore."""
    precedenti: str | None = None
    conteggio = 0
    for chiamata in chiamate:
        if chiamata.get("tipo") != "str_replace":
            continue
        esito = chiamata.get("esito_editor")
        if esito in FALLIMENTI:
            if esito == precedenti:
                conteggio += 1
            precedenti = str(esito)
        else:
            precedenti = None
    return conteggio


def contiene_testo_sospetto(riga: Mapping[str, Any]) -> bool:
    """Rileva le parole di cautela indicate nella premessa nei testi aggiunti."""
    return any(_SOSPETTO.search(str(c.get("testo_aggiunto", ""))) for c in riga["chiamate"])


def coppie_complete(righe: Iterable[Mapping[str, Any]]) -> tuple[list[Coppia], dict[str, list[str]]]:
    """Esclude un compito intero se manca una corsa o un esito è incerto/errore."""
    indice = valida_righe(righe)
    def ordine_compito(task: str) -> tuple[str, int | str]:
        prefisso, _, suffisso = task.rpartition("/")
        return (prefisso, int(suffisso) if suffisso.isdigit() else suffisso)

    compiti = sorted({c for c, _ in indice}, key=ordine_compito)
    complete: list[Coppia] = []
    escluse: dict[str, list[str]] = {}
    for compito in compiti:
        a = indice.get((compito, "acceso"))
        s = indice.get((compito, "spento"))
        motivi = []
        if a is None:
            motivi.append("manca_accesso")
        if s is None:
            motivi.append("manca_spento")
        for condizione, riga in (("acceso", a), ("spento", s)):
            if riga is None:
                continue
            esito = riga["esito"]
            if esito == "infrastruttura":
                motivi.append(f"infrastruttura_{condizione}")
            elif esito == "incerto":
                motivi.append(f"incerto_{condizione}")
        if motivi:
            escluse[compito] = motivi
        else:
            assert a is not None and s is not None
            complete.append(Coppia(compito, a, s))
    return complete, escluse


def mcnemar_esatto(vittorie: int, sconfitte: int) -> float:
    """P bilaterale esatto binomiale sulle coppie discordanti."""
    n = vittorie + sconfitte
    if n == 0:
        return 1.0
    coda = sum(math.comb(n, k) for k in range(min(vittorie, sconfitte) + 1)) / (2**n)
    return min(1.0, 2.0 * coda)


def _intervallo_bootstrap(valori: np.ndarray) -> tuple[float, float]:
    n = len(valori)
    if n == 0:
        raise ValueError("Bootstrap senza compiti")
    rng = np.random.default_rng(SEME_BOOTSTRAP)
    indici = rng.integers(0, n, size=(N_BOOTSTRAP, n))
    medie = valori[indici].mean(axis=1)
    return float(np.quantile(medie, 0.025)), float(np.quantile(medie, 0.975))


def riepiloga(righe: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Calcola L1-L3 e descrittive su coppie complete, prima del bootstrap."""
    coppie, escluse = coppie_complete(righe)
    if not coppie:
        raise ValueError("Nessuna coppia completa")

    def risolto(r: Mapping[str, Any]) -> bool:
        return r["esito"] == "risolto"

    win = sum(risolto(c.acceso) and not risolto(c.spento) for c in coppie)
    loss = sum(risolto(c.spento) and not risolto(c.acceso) for c in coppie)
    diff_l1 = np.array([int(risolto(c.acceso)) - int(risolto(c.spento)) for c in coppie], dtype=float)
    diff_l2 = np.array([conta_recupero(c.acceso["chiamate"]) - conta_recupero(c.spento["chiamate"]) for c in coppie], dtype=float)
    diff_l3 = np.array([conta_fallimenti_ripetuti(c.acceso["chiamate"]) - conta_fallimenti_ripetuti(c.spento["chiamate"]) for c in coppie], dtype=float)

    descrittive: dict[str, Any] = {}
    for condizione in CONDIZIONI:
        corse = [getattr(c, condizione) for c in coppie]
        esiti = Counter(
            chiamata["esito_editor"]
            for corsa in corse for chiamata in corsa["chiamate"]
            if chiamata.get("tipo") == "str_replace"
        )
        note_host = Counter(
            str(nota)
            for corsa in corse for nota in corsa.get("note_host", [])
        )
        descrittive[condizione] = {
            "esiti_str_replace": dict(sorted(esiti.items())),
            "note_host": dict(sorted(note_host.items())),
            "chiamate": sum(len(c["chiamate"]) for c in corse),
            "finish": sum(c.get("finish", 0) for c in corse),
            "dropped_calls": sum(c.get("dropped_calls", 0) for c in corse),
            "tempo_secondi": sum(c.get("tempo_secondi", 0.0) for c in corse),
            "token": sum(c.get("token", 0) for c in corse),
        }
    sospetti_accesso = {c.compito for c in coppie if contiene_testo_sospetto(c.acceso)}
    sospetti_spento = {c.compito for c in coppie if contiene_testo_sospetto(c.spento)}
    sospetti = sorted(sospetti_accesso | sospetti_spento)
    win_sens = sum(
        (risolto(c.acceso) and c.compito not in sospetti_accesso)
        and not (risolto(c.spento) and c.compito not in sospetti_spento)
        for c in coppie
    )
    loss_sens = sum(
        (risolto(c.spento) and c.compito not in sospetti_spento)
        and not (risolto(c.acceso) and c.compito not in sospetti_accesso)
        for c in coppie
    )
    return {
        "n_coppie_complete": len(coppie),
        "escluse": escluse,
        "L1": {
            "risolti_acceso": sum(risolto(c.acceso) for c in coppie),
            "risolti_spento": sum(risolto(c.spento) for c in coppie),
            "vittorie_guardiano": win,
            "sconfitte_guardiano": loss,
            "p_mcnemar_bilaterale": mcnemar_esatto(win, loss),
            "ic_bootstrap_differenza_quote": _intervallo_bootstrap(diff_l1),
            "sostenuta": mcnemar_esatto(win, loss) < 0.05 and win > loss,
            "sensitivity_vittorie": win_sens,
            "sensitivity_sconfitte": loss_sens,
            "sensitivity_p_mcnemar_bilaterale": mcnemar_esatto(win_sens, loss_sens),
            "sensitivity_sostenuta": mcnemar_esatto(win_sens, loss_sens) < 0.05 and win_sens > loss_sens,
            "compiti_sospetti": sospetti,
        },
        "L2": {"media_differenza": float(diff_l2.mean()), "ic_bootstrap": _intervallo_bootstrap(diff_l2), "sostenuta": bool(_intervallo_bootstrap(diff_l2)[1] < 0)},
        "L3": {"media_differenza": float(diff_l3.mean()), "ic_bootstrap": _intervallo_bootstrap(diff_l3), "sostenuta": bool(_intervallo_bootstrap(diff_l3)[1] < 0)},
        "descrittive": descrittive,
    }


def carica_json(percorso: str) -> list[dict[str, Any]]:
    """Carica esclusivamente il formato neutro documentato qui sotto."""
    import json
    with open(percorso, encoding="utf-8") as file:
        dati = json.load(file)
    if not isinstance(dati, dict) or set(dati) != {"righe"} or not isinstance(dati["righe"], list):
        raise ValueError("Atteso JSON normalizzato con la sola chiave 'righe'")
    return dati["righe"]


def normalizza_record_grezzo(raw: Mapping[str, Any], nome_file: str) -> dict[str, Any]:
    """Converte un log `*_on/off.json` in una corsa neutra, senza usare solved come unica fonte."""
    stem = Path(nome_file).stem
    match = re.fullmatch(r"(?P<task>\d+)_(?P<condition>on|off)", stem)
    if not match:
        raise ValueError(f"Nome di corsa inatteso: {nome_file}")
    if bool(raw.get("guard")) != (match.group("condition") == "on"):
        raise ValueError(f"Condizione discordante tra file e record: {nome_file}")

    hidden_output = str(raw.get("hidden_test_output") or "")
    hidden_state = raw.get("hidden")
    if raw.get("infra_error"):
        outcome = "infrastruttura"
    elif hidden_state == "passed" and re.search(r"(?m)^HIDDEN TESTS PASSED [0-9a-fA-F]+\s*$", hidden_output):
        outcome = "risolto"
    elif hidden_state == "failed" and re.search(
        r"Traceback|\b(?:Syntax|Name|Type|Value|Assertion|Import|ModuleNotFound|Runtime)Error\b|"
        r"timed? ?out|time limit|output limit|MemoryError|Killed",
        hidden_output,
        re.I,
    ):
        outcome = "non_risolto"
    else:
        outcome = "incerto"
    if raw.get("solved") is not (outcome == "risolto"):
        raise ValueError(f"Esito derivato discordante dal riepilogo grezzo: {nome_file}")

    messages = raw.get("messages")
    if not isinstance(messages, list):
        raise ValueError(f"Conversazione mancante: {nome_file}")
    calls: list[dict[str, Any]] = []
    host_notes: list[str] = []
    malformed = 0
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            calls.append({"tipo": "risposta"})
            continue
        following = []
        cursor = index + 1
        while cursor < len(messages) and messages[cursor].get("role") == "tool":
            following.append(messages[cursor])
            cursor += 1
        call_ids = [item.get("id") for item in tool_calls]
        output_ids = [item.get("tool_call_id") for item in following]
        if (call_ids and all(call_ids) and len(set(call_ids)) == len(call_ids)
                and len(following) == len(tool_calls) and output_ids and all(output_ids)
                and len(set(output_ids)) == len(output_ids)):
            by_id = {item.get("tool_call_id"): item for item in following}
            paired = [by_id.get(call_id) for call_id in call_ids]
        elif len(following) == len(tool_calls):
            paired = following
        else:
            paired = [None] * len(tool_calls)
        for raw_call, output in zip(tool_calls, paired):
            function = raw_call.get("function") or {}
            name = str(function.get("name") or "")
            try:
                args = json.loads(function.get("arguments") or "{}")
            except (TypeError, json.JSONDecodeError):
                args = None
            if not isinstance(args, dict):
                malformed += 1
                args = {}
            host_notes.extend(_categorie_note_host(str((output or {}).get("content") or "")))
            if name == "str_replace_editor" and args.get("command") == "str_replace":
                outcome_editor = _esito_editor(str((output or {}).get("content") or ""))
                calls.append({
                    "tipo": "str_replace",
                    "esito_editor": outcome_editor,
                    "testo_aggiunto": str(args.get("new_str") or ""),
                })
            else:
                calls.append({"tipo": name or "strumento"})

    if len(calls) != raw.get("calls"):
        raise ValueError(f"Numero di unità chiamata discordante ({len(calls)} vs {raw.get('calls')}): {nome_file}")
    token_count = 0
    for message in messages:
        token_data = ((message.get("meta") or {}).get("tokens") or {})
        if isinstance(token_data, Mapping):
            token_count += int(token_data.get("prompt", 0) or 0) + int(token_data.get("completion", 0) or 0)
    return {
        "compito": str(raw.get("task") or f"Python/{match.group('task')}"),
        "condizione": "acceso" if match.group("condition") == "on" else "spento",
        "esito": outcome,
        "chiamate": calls,
        "note_host": host_notes,
        "finish": sum(call["tipo"] == "finish" for call in calls),
        "dropped_calls": int(raw.get("dropped_calls", 0) or 0),
        "tempo_secondi": float(raw.get("seconds", 0) or 0),
        "token": token_count,
        "esito_grezzo_hidden": hidden_state,
        "chiamate_malformate": malformed,
        "solved_concorda": raw.get("solved") is (outcome == "risolto"),
    }


def carica_log_grezzi(directory: str | Path) -> list[dict[str, Any]]:
    """Legge solo i file delle corse, non il JSON di analisi di Claude."""
    root = Path(directory)
    rows = []
    for path in sorted(root.glob("*_*.json")):
        if not re.fullmatch(r"\d+_(?:on|off)\.json", path.name):
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows.append(normalizza_record_grezzo(raw, path.name))
    return rows


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("percorso", help="Cartella con i log *_on/off.json oppure un JSON normalizzato")
    parser.add_argument("--output", help="Salva i risultati in questo file JSON UTF-8")
    args = parser.parse_args()
    target = Path(args.percorso)
    rows = carica_log_grezzi(target) if target.is_dir() else carica_json(str(target))
    result = riepiloga(rows)
    result["metadati_ricalcolo"] = {
        "file_corsa": len(rows),
        "sorgente": "log grezzi *_on/off.json",
        "nessun_codice_modello_eseguito": True,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
