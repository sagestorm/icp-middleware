# LLM intake example

Offline-first ICP consumer: each AI persona gets one event fact pack, emits
exactly one interrogative **plus** `fact_refs`, and middleware validates
(retry ≤3 with error codes only). Accepted records go through blind export +
steward coding key.

`E_SPEC` rejects banal generics (e.g. “What event is being described?”) and,
when a fact sheet is supplied, requires content-token overlap with the pack.

## Mock (default — no API key)

From the repo root (after `pip install -e .` or with `src` on `PYTHONPATH`):

```bash
python examples/llm_intake/run.py --mock
```

Writes:

- `examples/llm_intake/out/records.json`
- `examples/llm_intake/out/analysis_packet.json`
- `examples/llm_intake/out/coding_key.json` (**steward-only** — do not share with blind reviewers)

## Live (OpenAI-compatible or NVIDIA NIM)

Uses stdlib `urllib` only (no `openai` / `httpx` package required).

`run.py` loads `../.env` then `.env` without overriding already-exported vars.

**NVIDIA NIM** (hosted catalog):

```bash
# In repo-root .env (never commit):
# NVIDIA_API_KEY=nvapi-...
# MASTERY_MODEL_NAME=google/gemma-4-31b-it
python examples/llm_intake/run.py --live
```

**Prove live retry** (attempt 1 = local pollution; attempt 2+ = real NIM):

```bash
python examples/llm_intake/run.py --live --probe-retry
```

Prints `probe_calls` / `network_calls` / `persona_attempts` and writes
`out/probe_retry_summary.json`.

**OpenAI / compatible**:

```bash
set OPENAI_API_KEY=sk-...
set OPENAI_BASE_URL=https://api.openai.com
set OPENAI_MODEL=gpt-4o-mini
python examples/llm_intake/run.py --live
```

| Env | Default | Purpose |
|-----|---------|---------|
| `OPENAI_API_KEY` or `NVIDIA_API_KEY` | _(required for `--live`)_ | Bearer token |
| `OPENAI_BASE_URL` / `MASTERY_MODEL_BASE_URL` | OpenAI host, or NIM `https://integrate.api.nvidia.com/v1` when using `NVIDIA_API_KEY` | API root (`…/v1` or host; both accepted) |
| `OPENAI_MODEL` / `MASTERY_MODEL_NAME` | `gpt-4o-mini` or NIM `google/gemma-4-31b-it` | Model id |

Catalog models go EOL — if you see HTTP 410, list models at
`GET /v1/models` and set `MASTERY_MODEL_NAME` to a live chat model.

## Sample events

Pass either pack with `--event`:

```bash
python examples/llm_intake/run.py --mock --event examples/llm_intake/sample_event.json
python examples/llm_intake/run.py --mock --event examples/llm_intake/sample_event_policy.json
```

### `sample_event.json` — `technical_incident` (asymmetric)

| Condition | Persona | Allowed facts |
|-----------|---------|---------------|
| K-01 | SRE on-call | F-001…F-003 |
| K-02 | Product owner | F-010, F-011 |
| K-03 | Support lead | F-020, F-021 |

### `sample_event_policy.json` — `policy_change` (asymmetric)

| Condition | Persona | Allowed facts |
|-----------|---------|---------------|
| K-01 | HR policy lead | F-101…F-103 |
| K-02 | Engineering manager | F-110, F-111 |
| K-03 | Employee representative | F-120, F-121 |

`respondent_type` is `ai_persona`. The model must emit
`{"interrogative":"...","fact_refs":["F-###",...]}` with refs ⊆ the persona
pack (no silent full-pack fill). Validation failures return error codes only —
no paraphrased coaching.
