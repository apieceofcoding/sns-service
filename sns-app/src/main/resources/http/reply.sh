#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Create Reply (Post ID=1) ==="
curl -X POST "${BASE_URL}/api/v1/posts/1/replies" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "content": "This is a reply to the post!"
  }' \
  -v

echo -e "\n\n"

echo "=== Get Replies (Post ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/posts/1/replies" \
  -v

echo -e "\n\n"

echo "=== Update Reply (Reply ID=2) ==="
curl -X PUT "${BASE_URL}/api/v1/replies/2" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "content": "This is my updated reply!"
  }' \
  -v

echo -e "\n\n"

echo "=== Delete Reply (Reply ID=2) ==="
curl -X DELETE "${BASE_URL}/api/v1/replies/2" \
  -b cookies.txt \
  -v

echo -e "\n"
