#!/bin/bash
# Post-edit/write formatting hook for Claude Code

FILE_PATH="$1"

# Debug output
if [ -z "$FILE_PATH" ]; then
    echo "ERROR: No file path provided to format hook"
    exit 0
fi

# Only process if file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "File not found, skipping formatting: $FILE_PATH"
    exit 0
fi

# Format Python files
if [[ "$FILE_PATH" == *.py ]]; then
    echo "🔧 Processing Python file: $(basename "$FILE_PATH")"
    
    # Try to use pixi environment first
    if command -v pixi &> /dev/null; then
        # Use pixi run to ensure correct environment
        pixi run ruff format "$FILE_PATH" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ Formatted with ruff"
        fi
        
        pixi run ruff check --fix "$FILE_PATH" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ Fixed linting issues"
        fi
    elif command -v ruff &> /dev/null; then
        # Fallback to system ruff
        ruff format "$FILE_PATH"
        ruff check --fix "$FILE_PATH"
        echo "✅ Python file processed"
    else
        echo "ℹ️  Ruff not available, skipping formatting"
    fi
fi

# Validate YAML files
if [[ "$FILE_PATH" == *.yml ]] || [[ "$FILE_PATH" == *.yaml ]]; then
    echo "🔧 Validating YAML: $(basename "$FILE_PATH")"
    
    # Special handling for conference data
    if [[ "$FILE_PATH" == *"_data/conferences.yml"* ]]; then
        echo "📋 Conference data modified - run 'pixi run sort' to validate"
    fi
    
    # Basic YAML validation
    if command -v python3 &> /dev/null; then
        python3 -c "import yaml; yaml.safe_load(open('$FILE_PATH'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ YAML syntax valid"
        else
            echo "❌ YAML syntax error - please fix before committing"
            exit 0  # Don't block, just warn
        fi
    elif command -v python &> /dev/null; then
        python -c "import yaml; yaml.safe_load(open('$FILE_PATH'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ YAML syntax valid"
        else
            echo "❌ YAML syntax error - please fix before committing"
            exit 0  # Don't block, just warn
        fi
    fi
fi

# Validate JSON files
if [[ "$FILE_PATH" == *.json ]]; then
    echo "🔧 Validating JSON: $(basename "$FILE_PATH")"
    
    if command -v python3 &> /dev/null; then
        python3 -c "import json; json.load(open('$FILE_PATH'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ JSON syntax valid"
        else
            echo "❌ JSON syntax error - please fix"
            exit 0  # Don't block, just warn
        fi
    elif command -v python &> /dev/null; then
        python -c "import json; json.load(open('$FILE_PATH'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ JSON syntax valid"
        else
            echo "❌ JSON syntax error - please fix"
            exit 0  # Don't block, just warn
        fi
    fi
fi

exit 0