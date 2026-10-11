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

The other scripts (figures, exploratory analyses, the incident index) were written after the freezes and are not
part of any pre-registered test.

**Earlier looks at the test data**
- The first study's detectors had produced aggregate counts on the same held-out logs before the two newer plans
  were written.
- Before the plan "versions, not actions" was written, an exploratory script (`esplora_idee.py`) counted on all 500
  runs per SWE-bench set how many failed `str_replace` calls repeated an identical earlier failed call on the same
  file version: 24 of 186 (30B) and 11 of 175 (480B). This is close to the complement of hypothesis S2, so S2 was
  not blind. S1 and S3 had not been computed on the test runs.
- The anatomy test (SWE-Hero held-out shards) had not been read by `esplora_idee.py`, which used only the
  development shards and the SWE-bench sets.

**Still open**
- The audit of 120 sampled incidents: the second annotator's labels are pending.
- An independent recomputation of the three newer studies by the reviewer.
