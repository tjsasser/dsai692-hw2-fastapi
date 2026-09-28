"""
A small client script to trigger the /search_and_save/jobs endpoint on
your running FastAPI service. Run this after the fastapi code is running,
and before running the Streamlit app.
This search and store data in GCS for the dashboard to read.

Usage:
    python call_fast_api.py
"""
import requests

api_server_url = "http://127.0.0.1:8000"

data = {
    "job_title": "Data Engineer",
    "company_dict": {"Anthropic": "anthropic.com/careers/jobs",
                     "Google": "www.google.com/about/"
                     "careers/applications/jobs",
                     "OpenAI": "openai.com/careers"}
}

response = requests.post(f"{api_server_url}/search_and_save/jobs", json=data)
print(response.status_code)
print(response.json())
