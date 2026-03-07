"""
app.py — Movie Search Engine (Flask Backend)
──────────────────────────────────────────────────────────────
Provides:
  GET  /                  → Main search UI
  POST /api/search        → Search movies via ES or BERT
  GET  /api/countries     → Country aggregation for world map
  GET  /api/movie/<id>    → Single movie details (optional)

Usage:
  python app.py
  → Visit http://localhost:5000
"""

import time
from flask import Flask, render_template, request, jsonify

import config

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)


# ─────────────────────────────────────────────────────────
# Lazy imports: only load what is actually available.
# This lets you develop the frontend even if BERT/FAISS or
# Elasticsearch aren't set up on your machine yet.
# ─────────────────────────────────────────────────────────

def _get_es_module():
    """Try to import es_search; return None if ES is unavailable."""
    try:
        import es_search
        # Quick connectivity check
        client = es_search.get_es_client()
        client.info()
        return es_search
    except Exception as e:
        print(f"[WARN] Elasticsearch unavailable: {e}")
        return None


def _get_bert_module():
    """Try to import bert_search; return None if FAISS/model files are missing."""
    try:
        import bert_search
        return bert_search
    except Exception as e:
        print(f"[WARN] BERT/FAISS unavailable: {e}")
        return None


# ─────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main search page."""
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    """
    Search movies.

    Request JSON:
        {
            "query": "space adventure",
            "index_type": "elasticsearch" | "bert",
            "top_k": 10,
            "country": "US"          // optional filter
        }

    Response JSON:
        {
            "query": "...",
            "index_type": "...",
            "time_ms": 123.4,
            "results": [ ... ]
        }
    """
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    index_type = data.get("index_type", "elasticsearch")
    top_k = min(int(data.get("top_k", 10)), 100)
    country = data.get("country", None)

    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    start = time.time()

    if index_type == "bert":
        module = _get_bert_module()
        if module is None:
            return jsonify({"error": "BERT/FAISS index is not available. "
                            "Make sure movie_faiss.index and movie_metadata.pkl exist in APP/models/."}), 503
        results = module.search(query, top_k=top_k, country_filter=country)
    else:
        module = _get_es_module()
        if module is None:
            return jsonify({"error": "Elasticsearch is not running or index not found."}), 503
        results = module.search(query, top_k=top_k, country_filter=country)

    elapsed_ms = round((time.time() - start) * 1000, 2)

    return jsonify({
        "query": query,
        "index_type": index_type,
        "time_ms": elapsed_ms,
        "result_count": len(results),
        "results": results,
    })


@app.route("/api/countries", methods=["GET"])
def api_countries():
    """
    Return movie counts per country for the world map visualization.

    Prefers ES (has origin_country keyword field).
    Falls back to BERT metadata (also has origin_country).

    Response JSON:
        {
            "countries": [
                {"country_code": "US", "count": 52340},
                ...
            ]
        }
    """
    # Try ES first — aggregation is fast
    es = _get_es_module()
    if es:
        try:
            countries = es.get_country_counts()
            return jsonify({"countries": countries, "source": "elasticsearch"})
        except Exception as e:
            print(f"[WARN] ES country counts failed: {e}")

    # Fallback to BERT metadata
    bert = _get_bert_module()
    if bert:
        try:
            countries = bert.get_country_counts()
            return jsonify({"countries": countries, "source": "bert_metadata"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Neither BERT metadata nor Elasticsearch is available."}), 503


@app.route("/api/movie/<movie_id>", methods=["GET"])
def api_movie_detail(movie_id):
    """
    Return full details for a single movie.
    Tries Elasticsearch first; falls back to BERT metadata.
    """
    es = _get_es_module()
    if es:
        try:
            client = es.get_es_client()
            resp = client.get(index=config.ES_INDEX_NAME, id=movie_id)
            return jsonify(resp["_source"])
        except Exception:
            pass

    # Fallback: search BERT metadata list by movie id
    bert = _get_bert_module()
    if bert:
        bert._load_resources()
        target_id = int(movie_id)
        for meta in bert._movie_metadata:
            if meta.get("id") == target_id:
                return jsonify(meta)

    return jsonify({"error": "Movie not found."}), 404


# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  TMDB Movie Search Engine")
    print(f"  http://localhost:{config.FLASK_PORT}")
    print("=" * 50)
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
