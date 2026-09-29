# Technical decisions

Each entry records a choice made in this project, the alternatives considered, and why. New decisions are added at the end; a decision that changes later is not deleted but marked as superseded.

---

## D1. uv instead of pip for dependency management

**Context:** the ADK quickstart uses `python -m venv` and `pip install`.

**Decision:** use [uv](https://docs.astral.sh/uv/) (`uv init`, `uv add`, `uv run`).

**Why:**
- Much faster installs than pip.
- One tool for the Python version, the virtual environment and the dependencies.
- `uv.lock` pins the exact version of every package, so anyone cloning the repo gets the same environment with `uv sync`.
- `uv run` runs commands inside the environment without activating it, which avoids PowerShell script-execution issues on Windows.

**Consequence:** commands in this repo are written as `uv run adk ...`.

---

## D2. One repository for all agents

**Context:** the project will contain several agents built over successive phases.

**Decision:** a single repository, with one folder per agent at the root.

**Why:**
- ADK is designed for this layout: `adk web` run from the root lists every agent folder.
- Agents share the same dependencies and configuration, managed once.
- The Git history and tags show the whole learning progression in one place.

**When to revisit:** if an agent becomes a standalone product with its own deployment cycle, it moves to its own repository.

---

## D3. Gemini Developer API (free tier) for local development, Vertex AI for deployment

**Context:** ADK can reach Gemini through two backends: the Gemini Developer API (authenticated with an AI Studio API key) or Vertex AI (authenticated with Google Cloud credentials, billed to a GCP project).

**Decision:** use the Gemini Developer API free tier while developing locally (phases 1 to 3), and switch to Vertex AI for deployment (phases 4 and 5).

**Why:**
- Local development involves a lot of trial and error; the free tier makes it cost nothing.
- Vertex AI is required for Agent Runtime and Gemini Enterprise, so it is used when it becomes necessary.
- Switching is a configuration change only (`GOOGLE_GENAI_USE_ENTERPRISE` in `.env`, which replaces the older `GOOGLE_GENAI_USE_VERTEXAI`); the agent code does not change.

**Trade-offs:**
- The free tier is rate-limited (requests per day and per minute).
- Free-tier content may be used by Google to improve its products, so only non-sensitive test data is used.

**Detail:** the API key is created in a free-tier project, separate from the billed GCP project, so it stays on the free tier.

---

## D4. `gemini-3.5-flash-lite` as the default model for local development

*Still valid for `my_agent` and `bq_agent` (free tier). For the deployed `mcp_agent`, superseded by [D11](#d11-gemini-25-flash-lite-in-europe-west1-for-the-deployed-agent).*

**Context:** several Gemini models are available on the free tier, with very different daily quotas.

**Decision:** use `gemini-3.5-flash-lite`.

**Why:**
- It is designed for high-volume agentic tasks.
- Its free daily quota is much larger than the more recent Flash models, which matters for agents: each question uses at least two model requests (one to choose a tool, one to write the answer).

**When to revisit:** if a task needs stronger reasoning than Flash-Lite provides.

---

## D5. Secrets kept out of Git

**Decision:** `.env` files are listed in `.gitignore`. Each agent has a committed `.env.example` with the variable names and placeholder values.

**Why:** the API key must never reach GitHub. `.env.example` documents what to configure without exposing anything.

---

## D6. A custom MCP server over stdio for the BigQuery tools

**Context:** phase 2 used ADK's built-in `BigQueryToolset`, where the tools live inside the agent process and only ADK can use them. Google also provides ready-made MCP servers for databases.

**Decision:** write a small MCP server in Python (`mcp_agent/bigquery_mcp_server.py`, moved into the agent folder in phase 4 so it is deployed with the agent) exposing three BigQuery tools, and connect the ADK agent to it with `McpToolset` over stdio.

**Why:**
- The tools become reusable: any MCP client (ADK, Claude Code, Gemini CLI, MCP Inspector) can use the same server.
- Writing the server, not just consuming one, is the goal of this phase: it shows how a tool is described, discovered and called over the protocol.
- stdio is the simplest transport: the agent starts the server as a subprocess, with no network port to open or secure.

**Trade-offs:** a hand-written server is less complete than the built-in toolset or a ready-made server. stdio only works when the client and server run on the same machine; a remote deployment would use an HTTP transport instead.

---

## D7. Cost and safety guardrails enforced in the MCP server

**Context:** the model writes the SQL. An instruction such as "always use LIMIT" is only a request to the model, and in BigQuery `LIMIT` does not even reduce the bytes scanned.

**Decision:** the server validates every query with a BigQuery dry run before running it. It refuses non-`SELECT` statements and queries estimated above 1 GB, sets `maximum_bytes_billed` as a second cap, and returns at most 100 rows. Refusals are returned as error messages, not raised as exceptions.

**Why:**
- Guardrails in the server apply to every client and every prompt; guardrails in an instruction depend on the model following them.
- The dry run is free and gives an exact estimate before any cost is incurred.
- Returned error messages let the model understand the refusal and propose a cheaper query.

**Evidence:** `SELECT * FROM bigquery-public-data.github_repos.commits LIMIT 10` was estimated at 910.6 GB and refused before running. The agent explained why and suggested selecting fewer columns.

---

## D8. Environment passed explicitly to the MCP server

**Context:** the MCP SDK starts a stdio server with only a minimal set of system environment variables, for security. `CLOUDSDK_CONFIG` (used locally to select a separate gcloud settings folder) is not in that set.

**Decision:** the agent builds the server's environment from `get_default_environment()` and adds only `CLOUDSDK_CONFIG` and `GOOGLE_CLOUD_PROJECT`.

**Why:** without it, the server would silently fall back to the default gcloud folder and use the wrong credentials. Passing only the two needed variables, not the whole environment, keeps the API key out of the server process (least privilege).

---

## D9. MCP Python SDK 2.x

**Context:** many tutorials use the 1.x API (`from mcp.server.fastmcp import FastMCP`). The installed SDK is 2.x, where `FastMCP` was renamed `MCPServer` (`from mcp.server.mcpserver import MCPServer`).

**Decision:** use the 2.x API rather than pinning `mcp<2`.

**Why:** 2.x is the version resolved alongside the installed ADK, and the current documentation targets it.

**Lesson:** the first version of the server used the 1.x import and crashed at startup. The agent did not report it: it simply received no tools, and Gemini answered with `MALFORMED_FUNCTION_CALL`. Testing the server alone (`scripts/test_mcp_server.py`) before connecting an agent makes this kind of failure visible immediately.

---

## D10. No personal identifiers in the repository

**Decision:** project IDs, account names and paths are read from environment variables (`.env`, never committed) or written as placeholders in the docs. Screenshots are checked before being committed.

**Why:** the repository is public. The code only contains variable names such as `GOOGLE_CLOUD_PROJECT`; the values stay on the machine that runs it.

---

## D11. `gemini-2.5-flash-lite` in `europe-west1` for the deployed agent

**Context:** the first deployment to Agent Runtime in `europe-west1` failed with `404 NOT_FOUND` for `gemini-3.5-flash-lite`. On Agent Runtime, the agent calls Gemini in the region where it runs. A small script (`scripts/check_model_availability.py`) tested four models in three locations on this project:

| Model | `global` | `us-central1` | `europe-west1` |
|---|---|---|---|
| `gemini-3.5-flash-lite` | OK | 404 | 404 |
| `gemini-3.5-flash` | OK | 404 | 404 |
| `gemini-3.1-flash-lite` | OK | 404 | 404 |
| `gemini-2.5-flash-lite` | OK | OK | OK |

The Gemini 3.x models were only available on the `global` endpoint.

**Options considered:**
- **3.x model on the `global` endpoint:** most recent models, same per-token price, but Google chooses where each request is processed. Data residency cannot be guaranteed, and organization policies restricting resource locations no longer apply to model calls.
- **`gemini-2.5-flash-lite` on a regional endpoint:** processing stays in a chosen region.

**Decision:** deploy to Agent Runtime in `europe-west1` (Belgium) with `gemini-2.5-flash-lite`, called through Vertex AI in the same region.

**Why:**
- Requests, agent and model stay in the EU, which is what a European company would require for its own data (GDPR, data residency).
- `gemini-2.5-flash-lite` is also about 5 times cheaper than `gemini-3.5-flash-lite` (around $0.10 / $0.40 per million input / output tokens, against $0.50 / $2.00).
- It passed the same three tests as the 3.x model: correct SQL on `usa_names`, the 910 GB query refused by the server guardrail, and an invalid column reported back to the user with the table schema.

**Trade-offs:**
- Older and less capable model; enough for three tools and simple SQL, to be revisited for more complex tasks.
- The model will be retired by Google at some point: check its discontinuation date and switch before it.
- The data itself (`bigquery-public-data`) is stored in the US; BigQuery runs each query where the data lives, and only the small result comes back to Europe. With real European data, the dataset would also be in the EU.

**Lesson:** the local test with the final configuration (same model, same region, Vertex AI) must pass before deploying. A local `adk web` run with the deployment's `.env` would have shown the same 404 in seconds.

---

## D12. Quota project set explicitly in the MCP server

**Context:** once deployed, every BigQuery call from the MCP server failed with `403: BigQuery API has not been used in project <number> before or it is disabled`, although the API was enabled in this project. The number was not this project's: it was the home project of the Google-managed service agent that Agent Runtime uses as its identity. Locally, the calls worked because the ADC file has a quota project set (`gcloud auth application-default set-quota-project`); the service agent's credentials have none, so API usage was attributed to Google's project.

**Decision:**
- In the server, `credentials.with_quota_project(PROJECT_ID)` makes every call count against this project.
- The service agent gets two roles on the project, and nothing more: `roles/bigquery.jobUser` (run queries) and `roles/serviceusage.serviceUsageConsumer` (use this project's enabled APIs as quota project). Public data is already readable by any authenticated identity.

**Also changed:** all three tools now catch BigQuery errors and return them as messages. In the first cloud tests, `list_tables` and `get_table_schema` raised exceptions, so the agent only saw "an error occurred"; the real cause was found in Cloud Logging. With errors returned, the agent reports the exact reason itself.

**Lesson:** code that works locally can fail in the cloud only because the identity differs. The deployed agent does not run as the developer: its identity only has the permissions and settings given to it explicitly.

---

## D13. Step-by-step instruction for a small model

**Context:** with `gemini-2.5-flash-lite` (D11), the deployed agent sometimes guessed table names, asked the user to choose between tables, and, worse, answered without calling any tool, for example stating that an existing table did not exist.

**Decision:** rewrite the instruction as explicit steps and rules: list the tables before querying and never guess a name; pick the table without asking for confirmation; run SQL given by the user as is; only state facts that come from a tool call made for the current message; retry once after an error; explain cost refusals.

**Result:** the natural-language question and the 910 GB query now go through the tools every time they were tested, and false statements stopped. One known limitation remains: for `SELECT prenom FROM ...` asked after the schema had already been read in the same session, the model answered correctly from that earlier schema without running the query.

**Why not a bigger model right away:** the instruction costs nothing and fixed most of the problem. A stronger model (`gemini-2.5-flash`) remains the next option if reliability matters more than cost.

**Next step:** measure reliability instead of judging from a few manual runs, with ADK's evaluation tooling (the same questions run many times, success rate counted).