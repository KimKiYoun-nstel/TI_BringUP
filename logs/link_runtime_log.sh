#!/bin/sh

# Usage: ./link_runtime_log.sh <source-log-file>
# Creates or updates logs/runtime_log as a symlink to the provided source file.

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <source-log-file>"
    exit 1
fi

SOURCE="$1"
TARGET_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$TARGET_DIR/runtime_log"

if [ ! -e "$SOURCE" ]; then
    echo "Error: source file does not exist: $SOURCE"
    exit 2
fi

ln -sfn "$SOURCE" "$TARGET"
echo "Linked $TARGET -> $SOURCE"
