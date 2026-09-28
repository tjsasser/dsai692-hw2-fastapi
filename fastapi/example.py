import os
import json

from google.cloud import discoveryengine_v1 as discoveryengine
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict

from dotenv import load_dotenv

load_dotenv()

VERTEX_AI_PROJECT_ID = os.getenv("VERTEX_AI_PROJECT_ID")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
GCP_SERVICE_ACCOUNT_KEY = os.getenv("GCP_SERVICE_ACCOUNT_KEY")


def call_google_search(search_param):
    credentials = service_account.Credentials.from_service_account_file(
        GCP_SERVICE_ACCOUNT_KEY
    )
    client = discoveryengine.SearchServiceClient(credentials=credentials)

    serving_config = (
        f"projects/{VERTEX_AI_PROJECT_ID}/locations/global"
        f"/collections/default_collection/engines/{SEARCH_ENGINE_ID}"
        f"/servingConfigs/default_config"
    )

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=search_param,
        page_size=10,
    )

    response = client.search(request)
    return [MessageToDict(result._pb) for result in response.results]


if __name__ == "__main__":
    results = call_google_search("data engineer")
    print(f"{len(results)} results\n")
    print(json.dumps(results, indent=2))
