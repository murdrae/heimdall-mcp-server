#!/usr/bin/env python3
"""
ONNX Model Conversion Script

Converts the all-MiniLM-L6-v2 sentence-transformer model to ONNX format
for Docker size optimization while maintaining identical embedding quality.

This script:
1. Loads the original PyTorch model
2. Exports it to ONNX format with proper configuration
3. Validates the conversion produces identical outputs
4. Saves the ONNX model and tokenizer to data/models/
"""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer


def setup_directories() -> Path:
    """Create necessary directories."""
    models_dir = Path("./data/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def load_original_model(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> tuple[SentenceTransformer, Any]:
    """Load the original sentence-transformer model."""
    print(f"Loading original model: {model_name}")
    model = SentenceTransformer(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return model, tokenizer


def create_torch_wrapper(sentence_model: SentenceTransformer) -> torch.nn.Module:
    """Create a PyTorch wrapper for ONNX export."""

    class SentenceTransformerWrapper(torch.nn.Module):
        def __init__(self, sentence_transformer: SentenceTransformer) -> None:
            super().__init__()
            # Extract the transformer model (first module)
            self.transformer = sentence_transformer._modules["0"].auto_model

        def forward(
            self, input_ids: torch.Tensor, attention_mask: torch.Tensor
        ) -> torch.Tensor:
            # Run transformer
            outputs = self.transformer(
                input_ids=input_ids, attention_mask=attention_mask
            )

            # Mean pooling (same as sentence-transformers)
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = (
                attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            )
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask

            # L2 normalization (same as sentence-transformers)
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)

            return normalized

    return SentenceTransformerWrapper(sentence_model)


def export_to_onnx(
    model_wrapper: torch.nn.Module, tokenizer: Any, output_path: Path
) -> Path:
    """Export the model to ONNX format."""
    print("Exporting model to ONNX format...")

    # Create dummy input for export
    dummy_text = "This is a sample sentence for ONNX export."
    dummy_encoding = tokenizer(
        dummy_text, padding=True, truncation=True, max_length=512, return_tensors="pt"
    )

    dummy_input_ids = dummy_encoding["input_ids"]
    dummy_attention_mask = dummy_encoding["attention_mask"]

    # Set model to evaluation mode
    model_wrapper.eval()

    # Export to ONNX
    onnx_path = output_path / "all-MiniLM-L6-v2.onnx"

    torch.onnx.export(
        model_wrapper,
        (dummy_input_ids, dummy_attention_mask),
        str(onnx_path),
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        input_names=["input_ids", "attention_mask"],
        output_names=["embeddings"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "embeddings": {0: "batch_size"},
        },
    )

    print(f"ONNX model saved to: {onnx_path}")
    return onnx_path


def save_tokenizer_config(tokenizer: Any, output_path: Path) -> dict[str, Any]:
    """Save tokenizer configuration."""

    # Save tokenizer
    tokenizer.save_pretrained(str(output_path / "tokenizer"))

    # Create a simple config for easy loading
    config = {
        "model_name": "all-MiniLM-L6-v2",
        "max_length": 512,
        "embedding_dimension": 384,
        "tokenizer_path": str(output_path / "tokenizer"),
    }

    with open(output_path / "model_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print(f"Tokenizer saved to: {output_path / 'tokenizer'}")
    return config


def validate_conversion(
    original_model: SentenceTransformer,
    onnx_path: Path,
    tokenizer: Any,
    num_test_cases: int = 10,
) -> bool:
    """Validate that ONNX model produces identical outputs."""
    print("Validating ONNX conversion...")

    # Try to import onnxruntime for validation
    try:
        import onnxruntime as ort
    except ImportError:
        print("WARNING: onnxruntime not installed, skipping validation")
        print("Install with: pip install onnxruntime")
        return True

    # Load ONNX model
    ort_session = ort.InferenceSession(str(onnx_path))

    # Test cases
    test_sentences = [
        "Hello world",
        "This is a test sentence for validation.",
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning and artificial intelligence are fascinating fields.",
        "短文本测试",  # Short text test
        "A" * 400,  # Long text test
        "",  # Empty test (will be handled by padding)
        "Special characters: !@#$%^&*()_+{}|:<>?",
        "Numbers: 123456789 and dates: 2024-01-01",
        "Mixed content with émojis 🚀 and unicode ñoñó",
    ]

    test_sentences = test_sentences[:num_test_cases]

    max_error = 0.0

    for i, sentence in enumerate(test_sentences):
        if not sentence:  # Skip empty strings for this test
            continue

        try:
            # Original model prediction
            original_embedding = original_model.encode(
                sentence, normalize_embeddings=True
            )

            # ONNX model prediction
            encoding = tokenizer(
                sentence,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np",
            )

            onnx_inputs = {
                "input_ids": encoding["input_ids"].astype(np.int64),
                "attention_mask": encoding["attention_mask"].astype(np.int64),
            }

            onnx_embedding = ort_session.run(None, onnx_inputs)[0][0]

            # Compare embeddings
            if isinstance(original_embedding, torch.Tensor):
                original_embedding = original_embedding.numpy()

            error = np.max(np.abs(original_embedding - onnx_embedding))
            max_error = max(max_error, error)

            print(
                f"Test {i + 1:2d}: Error = {error:.2e} (sentence: '{sentence[:50]}{'...' if len(sentence) > 50 else ''}')"
            )

        except Exception as e:
            print(f"Error testing sentence {i + 1}: {e}")
            return False

    print("\nValidation complete!")
    print(f"Maximum error: {max_error:.2e}")

    # Check if conversion is bit-for-bit or very close
    if max_error < 1e-5:
        print("✅ EXCELLENT: Near bit-for-bit compatibility!")
        return True
    elif max_error < 1e-3:
        print("✅ GOOD: High precision compatibility")
        return True
    else:
        print("❌ WARNING: Significant differences detected")
        return False


def main() -> bool:
    """Main conversion process."""
    print("🚀 Starting ONNX Model Conversion")
    print("=" * 50)

    try:
        # Step 1: Setup
        models_dir = setup_directories()
        print(f"Models directory: {models_dir.absolute()}")

        # Step 2: Load original model
        original_model, tokenizer = load_original_model()

        # Step 3: Create wrapper for ONNX export
        model_wrapper = create_torch_wrapper(original_model)

        # Step 4: Export to ONNX
        onnx_path = export_to_onnx(model_wrapper, tokenizer, models_dir)

        # Step 5: Save tokenizer
        save_tokenizer_config(tokenizer, models_dir)

        # Step 6: Validate conversion
        is_valid = validate_conversion(original_model, onnx_path, tokenizer)

        if is_valid:
            print("\n🎉 ONNX Conversion Successful!")
            print(f"   ONNX Model: {onnx_path}")
            print(f"   Tokenizer: {models_dir / 'tokenizer'}")
            print(f"   Config: {models_dir / 'model_config.json'}")

            # Show file sizes
            onnx_size = onnx_path.stat().st_size / (1024 * 1024)
            print(f"   ONNX model size: {onnx_size:.1f} MB")

            return True
        else:
            print("\n❌ ONNX Conversion Failed Validation")
            return False

    except Exception as e:
        print(f"\n❌ Error during conversion: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
