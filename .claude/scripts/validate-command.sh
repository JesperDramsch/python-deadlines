#!/bin/bash
# Pre-command validation hook for Claude Code Bash tool

COMMAND="$1"

# Debug output
if [ -z "$COMMAND" ]; then
    echo "ERROR: No command provided to validation hook"
    exit 0  # Don't block empty commands
fi

# Check for dangerous commands that should be blocked
DANGEROUS_PATTERNS=(
    "rm -rf /"
    "rm -rf ~"
    "git push --force"
    "git push origin :main"
    "git push origin :master"
    "git reset --hard HEAD~"
    ":(){:|:&};"  # Fork bomb
    "chmod 777"
    "chmod -R 777"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if [[ "$COMMAND" == *"$pattern"* ]]; then
        echo "🛑 BLOCKED: Dangerous command detected!"
        echo "Command contains: $pattern"
        echo "This operation has been prevented for safety."
        exit 1  # Block the command
    fi
done

# Warn about potentially destructive operations
WARNING_PATTERNS=(
    "git reset"
    "git rebase"
    "git clean"
    "rm -rf"
    "DROP TABLE"
    "DELETE FROM"
    "truncate"
)

for pattern in "${WARNING_PATTERNS[@]}"; do
    if [[ "$COMMAND" == *"$pattern"* ]]; then
        echo "⚠️  WARNING: Potentially destructive operation detected"
        echo "Command contains: $pattern"
        echo "Proceeding with caution..."
    fi
done

# Project-specific validations
if [[ "$COMMAND" == *"_data/archive.yml"* ]] && [[ "$COMMAND" == *"edit"* || "$COMMAND" == *"vim"* ]]; then
    echo "⚠️  WARNING: archive.yml is auto-managed"
    echo "Changes to this file will be overwritten by 'pixi run sort'"
fi

# Log command for debugging (optional)
# echo "🔍 Validating command: ${COMMAND:0:100}..."

exit 0