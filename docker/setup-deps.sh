#!/bin/bash
set -e

echo "🔧 Starting consolidated dependency setup..."

# Create model directory structure
mkdir -p /app/data/models/tokenizer

echo "📦 Setting up ONNX model environment..."
# Note: ONNX model, tokenizer, and config files should be provided in the build context
# or will be created by the convert_model_to_onnx.py script during runtime
echo "✅ ONNX model environment prepared"

echo "📦 Pre-downloading spaCy model..."
python -m spacy download en_core_web_md
echo "✅ spaCy model downloaded successfully"

echo "📦 Pre-downloading NLTK data..."
python -c "import nltk; nltk.download('punkt_tab')"
echo "✅ NLTK punkt_tab data downloaded successfully"

echo "🎉 All dependencies setup completed successfully!"
