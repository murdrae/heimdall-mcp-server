#!/bin/bash
set -e

# Real-time memory and performance monitoring
PROJECT_HASH=$(echo "$(pwd)" | sha256sum | cut -c1-8)
CONTAINER_NAME="heimdall-mcp-$PROJECT_HASH"
QDRANT_CONTAINER="qdrant-$PROJECT_HASH"

echo "📊 Real-time Memory & Performance Monitor"
echo "========================================"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Check if containers are running
if ! docker ps --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container not running: $CONTAINER_NAME"
    exit 1
fi

# Header
printf "%-10s %-12s %-12s %-12s %-8s %-8s %-15s %-12s\n" \
    "TIME" "CONTAINER" "MEM_USAGE" "MEM_LIMIT" "MEM_%" "CPU_%" "NET_I/O" "BLOCK_I/O"
echo "--------------------------------------------------------------------------------"

# Monitor loop
while true; do
    timestamp=$(date '+%H:%M:%S')

    # Get stats for both containers
    for container in "$CONTAINER_NAME" "$QDRANT_CONTAINER"; do
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            stats=$(docker stats "$container" --no-stream --format "{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}\t{{.NetIO}}\t{{.BlockIO}}")

            # Parse memory usage (format: "used / limit")
            mem_full=$(echo "$stats" | cut -f1)
            mem_used=$(echo "$mem_full" | cut -d'/' -f1 | xargs)
            mem_limit=$(echo "$mem_full" | cut -d'/' -f2 | xargs)
            mem_perc=$(echo "$stats" | cut -f2)
            cpu_perc=$(echo "$stats" | cut -f3)
            net_io=$(echo "$stats" | cut -f4)
            block_io=$(echo "$stats" | cut -f5)

            # Extract short container name
            if [[ "$container" == *"heimdall"* ]]; then
                short_name="heimdall"
            elif [[ "$container" == *"qdrant"* ]]; then
                short_name="qdrant"
            else
                short_name=$(echo "$container" | cut -d'-' -f1)
            fi

            printf "%-10s %-12s %-12s %-12s %-8s %-8s %-15s %-12s\n" \
                "$timestamp" "$short_name" "$mem_used" "$mem_limit" "$mem_perc" "$cpu_perc" "$net_io" "$block_io"
        fi
    done

    sleep 2
done
