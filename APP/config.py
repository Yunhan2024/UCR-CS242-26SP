"""
Configuration for the Movie Search Engine.
Aligned with:
  - build_es_index.py  → ES analyzer: en_tmdb_english_stem
  - CS242_BERT_Indexing.ipynb → model: all-MiniLM-L6-v2, FAISS IndexFlatL2, 384-dim
"""

import os

# ── Paths ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ── Elasticsearch ──────────────────────────────────────
# The ES instance runs on the school server, not locally.
# Update this to your assigned server, e.g. "http://class-0XX.cs.ucr.edu:9200"
ES_HOST = "http://localhost:9200"
ES_INDEX_NAME = "tmdb_movies_v2"

# ── BERT / FAISS ───────────────────────────────────────
# Model and index file names from CS242_BERT_Indexing.ipynb
BERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Files produced by the notebook, placed in APP/models/
FAISS_INDEX_PATH = os.path.join(MODELS_DIR, "movie_faiss.index")

# movie_metadata is a LIST where index i = FAISS vector i
# Each entry: {"id", "imdb_id", "title", "overview", "genres", "release_date",
#              "vote_average", "countries", "country_codes", "origin_country", "reviews"}
MOVIE_METADATA_PATH = os.path.join(MODELS_DIR, "movie_metadata.pkl")

# ── Flask ──────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5432
# Debug mode disabled — the reloader conflicts with FAISS/PyTorch on macOS,
# causing "leaked semaphore" crashes. Set to True only for frontend-only dev.
FLASK_DEBUG = False