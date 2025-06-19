# Docker Container Implementation Plan for Cognitive Memory MCP Server

## Overview
Create a project-scoped Docker containerization strategy for the cognitive memory MCP server that provides automatic project isolation while maintaining a clean MCP interface. This solves the current PATH issues and enables proper multi-project support without requiring project parameters in MCP tools.

## Problem Statement

### Current Issues
- **PATH Dependency**: MCP server fails with "spawn memory_system ENOENT" because Claude Code can't find the command
- **Project Contamination**: Single installation shares memory across all projects
- **Environment Complexity**: Requires Python virtual environment setup and dependency management
- **Deployment Difficulty**: Complex setup process with multiple moving parts

### Solution Requirements
- ✅ **Perfect Project Isolation**: Each project gets its own memory universe
- ✅ **Clean MCP Interface**: No project parameters in MCP tools
- ✅ **Simple Setup**: Single command deployment per project
- ✅ **Resource Efficiency**: Only active projects consume resources
- ✅ **Deterministic Behavior**: Same project always gets same resources

## Core Architecture: Project-Scoped Container Instances

### Design Principle
Each project directory automatically gets its own isolated MCP server instance using deterministic resource allocation based on project path hashing.

### Project Isolation Strategy
```
Project A (/path/to/project-a/)
├── Container: cognitive-memory-a1b2c3d4 (port 8080+hash)
├── Data Volume: cognitive-data-a1b2c3d4
├── Qdrant Collections: a1b2c3d4-concepts, a1b2c3d4-contexts, a1b2c3d4-episodes
└── Claude Config: --scope project (project-specific MCP)

Project B (/path/to/project-b/)
├── Container: cognitive-memory-e5f6g7h8 (port 8080+hash)
├── Data Volume: cognitive-data-e5f6g7h8
├── Qdrant Collections: e5f6g7h8-concepts, e5f6g7h8-contexts, e5f6g7h8-episodes
└── Claude Config: --scope project (project-specific MCP)
```

### Resource Allocation Algorithm
```bash
# Deterministic project identification
PROJECT_PATH=$(pwd)
PROJECT_HASH=$(echo $PROJECT_PATH | sha256sum | cut -c1-8)

# Deterministic resource allocation
PROJECT_PORT=$((8080 + 0x$PROJECT_HASH % 1000))
CONTAINER_NAME="cognitive-memory-$PROJECT_HASH"
VOLUME_NAME="cognitive-data-$PROJECT_HASH"
NETWORK_NAME="cognitive-network-$PROJECT_HASH"
```

## Implementation Phases

### Phase 1: HTTP Transport Enhancement
**Status**: Critical Priority
**Problem**: Current MCP server only supports stdio transport, incompatible with containers

#### Changes Required
1. **Enhanced MCP Server** (`interfaces/mcp_server.py`)
   - Add HTTP transport support alongside existing stdio
   - Implement FastAPI/Starlette integration
   - Add health check endpoints (`/health`, `/status`)
   - Support CORS for local development

2. **Server Modes**
   ```python
   # Stdio mode (current)
   memory_system serve mcp

   # HTTP mode (new)
   memory_system serve mcp --http --port 8080 --host 0.0.0.0
   ```

3. **HTTP Endpoints**
   ```
   POST /mcp/call    # MCP tool calls
   GET  /health      # Health check
   GET  /status      # System status
   GET  /metrics     # Prometheus metrics (future)
   ```

### Phase 2: Project-Aware Container Architecture
**Status**: Critical Priority
**Goal**: Enable automatic project isolation without user intervention

#### Core Components

1. **Project Detection System**
   - Hash-based project identification from directory path
   - Collision detection and resolution
   - Project metadata storage

2. **Deterministic Resource Allocation**
   - Consistent ports based on project hash
   - Predictable container and volume names
   - Isolated Docker networks per project

3. **Cognitive System Enhancements**
   - Project-aware Qdrant collection naming
   - Isolated SQLite databases per project
   - Project-scoped bridge discovery

#### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                Project A Container Network                  │
│                                                             │
│  ┌─────────────────┐    ┌────────────────────────────────┐  │
│  │   Qdrant        │    │  Cognitive Memory MCP Server   │  │
│  │   Collections:  │    │                                │  │
│  │   a1b2c3d4-*    │◄───┤  HTTP MCP :8123                │  │
│  │   :6333         │    │  Project: a1b2c3d4             │  │
│  └─────────────────┘    └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                    │
                            HTTP MCP Protocol
                                    │
                         ┌─────────────────────┐
                         │   Claude Code       │
                         │   Project A Scope   │
                         └─────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                Project B Container Network                  │
│                                                             │
│  ┌─────────────────┐    ┌────────────────────────────────┐  │
│  │   Qdrant        │    │  Cognitive Memory MCP Server   │  │
│  │   Collections:  │    │                                │  │
│  │   e5f6g7h8-*    │◄───┤  HTTP MCP :8456                │  │
│  │   :6333         │    │  Project: e5f6g7h8             │  │
│  └─────────────────┘    └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                    │
                            HTTP MCP Protocol
                                    │
                         ┌─────────────────────┐
                         │   Claude Code       │
                         │   Project B Scope   │
                         └─────────────────────┘
```

### Phase 3: Docker Infrastructure
**Status**: High Priority
**Goal**: Create robust, production-ready container infrastructure

#### File Structure
```
cognitive-memory/
├── docker/
│   ├── Dockerfile                     # Multi-stage application container
│   ├── docker-compose.template.yml    # Template for project-specific setup
│   ├── entrypoint.sh                  # Container startup script
│   ├── healthcheck.sh                 # Health monitoring script
│   └── wait-for-it.sh                 # Service dependency waiter
├── scripts/
│   ├── setup_project_memory.sh        # Main setup script
│   ├── start_memory.sh                # Start project memory system
│   ├── stop_memory.sh                 # Stop project memory system
│   ├── list_memory_projects.sh        # List all project containers
│   ├── cleanup_memory.sh              # Clean unused containers
│   └── backup_project_memory.sh       # Backup project data
├── .dockerignore                      # Build exclusions
└── docker-compose.override.yml.example # Local development overrides
```

#### Dockerfile Design
```dockerfile
# Multi-stage build for efficiency
FROM python:3.13-slim as builder
# Install dependencies and build wheels

FROM python:3.13-slim as runtime
# Copy wheels and install
# Pre-download sentence-transformers models
# Configure non-root user
# Set up entrypoint
```

#### Docker Compose Template
```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-${PROJECT_HASH}
    volumes:
      - qdrant-data-${PROJECT_HASH}:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
    networks:
      - cognitive-network-${PROJECT_HASH}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 5

  cognitive-memory:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: cognitive-memory-${PROJECT_HASH}
    ports:
      - "${PROJECT_PORT}:8080"
    volumes:
      - cognitive-data-${PROJECT_HASH}:/app/data
      - model-cache-${PROJECT_HASH}:/app/models
    environment:
      - PROJECT_ID=${PROJECT_HASH}
      - PROJECT_PATH=${PROJECT_PATH}
      - QDRANT_URL=http://qdrant:6333
      - QDRANT_COLLECTION_PREFIX=${PROJECT_HASH}
      - MCP_SERVER_HOST=0.0.0.0
      - MCP_SERVER_PORT=8080
      - SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
      - COGNITIVE_MEMORY_DB_PATH=/app/data/cognitive_memory.db
    depends_on:
      qdrant:
        condition: service_healthy
    networks:
      - cognitive-network-${PROJECT_HASH}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

networks:
  cognitive-network-${PROJECT_HASH}:
    driver: bridge

volumes:
  qdrant-data-${PROJECT_HASH}:
  cognitive-data-${PROJECT_HASH}:
  model-cache-${PROJECT_HASH}:
```

### Phase 4: Smart Setup Script
**Status**: High Priority
**Goal**: One-command setup for any project

#### Main Setup Script (`scripts/setup_project_memory.sh`)
```bash
#!/bin/bash
# Project-scoped cognitive memory setup

# 1. Project Detection
PROJECT_PATH=$(pwd)
PROJECT_HASH=$(echo $PROJECT_PATH | sha256sum | cut -c1-8)
PROJECT_PORT=$((8080 + 0x$PROJECT_HASH % 1000))

# 2. Docker Environment Setup
export PROJECT_HASH PROJECT_PATH PROJECT_PORT

# 3. Generate project-specific Docker Compose
envsubst < docker/docker-compose.template.yml > .cognitive-memory-compose.yml

# 4. Start containers
docker-compose -f .cognitive-memory-compose.yml up -d

# 5. Wait for health checks
./scripts/wait_for_health.sh $PROJECT_PORT

# 6. Configure Claude Code
claude mcp add --scope project \
  --transport http \
  cognitive-memory \
  http://localhost:$PROJECT_PORT/mcp

# 7. Verify setup
./scripts/verify_setup.sh $PROJECT_PORT
```

#### Setup Flow Example
```bash
cd /path/to/my-react-project
./scripts/setup_project_memory.sh

# Output:
# 🧠 Setting up cognitive memory for project: my-react-project
# 📊 Project ID: a1b2c3d4
# 🚢 Starting containers on port 8123...
# ⏳ Waiting for services to be healthy...
# ✅ Qdrant ready
# ✅ Cognitive Memory MCP server ready
# 🔗 Configuring Claude Code...
# ✅ MCP server added: cognitive-memory
# 🎉 Setup complete! Project memory ready.
```

### Phase 5: Container Lifecycle Management
**Status**: Medium Priority
**Goal**: Easy management of project-specific containers

#### Management Commands

1. **Start Memory System** (`scripts/start_memory.sh`)
   ```bash
   #!/bin/bash
   # Start cognitive memory for current project
   PROJECT_HASH=$(echo $(pwd) | sha256sum | cut -c1-8)
   docker-compose -f .cognitive-memory-compose.yml up -d
   ```

2. **Stop Memory System** (`scripts/stop_memory.sh`)
   ```bash
   #!/bin/bash
   # Stop cognitive memory for current project
   PROJECT_HASH=$(echo $(pwd) | sha256sum | cut -c1-8)
   docker-compose -f .cognitive-memory-compose.yml down
   ```

3. **List All Projects** (`scripts/list_memory_projects.sh`)
   ```bash
   #!/bin/bash
   # List all cognitive memory projects
   echo "Active Cognitive Memory Projects:"
   docker ps --filter "name=cognitive-memory-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```

4. **Cleanup Unused** (`scripts/cleanup_memory.sh`)
   ```bash
   #!/bin/bash
   # Clean up stopped containers and unused volumes
   docker container prune -f --filter "label=cognitive-memory"
   docker volume prune -f --filter "label=cognitive-memory"
   ```

#### Container States
- **Active**: Running and serving MCP requests
- **Stopped**: Container exists but not running (data preserved)
- **Removed**: Completely cleaned up (data can be preserved in volumes)

### Phase 6: Enhanced Cognitive System Integration
**Status**: Medium Priority
**Goal**: Native project awareness throughout the system

#### Project Namespace Support

1. **Qdrant Collection Naming**
   ```python
   # Before: "cognitive_concepts"
   # After:  "a1b2c3d4-cognitive_concepts"

   collection_name = f"{project_id}-{base_collection_name}"
   ```

2. **SQLite Database Isolation**
   ```python
   # Each project gets its own database file
   db_path = f"/app/data/{project_id}/cognitive_memory.db"
   ```

3. **Bridge Discovery Scoping**
   ```python
   # Bridge discovery only within project scope
   def discover_bridges(query, project_id):
       # Only search within project-specific collections
       pass
   ```

#### Configuration Management
```python
# Project-aware configuration
@dataclass
class ProjectConfig:
    project_id: str
    project_path: str
    qdrant_collection_prefix: str
    database_path: str
    model_cache_path: str
```

### Phase 7: Claude Code Integration Enhancement
**Status**: High Priority
**Goal**: Seamless project-scoped integration

#### Updated Integration Strategy
```bash
# Each project gets its own MCP server automatically
cd /path/to/project-a
./scripts/setup_project_memory.sh
# → claude mcp add --scope project cognitive-memory http://localhost:8123/mcp

cd /path/to/project-b
./scripts/setup_project_memory.sh
# → claude mcp add --scope project cognitive-memory http://localhost:8456/mcp
```

#### Claude Code Workflow
1. **Project A**: User runs setup in project directory
2. **Container Creation**: Project-specific container starts on unique port
3. **MCP Configuration**: Claude Code configured with project scope
4. **Isolation**: Memories only visible within Project A Claude sessions
5. **Project B**: Completely separate setup and memory space

#### Benefits
- ✅ **Clean MCP Interface**: No project parameters needed in tools
- ✅ **Automatic Project Detection**: Based on Claude Code's project context
- ✅ **Perfect Isolation**: No cross-contamination between projects
- ✅ **Natural Workflow**: Fits existing Claude Code project management

## Technical Specifications

### Port Allocation Strategy
```bash
# Hash-based port allocation
PROJECT_HASH=$(echo $PROJECT_PATH | sha256sum | cut -c1-8)
PROJECT_PORT=$((8080 + 0x$PROJECT_HASH % 1000))

# Examples:
# /home/user/project-a    → a1b2c3d4 → port 8123
# /home/user/project-b    → e5f6g7h8 → port 8456
# /work/client-project    → f9a8b7c6 → port 8789
```

### Container Naming Convention
```bash
# Predictable, collision-resistant naming
CONTAINER_NAME="cognitive-memory-${PROJECT_HASH}"
VOLUME_NAME="cognitive-data-${PROJECT_HASH}"
NETWORK_NAME="cognitive-network-${PROJECT_HASH}"

# Examples:
# cognitive-memory-a1b2c3d4
# cognitive-data-a1b2c3d4
# cognitive-network-a1b2c3d4
```

### Data Persistence Strategy
```
Project Data Layout:
/var/lib/docker/volumes/
├── cognitive-data-a1b2c3d4/
│   ├── cognitive_memory.db      # SQLite database
│   ├── logs/                    # Application logs
│   └── backups/                 # Automated backups
├── qdrant-data-a1b2c3d4/
│   └── storage/                 # Qdrant vector data
└── model-cache-a1b2c3d4/
    └── sentence-transformers/   # Cached ML models
```

### Health Check Strategy
```yaml
# Container health checks
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Security Considerations
- **Network Isolation**: Each project gets its own Docker network
- **Volume Isolation**: Project-specific data volumes
- **Port Binding**: Only bind to localhost (127.0.0.1)
- **User Permissions**: Non-root container user
- **Resource Limits**: Memory and CPU constraints

## Benefits Summary

### For Users
1. **Zero Configuration**: Run one script, everything works
2. **Perfect Isolation**: Projects can't interfere with each other
3. **Clean Interface**: No project management in MCP tools
4. **Portable**: Works on any system with Docker
5. **Resource Efficient**: Only active projects consume resources

### For Developers
1. **Maintainable**: Clear separation of concerns
2. **Testable**: Each project is an isolated test environment
3. **Scalable**: Support unlimited projects
4. **Debuggable**: Project-specific logs and monitoring
5. **Extensible**: Easy to add new features per project

### For Operations
1. **Monitoring**: Per-project health checks and metrics
2. **Backup**: Project-specific data backup strategies
3. **Cleanup**: Easy identification and removal of unused resources
4. **Security**: Isolated networks and data volumes
5. **Updates**: Rolling updates without affecting other projects

## Implementation Timeline

### Week 1: Core Infrastructure
- [ ] HTTP transport enhancement
- [ ] Basic Dockerfile and compose template
- [ ] Project detection and hashing logic

### Week 2: Container Management
- [ ] Setup and lifecycle scripts
- [ ] Health checking and monitoring
- [ ] Claude Code integration updates

### Week 3: Testing and Refinement
- [ ] Multi-project testing scenarios
- [ ] Performance optimization
- [ ] Documentation and examples

### Week 4: Production Readiness
- [ ] Security hardening
- [ ] Backup and restore procedures
- [ ] CI/CD integration

## Risk Mitigation

### Port Conflicts
- **Risk**: Hash collisions leading to port conflicts
- **Mitigation**: Collision detection with automatic port adjustment
- **Fallback**: Manual port specification option

### Resource Management
- **Risk**: Too many containers consuming resources
- **Mitigation**: Container resource limits and cleanup procedures
- **Monitoring**: Resource usage tracking and alerts

### Data Persistence
- **Risk**: Volume data loss during container updates
- **Mitigation**: Backup procedures and volume preservation
- **Recovery**: Data restore and migration tools

### Service Dependencies
- **Risk**: Services failing to start in correct order
- **Mitigation**: Health checks and dependency management
- **Monitoring**: Service health dashboards

## Success Metrics

### Technical Metrics
- ✅ Zero PATH-related errors
- ✅ 100% project isolation (no memory leakage between projects)
- ✅ < 30 second setup time per project
- ✅ < 5% resource overhead compared to native installation

### User Experience Metrics
- ✅ One-command setup per project
- ✅ Zero manual configuration required
- ✅ Seamless Claude Code integration
- ✅ Intuitive project management

This implementation plan provides a robust, scalable solution for project-scoped cognitive memory that solves the current PATH issues while enabling clean multi-project support through Docker containerization.
