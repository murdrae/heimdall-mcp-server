"""
Multi-dimensional encoding subsystem for cognitive memory.

This module provides comprehensive text encoding capabilities combining
Sentence-BERT semantic embeddings with rule-based cognitive dimensions
through neural fusion layers.
"""

from .cognitive_encoder import (
    CognitiveEncoder,
    CognitiveFusionLayer,
    create_cognitive_encoder,
)
from .dimensions import (
    BaseDimensionExtractor,
    CognitiveDimensionExtractor,
    ContextualExtractor,
    EmotionalExtractor,
    SocialExtractor,
    TemporalExtractor,
)
from .sentence_bert import SentenceBERTProvider, create_sentence_bert_provider

__all__ = [
    # Main cognitive encoder
    "CognitiveEncoder",
    "CognitiveFusionLayer",
    "create_cognitive_encoder",
    # Dimension extractors
    "CognitiveDimensionExtractor",
    "BaseDimensionExtractor",
    "EmotionalExtractor",
    "TemporalExtractor",
    "ContextualExtractor",
    "SocialExtractor",
    # Semantic embeddings
    "SentenceBERTProvider",
    "create_sentence_bert_provider",
]
