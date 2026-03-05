"""
build_bert_index.py
──────────────────────────────────────────────────────────────
Reads all movie JSON files, generates BERT embeddings,
builds a FAISS index, and saves everything to disk.

Usage:
    python build_bert_index.py --input ../data/movies/ --output ./models/

Your teammate responsible for BERT indexing should run this script.
"""

import argparse
import json
import os
import pickle
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

import config


def load_movies(data_dir: str) -> list:
    """
    Walk the data directory and load all movie JSON files.
    Returns a list of movie dicts.
    """
    movies = []
    data_path = Path(data_dir)

    # Handle both flat (*.json) and nested (id/details.json) structures
    json_files = list(data_path.rglob("*.json"))
    print(f"[DATA] Found {len(json_files)} JSON files.")

    for fp in json_files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                movie = json.load(f)
            if isinstance(movie, dict) and "id" in movie:
                movies.append(movie)
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"[DATA] Loaded {len(movies)} valid movies.")
    return movies


def movie_to_text(movie: dict) -> str:
    """
    Combine key fields into a single text passage for BERT embedding.
    Keeps it within ~350 words to stay under 512 tokens safely.
    """
    parts = []

    title = movie.get("title", "")
    if title:
        parts.append(title)

    overview = movie.get("overview", "")
    if overview:
        parts.append(overview)

    # Add cast names (top 10)
    cast = movie.get("cast", [])
    if isinstance(cast, list):
        names = [c.get("name", "") for c in cast[:10] if isinstance(c, dict)]
        if names:
            parts.append("Cast: " + ", ".join(names))

    # Add genre names
    genres = movie.get("genres", [])
    if isinstance(genres, list):
        genre_names = [g.get("name", "") if isinstance(g, dict) else str(g) for g in genres]
        if genre_names:
            parts.append("Genres: " + ", ".join(genre_names))

    text = " . ".join(parts)

    # Rough truncation to ~350 words
    words = text.split()
    if len(words) > 350:
        text = " ".join(words[:350])

    return text


def build_metadata(movies: list) -> dict:
    """Build a movie_id → metadata dict for quick lookups at search time."""
    metadata = {}
    for m in movies:
        mid = m.get("id")
        if mid is None:
            continue
        metadata[mid] = {
            "title": m.get("title", ""),
            "overview": m.get("overview", ""),
            "genres": m.get("genres", []),
            "production_countries": m.get("production_countries", []),
            "vote_average": m.get("vote_average", 0),
            "release_date": m.get("release_date", ""),
        }
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Build BERT + FAISS index for movie search")
    parser.add_argument("--input", type=str, default=config.DATA_DIR,
                        help="Path to the movie JSON data directory")
    parser.add_argument("--output", type=str, default=config.MODELS_DIR,
                        help="Path to save FAISS index and mappings")
    parser.add_argument("--batch-size", type=int, default=256,
                        help="Batch size for BERT encoding")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # ── Step 1: Load data ─────────────────────────────
    movies = load_movies(args.input)
    if not movies:
        print("[ERROR] No movies found. Check --input path.")
        return

    # ── Step 2: Prepare texts and passage map ─────────
    texts = []
    passage_map = []  # index → movie_id

    for movie in movies:
        mid = movie.get("id")
        if mid is None:
            continue
        text = movie_to_text(movie)
        if text.strip():
            texts.append(text)
            passage_map.append(mid)

    print(f"[INDEX] Prepared {len(texts)} passages for embedding.")

    # ── Step 3: Generate embeddings ───────────────────
    print(f"[BERT] Loading model: {config.BERT_MODEL_NAME}")
    model = SentenceTransformer(config.BERT_MODEL_NAME)

    print(f"[BERT] Encoding {len(texts)} passages (batch_size={args.batch_size}) ...")
    start_time = time.time()
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,  # for cosine similarity via inner product
    )
    embeddings = np.array(embeddings, dtype="float32")
    encode_time = time.time() - start_time
    print(f"[BERT] Encoding done in {encode_time:.2f}s "
          f"({len(texts) / encode_time:.1f} passages/sec)")

    # ── Step 4: Build FAISS index ─────────────────────
    dim = embeddings.shape[1]
    print(f"[FAISS] Building IndexFlatIP with dim={dim} ...")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    print(f"[FAISS] Index built. Total vectors: {index.ntotal}")

    # ── Step 5: Save everything ───────────────────────
    faiss_path = os.path.join(args.output, "faiss_index.bin")
    faiss.write_index(index, faiss_path)
    print(f"[SAVE] FAISS index → {faiss_path}")

    map_path = os.path.join(args.output, "passage_map.pkl")
    with open(map_path, "wb") as f:
        pickle.dump(passage_map, f)
    print(f"[SAVE] Passage map → {map_path}")

    meta_path = os.path.join(args.output, "movie_metadata.pkl")
    metadata = build_metadata(movies)
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)
    print(f"[SAVE] Movie metadata → {meta_path}")

    # ── Summary ───────────────────────────────────────
    print("\n" + "=" * 50)
    print("BUILD COMPLETE")
    print(f"  Movies:     {len(movies)}")
    print(f"  Passages:   {len(texts)}")
    print(f"  Dimensions: {dim}")
    print(f"  Encode time: {encode_time:.2f}s")
    print(f"  Output dir:  {args.output}")
    print("=" * 50)


if __name__ == "__main__":
    main()
