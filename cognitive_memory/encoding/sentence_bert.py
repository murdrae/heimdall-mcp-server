"""
Sentence-BERT wrapper for semantic embedding generation.

This module provides a clean interface to Sentence-BERT models for
generating high-quality semantic embeddings that serve as the foundation
for cognitive memory encoding.
"""

from typing import Any

import torch
from loguru import logger
from sentence_transformers import SentenceTransformer

from ..core.config import EmbeddingConfig
from ..core.interfaces import EmbeddingProvider


class SentenceBERTProvider(EmbeddingProvider):
    """
    Sentence-BERT embedding provider implementing the EmbeddingProvider interface.

    Provides semantic embeddings using pre-trained Sentence-BERT models
    with support for batch processing and configurable model selection.
    """

    def __init__(
        self, model_name: str | None = None, device: str | None = None
    ) -> None:
        """
        Initialize the Sentence-BERT provider.

        Args:
            model_name: Name of the Sentence-BERT model to use.
                       Defaults to configuration or 'all-MiniLM-L6-v2'.
            device: Device to run the model on ('cpu', 'cuda', 'mps').
                   Auto-detects if not specified.
        """
        self.config = EmbeddingConfig.from_env()
        self.model_name = model_name or self.config.model_name

        # Auto-detect device if not specified
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(
            "Initializing Sentence-BERT provider",
            model=self.model_name,
            device=self.device,
        )

        try:
            # Initialize the sentence transformer model
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.embedding_dimension: int = (
                self.model.get_sentence_embedding_dimension()
            )

            logger.info(
                "Sentence-BERT model loaded successfully",
                embedding_dim=self.embedding_dimension,
                model_name=self.model_name,
            )

        except Exception as e:
            logger.error(
                "Failed to load Sentence-BERT model",
                model=self.model_name,
                error=str(e),
            )
            raise RuntimeError(f"Failed to initialize Sentence-BERT model: {e}") from e

    def encode(self, text: str) -> torch.Tensor:
        """
        Encode a single text into a semantic embedding vector.

        Args:
            text: Input text to encode

        Returns:
            torch.Tensor: Semantic embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for encoding")
            return torch.zeros(self.embedding_dimension, dtype=torch.float32)

        try:
            # Encode single text
            embedding = self.model.encode(
                text.strip(),
                convert_to_tensor=True,
                show_progress_bar=False,
                normalize_embeddings=True,  # L2 normalize for better similarity computation
            )

            # Ensure tensor is on CPU and float32 for consistency
            if isinstance(embedding, torch.Tensor):
                embedding = embedding.cpu().float()
            else:
                embedding = torch.tensor(embedding, dtype=torch.float32)

            logger.debug(
                "Text encoded successfully",
                text_length=len(text),
                embedding_shape=embedding.shape,
            )

            return embedding

        except Exception as e:
            logger.error(
                "Failed to encode text",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            # Return zero vector as fallback
            return torch.zeros(self.embedding_dimension, dtype=torch.float32)

    def encode_batch(self, texts: list[str]) -> torch.Tensor:
        """
        Encode multiple texts into semantic embedding vectors.

        Args:
            texts: List of input texts to encode

        Returns:
            torch.Tensor: Batch of semantic embedding vectors
        """
        if not texts:
            logger.warning("Empty text list provided for batch encoding")
            return torch.zeros((0, self.embedding_dimension), dtype=torch.float32)

        # Filter out empty texts and track indices
        filtered_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            if text and text.strip():
                filtered_texts.append(text.strip())
                valid_indices.append(i)
            else:
                logger.warning(f"Empty text at index {i} in batch")

        if not filtered_texts:
            logger.warning("No valid texts in batch after filtering")
            return torch.zeros(
                (len(texts), self.embedding_dimension), dtype=torch.float32
            )

        try:
            # Encode batch of texts
            embeddings = self.model.encode(
                filtered_texts,
                convert_to_tensor=True,
                show_progress_bar=False,
                normalize_embeddings=True,
                batch_size=32,  # Process in reasonable batches
            )

            # Ensure tensor is on CPU and float32
            if isinstance(embeddings, torch.Tensor):
                embeddings = embeddings.cpu().float()
            else:
                embeddings = torch.tensor(embeddings, dtype=torch.float32)

            # If we had empty texts, we need to reconstruct the full batch
            if len(valid_indices) != len(texts):
                full_embeddings = torch.zeros(
                    (len(texts), self.embedding_dimension), dtype=torch.float32
                )
                for i, valid_idx in enumerate(valid_indices):
                    full_embeddings[valid_idx] = embeddings[i]
                embeddings = full_embeddings

            logger.debug(
                "Batch encoded successfully",
                batch_size=len(texts),
                valid_texts=len(filtered_texts),
                embedding_shape=embeddings.shape,
            )

            return embeddings

        except Exception as e:
            logger.error(
                "Failed to encode text batch",
                batch_size=len(texts),
                valid_texts=len(filtered_texts),
                error=str(e),
            )
            # Return zero vectors as fallback
            return torch.zeros(
                (len(texts), self.embedding_dimension), dtype=torch.float32
            )

    def get_embedding_dimension(self) -> int:
        """Get the dimensionality of the embeddings."""
        return self.embedding_dimension

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "device": self.device,
            "max_sequence_length": getattr(self.model, "max_seq_length", "unknown"),
        }

    def compute_similarity(
        self, embedding1: torch.Tensor, embedding2: torch.Tensor
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding tensor
            embedding2: Second embedding tensor

        Returns:
            float: Cosine similarity score between -1 and 1
        """
        try:
            # Ensure embeddings are normalized
            norm1 = torch.nn.functional.normalize(embedding1, p=2, dim=-1)
            norm2 = torch.nn.functional.normalize(embedding2, p=2, dim=-1)

            # Compute cosine similarity
            similarity = torch.dot(norm1, norm2).item()

            return float(similarity)

        except Exception as e:
            logger.error(
                "Failed to compute similarity",
                embedding1_shape=embedding1.shape,
                embedding2_shape=embedding2.shape,
                error=str(e),
            )
            return 0.0

    def compute_batch_similarity(
        self, query_embedding: torch.Tensor, candidate_embeddings: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute similarity between a query embedding and multiple candidates.

        Args:
            query_embedding: Single query embedding tensor
            candidate_embeddings: Batch of candidate embedding tensors

        Returns:
            torch.Tensor: Similarity scores for each candidate
        """
        try:
            # Ensure all embeddings are normalized
            query_norm = torch.nn.functional.normalize(query_embedding, p=2, dim=-1)
            candidates_norm = torch.nn.functional.normalize(
                candidate_embeddings, p=2, dim=-1
            )

            # Compute batch cosine similarity
            similarities = torch.mm(candidates_norm, query_norm.unsqueeze(-1)).squeeze(
                -1
            )

            return similarities

        except Exception as e:
            logger.error(
                "Failed to compute batch similarity",
                query_shape=query_embedding.shape,
                candidates_shape=candidate_embeddings.shape,
                error=str(e),
            )
            return torch.zeros(candidate_embeddings.size(0), dtype=torch.float32)


def create_sentence_bert_provider(
    model_name: str | None = None, device: str | None = None
) -> SentenceBERTProvider:
    """
    Factory function to create a Sentence-BERT provider.

    Args:
        model_name: Name of the Sentence-BERT model to use
        device: Device to run the model on

    Returns:
        SentenceBERTProvider: Configured provider instance
    """
    return SentenceBERTProvider(model_name=model_name, device=device)
