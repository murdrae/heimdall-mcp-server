# Cognitive Memory
**MCP server that gives Claude persistent memory of your project**

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![MCP Protocol](https://img.shields.io/badge/MCP-compatible-brightgreen.svg)](https://modelcontextprotocol.io/)

A tool that lets your LLM remember things between conversations - your project patterns, solutions you've found, and insights from past sessions.

**The problem it solves:**
Your coding assistant forgets everything when you close the chat. Every new session starts from zero, even if you discussed the same codebase yesterday.

**What it gives you:**
- Your LLM remembers project-specific knowledge across sessions
- Learns patterns from your git history (which files change together, common fix approaches)
- Stores insights and solutions you discover during coding sessions
- Connects related concepts it has learned about your codebase

This means instead of re-explaining your auth system every morning, your LLM already knows how it works and what problems you've solved before.


## 30-Second Setup (Per-Project)

**Important**: Run this setup script from within your project repository - it creates a project-specific MCP server.

```bash
# Navigate to your project first
cd /path/to/your/project

# Run setup (creates isolated memory for THIS project only)
/path/to/cognitive-memory-mcp/setup_claude_code_mcp.sh
```

This automatically configures:
- Project-isolated Docker containers with Qdrant + cognitive system
- MCP server integration for Claude Code (project-specific)
- Post-commit git hooks for pattern extraction from your repo
- Memory tools available immediately in Claude sessions

**Result**: Your LLM now has persistent memory of THIS specific project, separate from your other projects.

## MCP Tools Available

Your LLM gets access to these 4 memory tools via MCP protocol:

**`store_memory`** - Store experiences and insights
```
# LLM calls this MCP tool:
store_memory({
  text: "Found that React components re-render unnecessarily when using object destructuring in useEffect dependencies",
  context: {
    hierarchy_level: 1,
    importance_score: 0.8,
    tags: ["react", "performance"]
  }
})
```

**`recall_memories`** - Semantic search with rich context
```
# LLM calls this MCP tool:
recall_memories({
  query: "authentication timeout bug",
  types: ["core", "peripheral"],
  max_results: 5
})
# Returns: JSON with memories categorized by type, similarity scores, metadata
```

**`session_lessons`** - Record key learnings for future sessions
```
# LLM calls this MCP tool:
session_lessons({
  lesson_content: "When debugging API issues, always check network tab first, then API logs, then client error handling",
  lesson_type: "pattern",
  importance: "high"
})
```

**`memory_status`** - System health and statistics
```
# LLM calls this MCP tool:
memory_status({detailed: true})
# Returns: JSON with memory counts, storage stats, system health
```

## What the LLM learns to remember

- **Project patterns** from git history (files that change together, common fixes)
- **Session insights** stored via MCP calls during conversations
- **Documentation** from markdown files in your repo
- **Debugging approaches** that worked or failed
- **Context** about ongoing work and decisions

**Example conversation:**
```
You: "Having auth timeout issues again"

LLM: [calls recall_memories("auth timeout")]
     "Based on stored patterns:
     • auth/middleware.py and auth/config.py change together 92% of the time
     • Previous session lesson: 'Redis timeouts correlate with pool exhaustion'
     • From commit 3cdc88: increasing pool size to 20+ fixed similar timeouts
     • Check connection pool settings in auth/config.py"
```

## How It Works Under the Hood

**For Developers Who Want to Know**:
We extract memories from project docs and git history, encode them as vectors, and store them in Qdrant with smart retrieval algorithms.

```
Git History → Pattern Extraction → Multi-dimensional Memory
     ↓                                      ↓
Session Insights → Hierarchical Storage → Context-Aware Recall
                         ↓
               Cross-Reference Discovery
```

**Technology Stack**:
- **Vector Storage**: Qdrant with project-specific collections
- **Embeddings**: Sentence-BERT + git metadata extraction
- **Memory Systems**: Session persistence + git pattern mining
- **Integration**: MCP protocol for seamless Claude Code integration

**What Makes It Different**:
- **Git-Aware**: Mines your actual commit history for proven solutions
- **Project-Isolated**: Each repo gets its own memory space
- **Context-Rich**: Remembers not just what, but when, why, and how
- **Pattern Learning**: Discovers co-change patterns and debugging approaches that work

## Requirements

- Docker

## Roadmap

- Git post-commit hooks for automatic pattern updates
- Auto-detect new documents in shared docs directory

## License

Apache 2.0
