#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== User Signup ==="
curl -X POST "${BASE_URL}/api/v1/users/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "elon",
    "password": "elon123"
  }' \
  -c cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get My Info ==="
curl -X GET "${BASE_URL}/api/v1/users/me" \
  -b cookies.txt \
  -v

echo -e "\n"
