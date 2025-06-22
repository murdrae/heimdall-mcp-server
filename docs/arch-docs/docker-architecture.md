# Docker Container Implementation for Cognitive Memory MCP Server

## Overview
Project-scoped Docker containerization strategy for the cognitive memory MCP server that provides automatic project isolation while maintaining a clean MCP interface. Solves PATH dependency issues and enables proper multi-project support without requiring project parameters in MCP tools.

## Core Architecture: Project-Scoped Container Instances

### Design Principle
Each project directory automatically gets its own isolated MCP server instance using deterministic resource allocation based on project path hashing.

### Project Isolation Strategy
```
Project A (/path/to/project-a/)
├── Container: heimdall-project-a-a1b2c3d4 (port 6333+hash)
├── Qdrant Container: qdrant-project-a-a1b2c3d4
├── Data Volume: cognitive-data-a1b2c3d4
├── Qdrant Collections: a1b2c3d4-concepts, a1b2c3d4-contexts, a1b2c3d4-episodes
└── Claude Config: --scope project (project-specific MCP)

Project B (/path/to/project-b/)
├── Container: heimdall-project-b-e5f6g7h8 (port 6333+hash)
├── Qdrant Container: qdrant-project-b-e5f6g7h8
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
REPO_NAME=$(basename "$PROJECT_PATH")
HASH_DECIMAL=$((16#$(echo "$PROJECT_HASH" | cut -c1-3)))
QDRANT_PORT=$((6333 + ($HASH_DECIMAL % 1000)))
CONTAINER_PREFIX="heimdall-$REPO_NAME-$PROJECT_HASH"
QDRANT_CONTAINER="qdrant-$REPO_NAME-$PROJECT_HASH"
VOLUME_NAME="cognitive-data-$PROJECT_HASH"
NETWORK_NAME="cognitive-network-$PROJECT_HASH"
```

## Architecture Implementation

### Transport Strategy: STDIO with Container Integration
The implementation uses stdio transport with a wrapper script instead of HTTP for simplicity and reliability.

#### Key Components
- **MCP Server**: Stdio transport (`interfaces/mcp_server.py`)
- **Container Integration**: Via `claude_mcp_wrapper.sh` script
- **Claude Code Integration**: `--transport stdio` with wrapper script
- **Health Monitoring**: Built into Docker containers via `memory_system doctor`

### Project-Aware Container Architecture
Automatic project isolation without user intervention through deterministic resource allocation.

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
│  │   a1b2c3d4-*    │◄───┤  STDIO MCP via wrapper         │  │
│  │   :6333         │    │  Project: a1b2c3d4             │  │
│  └─────────────────┘    └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                    │
                            STDIO MCP Protocol
                                    │
                         ┌─────────────────────┐
                         │   Claude Code       │
                         │   Project A Scope   │
                         └─────────────────────┘
```

### Docker Infrastructure
Production-ready container infrastructure with script management.

#### Implemented File Structure
```
cognitive-memory/
├── docker/
│   ├── Dockerfile                     # Multi-stage application container
│   ├── docker-compose.template.yml    # Template for project-specific setup
│   ├── entrypoint.sh                  # Container startup script
│   └── healthcheck.sh                 # Health monitoring script
├── scripts/
│   ├── setup_project_memory.sh        # Main setup script (includes all functionality)
│   └── claude_mcp_wrapper.sh          # MCP integration wrapper
├── .dockerignore                      # Build exclusions
└── setup_claude_code_mcp.sh           # Simple MCP setup wrapper
```

#### Implementation Notes
- **Simplified Scripts**: All functionality consolidated into `setup_project_memory.sh`
- **Built-in Features**: Setup script includes `--help`, `--cleanup`, `--rebuild` flags
- **No Backup Script**: Not implemented (can be added later if needed)
  - However, databases are persistent in `.cognitive-memory`

### Unifier Docker Setup Script
One-command setup for any project with all lifecycle management built-in.

#### Actual Implementation (`scripts/setup_project_memory.sh`)
```bash
# Key implementation details:
# 1. Data stored in project directory: $PROJECT_PATH/.cognitive-memory
# 2. STDIO transport instead of HTTP
# 3. All functionality (start/stop/cleanup) in one script

# Core functionality:
./scripts/setup_project_memory.sh           # Setup containers
./scripts/setup_project_memory.sh --cleanup # Remove project containers
./scripts/setup_project_memory.sh --rebuild # Force rebuild
./setup_claude_code_mcp.sh                  # Configure Claude Code MCP
```

#### Implementation Details
- **Project-specific data**: Stored in `$PROJECT_PATH/.cognitive-memory/`
- **Compose file**: `$PROJECT_PATH/.cognitive-memory/docker-compose.yml`
- **Built-in health waiting**: No separate script needed
- **STDIO MCP**: Uses `claude_mcp_wrapper.sh` instead of HTTP endpoints

#### Setup Flow Example
```bash
cd /path/to/my-react-project
./scripts/setup_project_memory.sh

# Simplified Output:
# 🧠 Setting up cognitive memory for project: my-react-project
# 📊 Project ID: a1b2c3d4
# 🚢 Starting containers on port 6456...
# ⏳ Waiting for services to be healthy...
# ✅ Qdrant ready
# ✅ Cognitive Memory MCP server ready
# 🎉 Setup complete! Project memory ready.
# Container names: heimdall-my-react-project-a1b2c3d4, qdrant-my-react-project-a1b2c3d4
```

### Container Lifecycle Management
Easy management of project-specific containers with simplified commands.

#### Simplified Management
All lifecycle management is built into the main setup script:

```bash
# Setup new project
./scripts/setup_project_memory.sh

# Clean up project containers and data
./scripts/setup_project_memory.sh --cleanup

# Force rebuild and restart
./scripts/setup_project_memory.sh --rebuild

# View help and options
./scripts/setup_project_memory.sh --help
```

#### Manual Container Management
For advanced users who need direct control:

```bash
# Start project containers manually
cd $PROJECT_PATH/.cognitive-memory
docker compose up -d

# Stop project containers
docker compose down

# List all cognitive memory containers
docker ps --filter "name=heimdall-"
```

### Enhanced Cognitive System Integration
Native project awareness throughout the system.

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
   db_path = f"/app/data/cognitive_memory.db"
   ```

3. **Bridge Discovery Scoping**
   ```python
   # Bridge discovery only within project scope
   def discover_bridges(query, project_id):
       # Only search within project-specific collections
       pass
   ```

#### Configuration Management

- All config in `../../cognitive_memory/core/config.py`

### Claude Code Integration Enhancement
Seamless project-scoped integration with Claude Code.

#### Integration Strategy
```bash
# Each project gets its own MCP server automatically
cd /path/to/project-a
/path/to/this/repo/setup_claude_code_mcp.sh
/path/to/this/repo/scripts/load_project_content.sh

# Repeat for other projects you will work on
```

#### Claude Code Workflow
1. **Project A**: User runs setup in project directory
2. **Container Creation**: Project-specific container starts with unique hash
3. **MCP Configuration**: Claude Code configured with project scope via stdio wrapper
4. **Isolation**: Memories only visible within Project A Claude sessions
5. **Project B**: Completely separate setup and memory space

## Technical Specifications

### Port Allocation Strategy
```bash
# Hash-based port allocation
PROJECT_HASH=$(echo $PROJECT_PATH | sha256sum | cut -c1-8)
QDRANT_PORT=$((6333 + 0x$PROJECT_HASH % 1000))

# Examples:
# /home/user/project-a    → a1b2c3d4 → port 6456
# /home/user/project-b    → e5f6g7h8 → port 6789
# /work/client-project    → f9a8b7c6 → port 7012
```

### Container Naming Convention
```bash
# Human-readable, collision-resistant naming with repo name
REPO_NAME=$(basename "$PROJECT_PATH")
CONTAINER_PREFIX="heimdall-${REPO_NAME}-${PROJECT_HASH}"
QDRANT_CONTAINER="qdrant-${REPO_NAME}-${PROJECT_HASH}"
VOLUME_NAME="cognitive-data-${PROJECT_HASH}"
NETWORK_NAME="cognitive-network-${PROJECT_HASH}"

# Examples:
# heimdall-my-react-app-a1b2c3d4
# qdrant-my-react-app-a1b2c3d4
# cognitive-data-a1b2c3d4
# cognitive-network-a1b2c3d4
```

### Data Persistence Strategy (Actual Implementation)
```
Project Data Layout:
$PROJECT_PATH/.heimdall-mcp/
├── docker-compose.yml           # Generated compose file
├── qdrant/                      # Qdrant vector data (host volume)
├── cognitive/                   # Application data (host volume)
│   ├── cognitive_memory.db      # SQLite database
│   └── logs/                    # Application logs
├── logs/                        # Container logs
└── models/                      # Cached ML models

Docker Volumes:
├── cognitive-qdrant-{hash}      # Qdrant data volume
├── cognitive-data-{hash}        # App data volume
└── cognitive-network-{hash}     # Isolated network
```

### Security Considerations
- **Network Isolation**: Each project gets its own Docker network
- **Volume Isolation**: Project-specific data volumes
- **Port Binding**: Only bind to localhost (127.0.0.1)
- **User Permissions**: Host user mapping via docker-compose
- **Resource Limits**: Memory and CPU constraints can be added

### Docker Container User Permissions

#### Permission Architecture
The system uses different user permission strategies for different containers:

1. **Heimdall MCP Container**: Runs as host user via `user: "${HOST_UID}:${HOST_GID}"` mapping
2. **Qdrant Container**: Runs as root (required by official Qdrant image design)

#### File Ownership Implications
- **Qdrant creates root-owned files** in mounted volumes (`/path/to/project/.heimdall-mcp/qdrant/`)
- **Host user cannot directly delete** these files with `rm -rf`
- **Standard Docker cleanup pattern** is implemented for proper file removal

#### Cleanup Requirements
**❌ Don't use `rm -rf .heimdall-mcp/`** - will fail with permission denied errors

**✅ Use the provided cleanup script:**
```bash
# Proper cleanup that handles root-owned files
/path/to/heimdall-mcp-server/scripts/cleanup_memory.sh --project
```

#### Technical Implementation
The cleanup script uses the standard Docker pattern for removing root-owned files:
```bash
# Uses temporary Alpine container with root privileges to remove files
docker run --rm -v "$PROJECT_DATA_DIR:/cleanup" alpine:latest rm -rf /cleanup/* /cleanup/.[!.]*
```

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
