from user_definition import *
from pydantic import BaseModel
from google.cloud import storage
from google.oauth2 import service_account
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.protobuf.json_format import MessageToDict

from fastapi.responses import JSONResponse
from fastapi import FastAPI
import json
import datetime
import re


app = FastAPI()


class SearchModel(BaseModel):
    # Query parameters for '/search_and_save/jobs'
    job_title: str
    no_days_to_search: int = 1
    company_dict: dict

# Creates basis for google query parameters


class GoogleSearch(BaseModel):
    vertex_ai_project_id: str
    search_engine_id: str
    job_title: str
    company_dictionary: dict
    service_account_key: str
    location: str = "global"  # Values: "global", "us", "eu", etc.


class GcsStringUpload(BaseModel):
    service_account_key: str
    gcp_project_id: str
    bucket_name: str
    file_name: str
    data: str


def parse_google_search_results(search_results: dict, job_list: list) -> None:
    for job in search_results:
        # this pulls the relevant section of json
        job_data = job["document"]["derivedStructData"]

        if job_data.get("snippet"):
            snippet = job_data.get("snippet")
        else:
            snippet = ""

        # Look for post times in days in the snippet data
        match = re.search(r"(\d+)\s+days?\s+ago", snippet, re.IGNORECASE)

        # Add the parts to the list.
        job_list.append(
            {
                "title": job_data.get("title"),
                "link": job_data.get("link"),
                "snippet": job_data.get("snippet"),
                "date": datetime.date.today().isoformat()
            }
        )


def call_google_search(search_param: GoogleSearch):

    api_endpoint = f"{search_param.location}-discoveryengine.googleapis.com"

    client_options = (
        ClientOptions(api_endpoint=api_endpoint)
        if search_param.location != "global"
        else None
    )

    # Build credentials
    credentials = service_account.Credentials.from_service_account_file(
        search_param.service_account_key)

    # Build a discoveryengine.SearchServiceClient with credentials.
    client = discoveryengine.SearchServiceClient(
        client_options=client_options, credentials=credentials)

    serving_config = (
        f"projects/{search_param.vertex_ai_project_id}/"
        f"locations/{search_param.location}/"
        "collections/default_collection/"
        f"engines/{search_param.search_engine_id}/"
        "servingConfigs/default_config"
    )

    try:
        company_links = search_param.company_dictionary.values()

        site_restrict = "(" + " OR ".join(f"site:{url}"
                                          for url in company_links) + ")"

        SpellCorrectionSpec = discoveryengine.SearchRequest.SpellCorrectionSpec
        spell_correction_spec = SpellCorrectionSpec(
            mode=SpellCorrectionSpec.Mode.AUTO
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=f"{search_param.job_title} {site_restrict}",
            page_size=10,
            spell_correction_spec=spell_correction_spec,
        )

        response = client.search(request)

        results = [MessageToDict(result._pb) for result in response]

        job_list = []

        parse_google_search_results(results, job_list)

        return {
            "company_dict": search_param.company_dictionary,
            "job_title": search_param.job_title,
            "results": results,
            "job_list": job_list
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": str(e)})


def save_to_gcs(gcs_upload_param: GcsStringUpload):
    credentials = service_account.Credentials.from_service_account_file(
        gcs_upload_param.service_account_key)

    client = storage.Client(project=gcs_upload_param.gcp_project_id,
                            credentials=credentials)
    bucket = client.bucket(gcs_upload_param.bucket_name)
    blob = bucket.blob(gcs_upload_param.file_name)
    blob.upload_from_string(gcs_upload_param.data)
    return {"message": f"Uploaded to {gcs_upload_param.bucket_name}/{gcs_upload_param.file_name}"}


@app.post("/search_and_save/jobs")
def search_and_save_jobs(search_input: SearchModel):
    search_param = GoogleSearch(
        vertex_ai_project_id=vertex_ai_project_id,
        search_engine_id=search_engine_id,
        job_title=search_input.job_title,
        company_dictionary=search_input.company_dict,
        service_account_key=service_account_file_path,
    )

    try:
        result = call_google_search(search_param)
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

    if isinstance(result, JSONResponse):
        return result

    cutoff_date = datetime.date.today() - datetime.timedelta(days=search_input.no_days_to_search)

    recent_jobs = []
    for job in result["job_list"]:
        if datetime.date.fromisoformat(job["date"]) >= cutoff_date:
            recent_jobs.append(job)

    gcs_param = GcsStringUpload(
        service_account_key=service_account_file_path,
        gcp_project_id=project_id,
        bucket_name=bucket_name,
        file_name=f"{file_name_prefix}/{datetime.date.today()}.json",
        data=json.dumps({
            "results": recent_jobs,
            "job_title": search_input.job_title,
            "company_dict": search_input.company_dict
        })
    )

    return save_to_gcs(gcs_param)
