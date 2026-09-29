import os
import sys
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from mcp.client.stdio import get_default_environment

if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set. Add it to mcp_agent/.env")

# Path to the server, computed from this file's location (works on any machine)
SERVER = Path(__file__).resolve().parent / "bigquery_mcp_server.py"

# The server is a child process. For security, MCP only passes it a minimal set of
# environment variables by default, so we explicitly add the two it needs.
server_env = get_default_environment()
for name in ("CLOUDSDK_CONFIG", "GOOGLE_CLOUD_PROJECT"):
    if name in os.environ:
        server_env[name] = os.environ[name]

bigquery_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,  # The same Python as the agent (the project's .venv)
            args=[str(SERVER)],
            env=server_env,
        ),
        timeout=30,  # Seconds; BigQuery calls can take a few seconds
    ),
)

root_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="mcp_agent",
    description="Answers questions about BigQuery public data through a custom MCP server.",
    instruction=(
        "You are a data analyst answering questions with BigQuery public data. "
        "Public datasets live in the project 'bigquery-public-data': for example, "
        "the dataset 'usa_names' is 'bigquery-public-data.usa_names'.\n\n"
        "For a question in natural language, follow these steps without asking "
        "the user for confirmation:\n"
        "1. Call list_tables on the dataset. Never guess a table name.\n"
        "2. Pick the table that best covers the question, for example the one "
        "whose name covers the requested years, or the most recent one.\n"
        "3. Call get_table_schema on that table.\n"
        "4. Write one SELECT query with only the columns you need, and run it with run_query.\n"
        "5. Answer the question with the result.\n\n"
        "When the user gives a SQL query, run it as is with run_query, without steps 1 to 3.\n\n"
        "Rules:\n"
        "- Only state facts that come from a tool call made for the current message: "
        "never say from memory or from earlier messages that a table or column exists, "
        "and never invent a query result or an error.\n"
        "- If a tool returns an error, read the message, fix the call and try once more; "
        "if it still fails, explain the error to the user.\n"
        "- If run_query refuses a query because of its cost, explain why and suggest a cheaper query.\n"
        "- Only ask the user a question if the request is still ambiguous after these steps."
    ),
    tools=[bigquery_mcp],
)