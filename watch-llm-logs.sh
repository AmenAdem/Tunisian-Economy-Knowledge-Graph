#!/bin/bash
# Watch LLM trace logs in real-time
# Usage: ./watch-llm-logs.sh

echo "🔍 Watching LLM trace logs (CTRL+C to stop)..."
echo "================================================"
echo ""

# Watch for LLM-related logs with colored output
docker-compose logs -f backend 2>&1 | grep --line-buffered -E "TRACE|📤|📥|🔍|✅|❌|⚠️|took [0-9]+\.[0-9]+s|OpenRouter|Ollama|Retry|Fallback|Token Usage" | while read -r line; do
    # Color coding
    if echo "$line" | grep -q "📤"; then
        echo -e "\033[1;34m$line\033[0m"  # Blue for requests
    elif echo "$line" | grep -q "📥"; then
        echo -e "\033[1;32m$line\033[0m"  # Green for responses
    elif echo "$line" | grep -q "✅"; then
        echo -e "\033[1;32m$line\033[0m"  # Green for success
    elif echo "$line" | grep -q "❌"; then
        echo -e "\033[1;31m$line\033[0m"  # Red for errors
    elif echo "$line" | grep -q "⚠️"; then
        echo -e "\033[1;33m$line\033[0m"  # Yellow for warnings
    elif echo "$line" | grep -q "took"; then
        # Extract timing and color based on duration
        time=$(echo "$line" | grep -oE "[0-9]+\.[0-9]+s" | head -1 | grep -oE "[0-9]+\.[0-9]+")
        if (( $(echo "$time > 60" | bc -l) )); then
            echo -e "\033[1;31m$line\033[0m"  # Red for >60s
        elif (( $(echo "$time > 30" | bc -l) )); then
            echo -e "\033[1;33m$line\033[0m"  # Yellow for >30s
        else
            echo "$line"  # Normal for <30s
        fi
    else
        echo "$line"
    fi
done
