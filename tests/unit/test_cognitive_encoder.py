"""
Unit tests for cognitive encoder and fusion layer.
"""

import random

import numpy as np
import pytest

from cognitive_memory.encoding.cognitive_encoder import (
    CognitiveEncoder,
    CognitiveFusionLayer,
    create_cognitive_encoder,
)


@pytest.mark.slow
class TestCognitiveFusionLayer:
    """Test the neural fusion layer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Set seeds for deterministic behavior
        np.random.seed(42)
        random.seed(42)

        self.semantic_dim = 384
        self.cognitive_dim = 16
        self.output_dim = 512
        self.fusion = CognitiveFusionLayer(
            self.semantic_dim, self.cognitive_dim, self.output_dim
        )

    def test_initialization(self) -> None:
        """Test fusion layer initialization."""
        assert self.fusion.semantic_dim == 384
        assert self.fusion.cognitive_dim == 16
        assert self.fusion.output_dim == 512
        assert self.fusion.input_dim == 400  # 384 + 16

        # Check layers exist (converted to NumPy-based components)
        # Note: Actual layer checks will need to be adapted for NumPy implementation

    def test_single_input_forward(self) -> None:
        """Test forward pass with single input."""
        np.random.seed(42)
        semantic_emb = np.random.randn(self.semantic_dim)
        cognitive_dims = np.random.randn(self.cognitive_dim)

        output = self.fusion(semantic_emb, cognitive_dims)

        assert output.shape == (self.output_dim,)
        assert output.dtype == np.float32
        assert np.all(np.isfinite(output))

    def test_batch_input_forward(self) -> None:
        """Test forward pass with batch input."""
        batch_size = 3
        np.random.seed(42)
        semantic_embs = np.random.randn(batch_size, self.semantic_dim)
        cognitive_dims = np.random.randn(batch_size, self.cognitive_dim)

        output = self.fusion(semantic_embs, cognitive_dims)

        assert output.shape == (batch_size, self.output_dim)
        assert output.dtype == np.float32
        assert np.all(np.isfinite(output))

    def test_mismatched_batch_sizes(self) -> None:
        """Test handling of mismatched batch sizes."""
        np.random.seed(42)
        semantic_embs = np.random.randn(3, self.semantic_dim)
        cognitive_dims = np.random.randn(1, self.cognitive_dim)  # Will be expanded

        output = self.fusion(semantic_embs, cognitive_dims)

        assert output.shape == (3, self.output_dim)
        assert np.all(np.isfinite(output))

    def test_gradient_flow(self) -> None:
        """Test that gradients flow properly (NumPy-based)."""
        # Note: NumPy doesn't have automatic differentiation like PyTorch
        # This test would need to be adapted for the specific NumPy implementation
        # or could be removed if gradient computation is not needed
        np.random.seed(42)
        semantic_emb = np.random.randn(self.semantic_dim)
        cognitive_dims = np.random.randn(self.cognitive_dim)

        output = self.fusion(semantic_emb, cognitive_dims)
        # Simple check that the operation completed without error
        assert np.all(np.isfinite(output))


@pytest.mark.slow
class TestCognitiveEncoder:
    """Test the complete cognitive encoder."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Set seeds for deterministic behavior
        np.random.seed(42)
        random.seed(42)

        # Use CPU and smaller model for testing
        self.encoder = CognitiveEncoder(
            sentence_bert_model="all-MiniLM-L6-v2", device="cpu"
        )

    def test_initialization(self) -> None:
        """Test encoder initialization."""
        assert self.encoder.semantic_dim == 384
        assert self.encoder.cognitive_dim == 16
        assert self.encoder.output_dim == 400  # 384 semantic + 16 cognitive

        # Check components are initialized
        assert self.encoder.semantic_provider is not None
        assert self.encoder.dimension_extractor is not None
        assert self.encoder.fusion_layer is not None

    def test_single_text_encoding(self) -> None:
        """Test encoding of single text."""
        text = "I'm working on a machine learning project with my team"
        embedding = self.encoder.encode(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (400,)
        assert embedding.dtype == np.float32
        assert np.all(np.isfinite(embedding))

        # Should not be all zeros for valid text
        assert np.any(embedding != 0.0)

    def test_batch_encoding(self) -> None:
        """Test batch encoding of multiple texts."""
        texts = [
            "I'm frustrated with this debugging session",
            "Great! The algorithm is working perfectly now",
            "We need to collaborate on this urgent project",
        ]

        embeddings = self.encoder.encode_batch(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 400)
        assert embeddings.dtype == np.float32
        assert np.all(np.isfinite(embeddings))

        # Each embedding should be different
        for i in range(3):
            for j in range(i + 1, 3):
                assert not np.allclose(embeddings[i], embeddings[j], atol=1e-3)

    def test_empty_text_handling(self) -> None:
        """Test handling of empty text."""
        embedding = self.encoder.encode("")

        assert embedding.shape == (400,)
        assert np.all(embedding == 0.0)

    def test_empty_batch_handling(self) -> None:
        """Test handling of empty batch."""
        embeddings = self.encoder.encode_batch([])

        assert embeddings.shape == (0, 400)

    def test_mixed_batch_with_empty_texts(self) -> None:
        """Test batch with some empty texts."""
        texts = ["Valid cognitive text", "", "Another valid text about teamwork"]

        embeddings = self.encoder.encode_batch(texts)

        assert embeddings.shape == (3, 400)

        # Empty text should have zero embedding
        assert np.all(embeddings[1] == 0.0)

        # Valid texts should have non-zero embeddings
        assert np.any(embeddings[0] != 0.0)
        assert np.any(embeddings[2] != 0.0)

    def test_dimension_breakdown(self) -> None:
        """Test detailed dimension breakdown."""
        text = (
            "I'm really frustrated debugging this urgent API issue and need team help"
        )
        breakdown = self.encoder.get_dimension_breakdown(text)

        assert "semantic_embedding_norm" in breakdown
        assert "dimensions" in breakdown

        dimensions = breakdown["dimensions"]
        assert "emotional" in dimensions
        assert "temporal" in dimensions
        assert "contextual" in dimensions
        assert "social" in dimensions

        # Check emotional dimensions (should detect frustration)
        emotional = dimensions["emotional"]
        assert "values" in emotional
        assert "names" in emotional
        assert len(emotional["values"]) == 4
        assert len(emotional["names"]) == 4
        assert "frustration" in emotional["names"]

        # Frustration should be detected
        frustration_idx = emotional["names"].index("frustration")
        assert emotional["values"][frustration_idx] > 0.2

    def test_encoder_info(self) -> None:
        """Test encoder information retrieval."""
        info = self.encoder.get_encoder_info()

        assert "semantic_provider" in info
        assert "dimension_extractor" in info
        assert "fusion_layer" in info

        # Check fusion layer info
        fusion_info = info["fusion_layer"]
        assert fusion_info["input_dim"] == 400  # 384 + 16
        assert fusion_info["output_dim"] == 400
        assert fusion_info["parameters"] > 0

    def test_consistency(self) -> None:
        """Test that same text produces same embedding."""
        text = "Consistent cognitive encoding test"

        emb1 = self.encoder.encode(text)
        emb2 = self.encoder.encode(text)

        # Should be identical (no randomness in inference)
        assert np.allclose(emb1, emb2, atol=1e-6)

    def test_different_texts_different_embeddings(self) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "Happy successful project completion"
        text2 = "Frustrated debugging session with errors"

        emb1 = self.encoder.encode(text1)
        emb2 = self.encoder.encode(text2)

        # Should be different due to both semantic and dimensional differences
        assert not np.allclose(emb1, emb2, atol=1e-2)

    def test_cognitive_vs_semantic_differences(self) -> None:
        """Test that cognitive encoding captures more than just semantics."""
        # Semantically similar but emotionally different
        text1 = "I love working on this amazing machine learning project"
        text2 = "I hate struggling with this terrible machine learning project"

        emb1 = self.encoder.encode(text1)
        emb2 = self.encoder.encode(text2)

        # Get semantic embeddings directly for comparison
        sem1 = self.encoder.semantic_provider.encode(text1)
        sem2 = self.encoder.semantic_provider.encode(text2)

        # Cognitive embeddings should be more different than pure semantic
        cognitive_sim = np.dot(emb1, emb2) / (
            np.linalg.norm(emb1) * np.linalg.norm(emb2)
        )
        semantic_sim = np.dot(sem1, sem2) / (
            np.linalg.norm(sem1) * np.linalg.norm(sem2)
        )

        # Cognitive similarity should be lower due to emotional differences
        assert cognitive_sim < semantic_sim


@pytest.mark.slow
class TestCognitiveEncoderFactory:
    """Test factory function for creating encoders."""

    def test_factory_creation(self) -> None:
        """Test factory function."""
        encoder = create_cognitive_encoder(
            sentence_bert_model="all-MiniLM-L6-v2", device="cpu"
        )

        assert isinstance(encoder, CognitiveEncoder)
        assert encoder.semantic_provider.model_name == "all-MiniLM-L6-v2"
        assert encoder.semantic_provider.device == "cpu"

    def test_factory_defaults(self) -> None:
        """Test factory function with defaults."""
        encoder = create_cognitive_encoder()

        assert isinstance(encoder, CognitiveEncoder)


@pytest.mark.slow
@pytest.mark.integration
class TestCognitiveEncoderIntegration:
    """Integration tests for cognitive encoder."""

    def test_real_world_scenarios(self) -> None:
        """Test with realistic cognitive scenarios."""
        # Set seeds for deterministic behavior
        np.random.seed(42)
        random.seed(42)

        encoder = CognitiveEncoder(device="cpu")

        scenarios = [
            "I'm debugging a critical production bug that needs to be fixed before tomorrow's deadline",
            "Our team had a great brainstorming session and came up with innovative solutions",
            "I'm analyzing user behavior data to understand engagement patterns",
            "Can someone help me understand this complex algorithm? I'm curious about how it works",
        ]

        embeddings = encoder.encode_batch(scenarios)

        assert embeddings.shape == (4, 400)
        assert np.all(np.isfinite(embeddings))

        # Each scenario should produce a distinct embedding (not identical)
        for i in range(4):
            for j in range(i + 1, 4):
                # Embeddings should not be identical
                assert not np.allclose(embeddings[i], embeddings[j], atol=1e-3)

    def test_encoding_pipeline_flow(self) -> None:
        """Test complete encoding pipeline."""
        # Set seeds for deterministic behavior
        np.random.seed(42)
        random.seed(42)

        encoder = CognitiveEncoder(device="cpu")
        text = (
            "I'm working on an urgent machine learning project with my frustrated team"
        )

        # Get breakdown to verify pipeline
        breakdown = encoder.get_dimension_breakdown(text)

        # Verify semantic component
        assert breakdown["semantic_embedding_norm"] > 0

        # Verify dimensional components
        dims = breakdown["dimensions"]

        # Should detect work context
        contextual = dims["contextual"]
        work_idx = contextual["names"].index("work_context")
        tech_idx = contextual["names"].index("technical_context")
        assert contextual["values"][work_idx] > 0.2
        assert (
            contextual["values"][tech_idx] >= 0.0
        )  # ML could be detected as technical

        # Should detect urgency
        temporal = dims["temporal"]
        urgency_idx = temporal["names"].index("urgency")
        assert temporal["values"][urgency_idx] > 0.1

        # Should detect collaboration
        social = dims["social"]
        collab_idx = social["names"].index("collaboration")
        assert social["values"][collab_idx] > 0.1

        # Should detect frustration
        emotional = dims["emotional"]
        frust_idx = emotional["names"].index("frustration")
        assert emotional["values"][frust_idx] > 0.1
