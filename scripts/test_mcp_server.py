"""Test the BigQuery MCP server alone, without ADK or Gemini.

Run from the repo root, in personal mode:
    gperso
    set -a; source mcp_agent/.env; set +a
    uv run python scripts/test_mcp_server.py
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

SERVER = Path(__file__).resolve().parent.parent / "mcp_servers" / "bigquery" / "server.py"


async def main():
    # Same environment as the agent gives the server
    env = get_default_environment()
    for name in ("CLOUDSDK_CONFIG", "GOOGLE_CLOUD_PROJECT"):
        if name in os.environ:
            env[name] = os.environ[name]
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)

    async with stdio_client(params) as (read, write):   # 1. Start the server process
        async with ClientSession(read, write) as session:
            await session.initialize()                   # 2. MCP handshake
            tools = await session.list_tools()           # 3. What the agent should send to Gemini
            print("Tools:", [tool.name for tool in tools.tools])
            result = await session.call_tool(            # 4. One real call
                "list_tables", {"dataset": "bigquery-public-data.usa_names"}
            )
            print("list_tables:", result.content)


asyncio.run(main())