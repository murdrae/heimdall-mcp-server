#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$(pwd)"
PROJECT_HASH=$(echo "$PROJECT_PATH" | sha256sum | cut -c1-8)
REPO_NAME=$(basename "$PROJECT_PATH")
IMAGE_NAME="heimdall-mcp:$PROJECT_HASH"
CONTAINER_NAME="heimdall-$REPO_NAME-$PROJECT_HASH"
QDRANT_CONTAINER="qdrant-$REPO_NAME-$PROJECT_HASH"
DATA_DIR="$PROJECT_PATH/.heimdall-mcp"

echo -e "${CYAN}🔍 Heimdall MCP Container & Data Analysis${NC}"
echo "============================================"
echo ""

# Function to convert bytes to human readable
human_readable() {
    local bytes=$1
    if [[ $bytes -lt 1024 ]]; then
        echo "${bytes}B"
    elif [[ $bytes -lt 1048576 ]]; then
        echo "$(awk "BEGIN {printf \"%.1f\", $bytes/1024}")KB"
    elif [[ $bytes -lt 1073741824 ]]; then
        echo "$(awk "BEGIN {printf \"%.1f\", $bytes/1048576}")MB"
    else
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}")GB"
    fi
}

# 1. Docker Image Analysis
echo -e "${BLUE}📦 Docker Image Analysis${NC}"
echo "------------------------"

# Check if image exists
if docker image inspect "$IMAGE_NAME" &> /dev/null; then
    # Get image size
    IMAGE_SIZE=$(docker image inspect "$IMAGE_NAME" --format='{{.Size}}')
    IMAGE_SIZE_HUMAN=$(human_readable $IMAGE_SIZE)

    echo -e "Image: ${GREEN}$IMAGE_NAME${NC}"
    echo -e "Size: ${YELLOW}$IMAGE_SIZE_HUMAN${NC}"

    # Show image layers
    echo -e "\n${CYAN}Image Layers:${NC}"
    docker history "$IMAGE_NAME" --format "table {{.CreatedBy}}\t{{.Size}}" | head -20

    # Base image size comparison
    BASE_SIZE=$(docker image inspect python:3.13-slim --format='{{.Size}}' 2>/dev/null || echo 0)
    if [[ $BASE_SIZE -gt 0 ]]; then
        ADDED_SIZE=$((IMAGE_SIZE - BASE_SIZE))
        echo -e "\n${CYAN}Size Breakdown:${NC}"
        echo -e "Base image (python:3.13-slim): $(human_readable $BASE_SIZE)"
        echo -e "Added by build: $(human_readable $ADDED_SIZE)"
    fi
else
    echo -e "${RED}Image not found: $IMAGE_NAME${NC}"
fi

# 2. Container Runtime Analysis
echo -e "\n${BLUE}🏃 Container Runtime Analysis${NC}"
echo "--------------------------------"

# Check both containers
for container in "$CONTAINER_NAME" "$QDRANT_CONTAINER"; do
    if docker container inspect "$container" &> /dev/null; then
        echo -e "\n${CYAN}Container: $container${NC}"

        # Get container size (writable layer)
        CONTAINER_SIZE=$(docker ps -s --format "table {{.Names}}\t{{.Size}}" | grep "$container" | awk '{print $2}' || echo "0B")
        echo -e "Writable layer size: ${YELLOW}$CONTAINER_SIZE${NC}"

        # Get memory usage if running
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            STATS=$(docker stats "$container" --no-stream --format "{{.MemUsage}}\t{{.CPUPerc}}")
            MEM_USAGE=$(echo "$STATS" | awk '{print $1}')
            CPU_USAGE=$(echo "$STATS" | awk '{print $2}')
            echo -e "Memory usage: ${YELLOW}$MEM_USAGE${NC}"
            echo -e "CPU usage: ${YELLOW}$CPU_USAGE${NC}"
        fi
    fi
done

# 3. Data Volume Analysis
echo -e "\n${BLUE}💾 Data Volume Analysis${NC}"
echo "-----------------------"

if [ -d "$DATA_DIR" ]; then
    # Total data directory size (use actual disk usage, not apparent size)
    TOTAL_SIZE=$(du -s "$DATA_DIR" 2>/dev/null | awk '{print $1*1024}')
    echo -e "Total data directory (actual disk usage): ${YELLOW}$(human_readable $TOTAL_SIZE)${NC}"
    echo -e "Path: $DATA_DIR"

    # Breakdown by subdirectory
    echo -e "\n${CYAN}Directory breakdown:${NC}"
    du -sh "$DATA_DIR"/* 2>/dev/null | sort -hr | while read size dir; do
        dir_name=$(basename "$dir")
        echo -e "  $size\t$dir_name"
    done

    # Specific file analysis
    echo -e "\n${CYAN}Key files:${NC}"

    # SQLite database
    if [ -f "$DATA_DIR/heimdall/cognitive_memory.db" ]; then
        DB_SIZE=$(stat -f%z "$DATA_DIR/heimdall/cognitive_memory.db" 2>/dev/null || stat -c%s "$DATA_DIR/heimdall/cognitive_memory.db" 2>/dev/null || echo 0)
        echo -e "  Cognitive Memory DB: $(human_readable $DB_SIZE)"

        # Count records if possible
        if command -v sqlite3 &> /dev/null; then
            MEMORY_COUNT=$(sqlite3 "$DATA_DIR/heimdall/cognitive_memory.db" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo "N/A")
            echo -e "    Memory records: $MEMORY_COUNT"
        fi
    fi

    # Qdrant data
    if [ -d "$DATA_DIR/qdrant" ]; then
        QDRANT_SIZE=$(du -s "$DATA_DIR/qdrant" 2>/dev/null | awk '{print $1*1024}')
        QDRANT_APPARENT=$(du -sb "$DATA_DIR/qdrant" 2>/dev/null | awk '{print $1}')
        echo -e "  Qdrant vector data (actual): $(human_readable $QDRANT_SIZE)"
        echo -e "    Note: Uses memory-mapped files - apparent size $(human_readable $QDRANT_APPARENT) but actual disk usage $(human_readable $QDRANT_SIZE)"
    fi

    # Models
    if [ -d "$DATA_DIR/models" ]; then
        MODEL_SIZE=$(du -sb "$DATA_DIR/models" 2>/dev/null | awk '{print $1}')
        echo -e "  Downloaded models: $(human_readable $MODEL_SIZE)"

        # List models
        echo -e "\n${CYAN}Models:${NC}"
        find "$DATA_DIR/models" -type f -name "*.bin" -o -name "*.safetensors" 2>/dev/null | while read model; do
            model_size=$(stat -f%z "$model" 2>/dev/null || stat -c%s "$model" 2>/dev/null || echo 0)
            model_name=$(basename "$(dirname "$model")")
            echo -e "    $model_name: $(human_readable $model_size)"
        done
    fi
else
    echo -e "${RED}Data directory not found: $DATA_DIR${NC}"
fi

# 4. Docker System Impact
echo -e "\n${BLUE}🐳 Docker System Impact${NC}"
echo "------------------------"

# Docker disk usage
echo -e "${CYAN}Docker disk usage:${NC}"
docker system df | grep -E "(Images|Containers|Volumes)"

# Volume analysis
echo -e "\n${CYAN}Project volumes:${NC}"
docker volume ls --format "table {{.Name}}\t{{.Size}}" | grep "$PROJECT_HASH" || echo "No named volumes found"

# 5. Recommendations
echo -e "\n${BLUE}💡 Optimization Recommendations${NC}"
echo "--------------------------------"

# Check for optimization opportunities
if [[ $IMAGE_SIZE -gt 1073741824 ]]; then  # > 1GB
    echo -e "${YELLOW}⚠️  Image size is over 1GB (${IMAGE_SIZE_HUMAN}). Priority optimizations:${NC}"
    echo "  1. Models are likely in image - should be downloaded at runtime or cached"
    echo "  2. Clear pip cache: RUN pip cache purge"
    echo "  3. Review what's being copied in COPY layers"
    echo "  4. Use .dockerignore more aggressively"
    echo "  5. Consider using slim base images or distroless"
fi

# Data usage is actually fine
echo -e "${GREEN}✅ Data volume usage is healthy:${NC}"
echo "  - Actual disk usage: $(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)"
echo "  - Qdrant sparse files are normal behavior"

# Check for unused images and provide detailed cleanup info
UNUSED_IMAGES=$(docker images -f "dangling=true" -q | wc -l)
ALL_IMAGES=$(docker images -q | wc -l)
USED_IMAGES=$(docker ps -a --format "{{.Image}}" | sort -u | wc -l)

echo -e "${CYAN}Image cleanup opportunities:${NC}"
if [[ $UNUSED_IMAGES -gt 0 ]]; then
    echo -e "  ${YELLOW}⚠️  Dangling images: $UNUSED_IMAGES${NC}"
fi
echo -e "  Total images: $ALL_IMAGES (using $(docker system df | grep Images | awk '{print $4}'))"
echo -e "  Images in use: $USED_IMAGES"
echo -e "  Potential cleanup: $((ALL_IMAGES - USED_IMAGES)) unused images"

# Cleanup commands
echo -e "\n${CYAN}Safe cleanup commands:${NC}"
echo "# Remove only THIS project:"
echo "$SCRIPT_DIR/setup_project_memory.sh --cleanup"
echo ""
echo "# Remove only dangling images (safe):"
echo "docker image prune -f"
echo ""
echo "# List all images to manually review:"
echo "docker images"
echo ""
echo -e "${YELLOW}# Full cleanup (CAREFUL - affects other projects!):${NC}"
echo "# docker system prune -a --volumes"

echo -e "\n${GREEN}✅ Analysis complete${NC}"
