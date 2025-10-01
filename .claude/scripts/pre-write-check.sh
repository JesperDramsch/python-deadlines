#!/bin/bash
# Pre-write validation hook for Claude Code

FILE_PATH="$1"

# Debug output
if [ -z "$FILE_PATH" ]; then
    echo "ERROR: No file path provided to pre-write hook"
    exit 0
fi

# Check if overwriting important files
IMPORTANT_FILES=(
    "CLAUDE.md"
    "README.md"
    "pyproject.toml"
    "pixi.toml"
    "_config.yml"
    ".claude/settings.json"
    "LICENSE"
)

for important in "${IMPORTANT_FILES[@]}"; do
    if [[ "$FILE_PATH" == *"$important" ]]; then
        echo "⚠️  WARNING: Overwriting important file: $important"
        echo "Ensure changes are intentional and reviewed."
    fi
done

# Check for suspicious file types
SUSPICIOUS_EXTENSIONS=(
    ".exe"
    ".dll"
    ".so"
    ".dylib"
    ".key"
    ".pem"
    ".env"
)

for ext in "${SUSPICIOUS_EXTENSIONS[@]}"; do
    if [[ "$FILE_PATH" == *"$ext" ]]; then
        echo "⚠️  WARNING: Creating sensitive file type: $ext"
        echo "Never commit credentials or secrets to the repository."
    fi
done

# Project-specific warnings
if [[ "$FILE_PATH" == *"_data/archive.yml" ]]; then
    echo "⚠️  WARNING: archive.yml is auto-managed"
    echo "This file will be overwritten by 'pixi run sort'"
    echo "Add conferences to conferences.yml instead"
fi

if [[ "$FILE_PATH" == *".github/workflows"* ]]; then
    echo "⚠️  Creating GitHub workflow file"
    echo "Security reminders:"
    echo "  • Use secrets for sensitive data"
    echo "  • Pin action versions"
    echo "  • Review permissions"
fi

# Ensure directory exists
DIR_PATH=$(dirname "$FILE_PATH")
if [ ! -d "$DIR_PATH" ]; then
    echo "ℹ️  Creating directory: $DIR_PATH"
    mkdir -p "$DIR_PATH"
fi

# Log file creation for debugging (optional)
# echo "📝 Writing file: $(basename "$FILE_PATH")"

exit 0