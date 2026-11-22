#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Login ==="
curl -X POST "${BASE_URL}/api/v1/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123" \
  -c cookies.txt \
  -v

echo -e "\n\n"

echo "=== Get All Sessions ==="
curl -X GET "${BASE_URL}/api/v1/sessions" \
  -b cookies.txt \
  -v

echo -e "\n\n"

echo "=== Logout ==="
curl -X POST "${BASE_URL}/api/v1/logout" \
  -b cookies.txt \
  -c cookies.txt \
  -v

echo -e "\n"
