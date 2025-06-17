"""
Interactive shell for cognitive memory system.

This module provides an enhanced interactive REPL for the cognitive memory system
with rich formatting, command completion, and intuitive cognitive operations.
"""

from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cognitive_memory.core.interfaces import CognitiveSystem


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

        # Set up prompt_toolkit session with history and styling
        history_file = Path.home() / ".cognitive_memory_history"
        self.prompt_style = Style.from_dict(
            {
                "prompt": "#00aa00 bold",  # Bright green, similar to original
            }
        )

        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_file)),
            enable_history_search=True,
            style=self.prompt_style,
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
            "[dim]Type 'help' for commands, 'quit' to exit[/dim]",
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
            text = command[6:].strip()
            if text:
                self._store_experience(text)
            else:
                self.console.print(
                    "[bold red]❌ Please provide text to store[/bold red]"
                )

        # Retrieve memories
        elif command.startswith("retrieve ") or command.startswith("recall "):
            query = command.split(" ", 1)[1].strip() if " " in command else ""
            if query:
                self._retrieve_memories(query)
            else:
                self.console.print("[bold red]❌ Please provide a query[/bold red]")

        # Bridge discovery
        elif command.startswith("bridges ") or command.startswith("connect "):
            query = command.split(" ", 1)[1].strip() if " " in command else ""
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
                "Retrieve related memories",
                "retrieve 'machine learning'",
            ),
            ("recall <query>", "Same as retrieve", "recall 'debugging issues'"),
            ("bridges <query>", "Discover connections", "bridges 'programming'"),
            ("connect <query>", "Same as bridges", "connect 'algorithms'"),
            ("status", "Show system status", "status"),
            ("config", "Show configuration", "config"),
            ("consolidate", "Organize memories", "consolidate"),
            ("session", "Show session stats", "session"),
            ("clear", "Clear screen", "clear"),
            ("help", "Show this help", "help"),
            ("quit", "Exit shell", "quit"),
        ]

        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)

        self.console.print(help_table)

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
                types=["core", "peripheral"],
                max_results=10,
            )

            total_results = sum(len(memories) for memories in results.values())

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
                    type_panel = Panel(
                        self._format_memories(memories),
                        title=f"{memory_type.upper()} MEMORIES ({len(memories)})",
                        border_style="blue" if memory_type == "core" else "dim",
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
        """Format memories for display."""
        lines = []
        for i, memory in enumerate(memories, 1):
            content = (
                memory.content[:80] + "..."
                if len(memory.content) > 80
                else memory.content
            )
            lines.append(f"{i}. [{memory.memory_type}] {content}")
            # Use similarity score from metadata if available, otherwise fallback to memory strength
            score = memory.metadata.get("similarity_score", memory.strength)
            lines.append(
                f"   ID: {memory.id}, Level: L{memory.hierarchy_level}, Strength: {score:.2f}"
            )
        return "\n".join(lines)

    def _format_bridges(self, bridges: list[Any]) -> str:
        """Format bridge connections for display."""
        lines = []
        for i, bridge in enumerate(bridges, 1):
            content = (
                bridge.content[:80] + "..."
                if len(bridge.content) > 80
                else bridge.content
            )
            lines.append(f"{i}. {content}")
            lines.append(
                f"   Novelty: {getattr(bridge, 'novelty_score', 0):.2f}, "
                f"Connection: {getattr(bridge, 'connection_potential', 0):.2f}"
            )
        return "\n".join(lines)
