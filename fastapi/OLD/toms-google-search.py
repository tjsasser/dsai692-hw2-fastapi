import os
import re
from datetime import date, timedelta

from fastapi.responses import JSONResponse
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict

from dotenv import load_dotenv

load_dotenv()

#GCP_PROJECT_ID=os.getenv("GCP_PROJECT_ID")
VERTEX_AI_PROJECT_ID=os.getenv("VERTEX_AI_PROJECT_ID")
SEARCH_ENGINE_ID=os.getenv("SEARCH_ENGINE_ID")
#GCP_BUCKET_NAME=os.getenv("GCP_BUCKET_NAME")
GCP_SERVICE_ACCOUNT_KEY=os.getenv("GCP_SERVICE_ACCOUNT_KEY")

def call_google_search(search_param):
    try:
        credentials = service_account.Credentials.from_service_account_file(GCP_SERVICE_ACCOUNT_KEY)
        client = discoveryengine.SearchServiceClient(credentials=credentials)

        serving_config = (
            f"projects/{VERTEX_AI_PROJECT_ID}/locations/global"
            f"/collections/default_collection/engines/{SEARCH_ENGINE_ID}"
            f"/servingConfigs/default_config"
        )
        
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=search_param,
            page_size=10
        )

        response = client.search(request)
        search_results = [MessageToDict(result._pb) for result in response.results]

        job_list = []
        parse_google_search_results(search_results, job_list)
        return job_list

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})




if __name__ == "__main__":
    result = call_google_search("data engineer")
    if isinstance(result, JSONResponse):
        print("ERROR:", result.body)
    else:
        for job in result:
            print(job["date"], job["title"], job["link"])
