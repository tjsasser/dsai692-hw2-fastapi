import datetime
import json
import pathlib
import subprocess
import sys

from fastapi.testclient import TestClient
from google.api_core.exceptions import GoogleAPIError
from google.oauth2 import service_account
from google.cloud import storage

from extract_save_data import app
from user_definition import (bucket_name,
                             file_name_prefix,
                             project_id,
                             service_account_file_path)

company_dictionary = {
    "Google": "https://www.google.com/about/careers/applications/jobs",
    "OpenAI": "https://openai.com/careers",
    "Anthropic": "anthropic.com/careers/jobs"
}

client = TestClient(app)


def _gcs_bucket():
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file_path)
    gcs_client = storage.Client(project=project_id, credentials=credentials)
    return gcs_client.bucket(bucket_name)


def test_search_and_save_jobs_success():
    """
    This makes a Vertex AICustom Search call and
    write to GCS using the credentials in your .env.
    To pass the test, you should have all mentioned environment variables
    in user_definition.py
    """
    bucket = _gcs_bucket()
    file_name = f"{file_name_prefix}/{datetime.date.today()}.json"
    try:
        blob = bucket.blob(file_name)
        if blob.exists():
            blob.delete()
    except GoogleAPIError as e:
        print(f"Could not clear {file_name} before the test (may be under "
              f"a retention hold) -- continuing anyway: {e}")

    data = {
        "job_title": "Data Engineer",
        "company_dict": company_dictionary,
    }
    response = client.post("/search_and_save/jobs", json=data)
    assert response.status_code == 200

    body = response.json()
    assert "message" in body

    # Confirm the blob actually landed in GCS with the expected shape.
    blob = bucket.blob(file_name)
    assert blob.exists()
    saved = json.loads(blob.download_as_bytes())
    assert "company_dict" in saved
    assert "job_title" in saved
    assert "results" in saved
    assert isinstance(saved["results"], list)
    assert all("title" in job and "link" in job and "date" in job
               for job in saved["results"])
    assert saved["company_dict"] == company_dictionary
    assert saved["job_title"] == "Data Engineer"


def test_search_and_save_jobs_bad_search_engine_returns_500(monkeypatch):
    """An invalid SEARCH_ENGINE_ID should surface as a 500 with a
    message, not an unhandled exception."""
    import extract_save_data
    monkeypatch.setattr(extract_save_data, "search_engine_id",
                        "this-search-engine-does-not-exist")

    data = {
        "job_title": "Data Engineer",
        "company_dict": company_dictionary,
    }
    response = client.post("/search_and_save/jobs", json=data)
    assert response.status_code == 500
    assert "message" in response.json()


def test_hw2_api_pep8():
    """Ensure code passes pycodestyle with fewer than 5 issues."""
    target = pathlib.Path(__file__).with_name("extract_save_data.py")
    assert target.is_file(), f"{target.name} does not exist at {target}"
    result = subprocess.run(
        [sys.executable, "-m", "pycodestyle", str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1) and not result.stderr.strip(), (
        f"pycodestyle did not run (exit {result.returncode}):\n"
        f"{result.stderr.strip()}")

    errors = result.stdout.strip().splitlines()
    assert (result.returncode == 0) == (not errors), (
        f"Unexpected pycodestyle output (exit {result.returncode}):\n"
        f"{result.stdout.strip()}")
    assert len(errors) < 5, f"Too many PEP8 issues:\n{errors}"
