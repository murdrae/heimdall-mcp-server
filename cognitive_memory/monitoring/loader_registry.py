"""
Loader registry system for managing MemoryLoader implementations.

This module provides a registry system for discovering, registering, and managing
different MemoryLoader implementations. Enables automatic file type detection
and delegation to appropriate loaders for file synchronization.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from ..core.interfaces import MemoryLoader


class LoaderRegistry:
    """
    Registry for managing MemoryLoader implementations.

    Provides automatic discovery and registration of loaders, enabling
    efficient file type detection and delegation for sync operations.
    """

    def __init__(self) -> None:
        """Initialize empty loader registry."""
        self._loaders: dict[str, MemoryLoader] = {}
        self._extension_map: dict[str, list[str]] = {}  # extension -> loader names
        logger.debug("LoaderRegistry initialized")

    def register_loader(self, name: str, loader: MemoryLoader) -> None:
        """
        Register a memory loader with the registry.

        Args:
            name: Unique name for the loader (e.g., 'markdown', 'pdf')
            loader: MemoryLoader implementation to register

        Raises:
            ValueError: If loader name already exists or loader is invalid
        """
        if not isinstance(loader, MemoryLoader):
            raise ValueError(
                f"Loader must implement MemoryLoader interface: {type(loader)}"
            )

        if name in self._loaders:
            logger.warning(f"Overwriting existing loader registration: {name}")

        self._loaders[name] = loader

        # Update extension mapping
        try:
            supported_extensions = loader.get_supported_extensions()
            for ext in supported_extensions:
                ext_normalized = ext.lower().lstrip(".")
                if ext_normalized not in self._extension_map:
                    self._extension_map[ext_normalized] = []
                if name not in self._extension_map[ext_normalized]:
                    self._extension_map[ext_normalized].append(name)

            logger.info(
                f"Registered loader '{name}' for extensions: {supported_extensions}"
            )
        except Exception as e:
            logger.error(f"Failed to register extensions for loader '{name}': {e}")
            # Remove the loader if extension registration failed
            del self._loaders[name]
            raise

    def unregister_loader(self, name: str) -> bool:
        """
        Unregister a memory loader from the registry.

        Args:
            name: Name of the loader to unregister

        Returns:
            True if loader was found and removed, False otherwise
        """
        if name not in self._loaders:
            logger.warning(f"Attempted to unregister non-existent loader: {name}")
            return False

        loader = self._loaders[name]

        # Remove from extension mapping
        try:
            supported_extensions = loader.get_supported_extensions()
            for ext in supported_extensions:
                ext_normalized = ext.lower().lstrip(".")
                if ext_normalized in self._extension_map:
                    if name in self._extension_map[ext_normalized]:
                        self._extension_map[ext_normalized].remove(name)
                    # Clean up empty extension entries
                    if not self._extension_map[ext_normalized]:
                        del self._extension_map[ext_normalized]
        except Exception as e:
            logger.error(f"Error cleaning up extensions for loader '{name}': {e}")

        del self._loaders[name]
        logger.info(f"Unregistered loader: {name}")
        return True

    def get_loader_for_file(self, file_path: Path) -> MemoryLoader | None:
        """
        Get the appropriate loader for a given file path.

        Performs file type detection using extension matching and source validation.

        Args:
            file_path: Path to the file needing a loader

        Returns:
            MemoryLoader instance if found, None if no suitable loader exists
        """
        if not file_path.exists():
            logger.debug(f"File does not exist: {file_path}")
            return None

        file_extension = file_path.suffix.lower().lstrip(".")

        # Find potential loaders by extension
        candidate_loader_names = self._extension_map.get(file_extension, [])

        if not candidate_loader_names:
            logger.debug(f"No loaders registered for extension: .{file_extension}")
            return None

        # Try each candidate loader with validation
        for loader_name in candidate_loader_names:
            loader = self._loaders.get(loader_name)
            if not loader:
                logger.warning(f"Loader '{loader_name}' not found in registry")
                continue

            try:
                if loader.validate_source(str(file_path)):
                    logger.debug(
                        f"Selected loader '{loader_name}' for file: {file_path}"
                    )
                    return loader
            except Exception as e:
                logger.error(
                    f"Error validating source with loader '{loader_name}': {e}"
                )
                continue

        logger.debug(f"No valid loader found for file: {file_path}")
        return None

    def get_loader_by_name(self, name: str) -> MemoryLoader | None:
        """
        Get a registered loader by name.

        Args:
            name: Name of the loader to retrieve

        Returns:
            MemoryLoader instance if found, None otherwise
        """
        return self._loaders.get(name)

    def list_registered_loaders(self) -> list[str]:
        """
        Get list of all registered loader names.

        Returns:
            List of registered loader names
        """
        return list(self._loaders.keys())

    def get_supported_extensions(self) -> set[str]:
        """
        Get all file extensions supported by registered loaders.

        Returns:
            Set of supported file extensions (with leading dots)
        """
        extensions = set()
        for loader in self._loaders.values():
            try:
                loader_extensions = loader.get_supported_extensions()
                extensions.update(loader_extensions)
            except Exception as e:
                logger.error(f"Error getting extensions from loader {loader}: {e}")
        return extensions

    def clear_registry(self) -> None:
        """Clear all registered loaders from the registry."""
        loader_names = list(self._loaders.keys())
        for name in loader_names:
            self.unregister_loader(name)
        logger.info("Cleared all loaders from registry")

    def get_registry_stats(self) -> dict[str, Any]:
        """
        Get statistics about the current registry state.

        Returns:
            Dictionary containing registry statistics
        """
        return {
            "total_loaders": len(self._loaders),
            "loader_names": list(self._loaders.keys()),
            "supported_extensions": list(self.get_supported_extensions()),
            "extension_mapping": dict(self._extension_map),
        }


def create_default_registry() -> LoaderRegistry:
    """
    Create a LoaderRegistry with default loaders registered.

    Returns:
        LoaderRegistry instance with standard loaders registered
    """
    registry = LoaderRegistry()

    # Import and register standard loaders
    try:
        from ..core.config import CognitiveConfig
        from ..loaders.markdown_loader import MarkdownMemoryLoader

        # Create default config for loaders
        config = CognitiveConfig()

        # Register markdown loader
        markdown_loader = MarkdownMemoryLoader(config)
        registry.register_loader("markdown", markdown_loader)

    except ImportError as e:
        logger.error(f"Failed to import standard loaders: {e}")
    except Exception as e:
        logger.error(f"Failed to register standard loaders: {e}")

    return registry
