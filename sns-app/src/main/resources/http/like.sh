#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Create Like ==="
curl -X POST "${BASE_URL}/api/v1/likes" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "postId": 1
  }' \
  -v

echo -e "\n\n"

echo "=== Get All Likes ==="
curl -X GET "${BASE_URL}/api/v1/likes" \
  -v

echo -e "\n\n"

echo "=== Get Like by ID (ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/likes/1" \
  -v

echo -e "\n\n"

echo "=== Delete Like (ID=1) ==="
curl -X DELETE "${BASE_URL}/api/v1/likes/1" \
  -b cookies.txt \
  -v

echo -e "\n"
