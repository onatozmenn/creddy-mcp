---
title: Creddy
emoji: 📊
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

<p align="center">
  <img src="creedymcplogo.png" alt="Creddy logo" width="160" />
</p>

# Creddy

[![Smithery](https://img.shields.io/badge/Smithery-listed-ea580c)](https://smithery.ai/server/onatozmen44/creddy-mcp)
[![GitHub](https://img.shields.io/badge/GitHub-source-181717?logo=github)](https://github.com/onatozmenn/creddy-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20HTTP-2563eb)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)

**A credit-risk analytics MCP server for Claude & ChatGPT.**
Ask questions in plain language → it writes **safe, read-only SQL** over **30,000 real labeled
credit records**, scores **default risk** with an interpretable model, and pulls **live data
from Turkey's Central Bank (TCMB)** — all over the Model Context Protocol.

> ⚠️ **Disclaimer:** This is an educational / portfolio project. The labeled data is the public
> UCI "Default of Credit Card Clients" dataset (Taiwan, 2005). It is **not** a real lending
> system and must not be used for actual credit decisions.

## 💬 Example questions

Ask your assistant:

- *"What's the default rate by education level?"* → `run_query`
- *"24 years old, credit limit 20k, 2-month delay in September — will this client default?"* → `predict_default`
- *"How good is the risk model (AUC, recall)?"* → `model_metrics`
- *"Do clients with higher credit limits default less?"* → `run_query`
- *"What are the current USD, EUR and gold prices?"* → `tcmb_indicators` *(live TCMB)*
- *"Find TCMB series about credit-card spending."* → `tcmb_search` *(live TCMB)*
- *"Which columns are in the data?"* → `describe_schema`

Answers come from **real, labeled data** and an **actually trained model** — not guesses.

## 👥 Who is it for?

| Role | Start with | Why |
| --- | --- | --- |
| **Risk analyst** | `predict_default` · `model_metrics` | Score a borrower and see the signed drivers behind the decision |
| **Data scientist** | `run_query` · `describe_schema` | Explore 30k labeled records with safe SQL, no write risk |
| **BNPL / credit ops** | `tcmb_indicators` · `tcmb_search` | Live Turkish macro context (rates, FX, card spending) for underwriting |

## 🧰 Tools (9)

| Tool | What it does |
| --- | --- |
| `list_tables` | List database tables |
| `describe_schema` | Columns + types, to ground SQL generation |
| `run_query` | Validate + execute a read-only `SELECT` over `credit_clients` |
| `predict_default` | Predict a client's default probability + top risk factors |
| `model_metrics` | The trained model's AUC / precision / recall and key drivers |
| `tcmb_indicators` | **Live** headline Turkish indicators (USD, EUR, gold, rates, ...) — no key |
| `tcmb_search` | Search the TCMB EVDS catalog for series by name (key-authenticated) |
| `tcmb_series` | A specific EVDS time series via the public REST API (key + current endpoint) |
| `example_questions` | Suggested questions |

## 🚀 Connect it (no install)

The server is **live** (Hugging Face Spaces) — most people need zero setup. Pick your client:

### ChatGPT

1. ChatGPT → **Settings → Connectors → Advanced → Developer mode** (enable).
2. **Add connector** and enter the MCP URL:
   ```
   https://onatozmenn-creddy-mcp.hf.space/mcp
   ```
3. Save. Now ask *"What's the default rate by education level?"* in chat.

> Custom MCP tools only appear on accounts with **Developer mode** enabled.

### Claude Desktop

Add to `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json` ·
macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "creddy": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://onatozmenn-creddy-mcp.hf.space/mcp"]
    }
  }
}
```

Restart Claude Desktop; the tools show up in the 🔨 menu. *(Requires Node.js for `npx`.)*

### Claude.ai (web)

On Pro / Max / Team (and Free — one connector) you can connect a remote MCP directly:

1. **[Settings → Connectors](https://claude.ai/settings/connectors)** → **Add custom connector**.
2. Enter the MCP URL (leave OAuth fields empty — the server needs no auth):
   ```
   https://onatozmenn-creddy-mcp.hf.space/mcp
   ```
3. **Add**, then enable Creddy from the **"+" → Connectors** menu in a chat.

### Smithery (one command)

```
npx -y @smithery/cli install onatozmen44/creddy-mcp --client claude
```

### VS Code / Cursor

VS Code — `.vscode/mcp.json`:

```json
{ "servers": { "creddy": { "type": "http", "url": "https://onatozmenn-creddy-mcp.hf.space/mcp" } } }
```

Cursor — `.cursor/mcp.json` (note the `mcpServers` key):

```json
{ "mcpServers": { "creddy": { "url": "https://onatozmenn-creddy-mcp.hf.space/mcp" } } }
```

## Architecture

```mermaid
flowchart LR
    User([User]) -- "natural language" --> Client["Claude / ChatGPT / IDE"]
    Client -- "MCP (stdio or HTTP)" --> Server["Creddy MCP server (FastMCP)"]
    Server -- "run_query" --> Guard["SQL guard (sqlglot)"]
    Guard --> DB[("Postgres (read-only)\nreal credit_clients")]
    Server -- "predict_default / model_metrics" --> Model[["Risk model (scikit-learn)"]]
    Server -- "tcmb_indicators / tcmb_search / tcmb_series" --> EVDS[["TCMB EVDS (live)"]]
    DB --> Server
    Model --> Server
    EVDS --> Server
    Server -- "results" --> Client --> User
```

Two independent safety layers protect the database: the **SQL guard** (`sqlglot` — SELECT-only,
single statement, row cap) **and** a **read-only DB session**. Model-generated SQL is never
trusted blindly.

## Real data sources

| Source | What | Access |
| --- | --- | --- |
| **UCI Credit Default** | 30,000 real clients, real repayment history, **real default label** (~22%) | Free, no key ([UCI #350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients)) |
| **TCMB EVDS** | **Live** Turkish indicators: USD/EUR, gold, deposit & loan rates, reserves, M3, inflation | No key for indicators; free key for catalog search |

## Risk model

`creddy train-model` trains an **interpretable logistic-regression** pipeline (standardize
numerics + one-hot encode categoricals) on the real data with an 80/20 split. It reports
**AUC, accuracy, precision, recall, F1, KS**, picks the decision threshold with **Youden's J**,
and saves the model. Every `predict_default` returns the probability, a risk band, and the
**signed top factors** behind that specific decision — explainable, adverse-action friendly.

Current hold-out performance: **AUC ≈ 0.71**, KS ≈ 0.37. A low-risk profile scores ~12% and a
high-risk profile ~58% (base rate ≈ 22%) — meaningful scores, not just rankings.

---

## 🛠️ Run locally

Prerequisites: **Python 3.10+** and **Docker**.

```powershell
docker compose up -d                 # local Postgres
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
creddy setup                         # schema + real data + trained model
creddy serve                         # stdio  (or: creddy serve --http)
python eval/run_eval.py ; pytest     # 12/12 eval, 24 tests
```

### CLI

```
creddy init-db | load-data [--limit N] | train-model | setup | serve [--http --host H --port P]
```

## ☁️ Self-host for free (Hugging Face + Neon)

1. **Managed Postgres:** create a free serverless DB on [Neon](https://neon.tech) or
   [Supabase](https://supabase.com); note host / db / user / password.
2. **Hugging Face Space:** create a **Docker** Space and push this repo (it ships a
   [`Dockerfile`](Dockerfile) + [`docker-entrypoint.sh`](docker-entrypoint.sh)). Add the DB as
   Space **secrets**:
   ```
   CREDDY_DB_HOST, CREDDY_DB_PORT, CREDDY_DB_NAME, CREDDY_DB_USER, CREDDY_DB_PASSWORD
   CREDDY_DB_SSLMODE=require        # Neon / Supabase require SSL
   CREDDY_TCMB_API_KEY             # optional
   ```
   On first boot the container bootstraps (schema + data + model) and serves at
   `https://<user>-<space>.hf.space/mcp`.
3. **Keep it awake (optional):** a GitHub Actions workflow
   ([`.github/workflows/keepalive.yml`](.github/workflows/keepalive.yml)) pings the server every
   30 minutes — set a repo secret `MCP_URL` to your `/mcp` URL.

## Data model (`credit_clients`)

Monetary columns are in **NT$**; `pay_*` are repayment-status codes per month
(`-1/0` = paid duly, `>=1` = months of delay); `defaulted` is the label.

```
client_id, credit_limit, sex, education, marriage, age,
pay_sep..pay_apr,          -- repayment status (6 months)
bill_sep..bill_apr,        -- bill statement amounts
pay_amt_sep..pay_amt_apr,  -- amounts paid
defaulted                  -- TRUE = defaulted next month
```

## Project layout

```
sql/schema.sql              # Postgres DDL
src/creddy/
  config.py  db.py  sql_guard.py
  data_loader.py            # loads the real UCI dataset (ucimlrepo)
  risk_model.py             # trains + serves the default-risk model (scikit-learn)
  tcmb.py                   # live TCMB EVDS client
  server.py  cli.py
eval/                       # golden SQL + evaluation harness
tests/                      # unit tests (no DB / no network required)
Dockerfile, docker-entrypoint.sh   # container image for hosting
```

## Design decisions

- **Real, labeled data over synthetic** — labels come from the source, so the risk story is genuine.
- **Interpretable model on purpose** — signed per-decision factors (explainable scoring) over a marginally higher AUC.
- **Guard before LLM trust** — AST inspection blocks DML/DDL, statement stacking and `COPY`/`SET`; the DB session is independently read-only.
- **Eval as a first-class artifact** — `eval/` turns "does the SQL layer work?" into a measurable, CI-friendly pass rate.

## Security

- Read-only `SELECT` only, enforced at two layers (parser + DB session); per-query row cap.
- Secrets (DB password, TCMB key) come from the environment, never hard-coded.
- The UCI data is public and anonymized — no real PII.

## Honest note on `tcmb_series`

TCMB is migrating EVDS2 → EVDS3. The live `tcmb_indicators` and key-authenticated `tcmb_search`
tools work today; the documented key-based public REST service that `tcmb_series` targets is
currently offline behind that migration. Set `CREDDY_TCMB_BASE_URL` to the current endpoint once
it is republished.

## License

[MIT](LICENSE)
