"""
Unit tests for Sentence-BERT provider.
"""

import numpy as np
import pytest

from cognitive_memory.encoding.sentence_bert import (
    SentenceBERTProvider,
    create_sentence_bert_provider,
)


@pytest.mark.slow
class TestSentenceBERTProvider:
    """Test Sentence-BERT embedding provider."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Use a smaller model for faster testing
        self.provider = SentenceBERTProvider(
            model_name="all-MiniLM-L6-v2",
        )

    def test_initialization(self) -> None:
        """Test provider initialization."""
        assert self.provider.model_name == "all-MiniLM-L6-v2"
        assert self.provider.embedding_dimension == 384

    def test_single_text_encoding(self) -> None:
        """Test encoding of single text."""
        text = "This is a test sentence for cognitive memory encoding"
        embedding = self.provider.encode(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

        # Check embedding is normalized (approximately)
        norm = np.linalg.norm(embedding)
        assert 0.95 <= norm <= 1.05

    def test_batch_encoding(self) -> None:
        """Test batch encoding of multiple texts."""
        texts = [
            "First test sentence about programming",
            "Second sentence discussing cognitive memory",
            "Third text focusing on machine learning",
        ]

        embeddings = self.provider.encode_batch(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32

        # Check all embeddings are normalized
        norms = np.linalg.norm(embeddings, axis=1)
        assert np.all(norms >= 0.95)
        assert np.all(norms <= 1.05)

    def test_empty_text_handling(self) -> None:
        """Test handling of empty text."""
        embedding = self.provider.encode("")

        assert embedding.shape == (384,)
        assert np.all(embedding == 0.0)

    def test_empty_batch_handling(self) -> None:
        """Test handling of empty batch."""
        embeddings = self.provider.encode_batch([])

        assert embeddings.shape == (0, 384)

    def test_mixed_batch_with_empty_texts(self) -> None:
        """Test batch with some empty texts."""
        texts = [
            "Valid text",
            "",
            "Another valid text",
            "   ",  # whitespace only
            "Final valid text",
        ]

        embeddings = self.provider.encode_batch(texts)

        assert embeddings.shape == (5, 384)

        # Empty texts should have zero embeddings
        assert np.all(embeddings[1] == 0.0)  # Empty string
        assert np.all(embeddings[3] == 0.0)  # Whitespace only

        # Valid texts should have non-zero embeddings
        assert np.any(embeddings[0] != 0.0)
        assert np.any(embeddings[2] != 0.0)
        assert np.any(embeddings[4] != 0.0)

    def test_similarity_computation(self) -> None:
        """Test cosine similarity computation."""
        text1 = "Machine learning and artificial intelligence"
        text2 = "AI and ML are important technologies"
        text3 = "Cooking recipes and food preparation"

        emb1 = self.provider.encode(text1)
        emb2 = self.provider.encode(text2)
        emb3 = self.provider.encode(text3)

        # Similar texts should have higher similarity
        sim_12 = self.provider.compute_similarity(emb1, emb2)
        sim_13 = self.provider.compute_similarity(emb1, emb3)

        assert sim_12 > sim_13
        assert -1.0 <= sim_12 <= 1.0
        assert -1.0 <= sim_13 <= 1.0

    def test_batch_similarity_computation(self) -> None:
        """Test batch similarity computation."""
        query_text = "Machine learning algorithms"
        candidate_texts = [
            "Deep learning and neural networks",
            "Cooking and food preparation",
            "Artificial intelligence research",
            "Sports and athletics",
        ]

        query_emb = self.provider.encode(query_text)
        candidate_embs = self.provider.encode_batch(candidate_texts)

        similarities = self.provider.compute_batch_similarity(query_emb, candidate_embs)

        assert similarities.shape == (4,)
        assert np.all(similarities >= -1.0)
        assert np.all(similarities <= 1.0)

        # ML-related texts should be more similar
        assert similarities[0] > similarities[1]  # Deep learning > cooking
        assert similarities[2] > similarities[3]  # AI > sports

    def test_model_info(self) -> None:
        """Test model information retrieval."""
        info = self.provider.get_model_info()

        assert "model_name" in info
        assert "embedding_dimension" in info
        assert "max_sequence_length" in info

        assert info["model_name"] == "all-MiniLM-L6-v2"
        assert info["embedding_dimension"] == 384

    def test_embedding_dimension(self) -> None:
        """Test embedding dimension retrieval."""
        dim = self.provider.get_embedding_dimension()
        assert dim == 384

    def test_consistency(self) -> None:
        """Test that same text produces same embedding."""
        text = "Consistent encoding test"

        emb1 = self.provider.encode(text)
        emb2 = self.provider.encode(text)

        # Embeddings should be identical
        assert np.allclose(emb1, emb2, atol=1e-6)

    def test_different_texts_different_embeddings(self) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "First unique sentence"
        text2 = "Completely different content"

        emb1 = self.provider.encode(text1)
        emb2 = self.provider.encode(text2)

        # Embeddings should be different
        assert not np.allclose(emb1, emb2, atol=1e-3)


class TestSentenceBERTFactory:
    """Test factory function for creating providers."""

    def test_factory_creation(self) -> None:
        """Test factory function."""
        provider = create_sentence_bert_provider(model_name="all-MiniLM-L6-v2")

        assert isinstance(provider, SentenceBERTProvider)
        assert provider.model_name == "all-MiniLM-L6-v2"
        # Device is now handled by ONNX Runtime internally

    def test_factory_defaults(self) -> None:
        """Test factory function with defaults."""
        provider = create_sentence_bert_provider()

        assert isinstance(provider, SentenceBERTProvider)
        # Should use configuration defaults


@pytest.mark.slow
@pytest.mark.integration
class TestSentenceBERTIntegration:
    """Integration tests for Sentence-BERT provider."""

    def test_encoding_performance(self) -> None:
        """Test encoding performance with realistic text sizes."""
        provider = SentenceBERTProvider()

        # Test with various text lengths
        texts = [
            "Short text",
            "Medium length text with more content and details about cognitive memory systems",
            "Very long text that contains multiple sentences and extensive information about "
            "machine learning, artificial intelligence, cognitive science, memory systems, "
            "natural language processing, deep learning, neural networks, embeddings, and "
            "various other topics that might appear in real-world cognitive memory applications",
        ]

        for text in texts:
            embedding = provider.encode(text)
            assert embedding.shape == (384,)
            assert np.all(np.isfinite(embedding))

    def test_batch_vs_individual_consistency(self) -> None:
        """Test that batch and individual encoding produce same results."""
        provider = SentenceBERTProvider()

        texts = [
            "First consistency test",
            "Second consistency test",
            "Third consistency test",
        ]

        # Individual encoding
        individual_embs = [provider.encode(text) for text in texts]
        individual_batch = np.stack(individual_embs)

        # Batch encoding
        batch_embs = provider.encode_batch(texts)

        # Should be very close (allowing for minor numerical differences)
        assert np.allclose(individual_batch, batch_embs, atol=1e-5)
