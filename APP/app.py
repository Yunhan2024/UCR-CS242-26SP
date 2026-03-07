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
# Module caching: load once, remember failures.
# Without caching, a broken BERT import retries every request.
# ─────────────────────────────────────────────────────────

_es_module = None
_es_checked = False
_bert_module = None
_bert_checked = False


def _get_es_module():
    """Return es_search module or None. Caches result."""
    global _es_module, _es_checked
    if _es_checked:
        return _es_module
    _es_checked = True
    try:
        import es_search
        client = es_search.get_es_client()
        client.info()
        _es_module = es_search
        print("[OK] Elasticsearch connected.")
    except Exception as e:
        print(f"[WARN] Elasticsearch unavailable: {e}")
        _es_module = None
    return _es_module


def _get_bert_module():
    """Return bert_search module or None. Caches result."""
    global _bert_module, _bert_checked
    if _bert_checked:
        return _bert_module
    _bert_checked = True
    try:
        import bert_search
        _bert_module = bert_search
        print("[OK] BERT module imported.")
    except Exception as e:
        print(f"[WARN] BERT/FAISS unavailable: {e}")
        _bert_module = None
    return _bert_module


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
    Search movies. Returns JSON always (never an HTML error page).
    """
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    index_type = data.get("index_type", "elasticsearch")
    top_k = min(int(data.get("top_k", 10)), 100)
    country = data.get("country", None)

    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    start = time.time()

    try:
        if index_type == "bert":
            module = _get_bert_module()
            if module is None:
                return jsonify({"error": "BERT is not available. "
                                "Check that PyTorch >= 2.4 and numpy < 2 are installed, "
                                "and that movie_faiss.index + movie_metadata.pkl are in APP/models/."}), 503
            results = module.search(query, top_k=top_k, country_filter=country)
        else:
            module = _get_es_module()
            if module is None:
                return jsonify({"error": "Elasticsearch is not running or not reachable at "
                                f"{config.ES_HOST}. Start ES first, then restart this app."}), 503
            results = module.search(query, top_k=top_k, country_filter=country)
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

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
    Return movie counts per country for the world map.
    Tries ES first, falls back to BERT metadata.
    """
    # Try ES
    es = _get_es_module()
    if es:
        try:
            countries = es.get_country_counts()
            return jsonify({"countries": countries, "source": "elasticsearch"})
        except Exception as e:
            print(f"[WARN] ES country counts failed: {e}")

    # Try BERT metadata
    bert = _get_bert_module()
    if bert:
        try:
            countries = bert.get_country_counts()
            return jsonify({"countries": countries, "source": "bert_metadata"})
        except Exception as e:
            return jsonify({"error": f"BERT country counts failed: {str(e)}"}), 500

    return jsonify({"error": "Neither BERT nor Elasticsearch is available. "
                    "See APP/README.md for setup instructions."}), 503


@app.route("/api/movie/<movie_id>", methods=["GET"])
def api_movie_detail(movie_id):
    """Return full details for a single movie."""
    # Try ES
    es = _get_es_module()
    if es:
        try:
            client = es.get_es_client()
            resp = client.get(index=config.ES_INDEX_NAME, id=movie_id)
            return jsonify(resp["_source"])
        except Exception:
            pass

    # Try BERT metadata
    bert = _get_bert_module()
    if bert:
        try:
            bert._load_resources()
            target_id = int(movie_id)
            for meta in bert._movie_metadata:
                if meta.get("id") == target_id:
                    return jsonify(meta)
        except Exception:
            pass

    return jsonify({"error": "Movie not found."}), 404


# ─────────────────────────────────────────────────────────
# Reset cache (call if you start ES after the app is running)
# ─────────────────────────────────────────────────────────

@app.route("/api/reload", methods=["POST"])
def api_reload():
    """Reset module cache so ES/BERT are re-checked on next request."""
    global _es_module, _es_checked, _bert_module, _bert_checked
    _es_module = None
    _es_checked = False
    _bert_module = None
    _bert_checked = False
    return jsonify({"status": "Module cache cleared. Next request will re-check ES and BERT."})


@app.route("/api/status", methods=["GET"])
def api_status():
    """Diagnostic endpoint — shows what's loaded and sample country data."""
    status = {
        "es_available": _es_module is not None,
        "bert_available": _bert_module is not None,
        "es_index_name": config.ES_INDEX_NAME,
    }

    # Check if origin_country field exists in ES
    if _es_module:
        try:
            client = _es_module.get_es_client()
            mapping = client.indices.get_mapping(index=config.ES_INDEX_NAME)
            props = list(mapping.values())[0]["mappings"]["properties"]
            status["es_has_origin_country"] = "origin_country" in props
            status["es_fields"] = list(props.keys())
        except Exception as e:
            status["es_mapping_error"] = str(e)

    # Show sample country data
    if _es_module:
        try:
            countries = _es_module.get_country_counts()
            status["country_sample"] = countries[:10]
            status["country_total"] = len(countries)
        except Exception as e:
            status["country_error"] = str(e)

    return jsonify(status)


# ─────────────────────────────────────────────────────────
# Entry point — preload BERT at startup
# ─────────────────────────────────────────────────────────

def _preload():
    """Preload BERT model at startup so first search doesn't timeout."""
    print("[STARTUP] Preloading modules...")
    _get_es_module()
    bert = _get_bert_module()
    if bert:
        try:
            print("[STARTUP] Preloading BERT model + FAISS index...")
            bert._load_resources()
            print("[STARTUP] BERT ready.")
        except Exception as e:
            print(f"[STARTUP] BERT preload failed: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("  TMDB Movie Search Engine")
    print(f"  http://localhost:{config.FLASK_PORT}")
    print("=" * 50)

    # Preload before starting (only in main process, not reloader)
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not config.FLASK_DEBUG:
        _preload()

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )