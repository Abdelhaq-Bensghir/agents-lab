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

## D4. `gemini-3.5-flash-lite` as the default model

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

**Decision:** write a small MCP server in Python (`mcp_servers/bigquery/server.py`) exposing three BigQuery tools, and connect the ADK agent to it with `McpToolset` over stdio.

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

**Context:** the MCP SDK starts a stdio server with only a minimal set of system environment variables, for security. `CLOUDSDK_CONFIG` (which selects the personal gcloud settings folder, see [local-setup.md](local-setup.md)) is not in that set.

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