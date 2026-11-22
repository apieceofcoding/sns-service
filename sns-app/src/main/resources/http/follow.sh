#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Follow a user ==="
curl -X POST "${BASE_URL}/api/v1/follows" \
  -H "Content-Type: application/json" \
  -d '{
    "followeeId": 2
  }' \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get Followers ==="
curl -X GET "${BASE_URL}/api/v1/follows/followers" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get Followees ==="
curl -X GET "${BASE_URL}/api/v1/follows/followees" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get Follow Count ==="
curl -X GET "${BASE_URL}/api/v1/follow_counts" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Unfollow a user ==="
curl -X DELETE "${BASE_URL}/api/v1/follows" \
  -H "Content-Type: application/json" \
  -d '{
    "followeeId": 2
  }' \
  -b cookies.txt \
  -v

echo -e "\n"
