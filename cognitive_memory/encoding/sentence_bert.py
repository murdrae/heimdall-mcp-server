"""
Sentence-BERT wrapper for semantic embedding generation.

This module provides a clean interface to Sentence-BERT models for
generating high-quality semantic embeddings that serve as the foundation
for cognitive memory encoding.

Now implemented using ONNX Runtime for reduced dependencies and memory usage.
"""

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from ..core.config import EmbeddingConfig
from ..core.interfaces import EmbeddingProvider
from .onnx_provider import ONNXEmbeddingProvider


class SentenceBERTProvider(EmbeddingProvider):
    """
    Sentence-BERT embedding provider implementing the EmbeddingProvider interface.

    Now uses ONNX Runtime instead of PyTorch for significantly reduced memory usage
    and faster inference while maintaining identical embedding quality.
    """

    def __init__(
        self,
        model_name: str | None = None,
        model_path: str | Path | None = None,
        tokenizer_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """
        Initialize the Sentence-BERT provider using ONNX Runtime.

        Args:
            model_name: Name of the model (for compatibility, not used in ONNX version)
            model_path: Path to the ONNX model file. Defaults to data/models/all-MiniLM-L6-v2.onnx
            tokenizer_path: Path to the tokenizer directory. Defaults to data/models/tokenizer
            config_path: Path to the model config JSON. Defaults to data/models/model_config.json
        """
        self.config = EmbeddingConfig.from_env()
        self.model_name = model_name or self.config.model_name

        logger.info(
            "Initializing Sentence-BERT provider with ONNX Runtime",
            model=self.model_name,
            model_path=model_path,
        )

        try:
            # Initialize the ONNX provider
            self.onnx_provider = ONNXEmbeddingProvider(
                model_path=model_path,
                tokenizer_path=tokenizer_path,
                config_path=config_path,
            )

            self.embedding_dimension = self.onnx_provider.get_embedding_dimension()

            logger.info(
                "Sentence-BERT model loaded successfully with ONNX Runtime",
                embedding_dim=self.embedding_dimension,
                model_name=self.model_name,
            )

        except Exception as e:
            logger.error(
                "Failed to load Sentence-BERT model with ONNX",
                model=self.model_name,
                error=str(e),
            )
            raise RuntimeError(f"Failed to initialize Sentence-BERT model: {e}") from e

    def encode(self, text: str) -> np.ndarray:
        """
        Encode a single text into a semantic embedding vector.

        Args:
            text: Input text to encode

        Returns:
            np.ndarray: Semantic embedding vector
        """
        return self.onnx_provider.encode(text)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """
        Encode multiple texts into semantic embedding vectors.

        Args:
            texts: List of input texts to encode

        Returns:
            np.ndarray: Batch of semantic embedding vectors
        """
        return self.onnx_provider.encode_batch(texts)

    def get_embedding_dimension(self) -> int:
        """Get the dimensionality of the embeddings."""
        return self.embedding_dimension

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        info = self.onnx_provider.get_model_info()
        info["provider_type"] = "ONNX Runtime"
        return info

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding array
            embedding2: Second embedding array

        Returns:
            float: Cosine similarity score between -1 and 1
        """
        return self.onnx_provider.compute_similarity(embedding1, embedding2)

    def compute_batch_similarity(
        self, query_embedding: np.ndarray, candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute similarity between a query embedding and multiple candidates.

        Args:
            query_embedding: Single query embedding array
            candidate_embeddings: Batch of candidate embedding arrays

        Returns:
            np.ndarray: Similarity scores for each candidate
        """
        return self.onnx_provider.compute_batch_similarity(
            query_embedding, candidate_embeddings
        )


def create_sentence_bert_provider(
    model_name: str | None = None,
    model_path: str | Path | None = None,
    tokenizer_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> SentenceBERTProvider:
    """
    Factory function to create a Sentence-BERT provider using ONNX Runtime.

    Args:
        model_name: Name of the Sentence-BERT model to use (for compatibility)
        model_path: Path to the ONNX model file
        tokenizer_path: Path to the tokenizer directory
        config_path: Path to the model configuration JSON

    Returns:
        SentenceBERTProvider: Configured provider instance
    """
    return SentenceBERTProvider(
        model_name=model_name,
        model_path=model_path,
        tokenizer_path=tokenizer_path,
        config_path=config_path,
    )
