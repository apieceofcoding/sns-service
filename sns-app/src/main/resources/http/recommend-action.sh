#!/bin/bash
set -eu
BASE_URL="http://localhost:8080"
EVENT_ID="$(uuidgen)"

echo "클릭 기록 (로그인 쿠키 필요)"
curl -fsS -b cookies.txt -X POST "${BASE_URL}/api/v1/recommend/actions" \
  -H 'Content-Type: application/json' \
  -d "{\"eventId\":\"${EVENT_ID}\",\"action\":\"click\",\"postId\":4}"
