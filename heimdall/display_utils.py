"""
Display utilities for cognitive memory system.

Shared formatting functions for CLI and interactive shell.
"""

import json
from pathlib import Path
from typing import Any


def format_source_info(memory: Any) -> str:
    """
    Format memory source information for display.

    Args:
        memory: CognitiveMemory object

    Returns:
        Formatted source string or empty string if no source info
    """
    loader_type = memory.metadata.get("loader_type")
    source_path = memory.metadata.get("source_path")

    if not loader_type:
        # Fallback: try to infer from memory ID pattern
        if memory.id.startswith("git::"):
            loader_type = "git"
        elif source_path and source_path.endswith(".md"):
            loader_type = "markdown"

    if loader_type == "markdown":
        if source_path:
            # Show relative path if possible
            try:
                path_obj = Path(source_path)
                if path_obj.is_absolute():
                    # Try to make it relative to current working directory
                    try:
                        rel_path = path_obj.relative_to(Path.cwd())
                        source_display = str(rel_path)
                    except ValueError:
                        # Not relative to cwd, show just filename
                        source_display = path_obj.name
                else:
                    source_display = source_path
            except Exception:
                source_display = source_path

            # Add section info if available
            title = memory.metadata.get("title")
            if title and title != "Untitled":
                return f"📄 {source_display} → {title}"
            else:
                return f"📄 {source_display}"
        else:
            return "📄 Markdown"

    elif loader_type == "git":
        pattern_type = memory.metadata.get("pattern_type", "pattern")
        repo_path = source_path

        if repo_path:
            try:
                repo_name = Path(repo_path).name
            except Exception:
                repo_name = repo_path
        else:
            repo_name = "repository"

        # Add specific pattern details
        pattern_icons = {"cochange": "🔄", "hotspot": "🔥", "solution": "💡"}
        icon = pattern_icons.get(pattern_type, "📊")

        # Show file names for cochange patterns
        if pattern_type == "cochange":
            file_a = memory.metadata.get("file_a", "")
            file_b = memory.metadata.get("file_b", "")
            if file_a and file_b:
                file_a_name = Path(file_a).name
                file_b_name = Path(file_b).name
                return f"{icon} {repo_name} → {file_a_name} ↔ {file_b_name}"
        elif pattern_type == "hotspot":
            file_path = memory.metadata.get("file_path", "")
            if file_path:
                file_name = Path(file_path).name
                return f"{icon} {repo_name} → {file_name}"

        return f"{icon} {repo_name} → {pattern_type}"

    elif source_path:
        # Generic file source
        try:
            source_display = Path(source_path).name
        except Exception:
            source_display = source_path
        return f"📁 {source_display}"

    return ""


def format_memory_results_json(result_data: dict[str, Any]) -> str:
    """
    Format memory retrieval results optimized for LLM consumption using JSON structure.

    Args:
        result_data: Dictionary from operations.retrieve_memories()

    Returns:
        str: JSON-structured formatted string optimized for LLM processing
    """
    if not result_data["success"]:
        return f"❌ Error retrieving memories: {result_data['error']}"

    if result_data["total_count"] == 0:
        return f"No memories found for query: '{result_data['query']}'"

    formatted_results: dict[str, Any] = {
        "query": result_data["query"],
        "total_results": result_data["total_count"],
        "memories": {},
    }

    # Process each memory type
    for memory_type in ["core", "peripheral"]:
        memories = result_data.get(memory_type, [])
        if memories:
            formatted_results["memories"][memory_type] = []

            for memory_item in memories:
                # Handle regular memory objects
                memory = memory_item
                if hasattr(memory_item, "memory"):
                    memory = memory_item.memory

                memory_data = {
                    "type": memory_type,
                    "content": memory.content,
                    "metadata": {
                        "id": memory.id,
                        "hierarchy_level": memory.hierarchy_level,
                        "memory_type": memory.memory_type,
                        "source": format_source_info(memory),
                        "created_date": memory.created_date.isoformat()
                        if memory.created_date
                        else None,
                        "last_accessed": memory.last_accessed.isoformat()
                        if memory.last_accessed
                        else None,
                        "access_count": memory.access_count,
                        "importance_score": memory.importance_score,
                        "tags": memory.tags,
                    },
                }

                # Use similarity score from metadata if available, otherwise fallback to memory strength
                score = memory.metadata.get("similarity_score", memory.strength)
                memory_data["metadata"]["strength"] = round(score, 3)

                formatted_results["memories"][memory_type].append(memory_data)

    return json.dumps(formatted_results, ensure_ascii=False, separators=(",", ":"))
