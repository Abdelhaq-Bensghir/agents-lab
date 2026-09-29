"""MCP server exposing read-only, cost-guarded BigQuery tools."""
import json
import os

import google.auth
from google.api_core.exceptions import GoogleAPIError
from google.cloud import bigquery
from mcp.server.mcpserver import MCPServer

# Credentials and default project come from ADC: the personal ADC file locally,
# the metadata server on Agent Runtime. GOOGLE_CLOUD_PROJECT overrides the project if set.
credentials, default_project = google.auth.default()
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or default_project

# Count API usage and quota against our project. Without this, on Agent Runtime the calls
# are attributed to the home project of Google's service agent, where BigQuery is disabled.
credentials = credentials.with_quota_project(PROJECT_ID)

MAX_BYTES = 1_000_000_000  # Refuse any query that would scan more than 1 GB
MAX_ROWS = 100             # Never send more than 100 rows back to the model

mcp = MCPServer("bigquery-readonly")
client = bigquery.Client(project=PROJECT_ID, credentials=credentials)


def _error(error: GoogleAPIError) -> dict:
    """Turn a BigQuery error into a message the model can read and act on."""
    return {"status": "error", "message": str(error)}


@mcp.tool()
def list_tables(dataset: str) -> dict:
    """List the tables of a BigQuery dataset, e.g. 'bigquery-public-data.usa_names'."""
    try:
        tables = [table.table_id for table in client.list_tables(dataset)]
    except GoogleAPIError as error:
        return _error(error)
    return {"status": "success", "tables": tables}


@mcp.tool()
def get_table_schema(table: str) -> dict:
    """Return the column names and types of a table,
    e.g. 'bigquery-public-data.usa_names.usa_1910_current'."""
    try:
        schema = client.get_table(table).schema
    except GoogleAPIError as error:
        return _error(error)
    return {"status": "success", "columns": [{"name": f.name, "type": f.field_type} for f in schema]}


@mcp.tool()
def run_query(sql: str) -> dict:
    """Run a read-only SQL SELECT query and return at most 100 rows.
    Queries that would scan more than 1 GB are refused."""
    try:
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
    except GoogleAPIError as error:
        # Invalid SQL, unknown table, permission denied...: send the reason back to the model
        return _error(error)

    # Dates and decimals are not JSON-serializable: convert them to text
    rows = json.loads(json.dumps(rows, default=str))
    return {"status": "success", "bytes_scanned": dry.total_bytes_processed, "rows": rows}


if __name__ == "__main__":
    mcp.run(transport="stdio")  # The server talks to the agent over standard input/output