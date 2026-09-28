import json
import re

from google.oauth2 import service_account
from google.cloud import storage
import streamlit as st
import pandas as pd

from user_definition import (bucket_name, file_name_prefix, project_id,
                             service_account_file_path)


def retrieve_data_from_gcs(service_account_key: str,
                           project_id: str,
                           bucket_name: str,
                           file_name_prefix: str
                           ) -> dict:
    """
    Retrieve file (.json) contents from all files starting with
    'file_name_prefix' in "bucket_name" and return a dictionary
    including "results", "job_titles", and "company_dict".

    Args:
        service_account_key (str): path of service account key file (.json)
        project_id (str): GCP Project ID where the bucket is located
        bucket_name (str): bucket name
        file_name_prefix (str): prefix of files to retrieve data from
                                (Ex. "job_search")

    Returns:
        dict: {"results": combined "results" from every matching file,
               "job_titles": sorted unique "job_title"s across those files,
               "company_dict": combined "company_dict" across those files}
    """
    credentials = service_account.Credentials.from_service_account_file(
        service_account_key)
    client = storage.Client(project=project_id,
                            credentials=credentials)
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    # Retrieve file (.json) contents from all files starting with
    # 'file_name_prefix' in "bucket_name" and return a dictionary
    # including "results", "job_titles", and "company_dict".
    content = []
    job_titles = []
    company_dict = dict()
    for blob in blobs:
        if blob.name.startswith(file_name_prefix) and\
           blob.name.find(".json") > 0:
            blob_data = json.loads(blob.download_as_text())
            content += blob_data["results"]
            job_titles.append(blob_data["job_title"])
            company_dict = company_dict | blob_data["company_dict"]
    job_titles = list(set(job_titles))
    job_titles.sort()
    return {"results": content,
            "job_titles": job_titles,
            "company_dict": company_dict}


if __name__ == '__main__':
    gcs_data = retrieve_data_from_gcs(service_account_file_path,
                                      project_id,
                                      bucket_name,
                                      file_name_prefix)
    role_name = ", ".join(gcs_data["job_titles"])
    company_dictionary = gcs_data["company_dict"]
    data = pd.DataFrame(gcs_data["results"])

    st.title(f"{role_name} Job Listings")
    with st.sidebar:
        st.write("Filter by Company")
        unique_categories = list(company_dictionary.keys())
        unique_categories.sort()
        selected_categories = []

        for category in unique_categories:
            if st.checkbox(f"{category}",
                           value=True,
                           key=f"checkbox_{category}"):
                selected_categories.append(category.lower())

        pattern = "|".join(re.escape(category)
                           for category in selected_categories)
        if pattern:
            filtered_df = data[data["link"].str.contains(pattern)]
        else:
            filtered_df = data.iloc[0:0]
        print(filtered_df)
        filtered_df = filtered_df[["date", "title", "link"]]
        filtered_df = filtered_df.drop_duplicates(subset=["link"])
        filtered_df = filtered_df.sort_values(
            by=["date", "title"], ascending=[False, True])

    st.dataframe(filtered_df,
                 hide_index=True,
                 column_config={
                     "link": st.column_config.LinkColumn()})
