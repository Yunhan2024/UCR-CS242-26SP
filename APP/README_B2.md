# APP — Web Application (Part B2)

## What This Does

A Flask web app that provides a unified search interface for both the Elasticsearch (sparse) and BERT + FAISS (dense) indexes, plus a world map visualization of movie origins.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          BROWSER                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  index.html                                              │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────────┐  │   │
│  │  │ Search Box │  │ ES ○ BERT ○ │  │ Top-K: [10 ▼]    │  │   │
│  │  └────────────┘  └─────────────┘  └──────────────────┘  │   │
│  │                                                          │   │
│  │  [Search Results]  [World Map]  [Compare Indexes]        │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                    │                │                    │
│    app.js              map.js           app.js                  │
│    POST /api/search    GET /api/countries   POST /api/search x2 │
└───────┬────────────────────┬────────────────┬───────────────────┘
        │                    │                │
        ▼                    ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Flask (app.py)                                │
│                                                                 │
│  GET  /              → Serve index.html                         │
│  POST /api/search    → Route to ES or BERT based on index_type  │
│  GET  /api/countries → Aggregate origin_country for world map   │
│  GET  /api/movie/<id>→ Return full movie details                │
│  POST /api/reload    → Reset module cache (reconnect ES/BERT)   │
│  GET  /api/status    → Diagnostic: show loaded modules & fields │
└───────┬─────────────────────────────────────┬───────────────────┘
        │                                     │
        ▼                                     ▼
┌───────────────────────┐     ┌───────────────────────────────────┐
│   es_search.py        │     │   bert_search.py                  │
│                       │     │                                   │
│ multi_match query:    │     │ 1. Tokenize query (BERT tokenizer)│
│  title        ×3 boost│     │ 2. Encode → 384-dim vector        │
│  overview     ×2 boost│     │    (mean pooling over last hidden) │
│  cast_names   ×1.5    │     │ 3. FAISS IndexFlatL2.search()     │
│  crew_names   ×1      │     │    (L2 distance, lower = better)  │
│  all_text     ×1      │     │ 4. Map vector indices → metadata  │
│                       │     │ 5. Convert dist → similarity:     │
│ Fuzziness: AUTO       │     │    score = 1 / (1 + distance)     │
│ Country: origin_country│    │ Country: origin_country in meta   │
│ (keyword filter)      │     │ (post-search filter)              │
└───────┬───────────────┘     └──────────────┬────────────────────┘
        │                                    │
        ▼                                    ▼
┌───────────────────────┐     ┌───────────────────────────────────┐
│   Elasticsearch 8.x   │     │   FAISS Index (in memory)         │
│   (Docker, port 9200) │     │   movie_faiss.index  (220k vecs)  │
│                       │     │   movie_metadata.pkl (220k entries)│
│   Index: tmdb_movies_v2│    │                                   │
│   Analyzer: english_stem│   │   Model: all-MiniLM-L6-v2 (384d) │
│   220k+ documents     │     │   Distance: L2 (Euclidean)        │
└───────────────────────┘     └───────────────────────────────────┘
```

### Request flow (example: BERT search for "funny space adventure")

1. User types query, selects "BERT + FAISS", clicks Search
2. `app.js` sends `POST /api/search` with `{"query": "funny space adventure", "index_type": "bert", "top_k": 10}`
3. `app.py` routes to `bert_search.search()`
4. `bert_search` tokenizes the query, runs it through the BERT model, mean-pools the output into a 384-dim vector
5. FAISS searches all 220k vectors by L2 distance, returns the 20 nearest indices and distances
6. Each index maps to a movie in `movie_metadata` — title, overview, genres, origin_country, etc.
7. Distances are converted to similarity scores, results are deduplicated by movie ID
8. JSON response returns to the browser with results and timing (`time_ms`)
9. `app.js` renders each result as a card with title, year, genre badges, rating, and IMDb/TMDB links

### Frontend tabs

- **Search Results**: Shows ranked movie cards with title, year, genre badges (blue), country badges (orange), rating badge (green), overview snippet, and IMDb/TMDB links.
- **World Map**: Leaflet.js choropleth on dark CartoDB tiles. Countries colored by movie count (darker = more movies). Hover shows tooltip with count. Click a country to filter search results to movies from that country.
- **Compare Indexes**: Runs the same query on both ES and BERT in parallel, displays results side by side with individual timing. Useful for the Part B report's ranking quality comparison.

---

## File Breakdown

| File | Role |
|---|---|
| `config.py` | All settings: ES host, index name, BERT model path, Flask port |
| `app.py` | Flask server — 4 routes: `/`, `/api/search`, `/api/countries`, `/api/movie/<id>`. Lazy-loads ES and BERT modules so the app doesn't crash if one is unavailable. |
| `es_search.py` | Builds a `multi_match` query across title (3x boost), overview (2x), cast (1.5x), crew, and all_text. Uses `origin_country` keyword field for country filtering and aggregation. |
| `bert_search.py` | Loads BERT model + FAISS on first query (~15s). Encodes query → searches FAISS (L2 distance) → maps results back via `movie_metadata.pkl`. Converts L2 distance to similarity: `1/(1+distance)`. |
| `build_es_index.py` | Patched version of `a2_index/build_es_index.py` that adds `origin_country` as a keyword field. Run once before starting the web app. |
| `templates/index.html` | Single-page HTML: search bar, radio buttons (ES / BERT), top-k selector, 3 tabs (Results, World Map, Compare). |
| `static/js/app.js` | Search form → fetch `/api/search` → render result cards. Compare tab runs both indexes in parallel via `Promise.allSettled()`. |
| `static/js/map.js` | Leaflet.js world map with dark CartoDB tiles. Fetches `/api/countries` → colors countries by movie count (choropleth). Click a country → filters search results. |
| `static/css/style.css` | Dark theme. Genre badges (blue), country badges (orange), rating badges (green). |

---

## Setup

### Prerequisites

Before anything else, make sure the following are in place:

> **⚠️ IMPORTANT**: The crawled movie data must be in `data/movies/` relative to the project root. The ES index builder reads from this folder. If the folder is missing or empty, indexing will fail silently with 0 documents.

> **⚠️ IMPORTANT**: BERT index files (`movie_faiss.index` and `movie_metadata.pkl`) must be in `APP/models/`. These are generated by the notebook in `bert/` and are too large for git (~470 MB total). Get them from whoever ran the BERT indexing notebook.

### Step 1: Install Elasticsearch via Docker

Docker is the only recommended method. It requires no Java, no config file editing, and runs identically on every OS.

```bash
# Pull and start ES (single node, security disabled for local dev)
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0
```

Wait ~30 seconds, then verify:

```bash
curl http://localhost:9200
```

You should see JSON with `"tagline": "You Know, for Search"`. If you see "Connection refused", wait a bit longer — ES can take up to a minute on first start.

To manage later:

```bash
docker stop elasticsearch      # stop (data persists)
docker start elasticsearch     # restart
docker rm elasticsearch        # remove completely
```

> **Note**: If Docker is not installed, get it from https://www.docker.com/products/docker-desktop/

### Step 2: Build the ES Index (one-time)

> **⚠️ You must use `APP/build_es_index.py`** (not `a2_index/build_es_index.py`). The APP version includes the `origin_country` keyword field required for the world map. Using the wrong version will result in the map showing 0 country matches.

```bash
cd APP

python build_es_index.py \
  --source ../data/movies \
  --analyzer-option english_stem \
  --es-url http://localhost:9200 \
  --index-name tmdb_movies_v2 \
  --recreate-index \
  --threads 6 \
  --chunk-size 800 \
  --queue-size 12
```

This takes ~45 seconds for 221k movies. Verify:

```bash
curl "http://localhost:9200/tmdb_movies_v2/_count?pretty"
# Should show "count": ~220000
```

> **Note**: The `--source` path must point to the folder containing individual movie JSON files. If your data is in a zip, extract it to `data/movies/` first.

### Step 3: Place BERT Files

Copy these two files (from the BERT indexing notebook output) into `APP/models/`:

```
APP/models/movie_faiss.index    (~320 MB)
APP/models/movie_metadata.pkl   (~150 MB)
```

> **Note**: These files are in `.gitignore`. Every team member who runs the app needs to obtain them separately.

### Step 4: Install Dependencies and Run

```bash
pip install -r requirements.txt

python app.py
# Visit http://localhost:5000
```

Or from the project root, use the one-click script:

```bash
./start_app.sh
```

BERT model and FAISS index preload at startup (~15 seconds). After that, both ES and BERT searches respond in under 1 second.

If Elasticsearch is not running, BERT search still works (and vice versa). The unavailable mode shows a friendly error message.

### Troubleshooting

| Symptom | Fix |
|---|---|
| BERT segfault on macOS | Pin `faiss-cpu==1.7.4`, ensure `numpy<2`. The `requirements.txt` already handles this. |
| `PyTorch >= 2.4 required` | Downgrade transformers: `pip install "transformers<4.46"` |
| ES "Connection refused" | Elasticsearch isn't running. Start Docker container first. |
| ES "index not found" | Build the index first (Step 2), then `curl -X POST http://localhost:5000/api/reload` |
| BERT "Failed to fetch" in browser | BERT crashed during search. Check terminal for errors. Restart `python app.py`. |
| Map shows 0 countries matched | ES index was built without `origin_country`. Rebuild using `APP/build_es_index.py` (not `a2_index/`). |
| `--source` path error | Make sure `data/movies/` exists and contains JSON files. Extract from zip if needed. |

---

## What to Capture for the Report

1. **Screenshots** — Search results page, world map, comparison view
2. **Runtime comparison** — The search meta bar shows query time in ms for both indexes
3. **Ranking quality** — Use the Compare tab with these queries:
   - "funny space adventure" (semantic understanding)
   - "Brad Pitt" (exact name matching)
   - "romantic drama set in Paris" (complex intent)
   - "scary horror movie" (synonym handling)
4. **World map** — Geographic distribution of movie production

---

## Configuration

Edit `config.py` to change:

```python
ES_HOST = "http://localhost:9200"   # Elasticsearch URL
ES_INDEX_NAME = "tmdb_movies_v2"    # Index name (must match what you built)
FLASK_PORT = 5000                   # Web app port
```

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Web framework | Flask | Lightweight, easy Python integration |
| Frontend | Single HTML + vanilla JS | No build step, easy to demo |
| Map library | Leaflet.js (CDN) | Free, lightweight, dark tile support |
| Country field | `origin_country` | Typically 1 country per movie (cleaner for map) |
| Lazy loading | Modules loaded on first request | App starts instantly; missing components fail gracefully |
| Result format | Unified JSON | ES and BERT return identical field names so frontend renders both without branching |