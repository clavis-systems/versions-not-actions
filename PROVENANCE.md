# Provenance

I froze each plan with a git tag in my private working repository. The commit ids and the SHA-256 of the code
below let you check that the code here is the code that produced the results.
- For the first study, the hashes of `formati.py`, `rilevatori.py` and `misura.py` are also recorded in the plan
  and in the results file `misura_heldout.json`.
- For the live test, they are in the plan and in every Gemma run log (`config.agent_sha256`).
- For the two newer studies (versions, not actions; anatomy), the plans do not record the hashes: the link between
  code and results is the freeze tag and this table.

The repository stores every file byte for byte (`.gitattributes`: `* -text`), so the hashes hold on a clone.

| Study | Plan | Freeze tag | Commit | Time (CEST) |
|---|---|---|---|---|
| What fails | `PREMESSA_MODIFICHE.md` | `congelamento-modifiche-2026-10-10` | `a936baaab6e0` | 2026-10-10 20:14 |
| Live test with Gemma | `PREMESSA_PROVA_GEMMA.md` | `congelamento-prova-gemma-2026-10-10` | `610a9ddb0a36` | 2026-10-10 22:36 |
| Versions, not actions | `PREMESSA_STATO_AZIONE.md` | `congelamento-stato-azione-2026-10-11` | `c251880de970` | 2026-10-11 19:40 |
| Anatomy of failed quotes | `PREMESSA_ANATOMIA_COPIE.md` | `congelamento-anatomia-2026-10-11` | `03417d88da77` | 2026-10-11 19:55 |

The frozen code files in this repository are identical to their version at each freeze tag:

| File | SHA-256 |
|---|---|
| `formati.py` | `ac9479c8a98c494f630c39e278f4b6914a76a05be15cee67eaf14e4e27600c24` |
| `rilevatori.py` | `67736642fa833775858219cfafbf244a8855106b197d03d92beb7442321b4165` |
| `misura.py` | `ab9ddaa3c80f5982bbbc7bfdcf0978cf9e4a54ad9872a780e6a4bc3d7370156c` |
| `agente_gemma.py` | `dbb70bc73f870a90603657fea3aed384d20abf07e2e43f066223e92067343520` |
| `analisi_prova_gemma.py` | `e27de06953575f4b907feb18f0a707e0548d3441c72f538080c717c4e0512134` |
| `stato_azione.py` | `f5cc3d8d50d38916ebc562fed4f2a266842da593a1b614899d342583214ceacb` |
| `anatomia_copie.py` | `30bc247127e05f47e5a754039932c0a27be63c28eff5460bf9b297f23b91e79b` |
| `strumenti/valutazione/sandbox_wasm.py` | `0bc3f432d400a5fb4d58f16f8b245f8a20627f0b84af00bb90ff5c9042fc18d1` |
| `campione_verifica.py` (draws the audit sample; frozen with the first study) | `136e1f5fb2a279833bd1d54d8b171e95365060008c877f9c9c4a44ace764c005` |

The other scripts were written after the freezes and are not part of any pre-registered test:
- the figures, the exploratory analyses and the incident index;
- the audit tools: `mostra_campione.py`, `registra_etichette.py`, `confronta_etichette.py`,
  `aggiudica_campione.py` and `prepara_verifica_pubblica.py`.

**Earlier looks at the test data**
- The first study's detectors had produced aggregate counts on the same held-out logs before the two newer plans
  were written.
- Before the plan "versions, not actions" was written, an exploratory script (`esplora_idee.py`) counted on all 500
  runs per SWE-bench set how many failed `str_replace` calls repeated an identical earlier failed call on the same
  file version: 24 of 186 (30B) and 11 of 175 (480B). This is close to the complement of hypothesis S2, so S2 was
  not blind. S1 and S3 had not been computed on the test runs.
- The anatomy test (SWE-Hero held-out shards) had not been read by `esplora_idee.py`, which used only the
  development shards and the SWE-bench sets.

**The audit (plan of the first study, §7.4).** The judges are two AI systems, Claude and Codex; no person labelled
the cases.
- Codex labelled the 120 sampled incidents on 10 October 2026. Its labels sat in my working repository from then on.
  That Claude did not open them before finishing its own is a matter of procedure, which the next point documents.
- Claude finished its labels on 11 October 2026 at 21:49 CEST. Their SHA-256 was recorded in commit 244f3d0 of my
  working repository, before Codex's labels were opened.
  - The published `verifica_etichette_claude.jsonl` is that same file:
    `6f6ada279771f1b2d302bdedb610deea35a22bf45dd65c5489bdced4a7705c6c`.
  - Claude's criterion, `verifica_criterio_claude.md`:
    `61c5b5fc15ca6ea128d38ee061295ed62ec766a455cb423b6e706a7573c44106`.
- The plan now lists three deviations, dated:
  - the criterion of Claude's labels and how Claude read the cases;
  - the extra full-log step (`aggiudica_campione.py`);
  - the scope and counts of Codex's recomputation (below).
- `confronta_etichette.py` rebuilds `verifica_confronto.json` byte for byte from the published files. It writes
  `\n` line ends on every system.

**Independent recomputations by Codex.**
- Codex wrote its own code from the plans, without reading mine. It had reviewed my plans and code before the
  freezes.
- **Live test:** every number matches. The intervals of the recovery calls and of the repeated failures (L2, L3)
  matched after Codex corrected the order of the tasks in its code.
- **First study:** the decisions on H1, H2, H5 and H6 match. Some counts do not:

  | Measure | Set | Codex | `misura.py` |
  |---|---|---|---|
  | H3: runs naming the earlier error / eligible runs | 30B | 2 / 4 | 0 / 3 |
  | H3: runs naming the earlier error / eligible runs | 480B | 4 / 5 | 0 / 15 |
  | H3: runs naming the earlier error / eligible runs | SWE-Hero R2E-Gym (221 runs) | 0 / 2 | 0 / 5 |
  | H4: eligible runs | 30B, 480B, R2E-Gym | 0, 1, 1 | 1, 5, 4 |
  | H6: runs with a circle | R2E-Gym | 1 / 221 | 5 / 221 |

  - For SWE-Hero, Codex used only the 221 R2E-Gym runs instead of all 24,269. So H3 and H4, which `misura.py`
    decided on all 24,269 runs, were not recomputed there, and H1 matches only as a decision.
  - At least three deviations from the plan's §9 are visible in Codex's code. Whether they explain the
    differences is not checked:
    - a bash redirection with a single `>` does not count as a write (§9 uses `>>?\s*`);
    - targets that match no known path are dropped;
    - test commands are matched without regard to upper or lower case.
  - Codex had read the parts of the plan with the development values used by H6.
  - Its per-call failure rates use a denominator that leaves out "other" errors (9.51% and 5.51%, against 9.50%
    and 5.49%). Its H2 test uses the right one and matches.
  - The Codex reports mention test modules and a test suite of my working repository that are not published.

**Still open**
- Explain the H3 and H4 count differences, then check H3 and H4 independently on all 24,269 SWE-Hero runs.
- An independent recomputation of the two newer log studies (versions, not actions; anatomy of failed quotes).
