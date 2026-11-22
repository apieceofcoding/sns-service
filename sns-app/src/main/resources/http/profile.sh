#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Get My Posts (including reposts) ==="
curl -X GET "${BASE_URL}/api/v1/profile/posts" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get My Replies ==="
curl -X GET "${BASE_URL}/api/v1/profile/replies" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get My Liked Posts ==="
curl -X GET "${BASE_URL}/api/v1/profile/likes" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Init Profile Image Upload ==="
curl -X POST "${BASE_URL}/api/v1/profile/image/init" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "fileSize": 1024000
  }' \
  -v

echo -e "\n\n"

echo "=== Update Profile Image ==="
curl -X PUT "${BASE_URL}/api/v1/profile/image" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaId": 1
  }' \
  -v

echo -e "\n"
