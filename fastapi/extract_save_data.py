import json
import datetime
import re

from fastapi.responses import JSONResponse
from fastapi import FastAPI

from google.cloud import storage
from google.oauth2 import service_account
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.protobuf.json_format import MessageToDict

from pydantic import BaseModel

from user_definition import *

app = FastAPI()


class SearchModel(BaseModel):
    # Query parameters for '/search_and_save/jobs'
    job_title: str
    company_dict: dict


class GoogleSearch(BaseModel):
    vertex_ai_project_id: str
    search_engine_id: str
    job_title: str
    company_dictionary: dict
    service_account_key: str
    location: str = "global"  # Values: "global", "us", "eu"


class GcsStringUpload(BaseModel):
    service_account_key: str
    gcp_project_id: str
    bucket_name: str
    file_name: str
    data: str


def parse_google_search_results(search_results: dict,
                                job_list: list) -> None:
    """
    Extend job_list to be a list of dictionaries.
    Each dictionary should include title, link, snippet and date.
    title, link, and snippet are from search_results' "derivedStructData".
    date is based on the snippet's "xx days ago" -- use the current date
    and xx days to calculate an actual date.

    Args:
        search_results (dict): a list of raw search result documents.
        job_list (list): a list of dictionaries with title, link,
                         snippet and date. Extended in place.
    """
    for job in search_results:
        info = job["document"]["derivedStructData"]
        title = info["title"]
        link = info["link"]
        snippet = info["snippets"][0]["snippet"]
        day_diff_match = re.search(r"(\d+)\s*days?\s*ago", snippet.lower())
        day_diff = int(day_diff_match.group(1)) if day_diff_match else 0
        date = datetime.date.today() - datetime.timedelta(days=day_diff)
        job_list.append({"title": title,
                         "link": link,
                         "snippet": snippet,
                         "date": date.strftime('%Y-%m-%d')})


def call_google_search(search_param: GoogleSearch):
    """
    Use Vertex AI Search (Discovery Engine) to search for job postings
    restricted to the sites in search_param.company_dictionary, and
    return them as a plain dict shaped like:
    {"company_dict": ..., "job_title": ..., "results": [...]}.
    On failure, returns a JSONResponse with status_code=500 instead --
    callers must check for that before treating the return value as data.
    """
    api_endpoint = f"{search_param.location}-discoveryengine.googleapis.com"
    client_options = (
        ClientOptions(api_endpoint=api_endpoint)
        if search_param.location != "global"
        else None
    )

    credentials = service_account.Credentials.from_service_account_file(
        search_param.service_account_key
    )
    client = discoveryengine.SearchServiceClient(
        client_options=client_options,
        credentials=credentials)

    serving_config = (
        f"projects/{search_param.vertex_ai_project_id}/"
        f"locations/{search_param.location}/"
        "collections/default_collection/"
        f"engines/{search_param.search_engine_id}/"
        "servingConfigs/default_config"
    )
    try:
        # Restrict results to the sites in company_dictionary using
        # (site:url1 OR site:url2 OR ...) search-operator syntax.
        company_links = search_param.company_dictionary.values()
        site_list = [f"site:{link} " for link in company_links]
        site_list_str = " OR ".join(site_list)
        site_restrict = f"({site_list_str})"
        SpellCorrectionSpec = discoveryengine.SearchRequest.SpellCorrectionSpec
        spell_correction_spec = SpellCorrectionSpec(
            mode=SpellCorrectionSpec.Mode.AUTO
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=f"{search_param.job_title} {site_restrict}",
            page_size=1,
            spell_correction_spec=spell_correction_spec,
        )
        response = client.search(request)
        # response is a SearchPager backed by protobuf messages -- not
        # directly JSON-serializable, so convert each result to a plain
        # dict before returning it.
        results = [MessageToDict(result._pb) for result in response]
        job_list = []
        parse_google_search_results(results, job_list)
        return {"company_dict": search_param.company_dictionary,
                "job_title": search_param.job_title,
                "results": job_list}
    except Exception as e:
        print(f"Error making API request: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error making API request: {e}"},
        )


def save_to_gcs(gcs_upload_param: GcsStringUpload):
    """
    Access the bucket with service_account_key, and upload the object
    (blob) to the storage. Returns a dict with a status message.
    """
    credentials = service_account.Credentials.\
        from_service_account_file(gcs_upload_param.service_account_key)
    client = storage.Client(project=gcs_upload_param.gcp_project_id,
                            credentials=credentials)
    bucket = client.bucket(gcs_upload_param.bucket_name)
    file = bucket.blob(gcs_upload_param.file_name)
    file.upload_from_string(gcs_upload_param.data)
    return {"message": f"file {gcs_upload_param.file_name} has been uploaded "
            f"to {gcs_upload_param.bucket_name} successfully."}


@app.post("/search_and_save/jobs")
def search_and_save_jobs(search_input: SearchModel):
    """
    Combine call_google_search() and save_to_gcs() to search for jobs and
    save the results as a JSON blob in GCS.
    """
    google_search_param = GoogleSearch(
        vertex_ai_project_id=vertex_ai_project_id,
        search_engine_id=search_engine_id,
        job_title=search_input.job_title,
        company_dictionary=search_input.company_dict,
        service_account_key=service_account_file_path,
    )
    search_response = call_google_search(google_search_param)
    if isinstance(search_response, JSONResponse):
        return search_response

    gcs_data = GcsStringUpload(
        service_account_key=service_account_file_path,
        bucket_name=bucket_name,
        file_name=f'{file_name_prefix}/{datetime.date.today()}.json',
        data=json.dumps(search_response, indent=4),
        gcp_project_id=project_id,
    )
    return save_to_gcs(gcs_data)
