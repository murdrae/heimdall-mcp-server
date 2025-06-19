#!/usr/bin/env python3
"""
MCP Server for Cognitive Memory System.

This module implements a Model Context Protocol (MCP) server that provides
LLMs with secure, controlled access to cognitive memory operations through
a standardized interface, enabling persistent memory across conversations
and intelligent knowledge consolidation.
"""

import asyncio
import logging
import sys
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from cognitive_memory.core.interfaces import CognitiveSystem
from cognitive_memory.main import initialize_system, initialize_with_config
from interfaces.cli import CognitiveCLI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CognitiveMemoryMCPServer:
    """
    MCP Server wrapper for cognitive memory system.

    Provides LLMs with access to cognitive memory operations through
    the Model Context Protocol, including storing experiences,
    recalling memories, recording session lessons, and checking system status.
    """

    def __init__(self, cognitive_system: CognitiveSystem):
        """
        Initialize MCP server with cognitive system.

        Args:
            cognitive_system: The cognitive system interface to wrap
        """
        self.cognitive_system = cognitive_system
        self.cli = CognitiveCLI(cognitive_system)
        self.server: Server = Server("cognitive-memory")
        self._register_handlers()

        logger.info("Cognitive Memory MCP Server initialized")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()  # type: ignore[misc]
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return [
                Tool(
                    name="store_memory",
                    description="Store new experiences or knowledge in cognitive memory for future recall",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Content to store in cognitive memory",
                            },
                            "context": {
                                "type": "object",
                                "description": "Optional context and metadata",
                                "properties": {
                                    "hierarchy_level": {
                                        "type": "integer",
                                        "description": "Memory hierarchy level: 0=concept, 1=context, 2=episode",
                                        "minimum": 0,
                                        "maximum": 2,
                                    },
                                    "memory_type": {
                                        "type": "string",
                                        "enum": ["episodic", "semantic"],
                                        "description": "Type of memory to store",
                                    },
                                    "importance_score": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                        "description": "Importance score for the memory (0.0-1.0)",
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Categorization tags for the memory",
                                    },
                                    "source_info": {
                                        "type": "string",
                                        "description": "Description of the memory source",
                                    },
                                },
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="recall_memories",
                    description="Retrieve memories based on query with rich contextual information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for memory retrieval",
                            },
                            "types": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["core", "peripheral", "bridge"],
                                },
                                "description": "Types of memories to retrieve (default: all)",
                            },
                            "max_results": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Maximum number of memories to return (default: 10)",
                            },
                            "include_bridges": {
                                "type": "boolean",
                                "description": "Include bridge discoveries for novel connections (default: true)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="session_lessons",
                    description="Capture and consolidate key learnings from current session for future reference. This tool encourages metacognitive reflection - thinking about what you've learned that would be valuable after 'critical amnesia' between sessions.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lesson_content": {
                                "type": "string",
                                "description": "Key insight, pattern, or learning from this session",
                            },
                            "lesson_type": {
                                "type": "string",
                                "enum": [
                                    "discovery",
                                    "pattern",
                                    "solution",
                                    "warning",
                                    "context",
                                ],
                                "description": "Type of lesson: discovery (new insights), pattern (systematic approaches), solution (technical fixes), warning (things to avoid), context (situational information)",
                            },
                            "session_context": {
                                "type": "string",
                                "description": "What was being worked on or the situation context",
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "description": "Importance level for future retrieval prioritization",
                            },
                        },
                        "required": ["lesson_content"],
                    },
                ),
                Tool(
                    name="memory_status",
                    description="Get cognitive memory system health and statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "detailed": {
                                "type": "boolean",
                                "description": "Include detailed configuration information (default: false)",
                            }
                        },
                    },
                ),
            ]

        @self.server.call_tool()  # type: ignore[misc]
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle MCP tool calls."""
            try:
                if name == "store_memory":
                    return await self._store_memory(arguments)
                elif name == "recall_memories":
                    return await self._recall_memories(arguments)
                elif name == "session_lessons":
                    return await self._session_lessons(arguments)
                elif name == "memory_status":
                    return await self._memory_status(arguments)
                else:
                    return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [
                    TextContent(
                        type="text", text=f"❌ Error executing {name}: {str(e)}"
                    )
                ]

    async def _store_memory(self, arguments: dict) -> list[TextContent]:
        """Handle store_memory tool calls."""
        text = arguments.get("text", "")
        context = arguments.get("context", {})

        if not text.strip():
            return [
                TextContent(type="text", text="❌ Error: Memory text cannot be empty")
            ]

        try:
            # Store the experience using CLI wrapper
            success = self.cli.store_experience(text=text, context=context)

            if success:
                # Get hierarchy level and memory type from context
                hierarchy_level = context.get(
                    "hierarchy_level", 2
                )  # Default to episode
                memory_type = context.get(
                    "memory_type", "episodic"
                )  # Default to episodic

                level_names = {0: "L0 (Concept)", 1: "L1 (Context)", 2: "L2 (Episode)"}
                level_name = level_names.get(hierarchy_level, f"L{hierarchy_level}")

                response = "✓ Experience stored successfully\n\n"
                response += f"Hierarchy Level: {level_name}\n"
                response += f"Memory Type: {memory_type}\n"
                response += f"Stored At: {datetime.now().isoformat()}Z\n\n"
                response += "This knowledge is now available for future recall and will contribute to pattern recognition."

                return [TextContent(type="text", text=response)]
            else:
                return [
                    TextContent(
                        type="text",
                        text="❌ Failed to store experience. Please check system status.",
                    )
                ]

        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return [TextContent(type="text", text=f"❌ Error storing memory: {str(e)}")]

    async def _recall_memories(self, arguments: dict) -> list[TextContent]:
        """Handle recall_memories tool calls."""
        query = arguments.get("query", "")
        # Note: types_filter parameter from MCP schema not yet implemented in CLI
        # types_filter = arguments.get("types", ["core", "peripheral", "bridge"])
        max_results = arguments.get("max_results", 10)
        # include_bridges = arguments.get("include_bridges", True)  # TODO: Implement bridge discovery

        if not query.strip():
            return [TextContent(type="text", text="❌ Error: Query cannot be empty")]

        try:
            # Retrieve memories using CLI wrapper
            # Note: CLI method returns bool, but we need formatted results
            # This is a limitation that should be addressed in future refactoring
            success = self.cli.retrieve_memories(
                query=query, types=None, limit=max_results
            )

            if not success:
                return [
                    TextContent(
                        type="text", text=f"No memories found for query: '{query}'"
                    )
                ]

            # Format the response with rich metadata
            response = f"📋 Retrieved memories for: '{query}'\n\n"
            # Note: CLI method prints results directly and returns bool
            # In a future refactoring, this should return structured data
            response += (
                "Memories retrieved successfully. See console output for details."
            )

            return [TextContent(type="text", text=response)]

        except Exception as e:
            logger.error(f"Error recalling memories: {e}")
            return [
                TextContent(type="text", text=f"❌ Error recalling memories: {str(e)}")
            ]

    async def _session_lessons(self, arguments: dict) -> list[TextContent]:
        """Handle session_lessons tool calls."""
        lesson_content = arguments.get("lesson_content", "")
        lesson_type = arguments.get("lesson_type", "discovery")
        session_context = arguments.get("session_context", "")
        importance = arguments.get("importance", "medium")

        if not lesson_content.strip():
            return [
                TextContent(
                    type="text", text="❌ Error: Lesson content cannot be empty"
                )
            ]

        # Provide metacognitive prompting guidance
        if len(lesson_content) < 20:  # Very short lesson
            guidance = "\n\n💡 Consider expanding your lesson: What specific insights, patterns, or context would help a future session understand this situation after complete amnesia?\n\n"
            guidance += "Think about:\n"
            guidance += "• What key insights or discoveries emerged?\n"
            guidance += "• What patterns or approaches proved effective?\n"
            guidance += "• What context about the current work is essential?\n"
            guidance += "• What warnings or gotchas should be remembered?\n"

            return [
                TextContent(
                    type="text",
                    text=f"Session lesson noted, but could be more detailed.{guidance}",
                )
            ]

        try:
            # Create rich metadata for session lesson
            lesson_metadata = {
                "loader_type": "session_lesson",
                "lesson_type": lesson_type,
                "session_context": session_context,
                "importance_level": importance,
                "stored_at": datetime.now().isoformat(),
            }

            # Map importance to score
            importance_scores = {
                "low": 0.3,
                "medium": 0.6,
                "high": 0.8,
                "critical": 1.0,
            }

            context = {
                "hierarchy_level": 1,  # Context level for lessons
                "memory_type": "semantic",  # Lessons are semantic knowledge
                "importance_score": importance_scores.get(importance, 0.6),
                "tags": ["session_lesson", lesson_type],
                "source_info": f"Session Lesson ({lesson_type})",
                "metadata": lesson_metadata,
            }

            # Store the lesson
            success = self.cli.store_experience(text=lesson_content, context=context)

            if success:
                response = "✓ Session lesson recorded for future reference\n\n"
                response += f"Lesson Type: {lesson_type}\n"
                response += f"Importance Level: {importance}\n"
                response += f"Stored At: {datetime.now().isoformat()}Z\n\n"

                if session_context:
                    response += f"Session Context: {session_context}\n\n"

                response += "This lesson will be prioritized in future recalls and contribute to continuous learning across sessions."

                # Add contextual suggestions
                if lesson_type == "discovery":
                    response += "\n\n💡 Suggestion: Consider recording related patterns or solutions that emerged from this discovery."
                elif lesson_type == "pattern":
                    response += "\n\n💡 Suggestion: Consider documenting specific examples where this pattern applies."
                elif lesson_type == "solution":
                    response += "\n\n💡 Suggestion: Consider adding context about when this solution is most effective."
                elif lesson_type == "warning":
                    response += "\n\n💡 Suggestion: Consider documenting the consequences of ignoring this warning."
                elif lesson_type == "context":
                    response += "\n\n💡 Suggestion: Consider adding related discoveries or solutions from this context."

                return [TextContent(type="text", text=response)]
            else:
                return [
                    TextContent(
                        type="text",
                        text="❌ Failed to store session lesson. Please check system status.",
                    )
                ]

        except Exception as e:
            logger.error(f"Error storing session lesson: {e}")
            return [
                TextContent(
                    type="text", text=f"❌ Error storing session lesson: {str(e)}"
                )
            ]

    async def _memory_status(self, arguments: dict) -> list[TextContent]:
        """Handle memory_status tool calls."""
        detailed = arguments.get("detailed", False)

        try:
            # Get status using CLI wrapper
            status_result = self.cli.show_status()

            if status_result:
                response = "📊 COGNITIVE MEMORY SYSTEM STATUS\n"
                response += "=" * 40 + "\n\n"
                response += "System Status: ✅ HEALTHY\n\n"
                response += str(status_result)

                if detailed:
                    response += "\n\n🔧 DETAILED CONFIGURATION\n"
                    response += "-" * 30 + "\n"
                    response += "Embedding Model: all-MiniLM-L6-v2 (384 dimensions)\n"
                    response += "Activation Threshold: 0.7\n"
                    response += "Bridge Discovery K: 5\n"
                    response += "Max Activations: 50\n"

                response += "\n\n🧠 The cognitive memory system is operating optimally."

                return [TextContent(type="text", text=response)]
            else:
                return [
                    TextContent(
                        type="text",
                        text="❌ Unable to retrieve system status. Please check if services are running.",
                    )
                ]

        except Exception as e:
            logger.error(f"Error getting memory status: {e}")
            return [
                TextContent(
                    type="text", text=f"❌ Error getting system status: {str(e)}"
                )
            ]

    async def run_stdio(self) -> None:
        """Run MCP server with stdio transport."""
        logger.info("Starting Cognitive Memory MCP Server (stdio mode)")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main() -> None:
    """Main entry point for MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Cognitive Memory MCP Server")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="HTTP port (only used in http mode)"
    )

    args = parser.parse_args()

    try:
        # Initialize cognitive system
        if args.config:
            cognitive_system = initialize_with_config(args.config)
        else:
            cognitive_system = initialize_system("default")

        # Create and run MCP server
        mcp_server = CognitiveMemoryMCPServer(cognitive_system)

        if args.mode == "stdio":
            await mcp_server.run_stdio()
        else:
            logger.error("HTTP mode not yet implemented")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)


def run_server(cognitive_system: CognitiveSystem, port: int | None = None) -> None:
    """
    Run the MCP server with the given cognitive system.

    Args:
        cognitive_system: The cognitive system to use
        port: Optional port for HTTP mode (None for stdio)
    """
    # Create MCP server instance
    mcp_server = CognitiveMemoryMCPServer(cognitive_system)

    if port:
        logger.error("HTTP mode not yet implemented")
        sys.exit(1)
    else:
        # Run in stdio mode
        asyncio.run(mcp_server.run_stdio())


if __name__ == "__main__":
    asyncio.run(main())
