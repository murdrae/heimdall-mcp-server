# Heimdall MCP Server - Cognitive Memory Across Coding Sessions

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](hhttps://github.com/lcbcFoo/heimdall-mcp-server/blob/main/README.mdttps://opensource.org/licenses/Apache-2.0)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![MCP Protocol](https://img.shields.io/badge/MCP-compatible-brightgreen.svg)](https://modelcontextprotocol.io/)

A tool that lets your LLM remember things between conversations - your project patterns, solutions you've found, and insights from past sessions.

## **The problem it solves**
Your coding assistant forgets everything when you close the chat. Every new session starts from zero, even if you discussed the same codebase yesterday.

## **What it gives you**
- Your LLM remembers project-specific knowledge across sessions
- Stores complete git commit history (what changed, when, why, by whom)
- Stores insights and solutions you discover during coding sessions
- Connects related concepts it has learned about your codebase

This means instead of re-explaining your system every session or having hundreds of tool calls for context, your LLM remembers how it works and what problems you've solved before.

## **What it still requires from you**

This is not magic, it still depends on good documents, meaningful git commits and a good CLAUDE.md (or similar rules) encouraging LLM to use the MCP.

Also, this tool is not meant to keep track of development progress or project management, it is meant to help give LLM context faster and avoid
work and discussions replication.

Tips:

- Place Markdown architecture documents, guidelines, decisions, etc in `.heimdall-mcp` (or symlink to them)
- Instruct LLM to use meaningful git messages
- See CLAUDE.md for Heimdall MCP Server related rules

## Easy Setup

**Important**: Run this setup script from within your project repository - it creates a project-specific MCP server.

```bash
# Navigate to your project first
cd /path/to/your/project

# Run setup (creates isolated memory for THIS project only)
/path/to/heimdall-mcp-mcp/setup_claude_code_mcp.sh
# Save MD documents you want to feed into the cognitive system in .heimdall-mcp
# You can symlink to some other directory you normally use, like docs/arch-docs
# Then load the MD files and git history into the cognitive system:
/path/to/heimdall-mcp-mcp/scripts/load_project_content.sh
```

This automatically configures:
- Project-isolated Docker containers with Qdrant + cognitive system
 - Meaning: you have isolated memories on different projects. This is why calling the setup scripts from proper place is crucial.
- MCP server integration for Claude Code (project-specific)
  - If you are not integrating to Claude Code, just use `scripts/setup_project_memory.sh*`
- Loads the git history and relevant docs you places in .heimdall-mcp and transform them into memories.

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

- **Commit history** from git (what files changed, commit messages, authors, timestamps)
- **Session insights** stored via MCP calls during conversations
- **Documentation** from markdown files in your repo
- **Debugging approaches** that worked or failed
- **Context** about ongoing work and decisions

**Example conversation:**
```
You: "Having auth timeout issues again"

LLM: [calls recall_memories("auth timeout")]
     "Based on stored memories:
     • Found commit 3cdc88f by John Doe: 'Fix Redis timeout by increasing pool size'
     • Previous session lesson: 'Redis timeouts correlate with pool exhaustion'
     • Commit modified auth/config.py and auth/middleware.py with +15/-3 lines
     • Check connection pool settings in auth/config.py"
```

## How It Works Under the Hood

**For Developers Who Want to Know**:
We extract memories from project docs and git commit history, encode them as vectors, and store them in Qdrant with smart retrieval algorithms.

```
Git Commits → Direct Storage → Multi-dimensional Memory
     ↓                                      ↓
Session Insights → Hierarchical Storage → Context-Aware Recall
                         ↓
               Cross-Reference Discovery
```

**Technology Stack**:
- **Vector Storage**: Qdrant with project-specific collections
- **Embeddings**: Sentence-BERT + git commit content
- **Memory Systems**: Session persistence + git commit storage
- **Integration**: MCP protocol for seamless Claude Code integration

**What Makes It Different**:
- **Git-Aware**: Stores your actual commit history with full context
- **Project-Isolated**: Each repo gets its own memory space
- **Context-Rich**: Remembers not just what, but when, why, and how
- **Historical Access**: Direct access to development decisions and file evolution

## Requirements

- Docker

## Roadmap

- Git post-commit hooks for automatic pattern updates
- Auto-detect new documents in shared docs directory

## License

Apache 2.0
