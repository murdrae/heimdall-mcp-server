"""
Generic file synchronization handler for automatic memory updates.

This module implements a generic file synchronization system that detects file
changes and delegates to appropriate MemoryLoader implementations based on file
type. Provides atomic memory operations for file additions, modifications, and deletions.
"""

import time
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.interfaces import CognitiveSystem, MemoryLoader
from .file_monitor import ChangeType, FileChangeEvent
from .loader_registry import LoaderRegistry


class FileSyncError(Exception):
    """Exception raised when file synchronization operations fail."""

    pass


class FileSyncHandler:
    """
    Generic file synchronization handler.

    Coordinates file change events with memory operations using registered
    MemoryLoader implementations. Provides atomic operations to ensure
    memory consistency during file synchronization.
    """

    def __init__(
        self,
        cognitive_system: CognitiveSystem,
        loader_registry: LoaderRegistry,
        enable_atomic_operations: bool = True,
    ):
        """
        Initialize file sync handler.

        Args:
            cognitive_system: CognitiveSystem instance for memory operations
            loader_registry: Registry of available MemoryLoader implementations
            enable_atomic_operations: Whether to use atomic delete+reload operations
        """
        self.cognitive_system = cognitive_system
        self.loader_registry = loader_registry
        self.enable_atomic_operations = enable_atomic_operations

        # Statistics tracking
        self.stats: dict[str, int | float | None] = {
            "files_added": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "sync_errors": 0,
            "last_sync_time": None,
        }

        logger.info(
            "FileSyncHandler initialized with atomic operations: %s",
            enable_atomic_operations,
        )

    def handle_file_change(self, event: FileChangeEvent) -> bool:
        """
        Handle a file change event with appropriate memory operations.

        Args:
            event: FileChangeEvent describing the file change

        Returns:
            True if sync operation succeeded, False otherwise
        """
        try:
            logger.info(f"Processing file change event: {event}")
            start_time = time.time()

            # Dispatch based on change type
            success = False
            if event.change_type == ChangeType.ADDED:
                success = self._handle_file_added(event)
                if success:
                    self.stats["files_added"] = (self.stats["files_added"] or 0) + 1
            elif event.change_type == ChangeType.MODIFIED:
                success = self._handle_file_modified(event)
                if success:
                    self.stats["files_modified"] = (
                        self.stats["files_modified"] or 0
                    ) + 1
            elif event.change_type == ChangeType.DELETED:
                success = self._handle_file_deleted(event)
                if success:
                    self.stats["files_deleted"] = (self.stats["files_deleted"] or 0) + 1
            else:
                # This else block is for defensive programming in case enum is extended
                logger.error(f"Unknown change type: {event.change_type}")  # type: ignore[unreachable]

            # Update statistics
            sync_time = time.time() - start_time
            self.stats["last_sync_time"] = time.time()

            if success:
                logger.info(f"File sync completed in {sync_time:.3f}s: {event.path}")
            else:
                self.stats["sync_errors"] = (self.stats["sync_errors"] or 0) + 1
                logger.error(f"File sync failed after {sync_time:.3f}s: {event.path}")

            return success

        except Exception as e:
            self.stats["sync_errors"] = (self.stats["sync_errors"] or 0) + 1
            logger.error(f"Unexpected error handling file change {event}: {e}")
            return False

    def _handle_file_added(self, event: FileChangeEvent) -> bool:
        """
        Handle file addition by loading memories from the new file.

        Args:
            event: FileChangeEvent for file addition

        Returns:
            True if operation succeeded, False otherwise
        """
        try:
            # Get appropriate loader for this file
            loader = self.loader_registry.get_loader_for_file(event.path)
            if not loader:
                logger.debug(f"No loader available for file: {event.path}")
                return True  # Not an error - just unsupported file type

            # Load memories from the new file
            logger.debug(f"Loading memories from added file: {event.path}")
            memories = loader.load_from_source(str(event.path))

            if not memories:
                logger.debug(f"No memories extracted from file: {event.path}")
                return True

            # Store memories in cognitive system
            success_count = 0
            for memory in memories:
                try:
                    memory_id = self.cognitive_system.store_experience(
                        memory.content, memory.metadata
                    )
                    if memory_id:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to store memory from {event.path}: {e}")

            logger.info(
                f"Stored {success_count}/{len(memories)} memories from: {event.path}"
            )
            return success_count == len(memories)

        except Exception as e:
            logger.error(f"Error handling file addition {event.path}: {e}")
            return False

    def _handle_file_modified(self, event: FileChangeEvent) -> bool:
        """
        Handle file modification with atomic delete+reload operation.

        Args:
            event: FileChangeEvent for file modification

        Returns:
            True if operation succeeded, False otherwise
        """
        try:
            # Get appropriate loader for this file
            loader = self.loader_registry.get_loader_for_file(event.path)
            if not loader:
                logger.debug(f"No loader available for modified file: {event.path}")
                return True  # Not an error - just unsupported file type

            if self.enable_atomic_operations:
                return self._atomic_file_reload(event.path, loader)
            else:
                return self._simple_file_reload(event.path, loader)

        except Exception as e:
            logger.error(f"Error handling file modification {event.path}: {e}")
            return False

    def _handle_file_deleted(self, event: FileChangeEvent) -> bool:
        """
        Handle file deletion by removing all associated memories.

        Args:
            event: FileChangeEvent for file deletion

        Returns:
            True if operation succeeded, False otherwise
        """
        try:
            source_path = str(event.path)
            logger.debug(f"Deleting memories for deleted file: {source_path}")

            # Delete all memories associated with this source path
            result = self.cognitive_system.delete_memories_by_source_path(source_path)

            if result:
                deleted_count = result.get("deleted_memories", 0)
                logger.info(f"Deleted {deleted_count} memories for file: {source_path}")
                return True
            else:
                logger.warning(f"No delete result for file: {source_path}")
                return False

        except Exception as e:
            logger.error(f"Error handling file deletion {event.path}: {e}")
            return False

    def _atomic_file_reload(self, file_path: Path, loader: MemoryLoader) -> bool:
        """
        Perform atomic delete+reload operation for file modification.

        This method ensures memory consistency by treating the delete+reload
        as a single atomic operation. If reload fails, the system state
        remains consistent (though possibly stale).

        Args:
            file_path: Path to the modified file
            loader: MemoryLoader to use for reloading

        Returns:
            True if operation succeeded, False otherwise
        """
        source_path = str(file_path)

        try:
            # Step 1: Load new memories first (this can fail safely)
            logger.debug(f"Loading new memories for modified file: {file_path}")
            new_memories = loader.load_from_source(source_path)

            if not new_memories:
                logger.debug(f"No new memories from modified file: {file_path}")
                # Still need to delete old memories
                result = self.cognitive_system.delete_memories_by_source_path(
                    source_path
                )
                deleted_count = result.get("deleted_memories", 0) if result else 0
                logger.info(f"Deleted {deleted_count} old memories from: {file_path}")
                return True

            # Step 2: Delete existing memories
            logger.debug(f"Deleting existing memories for: {file_path}")
            delete_result = self.cognitive_system.delete_memories_by_source_path(
                source_path
            )
            deleted_count = (
                delete_result.get("deleted_memories", 0) if delete_result else 0
            )

            # Step 3: Store new memories
            logger.debug(f"Storing {len(new_memories)} new memories for: {file_path}")
            success_count = 0
            failed_memories = []

            for memory in new_memories:
                try:
                    memory_id = self.cognitive_system.store_experience(
                        memory.content, memory.metadata
                    )
                    if memory_id:
                        success_count += 1
                    else:
                        failed_memories.append(memory)
                except Exception as e:
                    logger.error(f"Failed to store memory during reload: {e}")
                    failed_memories.append(memory)

            # Log results
            logger.info(
                f"File reload: deleted {deleted_count}, stored {success_count}/{len(new_memories)} "
                f"memories for: {file_path}"
            )

            # Consider partial success acceptable for atomic operations
            return len(failed_memories) == 0

        except Exception as e:
            logger.error(f"Error in atomic file reload for {file_path}: {e}")
            return False

    def _simple_file_reload(self, file_path: Path, loader: MemoryLoader) -> bool:
        """
        Perform simple delete+reload operation without atomicity guarantees.

        Args:
            file_path: Path to the modified file
            loader: MemoryLoader to use for reloading

        Returns:
            True if operation succeeded, False otherwise
        """
        source_path = str(file_path)

        try:
            # Delete existing memories
            delete_result = self.cognitive_system.delete_memories_by_source_path(
                source_path
            )
            deleted_count = (
                delete_result.get("deleted_memories", 0) if delete_result else 0
            )

            # Load and store new memories
            new_memories = loader.load_from_source(source_path)
            if not new_memories:
                logger.info(
                    f"Simple reload: deleted {deleted_count}, no new memories: {file_path}"
                )
                return True

            success_count = 0
            for memory in new_memories:
                try:
                    memory_id = self.cognitive_system.store_experience(
                        memory.content, memory.metadata
                    )
                    if memory_id:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to store memory in simple reload: {e}")

            logger.info(
                f"Simple reload: deleted {deleted_count}, stored {success_count}/{len(new_memories)} "
                f"memories for: {file_path}"
            )

            return success_count == len(new_memories)

        except Exception as e:
            logger.error(f"Error in simple file reload for {file_path}: {e}")
            return False

    def get_sync_statistics(self) -> dict[str, Any]:
        """
        Get file synchronization statistics.

        Returns:
            Dictionary containing sync operation statistics
        """
        return dict(self.stats)

    def reset_statistics(self) -> None:
        """Reset all synchronization statistics to zero."""
        self.stats = {
            "files_added": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "sync_errors": 0,
            "last_sync_time": None,
        }
        logger.debug("File sync statistics reset")

    def get_supported_file_types(self) -> set[str]:
        """
        Get all file types supported by registered loaders.

        Returns:
            Set of supported file extensions
        """
        return self.loader_registry.get_supported_extensions()

    def is_file_supported(self, file_path: Path) -> bool:
        """
        Check if a file is supported by any registered loader.

        Args:
            file_path: Path to check for support

        Returns:
            True if file is supported, False otherwise
        """
        return self.loader_registry.get_loader_for_file(file_path) is not None
