"""
BERT + FAISS dense search module.
Aligned with CS242_BERT_Indexing.ipynb:
  - Model: sentence-transformers/all-MiniLM-L6-v2
  - FAISS: IndexFlatL2 (L2 distance — lower = more similar)
  - movie_metadata: a LIST where index i = FAISS vector i
  - Each metadata entry has: id, imdb_id, title, overview, genres,
    release_date, vote_average, countries, country_codes, origin_country, reviews
"""

import pickle
import time

import faiss
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

import config

# ── Module-level singletons (loaded once) ─────────────
_tokenizer = None
_model = None
_index = None
_movie_metadata = None    # LIST: position i → metadata dict for FAISS vector i
_device = None


def mean_pooling(model_output, attention_mask):
    """Mean pooling — matches the notebook's implementation exactly."""
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9
    )


def _load_resources():
    """Lazy-load the BERT model, FAISS index, and metadata."""
    global _tokenizer, _model, _index, _movie_metadata, _device

    if _device is None:
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[BERT] Using device: {_device}")

    if _tokenizer is None:
        print(f"[BERT] Loading tokenizer: {config.BERT_MODEL_NAME} ...")
        _tokenizer = AutoTokenizer.from_pretrained(config.BERT_MODEL_NAME)

    if _model is None:
        print(f"[BERT] Loading model: {config.BERT_MODEL_NAME} ...")
        _model = AutoModel.from_pretrained(config.BERT_MODEL_NAME)
        _model = _model.to(_device)
        _model.eval()
        print("[BERT] Model loaded.")

    if _index is None:
        print(f"[FAISS] Loading index from: {config.FAISS_INDEX_PATH} ...")
        _index = faiss.read_index(config.FAISS_INDEX_PATH)
        print(f"[FAISS] Index loaded. Total vectors: {_index.ntotal}")

    if _movie_metadata is None:
        print(f"[META] Loading metadata from: {config.MOVIE_METADATA_PATH} ...")
        with open(config.MOVIE_METADATA_PATH, "rb") as f:
            _movie_metadata = pickle.load(f)
        print(f"[META] Metadata loaded. Entries: {len(_movie_metadata)}")


def encode_query(query: str) -> np.ndarray:
    """Encode a query string into a 384-dim vector. Matches notebook's encode_query()."""
    inputs = _tokenizer(
        query,
        return_tensors="pt",
        truncation=True,
    ).to(_device)

    with torch.no_grad():
        model_output = _model(**inputs)

    embedding = mean_pooling(model_output, inputs["attention_mask"])
    return embedding.cpu().numpy().astype("float32")


def search(query: str, top_k: int = 10, country_filter: str = None) -> list:
    """
    Encode the query with BERT, search FAISS (L2), return top-k movies.

    NOTE: FAISS IndexFlatL2 returns L2 *distances* (lower = better).
    We convert to a similarity-like score for display.
    """
    _load_resources()

    # ── Encode query ──────────────────────────────────
    start = time.time()
    query_vec = encode_query(query)
    encode_time = time.time() - start

    # ── Search FAISS ──────────────────────────────────
    fetch_k = top_k * 5 if country_filter else top_k * 2
    start = time.time()
    distances, indices = _index.search(query_vec, fetch_k)
    search_time = time.time() - start

    print(f"[BERT] Encode: {encode_time:.3f}s | FAISS search: {search_time:.3f}s")

    # ── Build results from metadata list ──────────────
    seen_ids = set()
    results = []

    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(_movie_metadata):
            continue

        meta = _movie_metadata[idx]
        movie_id = meta.get("id")

        # Deduplicate by movie ID
        if movie_id in seen_ids:
            continue
        seen_ids.add(movie_id)

        # Country filter using origin_country (1 country per movie)
        if country_filter:
            origins = meta.get("origin_country", [])
            if country_filter not in origins:
                continue

        # Convert L2 distance to a similarity score.
        # L2 distance ≥ 0, lower is better. We invert for display:
        #   similarity = 1 / (1 + distance)
        similarity = round(1.0 / (1.0 + float(dist)), 4)

        # Extract release year from release_date string
        rd = meta.get("release_date") or ""
        release_year = str(rd)[:4] if rd else ""

        results.append({
            "movie_id": movie_id,
            "imdb_id": meta.get("imdb_id", ""),
            "title": meta.get("title", "Unknown"),
            "overview": (meta.get("overview") or "")[:300],
            "score": similarity,
            "genres": meta.get("genres", []),
            "countries": meta.get("origin_country", []),
            "rating": meta.get("vote_average", 0),
            "release_year": release_year,
        })

        if len(results) >= top_k:
            break

    return results


def get_country_counts() -> list:
    """
    Count movies per country using origin_country from BERT metadata.
    origin_country is typically a single-element list like ["US"].

    Returns: [{"country_code": "US", "count": 52340}, ...]
    """
    _load_resources()

    counts = {}
    for meta in _movie_metadata:
        for code in meta.get("origin_country", []):
            if code:
                counts[code] = counts.get(code, 0) + 1

    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
    return [{"country_code": code, "count": cnt} for code, cnt in sorted_counts]
