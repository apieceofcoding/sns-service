#!/bin/bash

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

case "$FILE_PATH" in
  *.java|*.kts|*.json|*.yaml|*.yml|*.md|*.properties|*.xml|*.sql)
    echo "[lint hook] Running spotlessApply on: $FILE_PATH" >&2
    cd "$GEMINI_PROJECT_DIR" || exit 0
    ./gradlew spotlessApply -q 2>/dev/null
    ;;
esac

echo '{}'
exit 0
