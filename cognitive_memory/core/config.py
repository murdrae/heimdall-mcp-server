"""
Configuration management for the cognitive memory system.

This module provides centralized configuration management using environment
variables and .env files as specified in the technical architecture.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger


@dataclass
class QdrantConfig:
    """Configuration for Qdrant vector database."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    timeout: int = 30
    prefer_grpc: bool = False

    def get_port(self) -> int:
        """Extract port number from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.port or 6333

    def get_host(self) -> str:
        """Extract host from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.hostname or "localhost"

    @classmethod
    def from_env(cls) -> "QdrantConfig":
        """Create configuration from environment variables."""
        return cls(
            url=os.getenv("QDRANT_URL", cls.url),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=int(os.getenv("QDRANT_TIMEOUT", str(cls.timeout))),
            prefer_grpc=os.getenv("QDRANT_PREFER_GRPC", "false").lower() == "true",
        )


@dataclass
class DatabaseConfig:
    """Configuration for SQLite database."""

    path: str = "./data/cognitive_memory.db"
    backup_interval_hours: int = 24
    enable_wal_mode: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            path=os.getenv("SQLITE_PATH", cls.path),
            backup_interval_hours=int(
                os.getenv("DB_BACKUP_INTERVAL", str(cls.backup_interval_hours))
            ),
            enable_wal_mode=os.getenv("DB_ENABLE_WAL", "true").lower() == "true",
        )


@dataclass
class EmbeddingConfig:
    """Configuration for embedding models."""

    model_name: str = "all-MiniLM-L6-v2"
    model_cache_dir: str = "./data/models"
    embedding_dimension: int = 384  # Sentence-BERT semantic embedding dimension
    batch_size: int = 32
    device: str = "auto"  # auto, cpu, cuda

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Create configuration from environment variables."""
        return cls(
            model_name=os.getenv("SENTENCE_BERT_MODEL", cls.model_name),
            model_cache_dir=os.getenv("MODEL_CACHE_DIR", cls.model_cache_dir),
            embedding_dimension=int(
                os.getenv("EMBEDDING_DIMENSION", str(cls.embedding_dimension))
            ),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", str(cls.batch_size))),
            device=os.getenv("EMBEDDING_DEVICE", cls.device),
        )


@dataclass
class CognitiveConfig:
    """Configuration for cognitive processing parameters."""

    # Activation and retrieval parameters
    activation_threshold: float = 0.7
    bridge_discovery_k: int = 5
    max_activations: int = 50
    consolidation_threshold: int = 100

    # Dimension weights for fusion
    emotional_weight: float = 0.2
    temporal_weight: float = 0.15
    contextual_weight: float = 0.25
    social_weight: float = 0.1

    # Cognitive dimension sizes - ONLY place magic numbers should be defined
    emotional_dimensions: int = 4
    temporal_dimensions: int = 3
    contextual_dimensions: int = 6
    social_dimensions: int = 3

    @classmethod
    def from_env(cls) -> "CognitiveConfig":
        """Create configuration from environment variables."""
        return cls(
            activation_threshold=float(
                os.getenv("ACTIVATION_THRESHOLD", str(cls.activation_threshold))
            ),
            bridge_discovery_k=int(
                os.getenv("BRIDGE_DISCOVERY_K", str(cls.bridge_discovery_k))
            ),
            max_activations=int(os.getenv("MAX_ACTIVATIONS", str(cls.max_activations))),
            consolidation_threshold=int(
                os.getenv("CONSOLIDATION_THRESHOLD", str(cls.consolidation_threshold))
            ),
            emotional_weight=float(
                os.getenv("EMOTIONAL_WEIGHT", str(cls.emotional_weight))
            ),
            temporal_weight=float(
                os.getenv("TEMPORAL_WEIGHT", str(cls.temporal_weight))
            ),
            contextual_weight=float(
                os.getenv("CONTEXTUAL_WEIGHT", str(cls.contextual_weight))
            ),
            social_weight=float(os.getenv("SOCIAL_WEIGHT", str(cls.social_weight))),
            emotional_dimensions=int(
                os.getenv("EMOTIONAL_DIMENSIONS", str(cls.emotional_dimensions))
            ),
            temporal_dimensions=int(
                os.getenv("TEMPORAL_DIMENSIONS", str(cls.temporal_dimensions))
            ),
            contextual_dimensions=int(
                os.getenv("CONTEXTUAL_DIMENSIONS", str(cls.contextual_dimensions))
            ),
            social_dimensions=int(
                os.getenv("SOCIAL_DIMENSIONS", str(cls.social_dimensions))
            ),
        )

    def get_total_cognitive_dimensions(self) -> int:
        """Get total number of cognitive dimensions."""
        return (
            self.emotional_dimensions
            + self.temporal_dimensions
            + self.contextual_dimensions
            + self.social_dimensions
        )


@dataclass
class LoggingConfig:
    """Configuration for logging system."""

    level: str = "INFO"
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    log_file: str | None = None
    rotate_size: str = "10 MB"
    retention: str = "7 days"

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Create configuration from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", cls.level),
            format=os.getenv("LOG_FORMAT", cls.format),
            log_file=os.getenv("LOG_FILE"),
            rotate_size=os.getenv("LOG_ROTATE_SIZE", cls.rotate_size),
            retention=os.getenv("LOG_RETENTION", cls.retention),
        )


@dataclass
class SystemConfig:
    """Master configuration for the cognitive memory system."""

    qdrant: QdrantConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    cognitive: CognitiveConfig
    logging: LoggingConfig

    # System-wide settings
    debug: bool = False
    max_memory_usage_mb: int = 1024
    cleanup_interval_hours: int = 24

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "SystemConfig":
        """Create complete system configuration from environment."""
        # Load .env file if specified or if default exists
        if env_file:
            load_dotenv(env_file)
        else:
            default_env = Path(".env")
            if default_env.exists():
                load_dotenv(default_env)

        return cls(
            qdrant=QdrantConfig.from_env(),
            database=DatabaseConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            cognitive=CognitiveConfig.from_env(),
            logging=LoggingConfig.from_env(),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            max_memory_usage_mb=int(os.getenv("MAX_MEMORY_USAGE_MB", "1024")),
            cleanup_interval_hours=int(os.getenv("CLEANUP_INTERVAL_HOURS", "24")),
        )

    def validate(self) -> bool:
        """Validate configuration and check for required resources."""
        errors = []

        # Check database directory
        db_dir = Path(self.database.path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except Exception as e:
                errors.append(f"Cannot create database directory {db_dir}: {e}")

        # Check model cache directory
        model_dir = Path(self.embedding.model_cache_dir)
        if not model_dir.exists():
            try:
                model_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created model cache directory: {model_dir}")
            except Exception as e:
                errors.append(f"Cannot create model cache directory {model_dir}: {e}")

        # Validate cognitive parameters
        if not 0.0 <= self.cognitive.activation_threshold <= 1.0:
            errors.append("Activation threshold must be between 0.0 and 1.0")

        if self.cognitive.bridge_discovery_k <= 0:
            errors.append("Bridge discovery K must be positive")

        if self.cognitive.max_activations <= 0:
            errors.append("Max activations must be positive")

        # Check dimension weights sum to reasonable range
        total_weight = (
            self.cognitive.emotional_weight
            + self.cognitive.temporal_weight
            + self.cognitive.contextual_weight
            + self.cognitive.social_weight
        )
        if total_weight > 1.0:
            logger.warning(
                f"Dimension weights sum to {total_weight:.2f}, consider normalizing"
            )

        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False

        logger.info("Configuration validation passed")
        return True

    def get_final_embedding_dimension(self) -> int:
        """Get final embedding dimension (semantic + cognitive)."""
        return (
            self.embedding.embedding_dimension
            + self.cognitive.get_total_cognitive_dimensions()
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "qdrant": {
                "url": self.qdrant.url,
                "timeout": self.qdrant.timeout,
                "prefer_grpc": self.qdrant.prefer_grpc,
                "api_key_set": self.qdrant.api_key is not None,
            },
            "database": {
                "path": self.database.path,
                "backup_interval_hours": self.database.backup_interval_hours,
                "enable_wal_mode": self.database.enable_wal_mode,
            },
            "embedding": {
                "model_name": self.embedding.model_name,
                "model_cache_dir": self.embedding.model_cache_dir,
                "embedding_dimension": self.embedding.embedding_dimension,
                "batch_size": self.embedding.batch_size,
                "device": self.embedding.device,
            },
            "cognitive": {
                "activation_threshold": self.cognitive.activation_threshold,
                "bridge_discovery_k": self.cognitive.bridge_discovery_k,
                "max_activations": self.cognitive.max_activations,
                "consolidation_threshold": self.cognitive.consolidation_threshold,
                "dimension_weights": {
                    "emotional": self.cognitive.emotional_weight,
                    "temporal": self.cognitive.temporal_weight,
                    "contextual": self.cognitive.contextual_weight,
                    "social": self.cognitive.social_weight,
                },
            },
            "logging": {
                "level": self.logging.level,
                "log_file": self.logging.log_file,
                "rotate_size": self.logging.rotate_size,
                "retention": self.logging.retention,
            },
            "system": {
                "debug": self.debug,
                "max_memory_usage_mb": self.max_memory_usage_mb,
                "cleanup_interval_hours": self.cleanup_interval_hours,
            },
        }


def get_config(env_file: str | None = None) -> SystemConfig:
    """
    Get system configuration, loading from environment variables and .env file.

    Args:
        env_file: Optional path to .env file. If None, looks for .env in current directory.

    Returns:
        SystemConfig: Complete system configuration

    Raises:
        ValueError: If configuration validation fails
    """
    config = SystemConfig.from_env(env_file)

    if not config.validate():
        raise ValueError("Configuration validation failed. Check logs for details.")

    return config
