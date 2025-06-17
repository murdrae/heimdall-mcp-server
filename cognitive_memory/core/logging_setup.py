"""
Logging configuration for the cognitive memory system.

This module sets up structured logging with Loguru as specified in the
technical architecture, providing cognitive event logging and debugging.
"""

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from .config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    Configure logging system with Loguru.

    Args:
        config: Logging configuration
    """
    # Remove default handler
    logger.remove()

    # Add console handler with formatting
    logger.add(
        sys.stderr,
        format=config.format,
        level=config.level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Add file handler if specified
    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path,
            format=config.format,
            level=config.level,
            rotation=config.rotate_size,
            retention=config.retention,
            compression="gz",
            backtrace=True,
            diagnose=True,
        )

    logger.info("Logging system initialized")


def log_cognitive_event(event_type: str, **kwargs: Any) -> None:
    """
    Log a cognitive event with structured data.

    Args:
        event_type: Type of cognitive event
        **kwargs: Additional event data
    """
    logger.info(f"Cognitive event: {event_type}", **kwargs)


def log_memory_formation(
    memory_id: str, content_length: int, level: int, dimensions: dict
) -> None:
    """Log memory formation event."""
    log_cognitive_event(
        "memory_formation",
        memory_id=memory_id,
        content_length=content_length,
        level=level,
        dimensions=list(dimensions.keys()),
    )


def log_activation_spreading(
    activated_count: int, threshold: float, activation_time_ms: float
) -> None:
    """Log activation spreading event."""
    log_cognitive_event(
        "activation_spreading",
        activated_count=activated_count,
        threshold=threshold,
        activation_time_ms=activation_time_ms,
    )


def log_bridge_discovery(
    bridges_found: int, query_context: str, discovery_time_ms: float
) -> None:
    """Log bridge discovery event."""
    log_cognitive_event(
        "bridge_discovery",
        bridges_found=bridges_found,
        query_context=query_context[:100],  # Truncate for logging
        discovery_time_ms=discovery_time_ms,
    )


def log_memory_consolidation(
    episodic_compressed: int, semantic_created: int, consolidation_time_ms: float
) -> None:
    """Log memory consolidation event."""
    log_cognitive_event(
        "memory_consolidation",
        episodic_compressed=episodic_compressed,
        semantic_created=semantic_created,
        consolidation_time_ms=consolidation_time_ms,
    )


def log_performance_metric(
    metric_name: str, value: float, unit: str = "", context: dict | None = None
) -> None:
    """Log performance metrics."""
    logger.info(
        f"Performance metric: {metric_name}",
        metric=metric_name,
        value=value,
        unit=unit,
        context=context or {},
    )


def log_error_with_context(error: Exception, context: str, **kwargs: Any) -> None:
    """Log error with additional context."""
    logger.error(
        f"Error in {context}: {error}",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context,
        **kwargs,
    )
