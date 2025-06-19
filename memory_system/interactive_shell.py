"""
Interactive shell for cognitive memory system.

This module provides an enhanced interactive REPL for the cognitive memory system
with rich formatting, command completion, and intuitive cognitive operations.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    WordCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cognitive_memory.core.interfaces import CognitiveSystem
from memory_system.display_utils import format_source_info


class CognitiveShellCompleter(Completer):
    """
    Custom completer for cognitive memory shell commands.

    Provides completion for:
    - Command names
    - File paths for load command
    - --recursive flag for load command
    """

    def __init__(self) -> None:
        """Initialize the completer with command definitions."""
        # Define main commands
        self.commands = [
            "store",
            "retrieve",
            "recall",
            "bridges",
            "connect",
            "status",
            "config",
            "consolidate",
            "session",
            "load",
            "git-load",
            "git-status",
            "git-patterns",
            "clear",
            "help",
            "quit",
            "exit",
        ]

        # Create sub-completers
        self.command_completer = WordCompleter(self.commands, ignore_case=True)
        self.path_completer = PathCompleter()

        # Load command specific flags
        self.load_flags = ["--recursive", "-r", "--dry-run"]

    def get_completions(
        self, document: Document, complete_event: Any
    ) -> Generator[Completion]:
        """Generate completions based on current input."""
        text = document.text
        words = text.split()

        if not words:
            # No input yet - suggest commands
            yield from self.command_completer.get_completions(document, complete_event)
            return

        command = words[0].lower()

        if len(words) == 1 and not text.endswith(" "):
            # Still typing the command
            yield from self.command_completer.get_completions(document, complete_event)
            return

        if command in ["load", "git-load"]:
            # Special handling for load and git-load commands
            if len(words) >= 2:
                # Get the current word being typed
                current_word = words[-1] if not text.endswith(" ") else ""

                # Check if it's a flag
                if current_word.startswith("-"):
                    flags = self.load_flags.copy()
                    if command == "git-load":
                        flags.extend(["--time-window", "--refresh"])

                    for flag in flags:
                        if flag.startswith(current_word):
                            yield Completion(
                                flag,
                                start_position=-len(current_word),
                                display=flag,
                                display_meta="flag option",
                            )
                else:
                    # Path completion for load command
                    # Create a document with just the path part
                    if text.endswith(" "):
                        path_document = Document("")
                    else:
                        path_start = text.rfind(" ") + 1
                        path_text = text[path_start:]
                        # Skip flags when finding path position
                        if not path_text.startswith("-"):
                            path_document = Document(path_text)
                            completions = list(
                                self.path_completer.get_completions(
                                    path_document, complete_event
                                )
                            )
                            for completion in completions:
                                # Add metadata to distinguish files vs directories
                                try:
                                    full_path = Path(path_text + completion.text)
                                    if full_path.exists():
                                        if full_path.is_dir():
                                            if (
                                                command == "git-load"
                                                and (full_path / ".git").exists()
                                            ):
                                                meta = "git repository"
                                            else:
                                                meta = "directory"
                                        elif full_path.suffix.lower() in [
                                            ".md",
                                            ".markdown",
                                            ".mdown",
                                            ".mkd",
                                        ]:
                                            meta = "markdown file"
                                        else:
                                            meta = "file"
                                    else:
                                        meta = completion.display_meta or ""
                                except Exception:
                                    meta = completion.display_meta or ""

                                yield Completion(
                                    completion.text,
                                    start_position=completion.start_position,
                                    display=completion.display,
                                    display_meta=meta,
                                )
            else:
                # First argument after load - suggest paths
                yield from self.path_completer.get_completions(
                    Document(""), complete_event
                )


class InteractiveShell:
    """
    Enhanced interactive shell for cognitive memory operations.

    Provides a user-friendly REPL with rich formatting, help system,
    and streamlined commands for cognitive memory interaction.
    """

    def __init__(
        self,
        cognitive_system: CognitiveSystem,
        custom_prompt: str | None = None,
    ):
        """
        Initialize interactive shell.

        Args:
            cognitive_system: The cognitive system interface
            custom_prompt: Optional custom prompt string
        """
        self.cognitive_system = cognitive_system
        self.console = Console()
        self.prompt_text = custom_prompt or "cognitive"
        self.session_stats = {
            "memories_stored": 0,
            "queries_made": 0,
            "bridges_discovered": 0,
        }

        # Set up prompt_toolkit session with history, styling, and completion
        # Use /app/data for history file to avoid permissions issues in container
        data_dir = Path("/app/data")
        if data_dir.exists() and data_dir.is_dir():
            history_file = data_dir / ".cognitive_memory_history"
        else:
            # Fallback to current directory if /app/data doesn't exist
            history_file = Path(".cognitive_memory_history")
        self.prompt_style = Style.from_dict(
            {
                "prompt": "#00aa00 bold",  # Bright green, similar to original
                "completion-menu": "bg:#888888 #ffffff",
                "completion-menu.completion": "bg:#888888 #ffffff",
                "completion-menu.completion.current": "bg:#444444 #ffffff bold",
                "completion-menu.meta.completion": "bg:#999999 #000000",
                "completion-menu.meta.completion.current": "bg:#444444 #ffffff",
            }
        )

        # Create completer instance
        self.completer = CognitiveShellCompleter()

        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_file)),
            enable_history_search=True,
            style=self.prompt_style,
            completer=self.completer,
            complete_while_typing=True,
        )

    def run(self) -> None:
        """Run the interactive shell."""
        self._show_welcome()

        while True:
            try:
                # Use prompt_toolkit for professional shell experience with history
                command = self.prompt_session.prompt(
                    [("class:prompt", f"\n{self.prompt_text}> ")],  # \n for spacing
                ).strip()

                if not command:
                    continue

                if self._handle_command(command):
                    break

            except KeyboardInterrupt:
                self.console.print("\n[bold yellow]👋 Goodbye![/bold yellow]")
                break
            except EOFError:
                self.console.print("\n[bold yellow]👋 Goodbye![/bold yellow]")
                break
            except Exception as e:
                self.console.print(f"[bold red]❌ Error: {e}[/bold red]")

    def _show_welcome(self) -> None:
        """Show welcome message and help."""
        welcome_panel = Panel(
            "[bold blue]🧠 Cognitive Memory Interactive Shell[/bold blue]\n\n"
            "Welcome to your cognitive memory system! This shell provides intuitive\n"
            "commands for storing experiences, retrieving memories, and discovering\n"
            "serendipitous connections.\n\n"
            "[dim]🧠 Memory Types:[/dim]\n"
            "[dim]  🎯 Core: Most relevant to your query[/dim]\n"
            "[dim]  🌐 Peripheral: Contextual associations[/dim]\n"
            "[dim]  🌉 Bridge: Creative connections between distant concepts[/dim]\n\n"
            "[dim]💡 Tips:[/dim]\n"
            "[dim]  • Type 'help' for commands, 'quit' to exit[/dim]\n"
            "[dim]  • Use TAB for command and path completion[/dim]\n"
            "[dim]  • Try 'load docs/' + TAB to browse directories[/dim]",
            title="Welcome",
            border_style="blue",
        )
        self.console.print(welcome_panel)

    def _handle_command(self, command: str) -> bool:
        """
        Handle user command.

        Args:
            command: User input command

        Returns:
            bool: True if should exit shell
        """
        # Store original command for file path handling
        original_command = command
        command = command.lower()

        # Exit commands
        if command in ["quit", "exit", "q", "bye"]:
            self._show_session_summary()
            return True

        # Help command
        elif command in ["help", "h", "?"]:
            self._show_help()

        # Store experience
        elif command.startswith("store "):
            # Use original command to preserve case and formatting
            text = original_command[6:].strip()
            if text:
                self._store_experience(text)
            else:
                self.console.print(
                    "[bold red]❌ Please provide text to store[/bold red]"
                )

        # Retrieve memories
        elif command.startswith("retrieve ") or command.startswith("recall "):
            # Use original command to preserve case in queries
            query = (
                original_command.split(" ", 1)[1].strip()
                if " " in original_command
                else ""
            )
            if query:
                self._retrieve_memories(query)
            else:
                self.console.print("[bold red]❌ Please provide a query[/bold red]")

        # Bridge discovery
        elif command.startswith("bridges ") or command.startswith("connect "):
            # Use original command to preserve case in queries
            query = (
                original_command.split(" ", 1)[1].strip()
                if " " in original_command
                else ""
            )
            if query:
                self._discover_bridges(query)
            else:
                self.console.print(
                    "[bold red]❌ Please provide a query for bridge discovery[/bold red]"
                )

        # System status
        elif command in ["status", "stats"]:
            self._show_status()

        # System configuration
        elif command in ["config", "settings"]:
            self._show_config()

        # Memory consolidation
        elif command in ["consolidate", "organize"]:
            self._consolidate_memories()

        # Session statistics
        elif command in ["session", "summary"]:
            self._show_session_summary()

        # Clear screen
        elif command in ["clear", "cls"]:
            self.console.clear()

        # Load memories from file
        elif command.startswith("load"):
            # Handle "load" command with or without arguments
            if command == "load":
                self.console.print("[bold red]❌ Please provide a file path[/bold red]")
                self.console.print("[dim]Usage: load <file_path> [--recursive][/dim]")
            else:
                # Use original command to preserve case-sensitive file paths
                args = original_command[5:].strip().split()
                if args:
                    file_path = args[0]
                    recursive = "--recursive" in args or "-r" in args
                    self._load_memories(file_path, recursive=recursive)
                else:
                    self.console.print(
                        "[bold red]❌ Please provide a file path[/bold red]"
                    )

        # Git commands
        elif command.startswith("git-load"):
            # Handle "git-load" command with or without arguments
            if command == "git-load":
                self.console.print(
                    "[bold red]❌ Please provide a repository path[/bold red]"
                )
                self.console.print(
                    "[dim]Usage: git-load <repo_path> [--dry-run] [--time-window 3m][/dim]"
                )
            else:
                # Use original command to preserve case-sensitive paths
                args = original_command[8:].strip().split()
                if args:
                    repo_path = args[0]
                    dry_run = "--dry-run" in args
                    self._load_git_patterns(repo_path, dry_run=dry_run)
                else:
                    self.console.print(
                        "[bold red]❌ Please provide a repository path[/bold red]"
                    )

        elif command.startswith("git-status"):
            # Handle "git-status" command
            args = (
                original_command[10:].strip().split()
                if len(original_command) > 10
                else []
            )
            git_repo_path = args[0] if args else None
            self._show_git_status(git_repo_path)

        elif command.startswith("git-patterns"):
            # Handle "git-patterns" command
            if command == "git-patterns":
                self.console.print(
                    "[bold red]❌ Please provide a search query[/bold red]"
                )
                self.console.print(
                    "[dim]Usage: git-patterns <query> [--type cochange|hotspot|solution][/dim]"
                )
            else:
                # Parse arguments
                args = original_command[12:].strip().split()
                if args:
                    # Extract query (everything that's not a flag)
                    query_parts = []
                    pattern_type = None
                    i = 0
                    while i < len(args):
                        if args[i] == "--type" and i + 1 < len(args):
                            pattern_type = args[i + 1]
                            i += 2
                        else:
                            query_parts.append(args[i])
                            i += 1

                    query = " ".join(query_parts)
                    self._search_git_patterns(query, pattern_type)
                else:
                    self.console.print(
                        "[bold red]❌ Please provide a search query[/bold red]"
                    )

        # Unknown command
        else:
            self.console.print(f"[bold red]❌ Unknown command: {command}[/bold red]")
            self.console.print("[dim]Type 'help' for available commands[/dim]")

        return False

    def _show_help(self) -> None:
        """Show help information."""
        help_table = Table(
            title="Available Commands", show_header=True, header_style="bold blue"
        )
        help_table.add_column("Command", style="cyan", width=20)
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim")

        commands = [
            (
                "store <text>",
                "Store new experience",
                "store 'Working on neural networks'",
            ),
            (
                "retrieve <query>",
                "Retrieve all memory types (core/peripheral/bridge)",
                "retrieve 'machine learning'",
            ),
            ("recall <query>", "Same as retrieve", "recall 'debugging issues'"),
            (
                "bridges <query>",
                "Focus on bridge connections only",
                "bridges 'programming'",
            ),
            ("connect <query>", "Same as bridges", "connect 'algorithms'"),
            ("status", "Show system status", "status"),
            ("config", "Show configuration", "config"),
            ("consolidate", "Organize memories", "consolidate"),
            ("session", "Show session stats", "session"),
            (
                "load <file> [--recursive]",
                "Load memories from file or directory",
                "load docs/ --recursive",
            ),
            (
                "git-load <repo> [--dry-run]",
                "Load git repository patterns",
                "git-load /path/to/repo --dry-run",
            ),
            (
                "git-status [repo]",
                "Show git pattern analysis status",
                "git-status /path/to/repo",
            ),
            (
                "git-patterns <query> [--type]",
                "Search git patterns",
                "git-patterns auth --type cochange",
            ),
            ("clear", "Clear screen", "clear"),
            ("help", "Show this help", "help"),
            ("quit", "Exit shell", "quit"),
        ]

        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)

        self.console.print(help_table)

        # Add completion tip
        self.console.print(
            "\n[dim]💡 Use TAB for command and path completion. "
            "For example: 'load docs/' + TAB[/dim]"
        )

    def _store_experience(self, text: str) -> None:
        """Store a new experience."""
        try:
            memory_id = self.cognitive_system.store_experience(text)
            if memory_id:
                self.session_stats["memories_stored"] += 1
                self.console.print(
                    f"[bold green]✅ Experience stored with ID: {memory_id}[/bold green]"
                )
            else:
                self.console.print("[bold red]❌ Failed to store experience[/bold red]")
        except Exception as e:
            self.console.print(f"[bold red]❌ Error storing experience: {e}[/bold red]")

    def _retrieve_memories(self, query: str) -> None:
        """Retrieve memories for a query."""
        try:
            self.session_stats["queries_made"] += 1

            results = self.cognitive_system.retrieve_memories(
                query=query,
                types=["core", "peripheral", "bridge"],
                max_results=10,
            )

            # Count total results (handle BridgeMemory objects in bridge results)
            total_results = 0
            for _memory_type, memories in results.items():
                total_results += len(memories)

            if total_results == 0:
                self.console.print(
                    "[bold yellow]🔍 No memories found for query[/bold yellow]"
                )
                return

            self.console.print(
                f"\n[bold blue]📋 Retrieved {total_results} memories for: '{query}'[/bold blue]"
            )

            for memory_type, memories in results.items():
                if memories:
                    # Choose appropriate styling for each memory type
                    if memory_type == "core":
                        border_style = "blue"
                        title_style = "🎯 CORE MEMORIES"
                    elif memory_type == "peripheral":
                        border_style = "dim"
                        title_style = "🌐 PERIPHERAL MEMORIES"
                    elif memory_type == "bridge":
                        border_style = "magenta"
                        title_style = "🌉 BRIDGE MEMORIES"
                    else:
                        border_style = "white"
                        title_style = f"{memory_type.upper()} MEMORIES"

                    # Use bridge-specific formatting for bridge memories
                    if memory_type == "bridge":
                        content = self._format_bridges(memories)
                    else:
                        content = self._format_memories(memories)

                    type_panel = Panel(
                        content,
                        title=f"{title_style} ({len(memories)})",
                        border_style=border_style,
                    )
                    self.console.print(type_panel)

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error retrieving memories: {e}[/bold red]"
            )

    def _discover_bridges(self, query: str) -> None:
        """Discover bridge connections."""
        try:
            self.session_stats["bridges_discovered"] += 1

            results = self.cognitive_system.retrieve_memories(
                query=query,
                types=["bridge"],
                max_results=5,
            )

            bridges = results.get("bridge", [])

            if not bridges:
                self.console.print(
                    "[bold yellow]🌉 No bridge connections found[/bold yellow]"
                )
                return

            bridge_panel = Panel(
                self._format_bridges(bridges),
                title=f"🌉 BRIDGE CONNECTIONS ({len(bridges)})",
                border_style="magenta",
            )
            self.console.print(bridge_panel)

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error discovering bridges: {e}[/bold red]"
            )

    def _show_status(self) -> None:
        """Show system status."""
        try:
            stats = self.cognitive_system.get_memory_stats()

            status_table = Table(
                title="System Status", show_header=True, header_style="bold green"
            )
            status_table.add_column("Metric", style="cyan")
            status_table.add_column("Value", style="white")

            # Memory counts
            if "memory_counts" in stats:
                for key, count in stats["memory_counts"].items():
                    if isinstance(count, int):
                        level_name = (
                            key.replace("level_", "L").replace("_", " ").title()
                        )
                        status_table.add_row(level_name, str(count))

            # Configuration
            if "system_config" in stats:
                config = stats["system_config"]
                status_table.add_row(
                    "Activation Threshold",
                    str(config.get("activation_threshold", "N/A")),
                )
                status_table.add_row(
                    "Bridge Discovery K", str(config.get("bridge_discovery_k", "N/A"))
                )

            self.console.print(status_table)

        except Exception as e:
            self.console.print(f"[bold red]❌ Error retrieving status: {e}[/bold red]")

    def _show_config(self) -> None:
        """Show detailed configuration."""
        try:
            stats = self.cognitive_system.get_memory_stats()

            if "system_config" in stats:
                config = stats["system_config"]

                config_table = Table(
                    title="System Configuration",
                    show_header=True,
                    header_style="bold blue",
                )
                config_table.add_column("Setting", style="cyan")
                config_table.add_column("Value", style="white")

                for key, value in config.items():
                    config_table.add_row(key.replace("_", " ").title(), str(value))

                self.console.print(config_table)
            else:
                self.console.print(
                    "[bold yellow]⚠️ Configuration not available[/bold yellow]"
                )

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error retrieving configuration: {e}[/bold red]"
            )

    def _consolidate_memories(self) -> None:
        """Trigger memory consolidation."""
        try:
            self.console.print(
                "[bold blue]🔄 Starting memory consolidation...[/bold blue]"
            )

            results = self.cognitive_system.consolidate_memories()

            consolidation_table = Table(
                title="Consolidation Results",
                show_header=True,
                header_style="bold green",
            )
            consolidation_table.add_column("Metric", style="cyan")
            consolidation_table.add_column("Count", style="white")

            consolidation_table.add_row(
                "Total Episodic", str(results.get("total_episodic", 0))
            )
            consolidation_table.add_row(
                "Consolidated", str(results.get("consolidated", 0))
            )
            consolidation_table.add_row("Failed", str(results.get("failed", 0)))
            consolidation_table.add_row("Skipped", str(results.get("skipped", 0)))

            self.console.print(consolidation_table)
            self.console.print("[bold green]✅ Consolidation completed[/bold green]")

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error during consolidation: {e}[/bold red]"
            )

    def _load_memories(self, file_path: str, recursive: bool = False) -> None:
        """Load memories from a file using CognitiveCLI."""
        try:
            # Import and use the existing CognitiveCLI implementation
            from interfaces.cli import CognitiveCLI

            cli = CognitiveCLI(self.cognitive_system)

            self.console.print(
                f"[bold blue]📁 Loading memories from {file_path}...[/bold blue]"
            )

            # Use the existing load_memories implementation
            success = cli.load_memories(file_path, recursive=recursive)

            if success:
                self.console.print(
                    "[bold green]✅ Memory loading completed successfully[/bold green]"
                )
            else:
                self.console.print("[bold red]❌ Memory loading failed[/bold red]")

        except Exception as e:
            self.console.print(f"[bold red]❌ Error loading memories: {e}[/bold red]")

    def _load_git_patterns(self, repo_path: str, dry_run: bool = False) -> None:
        """Load git patterns using CognitiveCLI."""
        try:
            # Import and use the existing CognitiveCLI implementation
            from interfaces.cli import CognitiveCLI

            cli = CognitiveCLI(self.cognitive_system)

            self.console.print(
                f"[bold blue]📁 Loading git patterns from {repo_path}...[/bold blue]"
            )

            # Use the existing load_git_patterns implementation
            success = cli.load_git_patterns(repo_path, dry_run=dry_run)

            if success:
                self.console.print(
                    "[bold green]✅ Git pattern loading completed successfully[/bold green]"
                )
            else:
                self.console.print("[bold red]❌ Git pattern loading failed[/bold red]")

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error loading git patterns: {e}[/bold red]"
            )

    def _show_git_status(self, repo_path: str | None = None) -> None:
        """Show git analysis status using CognitiveCLI."""
        try:
            # Import and use the existing CognitiveCLI implementation
            from interfaces.cli import CognitiveCLI

            cli = CognitiveCLI(self.cognitive_system)

            # Use the existing show_git_status implementation
            success = cli.show_git_status(repo_path)

            if not success:
                self.console.print(
                    "[bold red]❌ Failed to retrieve git status[/bold red]"
                )

        except Exception as e:
            self.console.print(f"[bold red]❌ Error showing git status: {e}[/bold red]")

    def _search_git_patterns(self, query: str, pattern_type: str | None = None) -> None:
        """Search git patterns using CognitiveCLI."""
        try:
            # Import and use the existing CognitiveCLI implementation
            from interfaces.cli import CognitiveCLI

            cli = CognitiveCLI(self.cognitive_system)

            # Use the existing search_git_patterns implementation
            success = cli.search_git_patterns(query, pattern_type=pattern_type)

            if not success:
                self.console.print(
                    "[bold red]❌ Failed to search git patterns[/bold red]"
                )

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error searching git patterns: {e}[/bold red]"
            )

    def _show_session_summary(self) -> None:
        """Show session statistics."""
        summary_table = Table(
            title="Session Summary", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("Activity", style="cyan")
        summary_table.add_column("Count", style="white")

        summary_table.add_row(
            "Memories Stored", str(self.session_stats["memories_stored"])
        )
        summary_table.add_row("Queries Made", str(self.session_stats["queries_made"]))
        summary_table.add_row(
            "Bridges Discovered", str(self.session_stats["bridges_discovered"])
        )

        self.console.print(summary_table)

    def _format_memories(self, memories: list[Any]) -> str:
        """Format memories for display with intelligent multiline handling."""
        lines = []
        for i, memory in enumerate(memories, 1):
            # Get title from metadata if available
            title = memory.metadata.get("title", "")

            # Smart content preview
            content_preview = self._create_content_preview(memory.content, title)

            # Memory header with type and title
            if title:
                lines.append(f"{i}. [{memory.memory_type}] {title}")
            else:
                lines.append(f"{i}. [{memory.memory_type}] Memory")

            # Content preview with proper indentation
            for line in content_preview.split("\n"):
                lines.append(f"   {line}")

            # Metadata line
            score = memory.metadata.get("similarity_score", memory.strength)
            lines.append(
                f"   ID: {memory.id}, Level: L{memory.hierarchy_level}, Strength: {score:.2f}"
            )

            # Source information
            source_info = format_source_info(memory)
            if source_info:
                lines.append(f"   Source: {source_info}")

            lines.append("")  # Empty line for separation

        return "\n".join(lines)

    def _create_content_preview(self, content: str, title: str = "") -> str:
        """Create an intelligent preview of memory content."""
        lines = content.strip().split("\n")
        preview_lines = []

        # Remove title from content if it's already shown
        if title and lines and title.strip() in lines[0]:
            lines = lines[1:]

        # Smart preview strategy
        max_lines = 4
        max_chars_per_line = 120

        for line in lines[:max_lines]:
            line = line.strip()
            if not line:
                continue

            # Truncate long lines smartly at word boundaries
            if len(line) > max_chars_per_line:
                words = line.split()
                truncated = ""
                for word in words:
                    if len(truncated + word + " ") <= max_chars_per_line - 3:
                        truncated += word + " "
                    else:
                        break
                line = truncated.strip() + "..."

            preview_lines.append(line)

        # Add continuation indicator if there's more content
        remaining_lines = len([line for line in lines[max_lines:] if line.strip()])
        if remaining_lines > 0:
            preview_lines.append(f"... (+{remaining_lines} more lines)")

        return "\n".join(preview_lines)

    def _format_bridges(self, bridges: list[Any]) -> str:
        """Format bridge connections for display."""
        lines = []
        for i, bridge_item in enumerate(bridges, 1):
            # Handle BridgeMemory objects properly
            if hasattr(bridge_item, "memory"):
                # This is a BridgeMemory object
                memory = bridge_item.memory
                content = (
                    memory.content[:80] + "..."
                    if len(memory.content) > 80
                    else memory.content
                )
                lines.append(f"{i}. {content}")
                lines.append(
                    f"   Novelty: {bridge_item.novelty_score:.2f}, "
                    f"Connection: {bridge_item.connection_potential:.2f}, "
                    f"Bridge Score: {bridge_item.bridge_score:.2f}"
                )
                if bridge_item.explanation:
                    lines.append(f"   {bridge_item.explanation}")

                # Add source information for bridge memories
                source_info = format_source_info(memory)
                if source_info:
                    lines.append(f"   Source: {source_info}")
            else:
                # Fallback for regular CognitiveMemory objects (backward compatibility)
                content = (
                    bridge_item.content[:80] + "..."
                    if len(bridge_item.content) > 80
                    else bridge_item.content
                )
                lines.append(f"{i}. {content}")
                lines.append(
                    f"   Novelty: {getattr(bridge_item, 'novelty_score', 0):.2f}, "
                    f"Connection: {getattr(bridge_item, 'connection_potential', 0):.2f}"
                )

                # Add source information for bridge memories (fallback case)
                source_info = format_source_info(bridge_item)
                if source_info:
                    lines.append(f"   Source: {source_info}")
            lines.append("")  # Empty line for separation
        return "\n".join(lines)
