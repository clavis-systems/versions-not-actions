# Data and licences

| Source | Licence | What this repository contains |
|---|---|---|
| SWE-Hero trajectories, NVIDIA (`nvidia/SWE-Hero-openhands-trajectories`; report arXiv:2604.01496) | CC BY 4.0 | A derived, filtered index of pointers (run ids, message and call numbers, categories), with no trajectory text. Aggregate counts. The audit files (`verifica_campione.json`, `verifica_aggiudicazione.json`, the label files and `verifica_confronto.json`) also hold short excerpts of the 107 sampled SWE-Hero items (106 runs): failing test lines, commands, code lines and a few quoted words, selected and cut |
| OpenHands trajectories on SWE-bench Verified (SWE-bench/experiments) | No reuse licence found | Aggregate counts. The input manifests list the trajectory files by instance id, size and SHA-256. Figure 1 is a graph of one public run (hashes of file contents, no text). No trajectory text, patches or messages, except a few words quoted in the audit labels of the 13 sampled SWE-bench items (tool messages, file names, short phrases) |
| HumanEvalPack / HumanEvalFix, BigCode (`bigcode/humanevalpack`) | MIT | The Gemma run logs include the task code shown to the model |
| Gemma 4 E4B (`gemma4:e4b-it-qat`) | Apache-2.0 (model card) | The model's replies in the Gemma run logs, which I release with the rest of this repository under Apache-2.0 |

Attribution for SWE-Hero: "Source: NVIDIA, SWE-Hero trajectories, CC BY 4.0. Derived pointer index, plus short
excerpts of 107 sampled items (106 runs) in the audit files. Changes: the excerpts were selected and cut; no full trajectory is
reproduced." Licence text: https://creativecommons.org/licenses/by/4.0/
