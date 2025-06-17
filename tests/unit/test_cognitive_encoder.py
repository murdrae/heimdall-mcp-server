"""
Unit tests for cognitive encoder and fusion layer.
"""

import pytest
import torch
import torch.nn as nn

from cognitive_memory.encoding.cognitive_encoder import (
    CognitiveEncoder,
    CognitiveFusionLayer,
    create_cognitive_encoder,
)


class TestCognitiveFusionLayer:
    """Test the neural fusion layer."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.semantic_dim = 384
        self.cognitive_dim = 16
        self.output_dim = 512
        self.fusion = CognitiveFusionLayer(
            self.semantic_dim, 
            self.cognitive_dim, 
            self.output_dim
        )
    
    def test_initialization(self) -> None:
        """Test fusion layer initialization."""
        assert self.fusion.semantic_dim == 384
        assert self.fusion.cognitive_dim == 16
        assert self.fusion.output_dim == 512
        assert self.fusion.input_dim == 400  # 384 + 16
        
        # Check layers exist
        assert isinstance(self.fusion.fusion_layer, nn.Linear)
        assert isinstance(self.fusion.layer_norm, nn.LayerNorm)
    
    def test_single_input_forward(self) -> None:
        """Test forward pass with single input."""
        semantic_emb = torch.randn(self.semantic_dim)
        cognitive_dims = torch.randn(self.cognitive_dim)
        
        output = self.fusion(semantic_emb, cognitive_dims)
        
        assert output.shape == (self.output_dim,)
        assert output.dtype == torch.float32
        assert torch.all(torch.isfinite(output))
    
    def test_batch_input_forward(self) -> None:
        """Test forward pass with batch input."""
        batch_size = 3
        semantic_embs = torch.randn(batch_size, self.semantic_dim)
        cognitive_dims = torch.randn(batch_size, self.cognitive_dim)
        
        output = self.fusion(semantic_embs, cognitive_dims)
        
        assert output.shape == (batch_size, self.output_dim)
        assert output.dtype == torch.float32
        assert torch.all(torch.isfinite(output))
    
    def test_mismatched_batch_sizes(self) -> None:
        """Test handling of mismatched batch sizes."""
        semantic_embs = torch.randn(3, self.semantic_dim)
        cognitive_dims = torch.randn(1, self.cognitive_dim)  # Will be expanded
        
        output = self.fusion(semantic_embs, cognitive_dims)
        
        assert output.shape == (3, self.output_dim)
        assert torch.all(torch.isfinite(output))
    
    def test_gradient_flow(self) -> None:
        """Test that gradients flow properly."""
        semantic_emb = torch.randn(self.semantic_dim, requires_grad=True)
        cognitive_dims = torch.randn(self.cognitive_dim, requires_grad=True)
        
        output = self.fusion(semantic_emb, cognitive_dims)
        loss = output.sum()
        loss.backward()
        
        assert semantic_emb.grad is not None
        assert cognitive_dims.grad is not None
        assert torch.all(torch.isfinite(semantic_emb.grad))
        assert torch.all(torch.isfinite(cognitive_dims.grad))


@pytest.mark.slow
class TestCognitiveEncoder:
    """Test the complete cognitive encoder."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Use CPU and smaller model for testing
        self.encoder = CognitiveEncoder(
            sentence_bert_model="all-MiniLM-L6-v2",
            device="cpu"
        )
    
    def test_initialization(self) -> None:
        """Test encoder initialization."""
        assert self.encoder.semantic_dim == 384
        assert self.encoder.cognitive_dim == 16
        assert self.encoder.output_dim == 512
        
        # Check components are initialized
        assert self.encoder.semantic_provider is not None
        assert self.encoder.dimension_extractor is not None
        assert self.encoder.fusion_layer is not None
    
    def test_single_text_encoding(self) -> None:
        """Test encoding of single text."""
        text = "I'm working on a machine learning project with my team"
        embedding = self.encoder.encode(text)
        
        assert isinstance(embedding, torch.Tensor)
        assert embedding.shape == (512,)
        assert embedding.dtype == torch.float32
        assert torch.all(torch.isfinite(embedding))
        
        # Should not be all zeros for valid text
        assert torch.any(embedding != 0.0)
    
    def test_batch_encoding(self) -> None:
        """Test batch encoding of multiple texts."""
        texts = [
            "I'm frustrated with this debugging session",
            "Great! The algorithm is working perfectly now",
            "We need to collaborate on this urgent project"
        ]
        
        embeddings = self.encoder.encode_batch(texts)
        
        assert isinstance(embeddings, torch.Tensor)
        assert embeddings.shape == (3, 512)
        assert embeddings.dtype == torch.float32
        assert torch.all(torch.isfinite(embeddings))
        
        # Each embedding should be different
        for i in range(3):
            for j in range(i + 1, 3):
                assert not torch.allclose(embeddings[i], embeddings[j], atol=1e-3)
    
    def test_empty_text_handling(self) -> None:
        """Test handling of empty text."""
        embedding = self.encoder.encode("")
        
        assert embedding.shape == (512,)
        assert torch.all(embedding == 0.0)
    
    def test_empty_batch_handling(self) -> None:
        """Test handling of empty batch."""
        embeddings = self.encoder.encode_batch([])
        
        assert embeddings.shape == (0, 512)
    
    def test_mixed_batch_with_empty_texts(self) -> None:
        """Test batch with some empty texts."""
        texts = [
            "Valid cognitive text",
            "",
            "Another valid text about teamwork"
        ]
        
        embeddings = self.encoder.encode_batch(texts)
        
        assert embeddings.shape == (3, 512)
        
        # Empty text should have zero embedding
        assert torch.all(embeddings[1] == 0.0)
        
        # Valid texts should have non-zero embeddings
        assert torch.any(embeddings[0] != 0.0)
        assert torch.any(embeddings[2] != 0.0)
    
    def test_dimension_breakdown(self) -> None:
        """Test detailed dimension breakdown."""
        text = "I'm really frustrated debugging this urgent API issue and need team help"
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
        assert fusion_info["output_dim"] == 512
        assert fusion_info["parameters"] > 0
    
    def test_consistency(self) -> None:
        """Test that same text produces same embedding."""
        text = "Consistent cognitive encoding test"
        
        emb1 = self.encoder.encode(text)
        emb2 = self.encoder.encode(text)
        
        # Should be identical (no randomness in inference)
        assert torch.allclose(emb1, emb2, atol=1e-6)
    
    def test_different_texts_different_embeddings(self) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "Happy successful project completion"
        text2 = "Frustrated debugging session with errors"
        
        emb1 = self.encoder.encode(text1)
        emb2 = self.encoder.encode(text2)
        
        # Should be different due to both semantic and dimensional differences
        assert not torch.allclose(emb1, emb2, atol=1e-2)
    
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
        cognitive_sim = torch.dot(emb1, emb2) / (torch.norm(emb1) * torch.norm(emb2))
        semantic_sim = torch.dot(sem1, sem2) / (torch.norm(sem1) * torch.norm(sem2))
        
        # Cognitive similarity should be lower due to emotional differences
        assert cognitive_sim < semantic_sim


class TestCognitiveEncoderFactory:
    """Test factory function for creating encoders."""
    
    def test_factory_creation(self) -> None:
        """Test factory function."""
        encoder = create_cognitive_encoder(
            sentence_bert_model="all-MiniLM-L6-v2",
            device="cpu"
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
        encoder = CognitiveEncoder(device="cpu")
        
        scenarios = [
            "I'm debugging a critical production bug that needs to be fixed before tomorrow's deadline",
            "Our team had a great brainstorming session and came up with innovative solutions",
            "I'm analyzing user behavior data to understand engagement patterns",
            "Can someone help me understand this complex algorithm? I'm curious about how it works"
        ]
        
        embeddings = encoder.encode_batch(scenarios)
        
        assert embeddings.shape == (4, 512)
        assert torch.all(torch.isfinite(embeddings))
        
        # Each scenario should have unique embedding
        for i in range(4):
            for j in range(i + 1, 4):
                similarity = torch.dot(embeddings[i], embeddings[j]) / (
                    torch.norm(embeddings[i]) * torch.norm(embeddings[j])
                )
                # Should be similar but not identical
                assert 0.1 <= similarity <= 0.9
    
    def test_encoding_pipeline_flow(self) -> None:
        """Test complete encoding pipeline."""
        encoder = CognitiveEncoder(device="cpu")
        text = "I'm working on an urgent machine learning project with my frustrated team"
        
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
        assert contextual["values"][tech_idx] >= 0.0  # ML could be detected as technical
        
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