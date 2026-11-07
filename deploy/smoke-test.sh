#!/usr/bin/env bash
# Disposable Docker-only state; never mounts a developer or production database.
set -euo pipefail
image="${1:-beer-run:ci}"
suffix="$(date +%s)-${RANDOM}"
volume="beer-run-smoke-${suffix}"
container="beer-run-smoke-${suffix}"
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker volume create "$volume" >/dev/null
docker run --rm --user 0:0 --mount "type=volume,src=${volume},dst=/state" "$image" \
  sh -c 'mkdir -p /state/data /state/uploads; cp /app/seed-data/drinks.json /state/data/drinks.json; chown -R 1000:1000 /state'
docker run --rm --mount "type=volume,src=${volume},dst=/state" "$image" python scripts/migrate_db.py
docker run --rm --mount "type=volume,src=${volume},dst=/state" "$image" python scripts/migrate_db.py --check
docker run -d --name "$container" --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --tmpfs /tmp:size=128m,mode=1777 \
  --mount "type=volume,src=${volume},dst=/state" \
  -e SECRET_KEY=container-smoke-only-secret-at-least-32-bytes \
  -e SIGNUP_CODE=container-smoke-only-signup \
  -e LEGAL_CONTROLLER_NAME='Container Smoke Test' \
  -e LEGAL_CONTACT_EMAIL=smoke@example.test "$image" >/dev/null
for attempt in {1..45}; do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$container")"
  if [ "$status" = healthy ]; then break; fi
  if [ "$status" = unhealthy ]; then docker logs "$container"; exit 1; fi
  sleep 2
done
test "$status" = healthy
docker exec "$container" python -c '
import json, os, urllib.request
assert os.getuid() == 1000
for path in ("/", "/terms", "/privacy", "/assets/js/app.js", "/static/css/wrapped.css", "/api/beer-runs?view=discover"):
    assert urllib.request.urlopen("http://127.0.0.1:8000" + path).status == 200, path
config = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/config"))
assert config["types"] and config["quantities"]
from pathlib import Path
Path("/state/uploads/smoke.txt").write_text("retained")
'
docker restart "$container" >/dev/null
docker exec "$container" python -c 'from pathlib import Path; assert Path("/state/uploads/smoke.txt").read_text() == "retained"'
