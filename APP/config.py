"""
Configuration for the Movie Search Engine.
Update these values to match your local environment.
"""

import os

# ── Paths ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "movies")

# ── Elasticsearch ──────────────────────────────────────
ES_HOST = "http://localhost:9200"
ES_INDEX_NAME = "tmdb_movies"
ES_USER = "elastic"         # change if needed
ES_PASSWORD = ""             # change if needed

# ── BERT / FAISS ───────────────────────────────────────
# Model used for generating embeddings.
# Option A (recommended for speed): "sentence-transformers/all-MiniLM-L6-v2" → 384-dim
# Option B (standard BERT):         "bert-base-uncased" → 768-dim
BERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384          # must match the model above

FAISS_INDEX_PATH = os.path.join(MODELS_DIR, "faiss_index.bin")
PASSAGE_MAP_PATH = os.path.join(MODELS_DIR, "passage_map.pkl")
MOVIE_METADATA_PATH = os.path.join(MODELS_DIR, "movie_metadata.pkl")

# ── Flask ──────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
