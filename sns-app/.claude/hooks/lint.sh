#!/bin/bash

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

case "$FILE_PATH" in
  *.java|*.kts|*.json|*.yaml|*.yml|*.md|*.properties|*.xml|*.sql)
    echo "[lint hook] Running spotlessApply on: $FILE_PATH"
    cd "$CLAUDE_PROJECT_DIR" || exit 0
    ./gradlew spotlessApply -q 2>/dev/null
    ;;
esac

exit 0
