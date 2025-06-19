# MCP Server Architecture for Cognitive Memory System

## Overview

This document describes the architecture and implementation of a Model Context Protocol (MCP) server for the cognitive memory system. The MCP server provides LLMs with secure, controlled access to cognitive memory operations through a standardized interface, enabling persistent memory across conversations and intelligent knowledge consolidation.

## Table of Contents

1. [Architecture Foundation](#architecture-foundation)
2. [Data Structures & Memory Types](#data-structures--memory-types)
3. [MCP Tool Specifications](#mcp-tool-specifications)
4. [Response Format Design](#response-format-design)
5. [Session Lessons Framework](#session-lessons-framework)
6. [Implementation Approach](#implementation-approach)
7. [Service Integration](#service-integration)
8. [Example Interactions](#example-interactions)
9. [Setup & Configuration](#setup--configuration)
10. [Implementation Steps](#implementation-steps)

## Architecture Foundation

### Design Principles

The MCP server follows a **wrapper-based architecture** that leverages existing cognitive memory infrastructure rather than reimplementing functionality:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   MCP Server    │    │ CognitiveCLI    │
│  (Claude, etc.) │◄──►│   (Wrapper)     │◄──►│   (Existing)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                        │
                               │                        ▼
                               │               ┌─────────────────┐
                               │               │ CognitiveSystem │
                               │               │   (Core Logic)  │
                               │               └─────────────────┘
                               ▼
                    ┌─────────────────────────┐
                    │ Memory System Services  │
                    │ (Qdrant, SQLite, etc.) │
                    └─────────────────────────┘
```

### Technology Stack

- **MCP SDK**: Official Python MCP SDK (`modelcontextprotocol/python-sdk`)
- **Transport Methods**: 
  - stdio (Standard Input/Output) - for local integrations
  - HTTP with Server-Sent Events (SSE) - for remote access
- **Integration Layer**: Wraps `interfaces/cli.py::CognitiveCLI`
- **Service Management**: Integrates with `memory_system/cli.py` service layer

### Core Components

1. **MCP Server Wrapper**: Translates MCP protocol to CognitiveCLI method calls
2. **Tool Registry**: Defines and manages the 4 core MCP tools
3. **Response Formatter**: Structures cognitive memory data for LLM consumption
4. **Service Bridge**: Connects to existing Qdrant and cognitive system services

## Data Structures & Memory Types

### CognitiveMemory Structure

The cognitive memory system uses rich data structures that provide extensive context for LLMs. The core `CognitiveMemory` class is already defined in `cognitive_memory/core/memory.py` and is actively used throughout the system:

```python
@dataclass
class CognitiveMemory:
    # Core identification
    id: str                                    # Unique memory identifier
    content: str                              # Main memory content
    
    # Hierarchical organization
    hierarchy_level: int                      # 0=Concepts, 1=Contexts, 2=Episodes
    memory_type: str                         # 'episodic' or 'semantic'
    
    # Temporal context (critical for LLM ranking)
    created_date: datetime                   # When memory was created
    modified_date: datetime | None           # When source was last modified
    source_date: datetime | None             # Original source date (commit, doc date)
    timestamp: datetime                      # Storage timestamp
    last_accessed: datetime                  # Last retrieval time
    
    # Activation and importance
    access_count: int                        # Usage frequency
    importance_score: float                  # Memory importance (0.0-1.0)
    strength: float                          # Memory strength (0.0-1.0)
    
    # Rich metadata
    metadata: dict[str, Any]                 # Extensible metadata
    tags: list[str] | None                   # Categorization tags
    
    # Embeddings and dimensions
    cognitive_embedding: torch.Tensor | None # 384D vector
    dimensions: dict[str, torch.Tensor]      # Multi-dimensional encoding
```

### Memory Types & Hierarchies

**Hierarchy Levels:**
- **L0 (Concepts)**: Abstract concepts, patterns, principles
- **L1 (Contexts)**: Contextual information, domain knowledge
- **L2 (Episodes)**: Specific experiences, interactions, events

**Memory Categories:**
- **Core Memories**: Highly relevant, recently accessed
- **Peripheral Memories**: Related but less central to current context
- **Bridge Memories**: Create novel connections between distant concepts (see `BridgeMemory` class in `cognitive_memory/core/memory.py`)

**Source Types** (identified via metadata):
- **Manual Storage**: User-provided experiences (`loader_type: null`)
- **Markdown Files**: Documentation, notes (`loader_type: "markdown"`)
- **Git Patterns**: Code repository insights (`loader_type: "git"`)
- **Session Lessons**: LLM-generated learning summaries (`loader_type: "session_lesson"`)

### Source Information Display

The system uses rich visual formatting for memory sources, leveraging the existing `format_source_info()` function from `memory_system/display_utils.py`:

```
📄 filename.md → Section Title         (Markdown files)
🔄 repo-name → file1.py ↔ file2.py    (Git co-change patterns)
🔥 repo-name → hotfile.py              (Git maintenance hotspots)  
💡 repo-name → solution                (Git solution patterns)
📝 Session Lesson                      (LLM-generated insights)
```

## MCP Tool Specifications

### 1. `store_memory`

**Purpose**: Store new experiences or knowledge in cognitive memory

**Wrapper Target**: `CognitiveCLI.store_experience()`

**Input Schema**:
```json
{
  "text": "string (required) - Content to store",
  "context": {
    "hierarchy_level": "integer (optional) - 0=concept, 1=context, 2=episode",
    "memory_type": "string (optional) - episodic|semantic", 
    "importance_score": "float (optional) - 0.0-1.0",
    "tags": "array[string] (optional) - Categorization tags",
    "source_info": "string (optional) - Source description"
  }
}
```

**Output Schema**:
```json
{
  "success": true,
  "memory_id": "uuid-string",
  "hierarchy_level": 2,
  "memory_type": "episodic",
  "stored_at": "2024-01-15T10:30:00Z",
  "message": "✓ Experience stored successfully"
}
```

### 2. `recall_memories`

**Purpose**: Retrieve memories based on query with rich contextual information

**Wrapper Target**: `CognitiveCLI.retrieve_memories()`

**Input Schema**:
```json
{
  "query": "string (required) - Search query",
  "types": "array[string] (optional) - [core|peripheral|bridge], default: all",
  "max_results": "integer (optional) - Maximum memories to return, default: 10",
  "include_bridges": "boolean (optional) - Include bridge discoveries, default: true"
}
```

**Output Schema**:
```json
{
  "success": true,
  "query": "authentication issues",
  "total_results": 15,
  "memories": {
    "core": [
      {
        "id": "uuid-string",
        "content": "Had trouble debugging the authentication flow...",
        "hierarchy_level": 2,
        "memory_type": "episodic",
        "similarity_score": 0.89,
        "strength": 0.75,
        "source_info": "📄 troubleshooting.md → Auth Issues",
        "created_date": "2024-01-10T14:22:00Z",
        "last_accessed": "2024-01-15T09:15:00Z",
        "access_count": 3,
        "metadata": {
          "loader_type": "markdown",
          "source_path": "/docs/troubleshooting.md",
          "title": "Auth Issues"
        }
      }
    ],
    "peripheral": [...],
    "bridge": [
      {
        "id": "uuid-string",
        "content": "Database connection pooling patterns...",
        "bridge_score": 0.82,
        "novelty_score": 0.91,
        "connection_potential": 0.76,
        "explanation": "Bridge connects authentication and database patterns",
        "source_info": "💡 backend-repo → solution"
      }
    ]
  }
}
```

### 3. `session_lessons`

**Purpose**: Capture and consolidate key learnings from current session for future reference

**Behavioral Design**: This tool encourages LLMs to practice "metacognitive reflection" - thinking about what they've learned and what would be valuable for future sessions after "critical amnesia."

**Wrapper Target**: `CognitiveCLI.store_experience()` with special metadata

**Input Schema**:
```json
{
  "lesson_content": "string (required) - Key insight or learning",
  "lesson_type": "string (optional) - discovery|pattern|solution|warning|context",
  "session_context": "string (optional) - What was being worked on",
  "importance": "string (optional) - low|medium|high|critical"
}
```

**Built-in Prompting**: The tool provides guidance to help LLMs create valuable session lessons:

> "Consider: What key insights, patterns, or discoveries from this session would be valuable for future interactions? What context about the current work would help a future session understand the situation? What approaches worked or failed? What warnings or gotchas should be remembered?"

**Output Schema**:
```json
{
  "success": true,
  "lesson_id": "uuid-string",
  "lesson_type": "discovery",
  "importance_level": "high",
  "stored_at": "2024-01-15T16:45:00Z",
  "message": "✓ Session lesson recorded for future reference",
  "suggestion": "Consider adding related context or follow-up insights"
}
```

**Special Metadata**: Session lessons are tagged with:
```json
{
  "loader_type": "session_lesson",
  "lesson_type": "discovery|pattern|solution|warning|context",
  "session_id": "session-uuid",
  "importance_level": "low|medium|high|critical"
}
```

### 4. `memory_status`

**Purpose**: Provide system health and memory statistics

**Wrapper Target**: `CognitiveCLI.show_status()`

**Input Schema**:
```json
{
  "detailed": "boolean (optional) - Include detailed configuration, default: false"
}
```

**Output Schema**:
```json
{
  "success": true,
  "system_status": "healthy",
  "memory_counts": {
    "total_memories": 1247,
    "level_0_concepts": 89,
    "level_1_contexts": 234,
    "level_2_episodes": 924,
    "episodic_memories": 856,
    "semantic_memories": 391,
    "session_lessons": 23
  },
  "storage_stats": {
    "qdrant_status": "running",
    "vector_count": 1247,
    "storage_size_mb": 45.2
  },
  "recent_activity": {
    "last_storage": "2024-01-15T16:45:00Z",
    "last_retrieval": "2024-01-15T16:50:00Z",
    "last_consolidation": "2024-01-14T02:00:00Z"
  },
  "configuration": {
    "activation_threshold": 0.7,
    "bridge_discovery_k": 5,
    "max_activations": 50,
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_dimensions": 384
  }
}
```

## Response Format Design

### Rich Metadata Strategy

The MCP server provides comprehensive metadata to give LLMs maximum context for decision-making:

**Always Include**:
- Source information with visual icons (📄🔄🔥💡📝)
- Hierarchy level and memory type
- All temporal data (created, modified, source dates)
- Similarity/strength scores
- Access patterns (count, last accessed)

**Conditional Include**:
- Bridge memory scoring (novelty, connection potential)
- Detailed metadata (based on relevance)
- Source-specific fields (file paths, git info, etc.)

### Memory Source Formatting

The existing `format_source_info()` function from `memory_system/display_utils.py` provides rich source context:

```python
def format_memory_source(memory: CognitiveMemory) -> str:
    """Generate rich source information for LLM context"""
    loader_type = memory.metadata.get("loader_type")
    
    if loader_type == "markdown":
        return f"📄 {file_name} → {section_title}"
    elif loader_type == "git":
        pattern_type = memory.metadata.get("pattern_type")
        if pattern_type == "cochange":
            return f"🔄 {repo_name} → {file_a} ↔ {file_b}"
        elif pattern_type == "hotspot":
            return f"🔥 {repo_name} → {hot_file}"
        elif pattern_type == "solution":
            return f"💡 {repo_name} → {solution_type}"
    elif loader_type == "session_lesson":
        lesson_type = memory.metadata.get("lesson_type", "insight")
        return f"📝 Session Lesson ({lesson_type})"
    else:
        return f"💭 Manual Entry"
```

## Session Lessons Framework

### Metacognitive Reflection Design

The session lessons system is designed to encourage LLMs to practice metacognitive reflection - thinking about their own thinking and learning process. This creates a feedback loop for continuous improvement.

### Lesson Categories

**Discovery Lessons**: New insights, patterns, or understanding
```
"Discovered that authentication issues often correlate with database connection problems in this codebase. The connection pool settings in auth middleware cause timeout cascades."
```

**Pattern Lessons**: Recurring themes or systematic approaches
```
"Pattern identified: When debugging React components, start with state inspection, then props, then useEffect dependencies. This sequence consistently reveals the root cause faster."
```

**Solution Lessons**: Specific technical solutions that worked
```
"Solution for memory leaks in long-running processes: Use weak references for event listeners and implement explicit cleanup in context managers."
```

**Warning Lessons**: Things to avoid or be cautious about
```
"Warning: Never modify the production database directly. Always use migrations. Found corrupted data from direct edits in user_profiles table."
```

**Context Lessons**: Situational context that affects future work
```
"Working on e-commerce platform redesign. Current focus is payment flow optimization. Key stakeholder concerns: PCI compliance and mobile UX. Tech debt in legacy checkout system blocking progress."
```

### Prompting Strategy

When the `session_lessons` tool is called, the MCP server provides contextual guidance:

```
Consider what would be valuable for a future session after complete amnesia:

• What key insights or discoveries emerged from this work?
• What patterns or systematic approaches proved effective?
• What technical solutions worked (or failed) and why?
• What context about the current project/problem would be essential?
• What warnings or gotchas should be remembered?
• What approaches or tools showed promise for future use?

Frame your lesson as if speaking to a future version of yourself who remembers nothing about this session but needs to pick up where you left off.
```

### Retrieval Optimization

Session lessons are optimized for future retrieval:

- **High Importance Weighting**: Automatically boosted in similarity searches
- **Temporal Relevance**: Recent lessons weighted higher
- **Cross-Session Linking**: Lessons can reference and build on previous insights
- **Searchable Metadata**: Lesson type, session context, importance level

## Implementation Approach

### Service Integration Architecture

```python
# interfaces/mcp_server.py

from mcp.server import Server
from mcp.types import Tool, TextContent
from interfaces.cli import CognitiveCLI  # Existing CLI wrapper
from cognitive_memory.main import initialize_system
from cognitive_memory.core.memory import CognitiveMemory, BridgeMemory  # Existing data types

class CognitiveMemoryMCPServer:
    def __init__(self, cognitive_system: CognitiveSystem):
        self.cli = CognitiveCLI(cognitive_system)  # Wrap existing CLI functionality
        self.server = Server("cognitive-memory")
        self._register_tools()
    
    def _register_tools(self):
        # Register all 4 MCP tools
        self.server.list_tools = self._list_tools
        self.server.call_tool = self._call_tool
    
    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        if name == "store_memory":
            return await self._store_memory(arguments)
        elif name == "recall_memories":
            return await self._recall_memories(arguments)
        elif name == "session_lessons":
            return await self._session_lessons(arguments)
        elif name == "memory_status":
            return await self._memory_status(arguments)
```

### Error Handling Strategy

**Graceful Degradation**:
- MCP server continues operating if Qdrant is temporarily unavailable
- Provides meaningful error messages to LLM clients
- Implements retry logic for transient failures

**Error Response Format**:
```json
{
  "success": false,
  "error": "qdrant_unavailable",
  "message": "Vector database temporarily unavailable. Memory storage queued for retry.",
  "retry_in_seconds": 30,
  "fallback_action": "cached_search_available"
}
```

### Configuration Management

**Environment Variables**:
```bash
# MCP Server Configuration
MCP_SERVER_PORT=8080                    # HTTP mode port (optional)
MCP_SERVER_MODE=stdio                   # stdio|http
MCP_MAX_MEMORIES_PER_QUERY=50          # Default limit for recall_memories

# Cognitive System Configuration  
QDRANT_URL=http://localhost:6333
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
COGNITIVE_MEMORY_DB_PATH=./data/cognitive_memory.db
```

**Configuration File Support**:
```python
# Load configuration from .env or explicit config file
cognitive_system = initialize_with_config(config_path) if config_path else initialize_system("default")
```

## Service Integration

### Integration with Memory System CLI

The MCP server integrates seamlessly with the existing service management layer:

```bash
# Start required services
memory_system qdrant start

# Start MCP server (stdio mode for Claude Desktop)
memory_system serve mcp

# Start MCP server (HTTP mode for remote access)  
memory_system serve mcp --port 8080
```

### Service Dependencies

**Required Services**:
1. **Qdrant Vector Database**: Must be running for vector operations
2. **SQLite Database**: Metadata persistence (auto-created)
3. **Sentence-BERT Model**: Embedding generation (auto-downloaded)

**Service Health Checking**:
```python
# Built-in health monitoring
async def check_service_health(self) -> dict:
    return {
        "qdrant": await self._check_qdrant_health(),
        "embeddings": await self._check_embedding_model(),
        "sqlite": await self._check_sqlite_connection(),
        "overall": "healthy|degraded|offline"
    }
```

### Startup Sequence

1. **Initialize Cognitive System**: Load configuration, connect to services
2. **Verify Dependencies**: Check Qdrant, SQLite, embedding model
3. **Register MCP Tools**: Set up tool definitions and handlers
4. **Start Transport**: Begin stdio or HTTP+SSE communication
5. **Ready Signal**: Indicate MCP server is ready for client connections

## Example Interactions

### Example 1: Storing a Discovery

**MCP Client Request**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "store_memory",
    "arguments": {
      "text": "Found that React components re-render unnecessarily when using object destructuring in useEffect dependencies. Using primitive values or useMemo resolves the issue.",
      "context": {
        "hierarchy_level": 1,
        "importance_score": 0.8,
        "tags": ["react", "performance", "hooks"],
        "source_info": "React optimization debugging session"
      }
    }
  }
}
```

**MCP Server Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "✓ Experience stored successfully\n\nMemory ID: f47ac10b-58cc-4372-a567-0e02b2c3d479\nHierarchy Level: L1 (Context)\nMemory Type: episodic\nImportance Score: 0.8\nStored At: 2024-01-15T16:30:00Z\n\nThis knowledge is now available for future recall and will contribute to React performance pattern recognition."
    }
  ]
}
```

### Example 2: Recalling Related Memories

**MCP Client Request**:
```json
{
  "method": "tools/call", 
  "params": {
    "name": "recall_memories",
    "arguments": {
      "query": "React performance optimization",
      "max_results": 5,
      "include_bridges": true
    }
  }
}
```

**MCP Server Response**:
```json
{
  "content": [
    {
      "type": "text", 
      "text": "📋 Retrieved 8 memories for: 'React performance optimization'\n\nCORE MEMORIES (3):\n\n1. [episodic] Found that React components re-render unnecessarily when using object destructuring...\n   ID: f47ac10b-58cc-4372-a567-0e02b2c3d479, Level: L1, Strength: 0.89\n   Source: 💭 Manual Entry\n   Created: 2024-01-15T16:30:00Z, Accessed: 1 times\n\n2. [semantic] React.memo and useMemo are key optimization tools for preventing unnecessary re-renders...\n   ID: a8b2c3d4-e5f6-7890-1234-567890abcdef, Level: L0, Strength: 0.82  \n   Source: 📄 react-guide.md → Performance Optimization\n   Created: 2024-01-10T09:15:00Z, Accessed: 5 times\n\n3. [episodic] Profiled app with React DevTools - identified UserProfile component as bottleneck...\n   ID: 9876543a-bcde-f012-3456-789abcdef012, Level: L2, Strength: 0.77\n   Source: 📝 Session Lesson (solution)\n   Created: 2024-01-12T14:20:00Z, Accessed: 2 times\n\nBRIDGE MEMORIES (1):\n\n1. [bridge] Database query optimization patterns show similar principles to React rendering optimization...\n   ID: bridge-123abc-def456, Level: L1, Bridge Score: 0.84\n   Novelty: 0.91, Connection: 0.78\n   Bridge connects React optimization with database performance patterns\n   Source: 💡 backend-repo → solution\n\nPERIPHERAL MEMORIES (4): [showing 2]\n\n5. [semantic] JavaScript memory management and garbage collection affects React app performance...\n   Source: 📄 js-performance.md → Memory Management\n\n6. [episodic] Bundle size optimization reduced initial load time by 40%...\n   Source: 📝 Session Lesson (discovery)"
    }
  ]
}
```

### Example 3: Recording Session Lessons

**MCP Client Request**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "session_lessons", 
    "arguments": {
      "lesson_content": "When debugging API integration issues, always check network tab first, then API logs, then client-side error handling. This sequence reveals 90% of integration problems quickly. Also discovered that the staging API has rate limiting enabled (50 req/min) which wasn't documented.",
      "lesson_type": "pattern",
      "session_context": "Working on payment API integration for e-commerce checkout flow",
      "importance": "high"
    }
  }
}
```

**MCP Server Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "✓ Session lesson recorded for future reference\n\nLesson ID: lesson-abc123-def456\nLesson Type: pattern\nImportance Level: high\nStored At: 2024-01-15T17:45:00Z\n\nThis lesson captures both a systematic debugging approach and specific environmental knowledge about the staging API. It will be prioritized in future recalls related to API integration work.\n\n💡 Suggestion: Consider adding a follow-up lesson about the specific payment API endpoints and their requirements once the integration is complete."
    }
  ]
}
```

### Example 4: System Status Check

**MCP Client Request**:
```json
{
  "method": "tools/call",
  "params": {
    "name": "memory_status",
    "arguments": {
      "detailed": true
    }
  }
}
```

**MCP Server Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "📊 COGNITIVE MEMORY SYSTEM STATUS\n========================================\n\nSystem Status: ✅ HEALTHY\n\nMemory Counts:\n  Total Memories: 1,247\n  L0 (Concepts): 89 memories\n  L1 (Contexts): 234 memories  \n  L2 (Episodes): 924 memories\n  \n  Episodic Memories: 856\n  Semantic Memories: 391\n  Session Lessons: 23\n\nStorage Statistics:\n  Qdrant Status: ✅ Running (port 6333)\n  Vector Count: 1,247 vectors\n  Storage Size: 45.2 MB\n  \nRecent Activity:\n  Last Storage: 2024-01-15T17:45:00Z (2 minutes ago)\n  Last Retrieval: 2024-01-15T17:50:00Z (now)\n  Last Consolidation: 2024-01-14T02:00:00Z\n\nConfiguration:\n  Activation Threshold: 0.7\n  Bridge Discovery K: 5\n  Max Activations: 50\n  Embedding Model: all-MiniLM-L6-v2 (384 dimensions)\n  \n🧠 The system is operating optimally with strong memory diversity across all hierarchy levels."
    }
  ]
}
```

## Setup & Configuration

### Claude Desktop Integration

To integrate with Claude Desktop, create a setup script:

**`setup_mcp_for_claude.sh`**:
```bash
#!/bin/bash
# Setup MCP server for Claude Desktop integration

echo "🧠 Setting up Cognitive Memory MCP Server for Claude Desktop..."

# 1. Ensure cognitive memory system is installed
if ! command -v memory_system &> /dev/null; then
    echo "❌ Cognitive memory system not found. Please install first:"
    echo "   pip install -e ."
    exit 1
fi

# 2. Start required services
echo "🚀 Starting Qdrant vector database..."
memory_system qdrant start

# 3. Verify system health
echo "🩺 Checking system health..."
memory_system doctor

# 4. Create Claude Desktop configuration
CLAUDE_CONFIG_DIR="$HOME/.config/claude-desktop"
CLAUDE_CONFIG_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

mkdir -p "$CLAUDE_CONFIG_DIR"

# 5. Add MCP server configuration to Claude Desktop
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    echo "⚠️  Backing up existing Claude Desktop config..."
    cp "$CLAUDE_CONFIG_FILE" "$CLAUDE_CONFIG_FILE.backup.$(date +%s)"
fi

cat > "$CLAUDE_CONFIG_FILE" << EOF
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "memory_system",
      "args": ["serve", "mcp"],
      "env": {
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
EOF

echo "✅ Claude Desktop configuration updated:"
echo "   Config file: $CLAUDE_CONFIG_FILE"
echo ""
echo "🎉 Setup complete! Restart Claude Desktop to activate the MCP server."
echo ""
echo "Available MCP Tools in Claude:"
echo "  • store_memory - Store experiences and knowledge"
echo "  • recall_memories - Retrieve relevant memories" 
echo "  • session_lessons - Record key learnings"
echo "  • memory_status - Check system health"
echo ""
echo "Usage Examples:"
echo "  'Store this debugging insight...' → Uses store_memory automatically"
echo "  'What do I know about React performance?' → Uses recall_memories"
echo "  'Record lesson: Always check network tab first when debugging APIs' → Uses session_lessons"
```

### Manual Configuration

**For other MCP clients:**

1. **stdio mode** (local clients):
```bash
# Start MCP server in stdio mode
memory_system serve mcp
```

2. **HTTP mode** (remote clients):
```bash
# Start MCP server with HTTP transport
memory_system serve mcp --port 8080
```

**Client Configuration Example**:
```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "memory_system",
      "args": ["serve", "mcp"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "MCP_MAX_MEMORIES_PER_QUERY": "20"
      }
    }
  }
}
```

### Environment Setup

**Required Environment Variables**:
```bash
# .env file or environment
QDRANT_URL=http://localhost:6333
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
COGNITIVE_MEMORY_DB_PATH=./data/cognitive_memory.db

# Optional MCP-specific settings
MCP_MAX_MEMORIES_PER_QUERY=10
MCP_SESSION_LESSON_BOOST=1.5
MCP_BRIDGE_DISCOVERY_THRESHOLD=0.7
```

## Implementation Steps

### Phase 1: Core MCP Server

1. **Install Dependencies**
```bash
pip install "mcp>=1.4.0"
pip install "fastmcp"  # Alternative: lighter framework
```

2. **Create MCP Server Module**
```
interfaces/
├── mcp_server.py          # Main MCP server implementation
├── mcp_tools/             # Tool implementations
│   ├── __init__.py
│   ├── store_memory.py    # store_memory tool
│   ├── recall_memories.py # recall_memories tool
│   ├── session_lessons.py # session_lessons tool
│   └── memory_status.py   # memory_status tool
└── mcp_utils.py          # MCP response formatting utilities
```

3. **Implement Tool Wrappers**
   - Each tool wraps corresponding CognitiveCLI methods
   - Implement input validation and error handling
   - Format responses for optimal LLM consumption

4. **Add Service Integration**
   - Extend `memory_system/cli.py` with MCP server commands
   - Integrate with existing service health checking
   - Implement graceful startup/shutdown

### Phase 2: Session Lessons Enhancement

1. **Design Lesson Prompting System**
   - Built-in guidance for effective lesson creation
   - Lesson categorization and importance scoring
   - Session context tracking

2. **Implement Lesson Retrieval Optimization**
   - Boost session lessons in similarity searches
   - Cross-session lesson linking
   - Temporal relevance weighting

3. **Add Lesson Analytics**
   - Track lesson usage and effectiveness
   - Identify knowledge gaps
   - Suggest lesson consolidation opportunities

### Phase 3: Advanced Features

1. **Rich Metadata Enhancement**
   - Expand source information formatting
   - Add temporal context analysis
   - Implement memory relationship mapping

2. **Bridge Discovery Integration**
   - Expose bridge discovery as MCP capability
   - Enhance serendipitous connection identification
   - Add bridge explanation generation

3. **Performance Optimization**
   - Implement response caching
   - Add batch operation support
   - Optimize vector search parameters

### Phase 4: Claude Desktop Integration

1. **Create Setup Automation**
   - Implement `setup_mcp_for_claude.sh` script
   - Add configuration validation
   - Provide troubleshooting guidance

2. **Enhanced Claude Integration**
   - Optimize tool descriptions for Claude
   - Add Claude-specific response formatting
   - Implement conversation context awareness

3. **User Experience Polish**
   - Add rich status displays
   - Implement interactive setup wizard
   - Create usage documentation

### Testing Strategy

**Unit Tests**:
```python
# tests/test_mcp_server.py
async def test_store_memory_tool():
    """Test store_memory MCP tool wrapper"""
    
async def test_recall_memories_with_filters():
    """Test recall_memories with type filtering"""
    
async def test_session_lessons_metadata():
    """Test session lesson special metadata handling"""
```

**Integration Tests**:
```python
# tests/integration/test_mcp_integration.py
async def test_full_mcp_workflow():
    """Test complete store → recall → lesson workflow"""
    
async def test_claude_desktop_integration():
    """Test MCP server with Claude Desktop client"""
```

**Performance Tests**:
```python
# tests/performance/test_mcp_performance.py
async def test_memory_recall_latency():
    """Test response times for memory retrieval"""
    
async def test_concurrent_mcp_requests():
    """Test handling multiple simultaneous MCP requests"""
```

## Conclusion

This MCP server architecture provides LLMs with sophisticated cognitive memory capabilities while leveraging the existing robust infrastructure. The design emphasizes:

- **Rich Context**: Comprehensive metadata and source information
- **Metacognitive Learning**: Session lessons for continuous improvement  
- **Flexible Integration**: Support for multiple MCP clients
- **Performance**: Efficient wrapping of existing functionality
- **User Experience**: Easy setup and intuitive tool interactions

The session lessons framework is particularly innovative, encouraging LLMs to practice reflection and create valuable knowledge for future interactions. This creates a positive feedback loop where each session contributes to long-term learning and capability enhancement.

By following this architecture, developers can create an MCP server that transforms any LLM into a persistent, learning system with rich memory capabilities that grow more valuable over time.