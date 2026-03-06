"""
Configuration for the Movie Search Engine.
Aligned with:
  - build_es_index.py  → ES index: tmdb_movies_s3_v1, analyzer: en_tmdb_english_stem
  - CS242_BERT_Indexing.ipynb → model: all-MiniLM-L6-v2, FAISS IndexFlatL2, 384-dim
"""

import os

# ── Paths ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ── Elasticsearch ──────────────────────────────────────
# Index name from the latest indexing run (index_report_tmdb_s3_20260304.json)
ES_HOST = "http://localhost:9200"
ES_INDEX_NAME = "tmdb_movies_s3_v1"

# ── BERT / FAISS ───────────────────────────────────────
# Model and index file names from CS242_BERT_Indexing.ipynb
BERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# IMPORTANT: The notebook saves as "movie_faiss.index" (not faiss_index.bin)
FAISS_INDEX_PATH = os.path.join(MODELS_DIR, "movie_faiss.index")

# IMPORTANT: movie_metadata is a LIST, not a dict.
# Position i in the list corresponds to FAISS vector i.
# Each entry: {"id", "imdb_id", "title", "overview", "genres", "release_date",
#              "vote_average", "countries", "country_codes", "origin_country", "reviews"}
MOVIE_METADATA_PATH = os.path.join(MODELS_DIR, "movie_metadata.pkl")

# ── Flask ──────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
