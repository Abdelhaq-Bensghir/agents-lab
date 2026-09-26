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