#!/usr/bin/env bash
# =====================================================================
# HW3 self-check
#
# Runs in three phases, in this order:
#
#   1. TEARDOWN  -- delete everything a previous run left behind: the two
#                   Cloud Run services, the Cloud Scheduler job, and the
#                   search result files in your GCS bucket. 
#   2. LOCAL     -- build both Dockerfiles, run both containers, POST a
#                   search to the API, confirm a new file appears in the
#                   bucket, and confirm the dashboard answers.
#   3. CLOUD     -- run gcloud_command.sh, then check the deployed API
#                   and dashboard the same way.
#
# Usage:
#   bash test_hw3.sh              # all three phases
#   bash test_hw3.sh teardown     # phase 1 only (clean up when you're done)
#   bash test_hw3.sh local        # phase 1 + 2
#   bash test_hw3.sh cloud        # phase 1 + 3
#   bash test_hw3.sh all --yes    # skip the confirmation prompt
#
# Requires: docker running, gcloud authenticated, and every TODO in
# gcloud_command.sh filled in.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

# =====================================================================
# CONFIGURATION
# =====================================================================
DEPLOY_SCRIPT=gcloud_command.sh
source ./config.sh

# Local-only names, so nothing here collides with your real resources.
API_CONTAINER=hw3-test-api
WEBAPP_CONTAINER=hw3-test-webapp
API_IMAGE=hw3-test-api-image
WEBAPP_IMAGE=hw3-test-webapp-image
KEY_IN_CONTAINER=/tmp/gcp-key.json

BUCKET_NAME=$(grep -m1 '^GCP_BUCKET_NAME=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')

usage() {
  echo "Usage: bash test_hw3.sh [all|teardown|local|cloud] [--yes]" >&2
}

PHASE=all
AUTO_YES=""
for arg in "$@"; do
  case "$arg" in
    all|teardown|local|cloud) PHASE=$arg ;;
    --yes) AUTO_YES=--yes ;;
    *) usage; exit 1 ;;
  esac
done

if [ -z "$BUCKET_NAME" ]; then
  echo "ERROR: GCP_BUCKET_NAME is not set in $ENV_FILE." >&2
  exit 1
fi

pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1" >&2; exit 1; }
banner() { echo; echo "=== $1 ==="; }

# =====================================================================
# PHASE 1 -- TEARDOWN (runs first)
# =====================================================================
teardown() {
  banner "PHASE 1: teardown"
  echo "About to DELETE, in project '$PROJECT_ID':"
  echo "  - Cloud Run service   $API_SERVICE ($REGION)"
  echo "  - Cloud Run service   $WEBAPP_SERVICE ($REGION)"
  echo "  - Scheduler job       $SCHEDULER_JOB ($REGION)"
  echo "  - GCS objects         gs://$BUCKET_NAME/$FILE_NAME_PREFIX/**"
  echo "  - local containers    $API_CONTAINER, $WEBAPP_CONTAINER"
  if [ "$AUTO_YES" != "--yes" ]; then
    read -r -p "Continue? [y/N] " reply
    [ "$reply" = "y" ] || [ "$reply" = "Y" ] || { echo "Aborted."; exit 1; }
  fi

  docker rm -f "$API_CONTAINER" "$WEBAPP_CONTAINER" >/dev/null 2>&1 || true
  pass "local containers removed"

  gcloud run services delete "$API_SERVICE" --region "$REGION" --quiet \
    >/dev/null 2>&1 || true
  gcloud run services delete "$WEBAPP_SERVICE" --region "$REGION" --quiet \
    >/dev/null 2>&1 || true
  pass "Cloud Run services removed"

  gcloud scheduler jobs delete "$SCHEDULER_JOB" --location "$REGION" --quiet \
    >/dev/null 2>&1 || true
  pass "scheduler job removed"

  gcloud storage rm "gs://$BUCKET_NAME/$FILE_NAME_PREFIX/**" --quiet \
    >/dev/null 2>&1 || true
  pass "gs://$BUCKET_NAME/$FILE_NAME_PREFIX/ emptied"
}

wait_for() {
  local url=$1 name=$2 tries=${3:-30}
  for _ in $(seq "$tries"); do
    if curl -fsS -o /dev/null "$url"; then
      pass "$name is answering ($url)"
      return 0
    fi
    sleep 2
  done
  fail "$name never answered at $url"
}

bucket_file_count() {
  local n
  n=$(gcloud storage ls "gs://$BUCKET_NAME/$FILE_NAME_PREFIX/**" 2>/dev/null \
    | grep -c '\.json$' || true)
  echo "${n:-0}"
}

# A fingerprint of the result files: the metadata GCS changes whenever a
# blob is written.
# Generation and ETag change on every upload, even when the new bytes are
# identical to the old ones
bucket_fingerprint() {
  gcloud storage ls -L "gs://$BUCKET_NAME/$FILE_NAME_PREFIX/**" 2>/dev/null \
    | grep -Ei '^[[:space:]]*(generation|etag|update time|content-length):' \
    | tr -d '[:space:]' || true
}

# =====================================================================
# PHASE 2 -- LOCAL CONTAINERS
# =====================================================================
test_local() {
  banner "PHASE 2: local containers"

  [ -f fastapi/Dockerfile ] || fail "fastapi/Dockerfile does not exist"
  [ -f streamlit/Dockerfile ] || fail "streamlit/Dockerfile does not exist"
  pass "both Dockerfiles exist"

  docker build -q -t "$API_IMAGE" ./fastapi >/dev/null
  docker build -q -t "$WEBAPP_IMAGE" ./streamlit >/dev/null
  pass "both images build"


  docker run -d --name "$API_CONTAINER" \
    -p "$API_PORT:$API_PORT" \
    --env-file "$ENV_FILE" \
    -e GCP_SERVICE_ACCOUNT_KEY="$KEY_IN_CONTAINER" \
    -v "$LOCAL_KEY_FILE:$KEY_IN_CONTAINER:ro" \
    "$API_IMAGE" >/dev/null
  wait_for "http://localhost:$API_PORT/docs" "local API"

  before_fp=$(bucket_fingerprint)
  before_n=$(bucket_file_count)
  code=$(curl -s -o /tmp/hw3_local_post.json -w '%{http_code}' \
    -X POST "http://localhost:$API_PORT$SEARCH_PATH" \
    -H 'Content-Type: application/json' -d "$MESSAGE_BODY")
  [ "$code" = "200" ] || fail "POST $SEARCH_PATH returned $code, not 200
        response: $(cat /tmp/hw3_local_post.json)"
  pass "POST $SEARCH_PATH returned 200"

  after_fp=$(bucket_fingerprint)
  after_n=$(bucket_file_count)
  [ -n "$after_fp" ] \
    || fail "nothing readable in gs://$BUCKET_NAME/$FILE_NAME_PREFIX/ after the POST"
  [ "$after_fp" != "$before_fp" ] \
    || fail "the API returned 200 but gs://$BUCKET_NAME/$FILE_NAME_PREFIX/ did not change"
  pass "search results written to GCS ($before_n -> $after_n files)"

  docker run -d --name "$WEBAPP_CONTAINER" \
    -p "$WEBAPP_PORT:$WEBAPP_PORT" \
    --env-file "$ENV_FILE" \
    -e GCP_SERVICE_ACCOUNT_KEY="$KEY_IN_CONTAINER" \
    -e API_SERVICE_URL="http://$API_CONTAINER:$API_PORT" \
    -v "$LOCAL_KEY_FILE:$KEY_IN_CONTAINER:ro" \
    "$WEBAPP_IMAGE" >/dev/null
  
   wait_for "http://localhost:$WEBAPP_PORT/_stcore/health" "local dashboard"

  LOCAL_URL="http://localhost:$WEBAPP_PORT"
}

# =====================================================================
# PHASE 3 -- CLOUD RUN
# =====================================================================
test_cloud() {
  banner "PHASE 3: Cloud Run"
  echo "Running $DEPLOY_SCRIPT (this takes several minutes)..."
  bash "$DEPLOY_SCRIPT"

  CLOUD_API_URL=$(gcloud run services describe "$API_SERVICE" \
    --region "$REGION" --format="value(urls[0])")
  CLOUD_WEBAPP_URL=$(gcloud run services describe "$WEBAPP_SERVICE" \
    --region "$REGION" --format="value(urls[0])")
  [ -n "$CLOUD_API_URL" ] || fail "$API_SERVICE has no URL -- did it deploy?"
  [ -n "$CLOUD_WEBAPP_URL" ] || fail "$WEBAPP_SERVICE has no URL"
  pass "both services deployed"

  wait_for "$CLOUD_API_URL/docs" "deployed API"

  before_fp=$(bucket_fingerprint)
  code=$(curl -s -o /tmp/hw3_cloud_post.json -w '%{http_code}' \
    -X POST "$CLOUD_API_URL$SEARCH_PATH" \
    -H 'Content-Type: application/json' -d "$MESSAGE_BODY")
  [ "$code" = "200" ] || fail "POST to deployed API returned $code, not 200
        response: $(cat /tmp/hw3_cloud_post.json)"
  pass "deployed API returned 200"

  
  after_fp=$(bucket_fingerprint)
  [ -n "$after_fp" ] \
    || fail "nothing readable in gs://$BUCKET_NAME/$FILE_NAME_PREFIX/ after the POST"
  [ "$after_fp" != "$before_fp" ] \
    || fail "the deployed API returned 200 but gs://$BUCKET_NAME/$FILE_NAME_PREFIX/ is unchanged,
        so it never wrote its results"
  pass "deployed API wrote to GCS"

  wait_for "$CLOUD_WEBAPP_URL/_stcore/health" "deployed dashboard" 45

  gcloud scheduler jobs describe "$SCHEDULER_JOB" --location "$REGION" \
    >/dev/null 2>&1 || fail "scheduler job $SCHEDULER_JOB was not created"
  pass "scheduler job $SCHEDULER_JOB exists"
}

case "$PHASE" in
  teardown) teardown ;;
  local)    teardown; test_local ;;
  cloud)    teardown; test_cloud ;;
  all)      teardown; test_local; test_cloud ;;
  *) usage; exit 1 ;;
esac

banner "REVIEW THESE URLS"
[ -n "${LOCAL_URL:-}" ] && echo "  Local dashboard:    $LOCAL_URL"
[ -n "${CLOUD_WEBAPP_URL:-}" ] && echo "  Deployed dashboard: $CLOUD_WEBAPP_URL"
[ -n "${CLOUD_API_URL:-}" ] && echo "  Deployed API docs:  $CLOUD_API_URL/docs"
echo
echo "Open the dashboard(s) above and confirm the job table renders."
echo "Everything is still running. When you're finished, clean up with:"
echo "  bash test_hw3.sh teardown"
