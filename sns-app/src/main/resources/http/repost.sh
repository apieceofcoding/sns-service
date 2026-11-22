#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Create Repost ==="
curl -X POST "${BASE_URL}/api/v1/reposts" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "postId": 1
  }' \
  -v

echo -e "\n\n"

echo "=== Get All Reposts ==="
curl -X GET "${BASE_URL}/api/v1/reposts" \
  -v

echo -e "\n\n"

echo "=== Get Repost by ID (ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/reposts/1" \
  -v

echo -e "\n\n"

echo "=== Delete Repost (ID=1) ==="
curl -X DELETE "${BASE_URL}/api/v1/reposts/1" \
  -b cookies.txt \
  -v

echo -e "\n"
