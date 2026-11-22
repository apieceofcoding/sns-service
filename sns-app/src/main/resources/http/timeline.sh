#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Get Timeline ==="
curl -X GET "${BASE_URL}/api/v1/timeline" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get Timeline with limit=10 ==="
curl -X GET "${BASE_URL}/api/v1/timeline?limit=10" \
  -b cookies.txt \
  -v

echo -e "\n"
