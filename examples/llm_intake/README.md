# LLM intake example

Offline-first ICP consumer: each AI persona gets one event fact pack, emits
exactly one interrogative, and middleware validates (retry ≤3 with error codes
only). Accepted records go through blind export + steward coding key.

## Mock (default — no API key)

From the repo root (after `pip install -e .` or with `src` on `PYTHONPATH`):

```bash
python examples/llm_intake/run.py --mock
```

Writes:

- `examples/llm_intake/out/records.json`
- `examples/llm_intake/out/analysis_packet.json`
- `examples/llm_intake/out/coding_key.json` (**steward-only** — do not share with blind reviewers)

## Live (optional OpenAI-compatible HTTP)

Uses stdlib `urllib` only (no `openai` / `httpx` package required).

```bash
set OPENAI_API_KEY=sk-...
set OPENAI_BASE_URL=https://api.openai.com
set OPENAI_MODEL=gpt-4o-mini
python examples/llm_intake/run.py --live
```

| Env | Default | Purpose |
|-----|---------|---------|
| `OPENAI_API_KEY` | _(required for `--live`)_ | Bearer token |
| `OPENAI_BASE_URL` | `https://api.openai.com` | Host root (`/v1/chat/completions` appended) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model id |

Any OpenAI-compatible Chat Completions endpoint works (local gateways, Azure
proxies with a compatible path, etc.).

## Sample event

`sample_event.json` is a `technical_incident` outage with **asymmetric** role
packs:

| Condition | Persona | Allowed facts |
|-----------|---------|---------------|
| K-01 | SRE on-call | F-001…F-003 |
| K-02 | Product owner | F-010, F-011 |
| K-03 | Support lead | F-020, F-021 |

`respondent_type` is `ai_persona`. Validation failures are returned to the
model as error codes only — no paraphrased coaching.
