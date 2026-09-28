# =====================================================================
# HW3 shared configuration -- FILL IN THE TODOs
#
# This file is SOURCED by both gcloud_command.sh and test_hw3.sh 
# to set environment variables:
#
#   source "$(dirname "$0")/config.sh"
#
# so you fill these values in ONCE to run the .sh files
# =====================================================================

# TODO 1: your GCP_PROJECT_ID.
PROJECT_ID=""

# TODO 2: the region to deploy into, e.g. "us-west1". 
# Cloud Run and Cloud Scheduler must be in the same region.
REGION=""

# TODO 3: absolute path to your .env file. 
# Cloud Run reads this at
# deploy time to set GCP_PROJECT_ID, VERTEX_AI_PROJECT_ID,
# SEARCH_ENGINE_ID, GCP_BUCKET_NAME and GCP_SERVICE_ACCOUNT_KEY 
# inside the containers.
ENV_FILE=""

# TODO 4: absolute path to your service account JSON key on your laptop
# (the file GCP_SERVICE_ACCOUNT_KEY points at for local development).
LOCAL_KEY_FILE=""

# TODO 5: the ports your two Dockerfiles EXPOSE. 
# These must match your Dockerfiles exactly.
API_PORT=""
WEBAPP_PORT=""

# ---------------------------------------------------------------------
# Provided -- no need to change anything below this line.
# ---------------------------------------------------------------------

# Secret Manager holds the key, and we need to mount it.
GCP_KEY_SECRET=hw3-gcp-key
SECRET_MOUNT_PATH=/run/secrets/gcp_key

# Cloud Run service names.
API_SERVICE=hw3-api-server
WEBAPP_SERVICE=hw3-webapp

# Cloud Scheduler job: name, schedule, and the request body.
SCHEDULER_JOB=hw3-refresh-jobs-trigger
SCHEDULE="0 0 * * *"
MESSAGE_BODY='{"job_title":"Data Engineer", "company_dict":{"Google":"www.google.com/about/careers/applications/jobs","OpenAI":"openai.com/careers","Anthropic":"anthropic.com/careers/jobs"}}'

# The API endpoint, and the GCS prefix.
SEARCH_PATH=/search_and_save/jobs
FILE_NAME_PREFIX=job_search

# =====================================================================
# Validation 
# =====================================================================
for _hw3_var in PROJECT_ID REGION ENV_FILE LOCAL_KEY_FILE API_PORT \
                WEBAPP_PORT; do
  if [ -z "${!_hw3_var}" ]; then
    echo "ERROR: $_hw3_var is empty - fill in TODOs in config.sh" \
         "before running this script." >&2
    exit 1
  fi
done
unset _hw3_var

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: ENV_FILE '$ENV_FILE' does not exist." >&2
  exit 1
fi
if [ ! -f "$LOCAL_KEY_FILE" ]; then
  echo "ERROR: LOCAL_KEY_FILE '$LOCAL_KEY_FILE' does not exist." >&2
  exit 1
fi
