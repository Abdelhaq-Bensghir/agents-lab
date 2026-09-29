"""Check which Gemini models answer in which Vertex AI locations for a project.

Run from the repo root, in personal mode:
    gperso
    set -a; source mcp_agent/.env; set +a   # loads GOOGLE_CLOUD_PROJECT
    uv run python scripts/check_model_availability.py

Each OK or error is one tiny model call (a few tokens), billed to the project.
"""
import os

from google import genai

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
LOCATIONS = ["global", "us-central1", "europe-west1"]

for model in MODELS:
    for location in LOCATIONS:
        client = genai.Client(vertexai=True, project=PROJECT, location=location)
        try:
            client.models.generate_content(model=model, contents="Reply with OK")
            result = "OK"
        except Exception as error:
            result = f"error {getattr(error, 'code', '?')}"
        print(f"{model:25} {location:14} {result}")