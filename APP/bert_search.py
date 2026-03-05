"""
BERT + FAISS dense search module.
Handles encoding queries with BERT and searching the FAISS index.
"""

import pickle
import time

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

import config

# ── Module-level singletons (loaded once) ─────────────
_model = None
_index = None
_passage_map = None       # list: passage_index → movie_id
_movie_metadata = None    # dict: movie_id → {title, overview, genres, countries, ...}


def _load_resources():
    """Lazy-load the BERT model, FAISS index, and mapping files."""
    global _model, _index, _passage_map, _movie_metadata

    if _model is None:
        print(f"[BERT] Loading model: {config.BERT_MODEL_NAME} ...")
        _model = SentenceTransformer(config.BERT_MODEL_NAME)
        print("[BERT] Model loaded.")

    if _index is None:
        print(f"[FAISS] Loading index from: {config.FAISS_INDEX_PATH} ...")
        _index = faiss.read_index(config.FAISS_INDEX_PATH)
        print(f"[FAISS] Index loaded. Total vectors: {_index.ntotal}")

    if _passage_map is None:
        with open(config.PASSAGE_MAP_PATH, "rb") as f:
            _passage_map = pickle.load(f)
        print(f"[FAISS] Passage map loaded. Entries: {len(_passage_map)}")

    if _movie_metadata is None:
        with open(config.MOVIE_METADATA_PATH, "rb") as f:
            _movie_metadata = pickle.load(f)
        print(f"[META] Movie metadata loaded. Movies: {len(_movie_metadata)}")


def search(query: str, top_k: int = 10, country_filter: str = None) -> list:
    """
    Encode the query with BERT, search the FAISS index, and return top-k movies.

    Args:
        query:          The user's search string.
        top_k:          Number of results to return.
        country_filter: Optional ISO country code to filter results.

    Returns:
        A list of result dicts matching the same format as es_search.search().
    """
    _load_resources()

    # ── Encode query ──────────────────────────────────
    start = time.time()
    query_vec = _model.encode([query], normalize_embeddings=True)
    query_vec = np.array(query_vec, dtype="float32")
    encode_time = time.time() - start

    # ── Search FAISS (fetch extra if we need to filter) ─
    fetch_k = top_k * 5 if country_filter else top_k
    start = time.time()
    scores, indices = _index.search(query_vec, fetch_k)
    search_time = time.time() - start

    print(f"[BERT] Encode: {encode_time:.3f}s | FAISS search: {search_time:.3f}s")

    # ── Map passage indices → movie results ───────────
    seen_movies = set()
    results = []

    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue

        movie_id = _passage_map[idx]

        # Deduplicate: one result per movie
        if movie_id in seen_movies:
            continue
        seen_movies.add(movie_id)

        meta = _movie_metadata.get(movie_id, {})

        # Apply country filter if requested
        if country_filter:
            country_codes = [c.get("iso_3166_1", "") for c in meta.get("production_countries", [])]
            if country_filter not in country_codes:
                continue

        results.append({
            "movie_id": movie_id,
            "title": meta.get("title", "Unknown"),
            "overview": meta.get("overview", "")[:300],
            "score": round(float(score), 4),
            "genres": meta.get("genres", []),
            "countries": meta.get("production_countries", []),
            "rating": meta.get("vote_average", 0),
            "release_year": str(meta.get("release_date", ""))[:4],
        })

        if len(results) >= top_k:
            break

    return results
