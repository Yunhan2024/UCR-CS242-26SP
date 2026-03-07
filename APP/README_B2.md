# APP — Web Application (Part B2)

## What This Does

A Flask web app that provides a unified search interface for both the Elasticsearch (sparse) and BERT + FAISS (dense) indexes, plus a world map visualization of movie origins.

---

## Architecture

```
Browser → Flask (app.py) → es_search.py  → Elasticsearch (port 9200)
                         → bert_search.py → FAISS index + movie_metadata.pkl
```

When a user searches:

1. Browser sends a POST to `/api/search` with `{query, index_type, top_k}`
2. `app.py` routes to either `es_search.py` or `bert_search.py`
3. The module queries its index and returns ranked results
4. `app.py` wraps results in JSON with timing info
5. JavaScript renders result cards in the browser

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

### Step 1: Install Elasticsearch

You need Elasticsearch running before building the index. Choose one option:

#### Docker (Recommended)

```bash
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

You should see JSON with `"tagline": "You Know, for Search"`.

To manage later:

```bash
docker stop elasticsearch      # stop (data persists)
docker start elasticsearch     # restart
docker rm elasticsearch        # remove completely
```

#### Homebrew (macOS alternative)

```bash
brew tap elastic/tap
brew install elastic/tap/elasticsearch-full
elasticsearch                  # runs in foreground, keep terminal open
```

If ES 8.x blocks connections with security errors, edit `config/elasticsearch.yml`:

```yaml
xpack.security.enabled: false
```

Then restart.

### Step 2: Build the ES Index (one-time)

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
```

The `--source` path should point to your `data/movies/` folder containing the crawled JSON files. Adjust the path based on your project layout.

### Step 3: Place BERT Files

Copy these two files (from the BERT indexing notebook output) into `APP/models/`:

```
APP/models/movie_faiss.index    (~320 MB)
APP/models/movie_metadata.pkl   (~150 MB)
```

### Step 4: Install Dependencies and Run

```bash
pip install -r requirements.txt

python app.py
# Visit http://localhost:5000
```

BERT model and FAISS index preload at startup (~15 seconds). After that, both ES and BERT searches respond in under 1 second.

If Elasticsearch is not running, BERT search still works (and vice versa). The unavailable mode shows a friendly error message.

### Troubleshooting

| Symptom | Fix |
|---|---|
| BERT segfault on macOS | Pin `faiss-cpu==1.7.4`, ensure `numpy<2`. The `requirements.txt` already handles this. |
| `PyTorch >= 2.4 required` | Downgrade transformers: `pip install "transformers<4.46"` |
| ES "index not found" | Build the index first (Step 2), then `curl -X POST http://localhost:5000/api/reload` |
| BERT "Failed to fetch" in browser | BERT crashed during search. Check terminal for errors. Restart `python app.py`. |
| Map shows 0 countries matched | ES index was built without `origin_country`. Rebuild using `APP/build_es_index.py` with `--recreate-index`. |

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