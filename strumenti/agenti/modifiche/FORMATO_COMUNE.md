# A common shape for coding-agent trajectories

Agent frameworks keep their trajectories ("diaries") in different formats. `formati.py` translates them into one
shape, so that the same detectors read every source in the same way. Nothing is lost silently: every translation
comes with a receipt that accounts for each unit of the source.

## One run

| Field | Meaning |
|---|---|
| `id` | run id: the SWE-Hero `trajectory_id`, or the SWE-bench instance id |
| `task` | task id (SWE-bench instance id) |
| `collection` | where the task comes from: for SWE-Hero the `dataset` column (R2E-Gym, SWE-Gym, SWE-rebench), otherwise `SWE-bench Verified` |
| `source` | `swehero`, `openhands_events` or `observations_only` |
| `model` | model name as written in the source; for SWE-Hero, given by the caller from the dataset card |
| `outcome` | `resolved`, `unresolved`, `no_generation` or `no_logs`, from the submission's `results.json`; `null` when unknown |
| `patch` | final patch, when the source keeps it (SWE-Hero) |
| `messages` | the messages below; `null` for observation-only logs |
| `observations` | `[tool, text]` pairs for observation-only logs; `null` otherwise |
| `receipt` | the accounting of the translation (below) |

## Messages

- `{"role": "system" | "user", "content": str}`
- `{"role": "assistant", "content": str, "tool_calls": [{"id": str, "function": {"name": str, "arguments": str}}]}`:
  `content` is the text the model wrote with the call, and `arguments` is the raw JSON string of the call. When one
  response holds several calls, each call repeats the response's text.
- `{"role": "tool", "content": str, "tool_call_id": str}`: the result as the model saw it.
- `{"role": "error", "content": str}`: an error raised before any tool ran, for example a call without a required
  argument.

Each tool message comes right after the assistant message that called it, with one call per assistant message.

**Margin notes.** A message carries `meta` only when its source keeps the information:
- `time`: ISO timestamp. For an assistant message, when the call was recorded; for a tool message, when the result
  arrived.
- `tokens`: `{"prompt": int, "completion": int}` of the model response, on its first call only.
- `shared_response`: `true` on the later calls of a response with several calls.
- `file_before`, `file_after`: the whole file around a successful edit.

## Receipt

| Key | Meaning |
|---|---|
| `events` | units read from the source (events or messages) |
| `written` | units written into messages |
| `set_aside` | `{reason: count}` for the units not written |
| `calls` | tool calls written |
| `calls_rebuilt` | calls rebuilt from the recorded action, because the model's raw call was missing |
| `edits_checked`, `edits_differing` | str_replace calls whose raw arguments were compared with the action recorded by the framework, and how many differ |
| `exit_lines_restored` | command results that got back the exit-code line the model saw |
| `malformed_calls` | errors kept with role `error` |
| `results_kept_raw` | stored results whose text could not be read, kept unchanged |
| `models` | `{model name: model responses}` |
| `framework_versions` | `{framework and version: count}`, when the source records it (OpenHands event lists) |

A receipt is **balanced** when `written` plus all `set_aside` counts equals `events`.

## What each source keeps

| | SWE-Hero | OpenHands events (SWE-bench) | Observation-only (Claude Opus 4.5) |
|---|---|---|---|
| Model calls with arguments | yes | yes, raw | no, lost |
| Tool results | yes | yes | yes |
| Time of each step | no | yes | no |
| Tokens of each response | no | yes | no |
| File before and after each edit | no | yes | no |
| Task outcome | no | yes, from `results.json` | yes, from `results.json` |
| Final patch | yes | no | no |

## Translation check on the real data (09/10/2026)

All receipts are balanced. These counts describe the translation only, not the agents' errors.

| Set | Runs | Units read | Written | Set aside | Calls | Raw calls rebuilt | str_replace calls checked against the action | Differing |
|---|---|---|---|---|---|---|---|---|
| SWE-Hero, shard 0 | 2,500 | 296,414 | 296,414 | 0 | 146,957 | 0 | – | – |
| OpenHands + Qwen3-Coder-30B | 500 | 63,088 | 61,591 | 1,497 (recall 1,002, finish 495) | 30,292 | 0 | 1,979 | 0 |
| OpenHands + Qwen3-Coder-480B | 500 | 77,285 | 75,782 | 1,503 (recall 1,003, finish 500) | 37,388 | 0 | 3,463 | 0 |
| Claude Opus 4.5, observations only | 489 | 54,094 | 26,558 | 27,536 (actions not recorded 26,558, prompts 978) | – | – | – | – |

- The model names in the OpenHands logs are `Qwen3-Coder-30A3-0731` and `Qwen3-Coder-Max-0721`, while the submissions
  call the models Qwen3-Coder-30B-A3B-Instruct and Qwen3-Coder-480B-A35B-Instruct. Both names are reported.
- Every model call in the two OpenHands sets has its time and token counts. File states are present after
  successful edits.

## Adding a new diary

1. Write a reader that yields runs in this shape, with a balanced receipt.
2. Add a test with invented data.
3. Run the receipt check on the real files before any analysis.
