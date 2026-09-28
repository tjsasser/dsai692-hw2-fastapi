import json
import pathlib
import subprocess
import sys

import pandas as pd
from streamlit.testing.v1 import AppTest

import hw2
from user_definition import (bucket_name, file_name_prefix, project_id,
                             service_account_file_path)


def test_retrieve_data_from_gcs():
    """
    This is a live integration test -- it reads real blobs from GCS using
    the credentials in your .env, so it depends on HW2's
    test_search_and_save_jobs_success having run at least once (or any
    other successful call to /search_and_save/jobs) so there's at least
    one blob under file_name_prefix to read.
    """
    output = hw2.retrieve_data_from_gcs(service_account_file_path,
                                        project_id,
                                        bucket_name,
                                        file_name_prefix)
    assert "results" in output
    assert "job_titles" in output
    assert "company_dict" in output
    assert isinstance(output["results"], list)
    assert len(output["results"]) > 0


def test_dashboard_renders():
    """
    UI test against the *actual* running app -- requires at least one
    successful /search_and_save/jobs call to have happened already (run
    fastapi/test_hw2_api.py, or call_fast_api.py, first).
    """
    at = AppTest.from_file("hw2.py").run()

    assert at.title[0].value.endswith("Job Listings")
    assert len(at.sidebar.checkbox) > 0
    # all checked by default
    assert all(cb.value for cb in at.sidebar.checkbox)

    df = at.dataframe[0].value
    assert set(df.columns) == {"date", "title", "link"}
    assert df["link"].is_unique

    columns_config = json.loads(at.dataframe[0].proto.columns)
    assert columns_config.get("link", {}).get(
        "type_config", {}).get("type") == "link"


def test_hw2_streamlit_pep8():
    """Ensure code passes pycodestyle with fewer than 5 issues."""
    target = pathlib.Path(__file__).with_name("hw2.py")
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