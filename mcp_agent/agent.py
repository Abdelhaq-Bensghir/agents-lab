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
SERVER = Path(__file__).resolve().parent.parent / "mcp_servers" / "bigquery" / "server.py"

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
    model="gemini-3.5-flash-lite",
    name="mcp_agent",
    description="Answers questions about BigQuery public data through a custom MCP server.",
    instruction=(
        "You are a data analyst. Data lives in the project 'bigquery-public-data'. "
        "Use list_tables and get_table_schema before writing a query with run_query. "
        "Select only the columns you need and always use LIMIT. "
        "If a query is refused, read the message and adjust the query."
    ),
    tools=[bigquery_mcp],
)