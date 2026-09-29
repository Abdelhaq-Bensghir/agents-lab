import os
import google.auth
from google.adk.agents import Agent
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

# Project where queries run and are billed. Read from bq_agent/.env
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set. Add it to bq_agent/.env")

# 1. Safety: the agent can read data but never modify or delete anything
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

# 2. Credentials: found automatically through ADC (your personal account)
credentials, _ = google.auth.default()
credentials_config = BigQueryCredentialsConfig(credentials=credentials)

# 3. The toolset: a ready-made bundle of BigQuery tools
bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    bigquery_tool_config=tool_config,
)

root_agent = Agent(
    model="gemini-3.5-flash-lite",
    name="bigquery_agent",
    description="Answers questions about BigQuery public data by running SQL queries.",
    instruction=(
        "You are a data analyst. Answer questions using BigQuery. "
        "Data lives in the project 'bigquery-public-data'. "
        f"Always run queries in the project '{PROJECT_ID}'. "
        "Before querying a table, inspect its schema. "
        "Select only the columns you need and always use LIMIT."
    ),
    tools=[bigquery_toolset],
)