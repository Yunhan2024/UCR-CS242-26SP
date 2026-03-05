#!/bin/bash
# ──────────────────────────────────────────────────────
# indexer.sh — Build the BERT + FAISS dense index
#
# Usage:
#   ./indexer.sh <input-dir> <output-dir>
#
# Example:
#   ./indexer.sh data/movies/ backend/models/
# ──────────────────────────────────────────────────────

set -e

INPUT_DIR="${1:-data/movies/}"
OUTPUT_DIR="${2:-backend/models/}"

echo "======================================"
echo "  BERT + FAISS Index Builder"
echo "  Input:  $INPUT_DIR"
echo "  Output: $OUTPUT_DIR"
echo "======================================"

cd "$(dirname "$0")"

python backend/build_bert_index.py \
    --input "$INPUT_DIR" \
    --output "$OUTPUT_DIR" \
    --batch-size 256

echo ""
echo "Done! Index files saved to $OUTPUT_DIR"
echo "  - faiss_index.bin"
echo "  - passage_map.pkl"
echo "  - movie_metadata.pkl"
