"""MCP server exposing read-only, cost-guarded BigQuery tools."""
import json
import os

from google.cloud import bigquery
from mcp.server.mcpserver import MCPServer

# Billing project, read from the environment (never hard-coded)
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
MAX_BYTES = 1_000_000_000  # Refuse any query that would scan more than 1 GB
MAX_ROWS = 100             # Never send more than 100 rows back to the model

mcp = MCPServer("bigquery-readonly") # MCP Server creation
client = bigquery.Client(project=PROJECT_ID)  # Credentials found through ADC

# MCP tools the model can call

@mcp.tool()
def list_tables(dataset: str) -> list[str]:
    """List the tables of a BigQuery dataset, e.g. 'bigquery-public-data.usa_names'."""
    return [table.table_id for table in client.list_tables(dataset)]


@mcp.tool()
def get_table_schema(table: str) -> list[dict]:
    """Return the column names and types of a table,
    e.g. 'bigquery-public-data.usa_names.usa_1910_current'."""
    return [{"name": f.name, "type": f.field_type} for f in client.get_table(table).schema]


@mcp.tool()
def run_query(sql: str) -> dict:
    """Run a read-only SQL SELECT query and return at most 100 rows.
    Queries that would scan more than 1 GB are refused."""
    # 1. Dry run: BigQuery validates the query and estimates its cost, without running it
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    if dry.statement_type != "SELECT":
        return {"status": "error", "message": "Only SELECT queries are allowed."}
    if dry.total_bytes_processed > MAX_BYTES:
        gb = dry.total_bytes_processed / 1e9
        return {"status": "error",
                "message": f"Query would scan {gb:.1f} GB (limit 1 GB). Select fewer columns or filter more."}

    # 2. Real run, with a hard billing cap as a second safety net
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
    rows = [dict(row) for row in job.result(max_results=MAX_ROWS)]
    # Dates and decimals are not JSON-serializable: convert them to text
    rows = json.loads(json.dumps(rows, default=str))
    return {"status": "success", "bytes_scanned": dry.total_bytes_processed, "rows": rows}


if __name__ == "__main__":
    mcp.run(transport="stdio") # the server communicates with the agent in standard input/output