#!/bin/bash

BASE_URL="http://localhost:8080"

echo "=== Initialize Media Upload (IMAGE) ==="
RESPONSE=$(curl -X POST "${BASE_URL}/api/v1/media/init" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaType": "IMAGE",
    "fileSize": 1048576
  }' \
  -s)

echo "$RESPONSE"
PRESIGNED_URL=$(echo "$RESPONSE" | grep -o '"presignedUrl":"[^"]*"' | cut -d'"' -f4)
echo "Presigned URL: $PRESIGNED_URL"

echo -e "\n=== Upload Image to Presigned URL ==="
echo "To upload an image, use:"
echo "curl -X PUT \"\$PRESIGNED_URL\" -H \"Content-Type: image/jpeg\" --data-binary @/path/to/image.jpg"
echo ""
echo "Example:"
echo "# Create a test image file"
echo "# echo 'test' > test.jpg"
echo "# curl -X PUT \"\$PRESIGNED_URL\" -H \"Content-Type: image/jpeg\" --data-binary @test.jpg"

echo -e "\n\n"

echo -e "\n=== Initialize Media Upload (VIDEO) ==="
VIDEO_RESPONSE=$(curl -X POST "${BASE_URL}/api/v1/media/init" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaType": "VIDEO",
    "fileSize": 5242880
  }' \
  -s)

echo "$VIDEO_RESPONSE"
VIDEO_PRESIGNED_URL=$(echo "$VIDEO_RESPONSE" | grep -o '"presignedUrl":"[^"]*"' | cut -d'"' -f4)
echo "Video Presigned URL: $VIDEO_PRESIGNED_URL"

echo -e "\n=== Upload Video to Presigned URL ==="
echo "To upload a video with Host header:"
echo "curl -X PUT \"\$VIDEO_PRESIGNED_URL\" -H \"Content-Type: video/mp4\" -H \"Host: localhost:9000\" --data-binary @/path/to/video.mp4"

echo -e "\n\n"

echo -e "\n=== Initialize Media Upload (VIDEO - Multipart) ==="
MULTIPART_RESPONSE=$(curl -X POST "${BASE_URL}/api/v1/media/init" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaType": "VIDEO",
    "fileSize": 20971520
  }' \
  -s)

echo "$MULTIPART_RESPONSE"
echo ""

echo -e "\n=== Upload Video to Presigned URL (Multipart) ==="
echo "For multipart upload (files > 8MB):"
echo "1. Extract uploadId and presignedUrlParts from the response"
echo "2. Split your video file into 8MB chunks:"
echo "   split -b 8388608 video.mp4 video_part_"
echo "3. Upload each part using the corresponding presigned URL with Host header:"
echo "   curl -X PUT \"<presignedUrl for part 1>\" -H \"Content-Type: application/octet-stream\" -H \"Host: localhost:9000\" --data-binary @video_part_aa"
echo "   curl -X PUT \"<presignedUrl for part 2>\" -H \"Content-Type: application/octet-stream\" -H \"Host: localhost:9000\" --data-binary @video_part_ab"
echo "   curl -X PUT \"<presignedUrl for part 3>\" -H \"Content-Type: application/octet-stream\" -H \"Host: localhost:9000\" --data-binary @video_part_ac"
echo "4. Save the ETag from each upload response header"
echo "5. Call /api/v1/media/uploaded with the mediaId and all part ETags"

echo -e "\n\n"

echo "=== Mark Media as Uploaded - Single Upload (ID=1) ==="
curl -X POST "${BASE_URL}/api/v1/media/uploaded" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaId": 1
  }' \
  -v

echo -e "\n\n"

echo "=== Mark Media as Uploaded - Multipart Upload (ID=2) ==="
curl -X POST "${BASE_URL}/api/v1/media/uploaded" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mediaId": 2,
    "parts": [
      {
        "partNumber": 1,
        "eTag": "\"eTag-from-part-1-response\""
      },
      {
        "partNumber": 2,
        "eTag": "\"eTag-from-part-2-response\""
      },
      {
        "partNumber": 3,
        "eTag": "\"eTag-from-part-3-response\""
      }
    ]
  }' \
  -v

echo -e "\n\n"

echo "=== Get Media by ID (ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/media/1" \
  -v

echo -e "\n\n"

echo "=== Get Presigned URL for Media (ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/media/1/presigned-url" \
  -v

echo -e "\n\n"

echo "=== Get Media by User ID (User ID=1) ==="
curl -X GET "${BASE_URL}/api/v1/users/1/media" \
  -v

echo -e "\n\n"

echo "=== Delete Media (ID=1) ==="
curl -X DELETE "${BASE_URL}/api/v1/media/1" \
  -b cookies.txt \
  -v

echo -e "\n"
