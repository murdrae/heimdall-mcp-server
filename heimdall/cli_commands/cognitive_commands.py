"""Cognitive memory commands: store, recall, load, git-load, status."""

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cognitive_memory.main import (
    InitializationError,
    graceful_shutdown,
    initialize_system,
    initialize_with_config,
)
from heimdall.display_utils import format_memory_results_json
from heimdall.operations import CognitiveOperations

console = Console()


def store_experience(
    text: str = typer.Argument(..., help="Experience text to store"),
    context_json: str | None = typer.Option(
        None, "--context", help="Context as JSON string"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Store an experience in cognitive memory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and store experience
        ops = CognitiveOperations(cognitive_system)
        result = ops.store_experience(text, context_json=context_json)

        if result["success"]:
            console.print(
                f"✅ Stored: L{result['hierarchy_level']}, {result['memory_type']}",
                style="bold green",
            )
            console.print(f"📝 Memory ID: {result['memory_id']}")
        else:
            console.print(
                f"❌ Failed to store experience: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error storing experience: {e}", style="bold red")
        raise typer.Exit(1) from e


def recall_memories(
    query: str = typer.Argument(..., help="Query to search for in memories"),
    types: list[str] = typer.Option(
        None, "--types", help="Memory types to retrieve (core, peripheral, bridge)"
    ),
    limit: int = typer.Option(10, "--limit", help="Maximum results per type"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Retrieve memories matching a query."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and retrieve memories
        ops = CognitiveOperations(cognitive_system)
        results = ops.retrieve_memories(query, types, limit)

        if not results["success"]:
            console.print(
                f"❌ Failed to retrieve memories: {results['error']}", style="bold red"
            )
            raise typer.Exit(1)

        if json_output:
            formatted_json = format_memory_results_json(results)
            console.print(formatted_json)
        else:
            # Display results with terminal-specific formatting
            console.print(f"🔍 Query: [bold cyan]{query}[/bold cyan]")
            console.print(f"📊 Total results: {results['total_count']}")

            for memory_type in ["core", "peripheral", "bridge"]:
                memories = results[memory_type]
                if memories:
                    console.print(
                        f"\n[bold]{memory_type.upper()}[/bold] ({len(memories)} results)"
                    )

                    for i, memory in enumerate(memories, 1):
                        # Handle different memory object types
                        if hasattr(memory, "memory") and hasattr(
                            memory.memory, "content"
                        ):
                            # This is a BridgeMemory object
                            content = memory.memory.content
                            score = getattr(memory, "bridge_score", "N/A")
                        elif hasattr(memory, "content"):
                            # This is a CognitiveMemory object
                            content = memory.content
                            score = getattr(memory, "similarity_score", "N/A")
                        elif isinstance(memory, dict):
                            content = memory.get("content", str(memory))
                            score = memory.get("similarity_score", "N/A")
                        else:
                            content = str(memory)
                            score = "N/A"

                        # Truncate long content for display
                        display_content = (
                            content[:200] + "..." if len(content) > 200 else content
                        )
                        console.print(f"  {i}. [dim]Score: {score}[/dim]")
                        console.print(f"     {display_content}")

            if results["total_count"] == 0:
                console.print(
                    "📭 No memories found matching your query", style="bold yellow"
                )

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error retrieving memories: {e}", style="bold red")
        raise typer.Exit(1) from e


def load_memories(
    source_path: str = typer.Argument(
        ..., help="Path to the source file or directory to load"
    ),
    loader_type: str = typer.Option(
        "markdown", help="Type of loader to use (markdown, git)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without loading"
    ),
    recursive: bool = typer.Option(
        False, "--recursive", help="Recursively process directories"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Load memories from external source file or directory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and load memories
        ops = CognitiveOperations(cognitive_system)
        result = ops.load_memories(
            source_path=source_path,
            loader_type=loader_type,
            dry_run=dry_run,
            recursive=recursive,
        )

        if not result["success"]:
            console.print(
                f"❌ Failed to load memories: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Display results with terminal-specific formatting
        if dry_run:
            console.print(
                "🔍 DRY RUN - No memories were actually loaded", style="bold blue"
            )
        else:
            console.print(
                "✅ Memory loading completed successfully", style="bold green"
            )

        # Results table
        results_table = Table(title="Loading Results")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Value", style="white")

        results_table.add_row("Memories Loaded", str(result["memories_loaded"]))
        if result.get("memories_deleted", 0) > 0:
            results_table.add_row(
                "Outdated Memories Replaced", str(result["memories_deleted"])
            )
        results_table.add_row("Connections Created", str(result["connections_created"]))
        results_table.add_row("Processing Time", f"{result['processing_time']:.2f}s")
        results_table.add_row("Memories Failed", str(result["memories_failed"]))
        results_table.add_row("Connections Failed", str(result["connections_failed"]))

        if result["files_processed"]:
            results_table.add_row(
                "Files Processed", str(len(result["files_processed"]))
            )

        console.print(results_table)

        # Hierarchy distribution
        if result["hierarchy_distribution"]:
            console.print("\n📊 Memory Hierarchy Distribution:")
            for level, count in result["hierarchy_distribution"].items():
                console.print(f"  L{level}: {count} memories")

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error loading memories: {e}", style="bold red")
        raise typer.Exit(1) from e


def load_git_patterns(
    repo_path: str = typer.Argument(".", help="Path to git repository"),
    max_commits: int = typer.Option(1000, help="Maximum commits to process"),
    force_full_load: bool = typer.Option(
        False, "--force-full", help="Force full history load"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be loaded without loading"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Load git commit patterns into cognitive memory."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and load git patterns
        ops = CognitiveOperations(cognitive_system)
        result = ops.load_git_patterns(
            repo_path=repo_path,
            max_commits=max_commits,
            force_full_load=force_full_load,
            dry_run=dry_run,
        )

        if not result["success"]:
            console.print(
                f"❌ Failed to load git patterns: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        # Display results with terminal-specific formatting
        if dry_run:
            console.print(
                "🔍 DRY RUN - No patterns were actually loaded", style="bold blue"
            )
        else:
            console.print(
                "✅ Git pattern loading completed successfully", style="bold green"
            )

        # Results table
        results_table = Table(title="Git Loading Results")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Value", style="white")

        results_table.add_row("Patterns Loaded", str(result["memories_loaded"]))
        if "files_processed" in result:
            results_table.add_row(
                "Files Processed", str(len(result["files_processed"]))
            )
        results_table.add_row("Connections Created", str(result["connections_created"]))
        results_table.add_row("Processing Time", f"{result['processing_time']:.2f}s")
        results_table.add_row("Memories Failed", str(result["memories_failed"]))
        results_table.add_row("Connections Failed", str(result["connections_failed"]))

        console.print(results_table)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error loading git patterns: {e}", style="bold red")
        raise typer.Exit(1) from e


def system_status(
    detailed: bool = typer.Option(
        False, "--detailed", help="Show detailed system statistics"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Show cognitive memory system status and statistics."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and get status
        ops = CognitiveOperations(cognitive_system)
        result = ops.get_system_status(detailed=detailed)

        if not result["success"]:
            console.print(
                f"❌ Failed to get system status: {result['error']}", style="bold red"
            )
            raise typer.Exit(1)

        if json_output:
            console.print(json.dumps(result, indent=2))
        else:
            # Terminal-specific formatting
            console.print("🧠 Cognitive Memory System Status", style="bold blue")

            # Memory counts table
            if result["memory_counts"]:
                memory_table = Table(title="Memory Statistics")
                memory_table.add_column("Type/Level", style="cyan")
                memory_table.add_column("Count", style="white")

                for key, count in result["memory_counts"].items():
                    memory_table.add_row(key.replace("_", " ").title(), str(count))

                console.print(memory_table)

            # Detailed information
            if detailed:
                if result.get("system_config"):
                    config_panel = Panel(
                        json.dumps(result["system_config"], indent=2),
                        title="System Configuration",
                        border_style="blue",
                    )
                    console.print(config_panel)

                if result.get("storage_stats"):
                    storage_panel = Panel(
                        json.dumps(result["storage_stats"], indent=2),
                        title="Storage Statistics",
                        border_style="green",
                    )
                    console.print(storage_panel)

                if result.get("embedding_info"):
                    embedding_panel = Panel(
                        json.dumps(result["embedding_info"], indent=2),
                        title="Embedding Information",
                        border_style="yellow",
                    )
                    console.print(embedding_panel)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error getting system status: {e}", style="bold red")
        raise typer.Exit(1) from e


def remove_file_cmd(
    file_path: str = typer.Argument(
        ..., help="Path to file whose memories should be removed"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Remove all memories associated with a deleted file."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance and delete memories
        ops = CognitiveOperations(cognitive_system)
        result = ops.delete_memories_by_source_path(file_path)

        if result["success"]:
            console.print(
                f"✅ Removed {result['deleted_count']} memories for: {file_path}",
                style="bold green",
            )
            if result["processing_time"] > 0:
                console.print(f"⏱️  Processing time: {result['processing_time']:.3f}s")
        else:
            console.print(
                f"❌ Failed to remove memories for {file_path}: {result['error']}",
                style="bold red",
            )
            raise typer.Exit(1)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error removing memories: {e}", style="bold red")
        raise typer.Exit(1) from e


def delete_memory_cmd(
    memory_id: str = typer.Argument(..., help="Memory ID to delete"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
    no_confirm: bool = typer.Option(
        False, "--no-confirm", help="Skip confirmation prompt"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Delete a single memory by its ID."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance
        ops = CognitiveOperations(cognitive_system)

        # First, run dry-run to show what would be deleted
        preview_result = ops.delete_memory_by_id(memory_id, dry_run=True)

        if not preview_result["success"]:
            console.print(f"❌ {preview_result['error']}", style="bold red")
            raise typer.Exit(1)

        if preview_result["deleted_count"] == 0:
            console.print(
                f"📭 No memory found with ID: {memory_id}", style="bold yellow"
            )
            graceful_shutdown(cognitive_system)
            return

        # Show preview information
        preview = preview_result.get("preview", {})
        console.print(f"🎯 Found memory: [bold cyan]{memory_id}[/bold cyan]")

        # Create preview table
        preview_table = Table(title="Memory Preview")
        preview_table.add_column("Property", style="cyan")
        preview_table.add_column("Value", style="white")

        preview_table.add_row("Content", preview.get("content", "N/A"))
        preview_table.add_row("Level", f"L{preview.get('hierarchy_level', 'N/A')}")
        preview_table.add_row("Tags", ", ".join(preview.get("tags", [])) or "None")
        preview_table.add_row("Source", preview.get("source_path", "N/A"))

        console.print(preview_table)

        if dry_run:
            console.print("🔍 DRY RUN - Memory would be deleted", style="bold blue")
            graceful_shutdown(cognitive_system)
            return

        # Confirmation prompt
        if not no_confirm:
            confirm = typer.confirm("Are you sure you want to delete this memory?")
            if not confirm:
                console.print("⚠️ Deletion cancelled", style="bold yellow")
                graceful_shutdown(cognitive_system)
                return

        # Perform actual deletion
        result = ops.delete_memory_by_id(memory_id, dry_run=False)

        if result["success"]:
            console.print(
                f"✅ Deleted memory: {memory_id}",
                style="bold green",
            )
            if result["processing_time"] > 0:
                console.print(f"⏱️  Processing time: {result['processing_time']:.3f}s")

            if result.get("vector_deletion_failures", 0) > 0:
                console.print(
                    "⚠️ Warning: Vector deletion failed but metadata was removed",
                    style="bold yellow",
                )
        else:
            console.print(
                f"❌ Failed to delete memory {memory_id}: {result['error']}",
                style="bold red",
            )
            raise typer.Exit(1)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error deleting memory: {e}", style="bold red")
        raise typer.Exit(1) from e


def delete_memories_by_tags_cmd(
    tags: list[str] = typer.Option(
        ..., "--tag", help="Tags to match (can be specified multiple times)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
    no_confirm: bool = typer.Option(
        False, "--no-confirm", help="Skip confirmation prompt"
    ),
    config: str | None = typer.Option(
        None, help="Path to .env configuration file to override default settings"
    ),
) -> None:
    """Delete all memories that have any of the specified tags."""
    try:
        # Initialize cognitive system
        if config:
            cognitive_system = initialize_with_config(config)
        else:
            cognitive_system = initialize_system("default")

        # Create operations instance
        ops = CognitiveOperations(cognitive_system)

        # First, run dry-run to show what would be deleted
        preview_result = ops.delete_memories_by_tags(tags, dry_run=True)

        if not preview_result["success"]:
            console.print(f"❌ {preview_result['error']}", style="bold red")
            raise typer.Exit(1)

        if preview_result["deleted_count"] == 0:
            console.print(
                f"📭 No memories found with tags: {', '.join(tags)}",
                style="bold yellow",
            )
            graceful_shutdown(cognitive_system)
            return

        # Show preview information
        console.print(
            f"🏷️  Found {preview_result['deleted_count']} memories with tags: [bold cyan]{', '.join(tags)}[/bold cyan]"
        )

        # Show preview of memories to be deleted
        preview_memories = preview_result.get("preview", [])
        if preview_memories:
            preview_table = Table(title="Memories to Delete")
            preview_table.add_column("ID", style="dim")
            preview_table.add_column("Content", style="white")
            preview_table.add_column("Level", style="cyan")
            preview_table.add_column("Tags", style="yellow")

            for mem in preview_memories[:10]:  # Show max 10 for readability
                preview_table.add_row(
                    mem["id"][:8] + "...",
                    mem["content"],
                    f"L{mem['hierarchy_level']}",
                    ", ".join(mem["tags"]) or "None",
                )

            console.print(preview_table)

            if len(preview_memories) > 10:
                console.print(
                    f"... and {len(preview_memories) - 10} more memories", style="dim"
                )

        if dry_run:
            console.print("🔍 DRY RUN - Memories would be deleted", style="bold blue")
            graceful_shutdown(cognitive_system)
            return

        # Confirmation prompt
        if not no_confirm:
            confirm = typer.confirm(
                f"Are you sure you want to delete {preview_result['deleted_count']} memories?"
            )
            if not confirm:
                console.print("⚠️ Deletion cancelled", style="bold yellow")
                graceful_shutdown(cognitive_system)
                return

        # Perform actual deletion
        result = ops.delete_memories_by_tags(tags, dry_run=False)

        if result["success"]:
            console.print(
                f"✅ Deleted {result['deleted_count']} memories with tags: {', '.join(tags)}",
                style="bold green",
            )
            if result["processing_time"] > 0:
                console.print(f"⏱️  Processing time: {result['processing_time']:.3f}s")

            if result.get("vector_deletion_failures", 0) > 0:
                console.print(
                    f"⚠️ Warning: {result['vector_deletion_failures']} vector deletions failed but metadata was removed",
                    style="bold yellow",
                )
        else:
            console.print(
                f"❌ Failed to delete memories with tags {', '.join(tags)}: {result['error']}",
                style="bold red",
            )
            raise typer.Exit(1)

        # Cleanup
        graceful_shutdown(cognitive_system)

    except InitializationError as e:
        console.print(f"❌ Failed to initialize system: {e}", style="bold red")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"❌ Error deleting memories: {e}", style="bold red")
        raise typer.Exit(1) from e
