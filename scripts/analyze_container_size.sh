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

echo -e "${CYAN}📊 Heimdall MCP System Analysis${NC}"
echo "=================================="
echo ""

# Collect key metrics first
if docker image inspect "$IMAGE_NAME" &> /dev/null; then
    IMAGE_SIZE=$(docker image inspect "$IMAGE_NAME" --format='{{.Size}}')
    IMAGE_SIZE_HUMAN=$(human_readable $IMAGE_SIZE)
    IMAGE_EXISTS=true
else
    IMAGE_EXISTS=false
fi

if [ -d "$DATA_DIR" ]; then
    TOTAL_SIZE=$(du -s "$DATA_DIR" 2>/dev/null | awk '{print $1*1024}')
    TOTAL_SIZE_HUMAN=$(human_readable $TOTAL_SIZE)
    DATA_EXISTS=true

    # Get memory count
    if [ -f "$DATA_DIR/heimdall/cognitive_memory.db" ] && command -v sqlite3 &> /dev/null; then
        MEMORY_COUNT=$(sqlite3 "$DATA_DIR/heimdall/cognitive_memory.db" "SELECT COUNT(*) FROM memories;" 2>/dev/null || echo "N/A")
    else
        MEMORY_COUNT="N/A"
    fi
else
    DATA_EXISTS=false
fi

# Check container status
CONTAINERS_RUNNING=0
if docker ps --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
    ((CONTAINERS_RUNNING++))
fi
if docker ps --format "{{.Names}}" | grep -q "$QDRANT_CONTAINER"; then
    ((CONTAINERS_RUNNING++))
fi

echo -e "${BLUE}🎯 Key Metrics${NC}"
echo "-------------"
if [ "$IMAGE_EXISTS" = true ]; then
    echo -e "Docker Image: ${YELLOW}$IMAGE_SIZE_HUMAN${NC}"
else
    echo -e "Docker Image: ${RED}Not built${NC}"
fi

if [ "$DATA_EXISTS" = true ]; then
    echo -e "Data Storage: ${YELLOW}$TOTAL_SIZE_HUMAN${NC}"
    echo -e "Memory Records: ${YELLOW}$MEMORY_COUNT${NC}"
else
    echo -e "Data Storage: ${RED}Not initialized${NC}"
fi

if [ $CONTAINERS_RUNNING -eq 0 ]; then
    echo -e "Status: ${YELLOW}No containers running${NC}"
elif [ $CONTAINERS_RUNNING -eq 1 ]; then
    echo -e "Status: ${GREEN}1 container running${NC}"
else
    echo -e "Status: ${GREEN}$CONTAINERS_RUNNING containers running${NC}"
fi

if [ "$DATA_EXISTS" = true ]; then
    echo -e "\n${BLUE}📦 Storage Breakdown${NC}"
    echo "-------------------"
    echo -e "Data Directory: ${CYAN}$TOTAL_SIZE_HUMAN${NC}"

    # Clean directory listing
    du -sh "$DATA_DIR"/* 2>/dev/null | sort -hr | while read size dir; do
        dir_name=$(basename "$dir")
        case $dir_name in
            "qdrant") echo -e "├── Qdrant vectors: ${YELLOW}$size${NC}" ;;
            "heimdall") echo -e "├── Cognitive DB: ${YELLOW}$size${NC}" ;;
            "models") echo -e "├── Models: ${YELLOW}$size${NC}" ;;
            "logs") echo -e "├── Logs: ${YELLOW}$size${NC}" ;;
            *) echo -e "├── $dir_name: ${YELLOW}$size${NC}" ;;
        esac
    done
fi

if [ "$IMAGE_EXISTS" = true ]; then
    echo -e "\n${BLUE}🐳 Docker Image${NC}"
    echo "---------------"
    echo -e "Image: ${GREEN}$IMAGE_NAME${NC}"
    echo -e "Size: ${YELLOW}$IMAGE_SIZE_HUMAN${NC}"

    # Base image comparison
    BASE_SIZE=$(docker image inspect python:3.13-slim --format='{{.Size}}' 2>/dev/null || echo 0)
    if [[ $BASE_SIZE -gt 0 ]]; then
        ADDED_SIZE=$((IMAGE_SIZE - BASE_SIZE))
        echo -e "├── Base (python:3.13-slim): ${YELLOW}$(human_readable $BASE_SIZE)${NC}"
        echo -e "└── Added by build: ${YELLOW}$(human_readable $ADDED_SIZE)${NC}"
    fi
fi

# Container status
echo -e "\n${BLUE}🏃 Container Status${NC}"
echo "------------------"
FOUND_CONTAINERS=false
for container in "$CONTAINER_NAME" "$QDRANT_CONTAINER"; do
    if docker container inspect "$container" &> /dev/null; then
        FOUND_CONTAINERS=true
        if docker ps --format "{{.Names}}" | grep -q "$container"; then
            STATS=$(docker stats "$container" --no-stream --format "{{.MemUsage}}\t{{.CPUPerc}}" 2>/dev/null || echo "N/A N/A")
            MEM_USAGE=$(echo "$STATS" | awk '{print $1}')
            CPU_USAGE=$(echo "$STATS" | awk '{print $2}')
            echo -e "${GREEN}●${NC} $(basename $container): Running (${YELLOW}$MEM_USAGE${NC} RAM, ${YELLOW}$CPU_USAGE${NC} CPU)"
        else
            echo -e "${YELLOW}○${NC} $(basename $container): Stopped"
        fi
    fi
done

if [ "$FOUND_CONTAINERS" = false ]; then
    echo -e "${YELLOW}No containers for this project${NC}"

    # Check for other Heimdall projects
    OTHER_HEIMDALL=$(docker ps --format "{{.Names}}" | grep -E "^(heimdall|qdrant)-.*-[a-f0-9]{8}$" | wc -l)
    if [ "$OTHER_HEIMDALL" -gt 0 ]; then
        echo -e "${CYAN}Other Heimdall projects running:${NC}"
        # Use process substitution to avoid subshell issues
        while IFS= read -r name; do
            if [[ "$name" == heimdall-* ]]; then
                project=$(echo "$name" | sed -E 's/heimdall-(.+)-[a-f0-9]{8}/\1/')
                echo -e "  ${GREEN}●${NC} $project"
            fi
        done < <(docker ps --format "{{.Names}}" | grep -E "^heimdall-.*-[a-f0-9]{8}$")
    fi
fi

# Docker system overview
echo -e "\n${BLUE}🐳 Docker System${NC}"
echo "----------------"
DOCKER_STATS=$(docker system df)
IMAGES_LINE=$(echo "$DOCKER_STATS" | grep "Images")
CONTAINERS_LINE=$(echo "$DOCKER_STATS" | grep "Containers")
VOLUMES_LINE=$(echo "$DOCKER_STATS" | grep "Volumes")

echo -e "Images: $(echo "$IMAGES_LINE" | awk '{print $2}') total, $(echo "$IMAGES_LINE" | awk '{print $3}') active ($(echo "$IMAGES_LINE" | awk '{print $4}'))"
echo -e "Containers: $(echo "$CONTAINERS_LINE" | awk '{print $2}') total, $(echo "$CONTAINERS_LINE" | awk '{print $3}') active"

# List all Docker images
echo -e "\n${CYAN}All Docker Images:${NC}"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" | head -10

# Cleanup opportunities
UNUSED_IMAGES=$(docker images -f "dangling=true" -q | wc -l)
ALL_IMAGES=$(docker images -q | wc -l)
USED_IMAGES=$(docker ps -a --format "{{.Image}}" | sort -u | wc -l)

echo -e "\n${BLUE}🧹 Cleanup Opportunities${NC}"
echo "------------------------"
if [[ $UNUSED_IMAGES -gt 0 ]]; then
    echo -e "${YELLOW}⚠️${NC}  Dangling images: $UNUSED_IMAGES"
    # Show details of dangling images and check if they're Heimdall-related
    docker images -f "dangling=true" --format "{{.ID}}\t{{.Size}}\t{{.CreatedSince}}" | while read id size created; do
        # Check if size matches known Heimdall images (likely 600-800MB range)
        if [[ "$size" =~ ^[67][0-9][0-9]MB$ ]]; then
            echo -e "    ${CYAN}$id${NC} ($size, created $created) ${YELLOW}[likely Heimdall build]${NC}"
        else
            echo -e "    ${CYAN}$id${NC} ($size, created $created)"
        fi
    done
fi
echo -e "Unused images: $((ALL_IMAGES - USED_IMAGES)) of $ALL_IMAGES total"

echo -e "\n${CYAN}Quick cleanup commands:${NC}"
echo "# Remove this project:"
echo "$SCRIPT_DIR/setup_project_memory.sh --cleanup"
echo ""
echo "# Remove dangling images:"
echo "docker image prune -f"

# Recommendations
echo -e "\n${BLUE}💡 Recommendations${NC}"
echo "------------------"
if [ "$IMAGE_EXISTS" = true ] && [[ $IMAGE_SIZE -gt 1073741824 ]]; then
    echo -e "${YELLOW}⚠️${NC}  Image over 1GB - consider optimization"
fi

if [ "$DATA_EXISTS" = true ]; then
    echo -e "${GREEN}✅${NC} Data usage is healthy ($TOTAL_SIZE_HUMAN)"
else
    echo -e "${YELLOW}ℹ️${NC}  Run setup to initialize data directory"
fi

echo -e "\n${GREEN}✅ Analysis complete${NC}"
