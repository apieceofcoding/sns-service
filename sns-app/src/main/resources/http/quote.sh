#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Create Quote (Quote Post ID=1) ==="
curl -X POST "${BASE_URL}/api/v1/posts/1/quotes" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "content": "I want to quote this post!"
  }' \
  -v

echo -e "\n\n"

echo "=== Get All Quotes ==="
curl -X GET "${BASE_URL}/api/v1/quotes" \
  -v

echo -e "\n\n"

echo "=== Get Quote by ID (ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/quotes/1" \
  -v

echo -e "\n\n"

echo "=== Delete Quote (ID=1) ==="
curl -X DELETE "${BASE_URL}/api/v1/quotes/1" \
  -b cookies.txt \
  -v

echo -e "\n"
