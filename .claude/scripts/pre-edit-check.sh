#!/bin/bash
# Pre-edit validation hook for Claude Code

FILE_PATH="$1"

# Debug output for Claude Code
if [ -z "$FILE_PATH" ]; then
    echo "ERROR: No file path provided to pre-edit hook"
    exit 0  # Don't block, just warn
fi

# Check if editing protected files
PROTECTED_FILES=(
    ".github/workflows/"
    "LICENSE"
    ".env"
    "secrets.yml"
    ".claude/settings.json"
    "*.key"
    "*.pem"
)

for protected in "${PROTECTED_FILES[@]}"; do
    if [[ "$FILE_PATH" == *"$protected"* ]]; then
        echo "⚠️  WARNING: Editing protected file: $FILE_PATH"
        echo "Ensure changes are reviewed carefully."
        echo "Consider the security implications of this change."
    fi
done

# Special handling for conference data
if [[ "$FILE_PATH" == *"_data/conferences.yml"* ]]; then
    echo "📝 Editing conference data - remember to:"
    echo "  • Validate with 'pixi run sort'"
    echo "  • Check timezone validity"
    echo "  • Ensure HTTPS URLs only"
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "ℹ️  Creating new file: $FILE_PATH"
fi

exit 0