"""
Enhanced MCP server for the new Heimdall architecture.

This module provides MCP integration for the enhanced temporal-semantic memory system,
maintaining compatibility with existing MCP clients while leveraging the new architecture.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource,
    CallToolResult, EmptyResult, ListResourcesResult, ListToolsResult,
    ReadResourceResult
)
import mcp.types as types

# Import enhanced architecture components
from cognitive_memory.core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow, 
    MemoryDomain
)
from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.retrieval.enhanced_query_engine import (
    EnhancedQueryEngine,
    create_query_context
)
from cognitive_memory.retrieval.temporal_semantic_coordinator import (
    TemporalSemanticCoordinator,
    QueryStrategy
)
from cognitive_memory.migration.enhanced_migration_tools import (
    LegacyHeimdallBridge,
    EnhancedMigrationEngine,
    MigrationOrchestrator
)


class EnhancedMCPServer:
    """
    Enhanced MCP server with temporal-semantic memory architecture.
    
    Provides backward-compatible MCP interface while leveraging the new
    enhanced memory system for improved query performance and organization.
    """
    
    def __init__(
        self,
        qdrant_host: str = "localhost", 
        qdrant_port: int = 6333,
        collection_prefix: str = "enhanced_heimdall",
        enable_migration: bool = True,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the enhanced MCP server."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize enhanced architecture components
        self.storage = EnhancedQdrantStorage(
            host=qdrant_host,
            port=qdrant_port,
            collection_prefix=collection_prefix
        )
        self.query_engine = EnhancedQueryEngine()
        self.coordinator = TemporalSemanticCoordinator(
            storage=self.storage,
            query_engine=self.query_engine,
            logger=self.logger
        )
        
        # Migration components (optional)
        self.enable_migration = enable_migration
        if enable_migration:
            self.legacy_bridge = LegacyHeimdallBridge(
                legacy_qdrant_host=qdrant_host,
                legacy_qdrant_port=qdrant_port,
                logger=self.logger
            )
            self.migration_engine = EnhancedMigrationEngine(
                enhanced_storage=self.storage,
                logger=self.logger
            )
        
        # MCP server setup
        self.server = Server("enhanced-heimdall")
        self._setup_mcp_handlers()
        
        # System state
        self.initialized = False
        self.migration_completed = False
    
    def _setup_mcp_handlers(self) -> None:
        """Setup MCP server handlers for tools and resources."""
        
        # Tool handlers
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle MCP tool calls."""
            try:
                if name == "store_memory":
                    return await self._handle_store_memory(arguments)
                elif name == "recall_memories":
                    return await self._handle_recall_memories(arguments)
                elif name == "session_lessons":
                    return await self._handle_session_lessons(arguments)
                elif name == "memory_status":
                    return await self._handle_memory_status(arguments)
                elif name == "migrate_legacy_data":
                    return await self._handle_migrate_legacy_data(arguments)
                elif name == "delete_memory":
                    return await self._handle_delete_memory(arguments)
                elif name == "delete_memories_by_tags":
                    return await self._handle_delete_memories_by_tags(arguments)
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: {name}"
                        )],
                        isError=True
                    )
            except Exception as e:
                self.logger.error(f"Tool call failed for {name}: {e}")
                return CallToolResult(
                    content=[TextContent(
                        type="text", 
                        text=f"Tool execution failed: {str(e)}"
                    )],
                    isError=True
                )
        
        # Tool listing
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available MCP tools."""
            tools = [
                Tool(
                    name="store_memory",
                    description="Store new experiences or knowledge in enhanced cognitive memory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Content to store in cognitive memory"
                            },
                            "context": {
                                "type": "object",
                                "description": "Optional context and metadata",
                                "properties": {
                                    "memory_type": {
                                        "type": "string",
                                        "enum": ["episodic", "semantic"],
                                        "description": "Type of memory to store"
                                    },
                                    "temporal_window": {
                                        "type": "string",
                                        "enum": ["active", "working", "reference", "archive"],
                                        "description": "Temporal classification for the memory"
                                    },
                                    "semantic_domain": {
                                        "type": "string",
                                        "enum": [
                                            "project_context", "technical_patterns", 
                                            "decision_chains", "session_continuity",
                                            "development_history", "ai_interactions"
                                        ],
                                        "description": "Semantic domain for the memory"
                                    },
                                    "importance_score": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                        "description": "Importance score for the memory (0.0-1.0)"
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Categorization tags for the memory"
                                    },
                                    "source_info": {
                                        "type": "string",
                                        "description": "Description of the memory source"
                                    }
                                }
                            }
                        },
                        "required": ["text"]
                    }
                ),
                Tool(
                    name="recall_memories",
                    description="Retrieve memories with enhanced temporal-semantic search",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "Search query for memory retrieval"
                            },
                            "query_type": {
                                "type": "string",
                                "enum": [
                                    "project_status", "technical_pattern", "decision_context",
                                    "session_continuity", "knowledge_discovery", "general_search"
                                ],
                                "description": "Type of query for optimized retrieval"
                            },
                            "max_results": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 50,
                                "description": "Maximum number of memories to return (default: 10)"
                            },
                            "temporal_focus": {
                                "type": "string",
                                "enum": ["active", "working", "reference", "archive"],
                                "description": "Focus on specific temporal window"
                            },
                            "domain_focus": {
                                "type": "string", 
                                "enum": [
                                    "project_context", "technical_patterns",
                                    "decision_chains", "session_continuity", 
                                    "development_history", "ai_interactions"
                                ],
                                "description": "Focus on specific semantic domain"
                            },
                            "include_bridges": {
                                "type": "boolean",
                                "description": "Include bridge discoveries for novel connections (default: true)"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="session_lessons",
                    description="Capture key learnings from current session for future reference",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lesson_content": {
                                "type": "string",
                                "description": "Key insight, pattern, or learning from this session"
                            },
                            "lesson_type": {
                                "type": "string",
                                "enum": ["discovery", "pattern", "solution", "warning", "context"],
                                "description": "Type of lesson being recorded"
                            },
                            "session_context": {
                                "type": "string",
                                "description": "What was being worked on or the situation context"
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "description": "Importance level for future retrieval prioritization"
                            }
                        },
                        "required": ["lesson_content"]
                    }
                ),
                Tool(
                    name="memory_status",
                    description="Get enhanced cognitive memory system health and statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "detailed": {
                                "type": "boolean",
                                "description": "Include detailed configuration information (default: false)"
                            }
                        }
                    }
                ),
                Tool(
                    name="migrate_legacy_data",
                    description="Migrate data from legacy Heimdall L0/L1/L2 system to enhanced architecture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "dry_run": {
                                "type": "boolean",
                                "description": "Analyze migration without actually migrating data (default: true)"
                            },
                            "backup_legacy": {
                                "type": "boolean", 
                                "description": "Create backup of legacy data before migration (default: true)"
                            }
                        }
                    }
                ),
                Tool(
                    name="delete_memory",
                    description="Delete a single memory by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "The unique ID of the memory to delete"
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "Preview what would be deleted without actually deleting (default: false)"
                            }
                        },
                        "required": ["memory_id"]
                    }
                ),
                Tool(
                    name="delete_memories_by_tags",
                    description="Delete all memories that have any of the specified tags",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of tags - memories with any of these tags will be deleted"
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "Preview what would be deleted without actually deleting (default: false)"
                            }
                        },
                        "required": ["tags"]
                    }
                )
            ]
            
            # Add migration tool only if migration is enabled
            if self.enable_migration:
                tools.append(tools[4])  # migrate_legacy_data tool
            
            return ListToolsResult(tools=tools)
    
    async def _handle_store_memory(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle store_memory tool calls."""
        text = arguments.get("text", "")
        context = arguments.get("context", {})
        
        if not text.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Memory text cannot be empty")],
                isError=True
            )
        
        try:
            # Create enhanced memory from arguments
            memory = EnhancedCognitiveMemory(
                content=text,
                temporal_window=self._parse_temporal_window(
                    context.get("temporal_window", "active")
                ),
                semantic_domain=self._parse_semantic_domain(
                    context.get("semantic_domain", "ai_interactions")
                ),
                memory_type=context.get("memory_type", "semantic"),
                importance_score=float(context.get("importance_score", 0.5))
            )
            
            # Add user-defined tags
            if "tags" in context:
                memory.user_defined_tags = set(context["tags"])
            
            # Add source information to metadata
            if "source_info" in context:
                memory.metadata["source_info"] = context["source_info"]
            
            # Store memory
            await self.storage.store_memory(memory)
            
            response_text = f"Memory stored successfully with ID: {memory.id}"
            if context.get("source_info"):
                response_text += f"\nSource: {context['source_info']}"
            
            return CallToolResult(
                content=[TextContent(type="text", text=response_text)]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to store memory: {str(e)}")],
                isError=True
            )
    
    async def _handle_recall_memories(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle recall_memories tool calls."""
        query = arguments.get("query", "")
        
        if not query.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Query cannot be empty")],
                isError=True
            )
        
        try:
            # Execute enhanced query
            results, metrics = await self.coordinator.query_memories(
                query_text=query,
                query_type=arguments.get("query_type", "general_search"),
                max_results=int(arguments.get("max_results", 10)),
                temporal_focus=self._parse_temporal_window(arguments.get("temporal_focus")) if arguments.get("temporal_focus") else None,
                domain_focus=self._parse_semantic_domain(arguments.get("domain_focus")) if arguments.get("domain_focus") else None,
                include_relationship_expansion=arguments.get("include_bridges", True)
            )
            
            if not results:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"No memories found for query: '{query}'"
                    )]
                )
            
            # Format results for MCP response 
            response_sections = [
                f"Query: '{query}'",
                f"Retrieved {len(results)} memories in {metrics.total_query_time:.3f}s",
                ""
            ]
            
            # Group results by temporal window for better organization
            by_window = {}
            for result in results:
                window = result.memory.temporal_window.value
                if window not in by_window:
                    by_window[window] = []
                by_window[window].append(result)
            
            # Format each temporal window group
            window_order = ["active", "working", "reference", "archive"]
            for window in window_order:
                if window in by_window:
                    response_sections.append(f"## {window.upper()} MEMORIES")
                    
                    for result in by_window[window]:
                        memory = result.memory
                        relevance = result.relevance
                        
                        # Memory header with relevance
                        response_sections.extend([
                            f"**Memory ID:** {memory.id}",
                            f"**Relevance:** {relevance.total_score:.3f} ({result.explanation})",
                            f"**Domain:** {memory.semantic_domain.value}",
                            f"**Created:** {memory.created_date.strftime('%Y-%m-%d %H:%M')}",
                            f"**Access Count:** {memory.access_count}",
                            ""
                        ])
                        
                        # Memory content (truncate if very long)
                        content = memory.content
                        if len(content) > 500:
                            content = content[:500] + "..."
                        
                        response_sections.extend([
                            content,
                            ""
                        ])
                        
                        # Tags if present
                        if memory.user_defined_tags:
                            tags_str = ", ".join(sorted(memory.user_defined_tags))
                            response_sections.extend([
                                f"*Tags: {tags_str}*",
                                ""
                            ])
                        
                        response_sections.append("---")
                        response_sections.append("")
            
            # Add performance summary
            if metrics.early_termination_triggered:
                response_sections.append("*Early termination triggered due to high-quality results*")
            
            performance_summary = self.coordinator.get_performance_summary()
            response_sections.extend([
                "",
                f"**System Performance:**",
                f"- Average query time: {performance_summary['recent_avg_query_time']:.3f}s",
                f"- Average results: {performance_summary['recent_avg_results']:.1f}",
                f"- Early termination rate: {performance_summary['early_termination_rate']:.1%}"
            ])
            
            return CallToolResult(
                content=[TextContent(type="text", text="\n".join(response_sections))]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to recall memories: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to recall memories: {str(e)}")],
                isError=True
            )
    
    async def _handle_session_lessons(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle session_lessons tool calls."""
        lesson_content = arguments.get("lesson_content", "")
        
        if not lesson_content.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Lesson content cannot be empty")],
                isError=True
            )
        
        try:
            # Convert lesson to enhanced memory format
            lesson_type = arguments.get("lesson_type", "discovery")
            session_context = arguments.get("session_context", "")
            importance = arguments.get("importance", "medium")
            
            # Map importance to numeric score
            importance_scores = {
                "low": 0.3,
                "medium": 0.6, 
                "high": 0.8,
                "critical": 1.0
            }
            importance_score = importance_scores.get(importance, 0.6)
            
            # Create structured lesson content
            structured_content = f"SESSION LESSON ({lesson_type.upper()})\n\n"
            structured_content += f"Context: {session_context}\n\n" if session_context else ""
            structured_content += f"Lesson: {lesson_content}"
            
            # Create memory with session continuity domain
            memory = EnhancedCognitiveMemory(
                content=structured_content,
                temporal_window=TemporalWindow.ACTIVE,  # Lessons start as active
                semantic_domain=MemoryDomain.SESSION_CONTINUITY,
                memory_type="episodic",
                importance_score=importance_score
            )
            
            # Add lesson-specific tags
            memory.user_defined_tags = {
                "session_lesson",
                lesson_type,
                importance,
                f"lesson_{datetime.now().strftime('%Y%m%d')}"
            }
            
            # Add lesson metadata
            memory.metadata.update({
                "lesson_type": lesson_type,
                "session_context": session_context,
                "importance_level": importance,
                "lesson_date": datetime.now().isoformat()
            })
            
            # Store lesson
            await self.storage.store_memory(memory)
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Session lesson captured successfully (ID: {memory.id})\n"
                         f"Type: {lesson_type} | Importance: {importance}\n"
                         f"This lesson will be available for future session continuity."
                )]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store session lesson: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to store session lesson: {str(e)}")],
                isError=True
            )
    
    async def _handle_memory_status(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle memory_status tool calls."""
        detailed = arguments.get("detailed", False)
        
        try:
            # Get storage statistics
            storage_stats = await self.storage.get_system_statistics()
            
            # Get coordinator performance
            performance_stats = self.coordinator.get_performance_summary()
            
            # Build status response
            status_sections = [
                "# Enhanced Heimdall Memory System Status",
                "",
                f"**System Status:** {'Operational' if self.initialized else 'Initializing'}",
                f"**Architecture:** Enhanced Temporal-Semantic",
                f"**Migration Status:** {'Completed' if self.migration_completed else 'Available' if self.enable_migration else 'Disabled'}",
                "",
                "## Memory Statistics",
                f"- **Total Memories:** {storage_stats.get('total_memories', 0)}",
                f"- **Active Window:** {storage_stats.get('active_memories', 0)}",
                f"- **Working Window:** {storage_stats.get('working_memories', 0)}",
                f"- **Reference Window:** {storage_stats.get('reference_memories', 0)}",
                f"- **Archive Window:** {storage_stats.get('archive_memories', 0)}",
                "",
                "## Query Performance",
                f"- **Total Queries:** {performance_stats.get('total_queries', 0)}",
                f"- **Average Query Time:** {performance_stats.get('recent_avg_query_time', 0):.3f}s",
                f"- **Average Results:** {performance_stats.get('recent_avg_results', 0):.1f}",
                f"- **Early Termination Rate:** {performance_stats.get('early_termination_rate', 0):.1%}",
                "",
                "## Semantic Domain Distribution"
            ]
            
            # Add domain distribution if available
            domain_stats = storage_stats.get('domain_distribution', {})
            for domain, count in domain_stats.items():
                status_sections.append(f"- **{domain.replace('_', ' ').title()}:** {count}")
            
            if detailed:
                status_sections.extend([
                    "",
                    "## Detailed Configuration",
                    f"- **Storage Backend:** Qdrant Vector Database",
                    f"- **Collection Prefix:** {self.storage.collection_prefix}",
                    f"- **Query Engine:** Multi-dimensional relevance scoring",
                    f"- **Temporal Windows:** 4 (Active, Working, Reference, Archive)",
                    f"- **Semantic Domains:** 6 (Project, Technical, Decision, Session, Development, AI)",
                    "",
                    "## Adaptive Thresholds",
                ])
                
                adaptive_thresholds = performance_stats.get('adaptive_thresholds', {})
                for threshold_name, value in adaptive_thresholds.items():
                    status_sections.append(f"- **{threshold_name}:** {value}")
                
                status_sections.extend([
                    "",
                    "## Temporal Window Usage (Recent Queries)"
                ])
                
                window_usage = performance_stats.get('temporal_window_usage', {})
                for window, count in window_usage.items():
                    status_sections.append(f"- **{window.title()}:** {count} queries")
            
            return CallToolResult(
                content=[TextContent(type="text", text="\n".join(status_sections))]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get memory status: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to get memory status: {str(e)}")],
                isError=True
            )
    
    async def _handle_migrate_legacy_data(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle migrate_legacy_data tool calls."""
        if not self.enable_migration:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="Migration is not enabled for this server instance."
                )],
                isError=True
            )
        
        dry_run = arguments.get("dry_run", True)
        backup_legacy = arguments.get("backup_legacy", True)
        
        try:
            # Create migration orchestrator
            orchestrator = MigrationOrchestrator(
                legacy_bridge=self.legacy_bridge,
                migration_engine=self.migration_engine,
                logger=self.logger
            )
            
            # Run migration
            report = await orchestrator.run_full_migration(
                dry_run=dry_run,
                backup_legacy_data=backup_legacy and not dry_run
            )
            
            # Format migration report
            report_sections = [
                f"# Migration Report {'(DRY RUN)' if dry_run else ''}",
                "",
                f"**Status:** {'Analysis Complete' if dry_run else 'Migration Complete'}",
                f"**Total Legacy Memories:** {report.total_legacy_memories}",
                f"**Successfully {'Analyzed' if dry_run else 'Migrated'}:** {report.successfully_migrated}",
                f"**Failed:** {report.failed_migrations}",
                "",
                "## Hierarchy Breakdown",
                f"- **L0 (Concepts):** {report.l0_migrated}",
                f"- **L1 (Contexts):** {report.l1_migrated}",
                f"- **L2 (Episodes):** {report.l2_migrated}",
                "",
                "## New Temporal Window Distribution",
                f"- **Active:** {report.active_memories}",
                f"- **Working:** {report.working_memories}",
                f"- **Reference:** {report.reference_memories}",
                f"- **Archive:** {report.archive_memories}",
                ""
            ]
            
            if not dry_run:
                report_sections.extend([
                    f"**Migration Duration:** {report.migration_duration:.2f}s",
                    f"**Processing Rate:** {report.memories_per_second:.1f} memories/second",
                    ""
                ])
                
                # Mark migration as completed
                self.migration_completed = True
            
            if report.errors:
                report_sections.extend([
                    f"## Errors ({len(report.errors)})",
                    ""
                ])
                for error in report.errors[:5]:  # Show first 5 errors
                    report_sections.append(f"- {error}")
                if len(report.errors) > 5:
                    report_sections.append(f"- ... and {len(report.errors) - 5} more errors")
                report_sections.append("")
            
            if report.warnings:
                report_sections.extend([
                    f"## Warnings ({len(report.warnings)})",
                    ""
                ])
                for warning in report.warnings[:3]:  # Show first 3 warnings
                    report_sections.append(f"- {warning}")
                if len(report.warnings) > 3:
                    report_sections.append(f"- ... and {len(report.warnings) - 3} more warnings")
            
            success_rate = (report.successfully_migrated / report.total_legacy_memories * 100) if report.total_legacy_memories > 0 else 0
            report_sections.extend([
                "",
                f"**Success Rate:** {success_rate:.1f}%"
            ])
            
            if dry_run and report.successfully_migrated > 0:
                report_sections.extend([
                    "",
                    "*Run with dry_run=false to perform actual migration.*"
                ])
            
            return CallToolResult(
                content=[TextContent(type="text", text="\n".join(report_sections))]
            )
            
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Migration failed: {str(e)}")],
                isError=True
            )
    
    async def _handle_delete_memory(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle delete_memory tool calls."""
        memory_id = arguments.get("memory_id", "")
        dry_run = arguments.get("dry_run", False)
        
        if not memory_id:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: memory_id is required")],
                isError=True
            )
        
        try:
            # Get memory details for preview
            memory = await self.storage.get_memory_by_id(memory_id)
            
            if not memory:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Memory with ID '{memory_id}' not found")],
                    isError=True
                )
            
            preview_text = f"Memory to {'be deleted' if not dry_run else 'delete'}:\n\n"
            preview_text += f"**ID:** {memory.id}\n"
            preview_text += f"**Temporal Window:** {memory.temporal_window.value}\n"
            preview_text += f"**Domain:** {memory.semantic_domain.value}\n"
            preview_text += f"**Created:** {memory.created_date.strftime('%Y-%m-%d %H:%M')}\n"
            preview_text += f"**Access Count:** {memory.access_count}\n"
            preview_text += f"**Content Preview:** {memory.content[:200]}{'...' if len(memory.content) > 200 else ''}\n"
            
            if memory.user_defined_tags:
                preview_text += f"**Tags:** {', '.join(sorted(memory.user_defined_tags))}\n"
            
            if dry_run:
                preview_text += "\n*This is a preview. Use dry_run=false to actually delete.*"
                return CallToolResult(
                    content=[TextContent(type="text", text=preview_text)]
                )
            else:
                # Actually delete the memory
                await self.storage.delete_memory(memory_id)
                preview_text += "\n✅ **Memory deleted successfully.**"
                
                return CallToolResult(
                    content=[TextContent(type="text", text=preview_text)]
                )
                
        except Exception as e:
            self.logger.error(f"Failed to delete memory: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to delete memory: {str(e)}")],
                isError=True
            )
    
    async def _handle_delete_memories_by_tags(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Handle delete_memories_by_tags tool calls."""
        tags = arguments.get("tags", [])
        dry_run = arguments.get("dry_run", False)
        
        if not tags:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: At least one tag is required")],
                isError=True
            )
        
        try:
            # Find memories with any of the specified tags
            matching_memories = await self.storage.find_memories_by_tags(tags)
            
            if not matching_memories:
                return CallToolResult(
                    content=[TextContent(
                        type="text", 
                        text=f"No memories found with tags: {', '.join(tags)}"
                    )]
                )
            
            preview_text = f"{'Memories to be deleted' if not dry_run else 'Memories that would be deleted'}:\n\n"
            preview_text += f"**Found {len(matching_memories)} memories with tags:** {', '.join(tags)}\n\n"
            
            # Show preview of first few memories
            for i, memory in enumerate(matching_memories[:5]):
                preview_text += f"**{i+1}. ID:** {memory.id}\n"
                preview_text += f"   **Content:** {memory.content[:100]}{'...' if len(memory.content) > 100 else ''}\n"
                preview_text += f"   **Tags:** {', '.join(sorted(memory.user_defined_tags))}\n\n"
            
            if len(matching_memories) > 5:
                preview_text += f"... and {len(matching_memories) - 5} more memories\n\n"
            
            if dry_run:
                preview_text += "*This is a preview. Use dry_run=false to actually delete these memories.*"
                return CallToolResult(
                    content=[TextContent(type="text", text=preview_text)]
                )
            else:
                # Actually delete the memories
                deleted_count = await self.storage.delete_memories_by_tags(tags)
                preview_text += f"✅ **Successfully deleted {deleted_count} memories.**"
                
                return CallToolResult(
                    content=[TextContent(type="text", text=preview_text)]
                )
                
        except Exception as e:
            self.logger.error(f"Failed to delete memories by tags: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to delete memories by tags: {str(e)}")],
                isError=True
            )
    
    def _parse_temporal_window(self, window_str: str) -> TemporalWindow:
        """Parse temporal window string to enum."""
        try:
            return TemporalWindow(window_str.lower())
        except ValueError:
            return TemporalWindow.ACTIVE  # Default fallback
    
    def _parse_semantic_domain(self, domain_str: str) -> MemoryDomain:
        """Parse semantic domain string to enum."""
        try:
            return MemoryDomain(domain_str.lower())
        except ValueError:
            return MemoryDomain.AI_INTERACTIONS  # Default fallback
    
    async def initialize(self) -> None:
        """Initialize the enhanced MCP server."""
        try:
            # Initialize storage
            await self.storage.initialize()
            
            # Check if legacy data exists and auto-migration is needed
            if self.enable_migration and not self.migration_completed:
                self.logger.info("Checking for legacy data to migrate...")
                legacy_memories = await self.legacy_bridge.extract_all_legacy_memories()
                
                if legacy_memories:
                    self.logger.info(f"Found {len(legacy_memories)} legacy memories - consider running migration")
            
            self.initialized = True
            self.logger.info("Enhanced MCP server initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced MCP server: {e}")
            raise
    
    async def run_stdio(self) -> None:
        """Run the MCP server in stdio mode."""
        await self.initialize()
        
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream,
                InitializationOptions(
                    server_name="enhanced-heimdall",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


# Main entry point for standalone execution
async def main():
    """Main entry point for the enhanced MCP server."""
    import sys
    import os
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('enhanced_heimdall_mcp.log'),
            logging.StreamHandler(sys.stderr)
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get configuration from environment
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        collection_prefix = os.getenv("COLLECTION_PREFIX", "enhanced_heimdall")
        enable_migration = os.getenv("ENABLE_MIGRATION", "true").lower() == "true"
        
        # Create and run server
        server = EnhancedMCPServer(
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            collection_prefix=collection_prefix,
            enable_migration=enable_migration,
            logger=logger
        )
        
        logger.info("Starting Enhanced Heimdall MCP Server...")
        await server.run_stdio()
        
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())