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

from cognitive_memory.core.interfaces import CognitiveSystem
from heimdall.monitoring.file_types import ChangeType, FileChangeEvent

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
    ):
        """
        Initialize file sync handler.

        Args:
            cognitive_system: CognitiveSystem instance for memory operations
            loader_registry: Registry of available MemoryLoader implementations
        """
        self.cognitive_system = cognitive_system
        self.loader_registry = loader_registry

        # Statistics tracking
        self.stats: dict[str, int | float | None] = {
            "files_added": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "sync_errors": 0,
            "last_sync_time": None,
        }

        logger.info("FileSyncHandler initialized")

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

            # Use centralized atomic reload operation
            source_path = str(event.path)
            logger.debug(f"Performing atomic reload for modified file: {event.path}")

            result = self.cognitive_system.atomic_reload_memories_from_source(
                loader, source_path
            )

            if result.get("success", False):
                deleted_count = result.get("deleted_count", 0)
                loaded_count = result.get("memories_loaded", 0)
                logger.info(
                    f"File sync reload completed: deleted {deleted_count}, "
                    f"loaded {loaded_count} memories from {event.path}"
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Atomic reload failed for {event.path}: {error_msg}")
                return False

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
                deleted_count = result.get("deleted_count", 0)
                logger.info(f"Deleted {deleted_count} memories for file: {source_path}")
                return True
            else:
                logger.warning(f"No delete result for file: {source_path}")
                return False

        except Exception as e:
            logger.error(f"Error handling file deletion {event.path}: {e}")
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
