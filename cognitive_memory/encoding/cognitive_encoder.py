"""
Cognitive encoder with multi-dimensional fusion layer.

This module implements the core cognitive encoding system that combines
Sentence-BERT semantic embeddings with rule-based cognitive dimensions
through a learned linear fusion layer to produce rich 512-dimensional
cognitive memory representations.
"""

from typing import Any

import torch
import torch.nn as nn
from loguru import logger

from ..core.config import CognitiveConfig
from .dimensions import CognitiveDimensionExtractor
from .sentence_bert import SentenceBERTProvider


class CognitiveFusionLayer(nn.Module):
    """
    Neural fusion layer that combines semantic and dimensional features.

    Takes concatenated Sentence-BERT embeddings (384D) and cognitive dimensions (16D)
    and transforms them into a unified 512-dimensional cognitive representation
    through a learned linear transformation.
    """

    def __init__(
        self, semantic_dim: int = 384, cognitive_dim: int = 16, output_dim: int = 512
    ) -> None:
        """
        Initialize the fusion layer.

        Args:
            semantic_dim: Dimensionality of semantic embeddings (Sentence-BERT)
            cognitive_dim: Dimensionality of cognitive dimensions
            output_dim: Dimensionality of final cognitive embeddings
        """
        super().__init__()

        self.semantic_dim = semantic_dim
        self.cognitive_dim = cognitive_dim
        self.output_dim = output_dim
        self.input_dim = semantic_dim + cognitive_dim

        # Linear transformation layer
        self.fusion_layer = nn.Linear(self.input_dim, output_dim, bias=True)

        # Layer normalization for stable training
        self.layer_norm = nn.LayerNorm(output_dim)

        # Initialize weights using Xavier uniform initialization
        self._initialize_weights()

        logger.debug(
            "Cognitive fusion layer initialized",
            semantic_dim=semantic_dim,
            cognitive_dim=cognitive_dim,
            output_dim=output_dim,
            total_params=sum(p.numel() for p in self.parameters()),
        )

    def _initialize_weights(self) -> None:
        """Initialize layer weights using Xavier uniform initialization."""
        nn.init.xavier_uniform_(self.fusion_layer.weight)
        nn.init.zeros_(self.fusion_layer.bias)

    def forward(
        self, semantic_embedding: torch.Tensor, cognitive_dimensions: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass through the fusion layer.

        Args:
            semantic_embedding: Sentence-BERT embedding tensor [batch_size, semantic_dim] or [semantic_dim]
            cognitive_dimensions: Cognitive dimensions tensor [batch_size, cognitive_dim] or [cognitive_dim]

        Returns:
            torch.Tensor: Fused cognitive embedding [batch_size, output_dim] or [output_dim]
        """
        # Handle both single and batch inputs
        if semantic_embedding.dim() == 1:
            semantic_embedding = semantic_embedding.unsqueeze(0)
            single_input = True
        else:
            single_input = False

        if cognitive_dimensions.dim() == 1:
            cognitive_dimensions = cognitive_dimensions.unsqueeze(0)

        # Ensure batch dimensions match
        batch_size = semantic_embedding.size(0)
        if cognitive_dimensions.size(0) != batch_size:
            cognitive_dimensions = cognitive_dimensions.expand(batch_size, -1)

        # Concatenate semantic and cognitive features
        combined_features = torch.cat([semantic_embedding, cognitive_dimensions], dim=1)

        # Apply linear fusion
        fused_embedding = self.fusion_layer(combined_features)

        # Apply layer normalization
        fused_embedding = self.layer_norm(fused_embedding)

        # Return single tensor if single input was provided
        if single_input:
            fused_embedding = fused_embedding.squeeze(0)

        return fused_embedding


class CognitiveEncoder:
    """
    Complete cognitive encoding system combining semantic and dimensional analysis.

    This encoder integrates Sentence-BERT semantic embeddings with rule-based
    cognitive dimensions through a learned fusion layer to create rich
    cognitive memory representations suitable for the multi-layered memory system.
    """

    def __init__(
        self,
        sentence_bert_model: str | None = None,
        device: str | None = None,
        fusion_weights_path: str | None = None,
    ) -> None:
        """
        Initialize the cognitive encoder.

        Args:
            sentence_bert_model: Name of Sentence-BERT model to use
            device: Device for computation ('cpu', 'cuda', 'mps')
            fusion_weights_path: Path to pre-trained fusion layer weights
        """
        self.config = CognitiveConfig()

        # Initialize components
        logger.info("Initializing cognitive encoder components")

        # Initialize Sentence-BERT provider
        self.semantic_provider = SentenceBERTProvider(
            model_name=sentence_bert_model, device=device
        )

        # Initialize cognitive dimension extractor
        self.dimension_extractor = CognitiveDimensionExtractor()

        # Get dimensions for fusion layer
        self.semantic_dim = self.semantic_provider.get_embedding_dimension()
        self.cognitive_dim = self.dimension_extractor.get_total_dimensions()
        self.output_dim = 512  # Target cognitive embedding dimension

        # Initialize fusion layer
        self.fusion_layer = CognitiveFusionLayer(
            semantic_dim=self.semantic_dim,
            cognitive_dim=self.cognitive_dim,
            output_dim=self.output_dim,
        )

        # Load pre-trained weights if provided
        if fusion_weights_path:
            self._load_fusion_weights(fusion_weights_path)

        # Set to evaluation mode (no training by default)
        self.fusion_layer.eval()

        logger.info(
            "Cognitive encoder initialized successfully",
            semantic_dim=self.semantic_dim,
            cognitive_dim=self.cognitive_dim,
            output_dim=self.output_dim,
            device=self.semantic_provider.device,
        )

    def encode(self, text: str, context: dict[str, Any] | None = None) -> torch.Tensor:
        """
        Encode text into a cognitive memory representation.

        Args:
            text: Input text to encode
            context: Optional context information (currently unused)

        Returns:
            torch.Tensor: 512-dimensional cognitive embedding
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for cognitive encoding")
            return torch.zeros(self.output_dim, dtype=torch.float32)

        try:
            # Extract semantic embedding
            semantic_embedding = self.semantic_provider.encode(text)

            # Extract cognitive dimensions
            dimension_dict = self.dimension_extractor.extract_dimensions(text)

            # Concatenate all cognitive dimensions
            cognitive_dims = torch.cat(
                [
                    dimension_dict["emotional"],
                    dimension_dict["temporal"],
                    dimension_dict["contextual"],
                    dimension_dict["social"],
                ],
                dim=0,
            )

            # Fuse through neural layer
            with torch.no_grad():  # No gradients needed for inference
                cognitive_embedding = self.fusion_layer(
                    semantic_embedding, cognitive_dims
                )

            logger.debug(
                "Text encoded into cognitive representation",
                text_length=len(text),
                semantic_shape=semantic_embedding.shape,
                cognitive_dims_shape=cognitive_dims.shape,
                output_shape=cognitive_embedding.shape,
            )

            return cognitive_embedding

        except Exception as e:
            logger.error(
                "Failed to encode text cognitively",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            return torch.zeros(self.output_dim, dtype=torch.float32)

    def encode_batch(
        self, texts: list[str], contexts: list[dict[str, Any]] | None = None
    ) -> torch.Tensor:
        """
        Encode multiple texts into cognitive memory representations.

        Args:
            texts: List of input texts to encode
            contexts: Optional list of context information (currently unused)

        Returns:
            torch.Tensor: Batch of 512-dimensional cognitive embeddings
        """
        if not texts:
            logger.warning("Empty text list provided for batch encoding")
            return torch.zeros((0, self.output_dim), dtype=torch.float32)

        try:
            # Extract semantic embeddings for all texts
            semantic_embeddings = self.semantic_provider.encode_batch(texts)

            # Extract cognitive dimensions for all texts
            batch_cognitive_dims = []
            for text in texts:
                dimension_dict = self.dimension_extractor.extract_dimensions(text)
                cognitive_dims = torch.cat(
                    [
                        dimension_dict["emotional"],
                        dimension_dict["temporal"],
                        dimension_dict["contextual"],
                        dimension_dict["social"],
                    ],
                    dim=0,
                )
                batch_cognitive_dims.append(cognitive_dims)

            # Stack cognitive dimensions into batch tensor
            cognitive_dims_batch = torch.stack(batch_cognitive_dims, dim=0)

            # Fuse through neural layer
            with torch.no_grad():
                cognitive_embeddings = self.fusion_layer(
                    semantic_embeddings, cognitive_dims_batch
                )

            logger.debug(
                "Batch encoded into cognitive representations",
                batch_size=len(texts),
                semantic_shape=semantic_embeddings.shape,
                cognitive_dims_shape=cognitive_dims_batch.shape,
                output_shape=cognitive_embeddings.shape,
            )

            return cognitive_embeddings

        except Exception as e:
            logger.error(
                "Failed to encode text batch cognitively",
                batch_size=len(texts),
                error=str(e),
            )
            return torch.zeros((len(texts), self.output_dim), dtype=torch.float32)

    def get_dimension_breakdown(self, text: str) -> dict[str, Any]:
        """
        Get detailed breakdown of dimensions extracted from text.

        Args:
            text: Input text to analyze

        Returns:
            dict: Detailed dimension analysis including scores and explanations
        """
        try:
            # Get semantic embedding
            semantic_embedding = self.semantic_provider.encode(text)

            # Get cognitive dimensions
            dimension_dict = self.dimension_extractor.extract_dimensions(text)
            dimension_names = self.dimension_extractor.get_all_dimension_names()

            breakdown: dict[str, Any] = {
                "semantic_embedding_norm": float(torch.norm(semantic_embedding).item()),
                "dimensions": {},
            }

            # Add detailed dimension breakdowns
            for category, tensor in dimension_dict.items():
                names = dimension_names[category]
                values = tensor.tolist()

                breakdown["dimensions"][category] = {
                    "values": values,
                    "names": names,
                    "total_activation": float(sum(values)),
                    "max_dimension": names[values.index(max(values))]
                    if values
                    else None,
                    "max_value": float(max(values)) if values else 0.0,
                }

            return breakdown

        except Exception as e:
            logger.error(
                "Failed to generate dimension breakdown",
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                error=str(e),
            )
            return {"error": str(e)}

    def _load_fusion_weights(self, weights_path: str) -> None:
        """Load pre-trained fusion layer weights."""
        try:
            state_dict = torch.load(weights_path, map_location="cpu")
            self.fusion_layer.load_state_dict(state_dict)
            logger.info("Fusion layer weights loaded successfully", path=weights_path)
        except Exception as e:
            logger.warning(
                "Failed to load fusion weights, using random initialization",
                path=weights_path,
                error=str(e),
            )

    def save_fusion_weights(self, weights_path: str) -> bool:
        """Save current fusion layer weights."""
        try:
            torch.save(self.fusion_layer.state_dict(), weights_path)
            logger.info("Fusion layer weights saved successfully", path=weights_path)
            return True
        except Exception as e:
            logger.error(
                "Failed to save fusion weights", path=weights_path, error=str(e)
            )
            return False

    def get_encoder_info(self) -> dict[str, Any]:
        """Get information about the encoder configuration."""
        return {
            "semantic_provider": self.semantic_provider.get_model_info(),
            "dimension_extractor": {
                "total_dimensions": self.cognitive_dim,
                "dimension_breakdown": self.dimension_extractor.get_all_dimension_names(),
            },
            "fusion_layer": {
                "input_dim": self.semantic_dim + self.cognitive_dim,
                "output_dim": self.output_dim,
                "parameters": sum(p.numel() for p in self.fusion_layer.parameters()),
            },
        }


def create_cognitive_encoder(
    sentence_bert_model: str | None = None,
    device: str | None = None,
    fusion_weights_path: str | None = None,
) -> CognitiveEncoder:
    """
    Factory function to create a cognitive encoder.

    Args:
        sentence_bert_model: Name of Sentence-BERT model to use
        device: Device for computation
        fusion_weights_path: Path to pre-trained fusion weights

    Returns:
        CognitiveEncoder: Configured encoder instance
    """
    return CognitiveEncoder(
        sentence_bert_model=sentence_bert_model,
        device=device,
        fusion_weights_path=fusion_weights_path,
    )
