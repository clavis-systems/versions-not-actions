# Versions, not actions

Code, frozen plans, reviews, results and logs for my study of **wasted edits in coding agents**: edits that fail,
change nothing, or bring a file back to a version that already failed. I look at them from the side of the host,
the software that runs the agent's tools and can record every version of an edited file.

Author: Emanuele Rizzan, independent researcher (GitHub: clavis-systems).

Each study had a written plan, frozen before its method was run on the test data, and the test data were analyzed
with it once. Some test runs had been read by earlier studies or exploratory scripts; the plans and
`PROVENANCE.md` say where.

## What I found

| Study | Data | Result |
|---|---|---|
| What fails, and how often | OpenHands logs of Qwen3-Coder 30B and 480B on SWE-bench Verified; SWE-Hero (Qwen3-Coder-480B) | The 30B model fails more `str_replace` calls than the 480B (9.50% vs 5.49% on the same 500 tasks; the two differ in more than size). Runs with a no-op edit resolve fewer tasks (an association). 4 of 6 hypotheses supported |
| Versions, not actions | 450 held-out runs per model | 77% (30B) and 86% (480B) of the returns to an earlier file content are not a repeated node in a graph of concrete actions. All 6 tests passed |
| Anatomy of failed quotes | 24,269 held-out SWE-Hero runs, 552 cases | Only 24% of failed quotes differ from the real lines in whitespace alone. The second hypothesis, that most wrong lines match lines seen elsewhere in the file, is not supported (52%, 95% CI 46–59%) |
| Live test with Gemma 4 E4B | 144 HumanEvalFix tasks, notes off vs on | Repeated edit failures −58%, recovery calls −41%. Solved tasks 117 → 124, not significant (p = 0.092) |

## What is in this repository

| Folder | Content |
|---|---|
| `strumenti/agenti/modifiche/` | The code (translator `formati.py`, detectors `rilevatori.py`, measures, live-test harness `agente_gemma.py`, analyses, figures, incident index), its tests, and the plans `PREMESSA_*.md` |
| `strumenti/valutazione/` | The WebAssembly sandbox where all code written by the model, and all tests, ran. The model itself ran on Ollama |
| `strumenti/risultati/modifiche/` | Results of the log studies. `revisioni/` holds every review of the plans, with the request that started it where I kept one |
| `strumenti/risultati/prova_gemma/` | The Gemma run logs: smoke tests (`fumo`, `fumo_congelato`), development (`sviluppo`, `sviluppo2` interrupted, `sviluppo3`), and the 288 test runs (`prova`), with their analyses |
| `strumenti/risultati/indice_incidenti/` | A pointer-only index of edit incidents in SWE-Hero (see below) |
| `figures/` | The figures of the paper |

The folder names and the plans are in Italian, my language; the code and its comments are in English. Plans and
reviews sometimes mention files of my working folder that are not published (private notes, and an audit sample
that contains trajectory text); the reviews they mention are in `revisioni/`.

## How the studies were run

1. I wrote a plan: hypotheses, decision rules, a development part and a test part.
2. OpenAI Codex, run read-only, reviewed the plan and the code. Every blocking point was fixed. Each plan took 3 to
   5 rounds.
3. I froze the plan with a tag in my working repository. `PROVENANCE.md` lists the tags, the commits and the
   SHA-256 of the code; the files here are byte-identical to the frozen ones.
4. The test part ran once. Every later change is listed at the end of the plan, under "Scostamenti" (deviations).

## Reproduce

Python 3.12 with `numpy` and `pyarrow`. Tests: `python -m unittest discover -s strumenti/agenti/modifiche`.

Data, downloaded into `esterni/`:
- **SWE-Hero:** `nvidia/SWE-Hero-openhands-trajectories` on Hugging Face; the parquet shards go into
  `esterni/SWE-Hero-openhands-trajectories/data/`.
- **SWE-bench Verified logs:** the OpenHands runs listed in the SWE-bench/experiments repository. Trajectories go
  into `esterni/swebench-trajs/<run>/<instance>/trajectory.json` (Opus: `<run>/<instance>.json`). Results go into
  `esterni/swebench-results/<run>/results.json`; their folder names use an underscore, as in
  `20250805_openhands-Qwen3-Coder-30B-A3B-Instruct`. `misura.py` lists the exact names. I do not redistribute these
  logs.
- **HumanEvalFix:** `bigcode/humanevalpack`, Python split, into `esterni/humanevalpack/` (see the manifest there).

The scripts never overwrite a result. To rerun the first study, move `misura_heldout.json` and
`misura_heldout.inputs.json` out of `strumenti/risultati/modifiche/`. Keep `misura_dev.json`, which is an input of
the held-out part. Then compare your file with mine.

```
python -I strumenti/agenti/modifiche/misura.py heldout
python -I strumenti/agenti/modifiche/stato_azione.py swebench --part test --out stato_azione_test.json
python -I strumenti/agenti/modifiche/anatomia_copie.py swehero heldout --out anatomia_test.json
python -I strumenti/agenti/modifiche/analisi_prova_gemma.py --dir strumenti/risultati/prova_gemma/prova --tasks 20-163 --out analysis.json
python -I strumenti/agenti/modifiche/indice_incidenti.py --out-dir index
```

**The live test** does not need to be rerun to check my numbers: the analysis reads the logs included here. To
rerun it you need:
- Windows, because the sandbox installer fetches the x86_64-windows build of wasmtime
  (`python strumenti/valutazione/installa_sandbox.py`);
- Ollama with `gemma4:e4b-it-qat`;
- a lock file `strumenti/risultati/.gpu_lock`, less than 24 hours old, whose text contains "agente_gemma".

Then run `python -I strumenti/agenti/modifiche/agente_gemma.py --tasks 20-163 --guard both --out <folder>`.

## The incident index

`incidenti.jsonl` has one line per incident: set, run id, task, category (`noop`, `multiple`, `stale`,
`never_seen`, `known_bad_retry`, `circle`), message index and call number. Some lines also point to the failing
tests. It contains no trajectory text: you rebuild the context from the public data with `formati.py`.
`manifest.json` records the SHA-256 of every input file and of the code. The index covers only SWE-Hero, because I
found no reuse licence for the SWE-bench trajectories. The detectors are rules and can be wrong; an audit of a
sample is in progress.

## Licences

- The code and my texts are under Apache-2.0 (`LICENSE`).
- The data I use keep their own licences (`DATA_LICENSES.md`).

## Use of AI

Claude (Anthropic) wrote most of the code and drafted the texts under my direction. Codex (OpenAI) reviewed every
plan before its freeze. I chose the questions, made the decisions and checked the results.

## Citing

Emanuele Rizzan, *Versions, not actions: wasted edits of coding agents seen from the host*, 2026,
https://github.com/clavis-systems/versions-not-actions
