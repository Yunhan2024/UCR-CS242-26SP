# UCR 2026 Spring CS242 - TMDB Search Engine

A search engine for movie data using Elasticsearch and BERT, built for CS242 course project.

## Project Overview

This project builds a search engine using data crawled from TMDB (The Movie Database):
- **Part A1**: Scrapy crawler to collect 500+ MB of movie data
- **Part A2**: Elasticsearch index with configurable analyzers
- **Part B1**: BERT embeddings with FAISS index (dense retrieval)
- **Part B2**: Web application with dual-index search and world map visualization

## Data Collected

| Metric | Value |
|--------|-------|
| Movies | 221,645 |
| Total Size | 1.09 GB |

Each movie record includes: title, overview, tagline, release date, runtime, genres, cast (top 20), crew (key roles), user reviews (up to 10), ratings, popularity, budget, revenue, origin country, production countries, and more.

## Project Structure

```
UCR-CS242-26SP/
├── .claude/                        # Claude Code config
├── APP/                            # Part B2: Web application
│   ├── app.py                      # Flask web server
│   ├── config.py                   # Central configuration
│   ├── es_search.py                # Elasticsearch query module
│   ├── bert_search.py              # BERT + FAISS query module
│   ├── build_es_index.py           # ES indexer (with origin_country field)
│   ├── requirements.txt
│   ├── README.md                   # Detailed setup & troubleshooting
│   ├── .gitignore
│   ├── models/                     # BERT index files (not in git)
│   │   ├── movie_faiss.index
│   │   └── movie_metadata.pkl
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js              # Search & comparison logic
│           └── map.js              # World map (Leaflet.js)
├── a2_index/                       # Part A2: Elasticsearch indexing
│   ├── build_es_index.py           # Core indexing pipeline
│   ├── benchmark_runtime.py        # Runtime benchmark utility
│   ├── requirements-index.txt
│   └── README_A2.md
├── bert/                           # Part B1: BERT dense indexing
│   ├── CS242_BERT_Indexing.ipynb   # Colab notebook for building FAISS index
│   ├── README_BERT.md              # BERT indexing documentation
│   └── index_time_comparison.csv   # ES vs BERT indexing time comparison
├── data/
│   └── samples/                    # Sample data files
├── tmdb_crawler/                   # Part A1: Scrapy crawler
│   └── tmdb_crawler/
│       ├── items.py                # MovieItem data model
│       ├── settings.py             # API keys, rate limits, pipelines
│       ├── pipelines.py            # Dedup filter, JSON storage, stats
│       └── spiders/
│           ├── discover_spider.py  # Phase 1: Collect movie IDs
│           └── details_spider.py   # Phase 2: Fetch full details
├── .gitignore
├── README.md                       # This file
├── crawler.bat                     # Windows crawler script
├── crawler.sh                      # Unix crawler script
├── indexbuilder.sh                 # ES index builder script (Part A2)
└── start_app.sh                    # One-click web app launcher
```

---

## Quick Start

To launch the full search engine from the project root:

```bash
chmod +x start_app.sh
./start_app.sh
```

The script automatically checks all prerequisites (Python, crawled data in `data/movies/`, BERT files in `APP/models/`), installs dependencies, starts Elasticsearch via Docker if not already running, builds the ES index if it doesn't exist yet, and launches the Flask web app. Visit `http://localhost:5000` once the server starts.

For manual setup or troubleshooting, see `APP/README.md`.

---

## Part A1: Crawler

### Architecture

The crawler uses a two-phase design:

- **Phase 1 (Discover Spider)**: Queries the TMDB discover API with combinations of genre (19 genres), year (1970–2026), language (10 languages), and vote count ranges. Each combination stays under TMDB's 500-page limit. Outputs `movie_ids.jsonl`.
- **Phase 2 (Details Spider)**: Reads the ID list, then for each movie chains three API calls — movie details → credits → reviews — merging them into a single `MovieItem`. Saves one JSON file per movie.

### Features

- **Multi-key API rotation**: Supports multiple TMDB API keys via environment variables (`TMDB_API_KEY`, `TMDB_API_KEY_2`, `TMDB_API_KEY_3`). Keys rotate per request across both spiders for higher aggregate throughput.
- **High concurrency**: 32 concurrent requests with auto-throttle (adaptive delay from 0.1s to 2.0s based on server response time)
- **Callback chaining**: Details spider chains movie → credits → reviews requests, passing accumulated data through `response.meta` before yielding the final item
- **Duplicate handling**: In-memory deduplication during discovery + `DuplicateFilterPipeline` during details fetching
- **Resumable crawling**: Details spider checks if a movie's JSON file already exists on disk and skips it, so crawling can be safely interrupted and resumed
- **Auto-retry**: Up to 10 retries on 5xx and 429 (rate limit) errors

### Usage

```bash
# Set API keys (supports up to 3 for rotation)
export TMDB_API_KEY="your-first-key"
export TMDB_API_KEY_2="your-second-key"       # optional
export TMDB_API_KEY_3="your-third-key"         # optional

cd tmdb_crawler

# Phase 1: Discover movie IDs
scrapy crawl discover

# Phase 2: Fetch full details (3 chained API calls per movie)
scrapy crawl details -s LOG_FILE=../logs/crawler.log
```

Get free API keys at https://www.themoviedb.org/settings/api

---

## Part A2: Elasticsearch Index

Builds a sparse (BM25) index using PyElasticsearch with configurable analyzers.

### Key design choices

- **Analyzer**: `english_stem` (lowercase + ASCII folding + stop words + Porter stemming) for maximum recall
- **Field decomposition**: Separate text fields for title, overview, cast, crew, reviews; keyword fields for genres, origin_country; numeric fields for ratings, year
- **Combined field**: `all_text` merges all text for fallback matching
- **Parallel bulk ingestion**: 6 threads, 800 chunk size, reaching ~5,000 docs/sec throughput

The A2 indexing implementation is in `a2_index/`.

```bash
pip install -r a2_index/requirements-index.txt
chmod +x indexbuilder.sh

# Assignment-style executable entry
./indexbuilder.sh /path/to/data.zip english_stem

# Dry-run (parse/transform only)
python a2_index/build_es_index.py \
  --source /path/to/data.zip \
  --source-subpath data/movies \
  --analyzer-option english_stem \
  --dry-run

# Build index
python a2_index/build_es_index.py \
  --source /path/to/data.zip \
  --source-subpath data/movies \
  --analyzer-option english_stem \
  --es-url http://localhost:9200 \
  --index-name tmdb_movies_v1 \
  --recreate-index
```

For detailed field design rationale, see `a2_index/README_A2.md`.

> **Note for Part B2**: The web app uses a patched version of the indexer (`APP/build_es_index.py`) that adds `origin_country` as a keyword field for the world map feature. See `APP/README.md` for setup instructions.

---

## Part B1: BERT Dense Index

### What it does

Converts each movie's text into a 384-dimensional embedding vector using BERT, then stores all vectors in a FAISS index for semantic similarity search.

### Why

Elasticsearch matches exact words. BERT understands meaning. A query like "funny space adventure" would miss a movie described as "hilarious intergalactic journey" in ES, but BERT would match it because the embeddings capture semantic similarity.

### How it works

1. **Text preparation**: For each movie, combine title (repeated 3x for emphasis), overview, tagline, genres, cast, and director into one passage
2. **BERT encoding**: `sentence-transformers/all-MiniLM-L6-v2` produces a 384-dim vector via mean pooling
3. **FAISS indexing**: Vectors stored in `IndexFlatL2` (brute-force L2 distance, lower = more similar)
4. **Metadata**: A parallel list maps each FAISS vector position to movie metadata (title, overview, genres, origin_country, etc.)

### Output files

| File | Description |
|---|---|
| `movie_faiss.index` | FAISS vector index (~320 MB) |
| `movie_metadata.pkl` | Metadata list aligned with FAISS positions (~150 MB) |

Place both in `APP/models/`.

### Reproduce (if needed)

Open `bert/CS242_BERT_Indexing.ipynb` in Google Colab with GPU runtime, upload and unzip the crawled data, run all cells (~30–40 min on T4 GPU). For detailed documentation, see `bert/README_BERT.md`. For indexing time comparison between ES and BERT, see `bert/index_time_comparison.csv`.

---

## Part B2: Web Application

### What it does

A Flask web app that provides a unified search interface for both the Elasticsearch (sparse) and BERT + FAISS (dense) indexes, plus a world map visualization of movie origins by country.

### Why

Parts A and B1 create the indexes, but they have no user interface. The web app lets users input a query, choose an index, and see ranked results. The Compare tab runs the same query on both indexes side by side — this directly supports the Part B report requirement of comparing ranking quality between sparse and dense retrieval. The world map uses the `origin_country` field to visualize global movie production patterns and lets users explore movies by clicking a country.

### Architecture

```
Browser → Flask (app.py) → es_search.py  → Elasticsearch (port 9200)
                         → bert_search.py → FAISS index + movie_metadata.pkl
```

ES search uses `multi_match` across title (3x boost), overview (2x), cast_names (1.5x), crew_names, and all_text with fuzzy matching. BERT search encodes the query into a 384-dim vector, searches the FAISS index by L2 distance, and converts distances to similarity scores via `1/(1+distance)`. Both return results in an identical JSON format so the frontend renders them without branching.

### Features

- **Dual-index search**: Toggle between Elasticsearch (keyword matching) and BERT + FAISS (semantic matching)
- **Side-by-side comparison**: Run the same query on both indexes to compare ranking quality
- **World map**: Leaflet.js choropleth colored by origin country; click a country to filter results
- **Search timing**: Displays query execution time in milliseconds for both indexes
- **External links**: Each result links to IMDb and TMDB pages
- **Graceful degradation**: If ES or BERT is unavailable, the other still works

For detailed architecture diagrams, request flow, file breakdown, and troubleshooting, see `APP/README.md`.

---

## Data Schema

Each movie JSON file contains the following fields (produced by the details spider via three chained API calls):

```json
{
  "id": 550,
  "imdb_id": "tt0137523",
  "title": "Fight Club",
  "original_title": "Fight Club",
  "original_language": "en",
  "overview": "A ticking-time-bomb insomniac and a slippery soap salesman...",
  "tagline": "Mischief. Mayhem. Soap.",
  "release_date": "1999-10-15",
  "status": "Released",
  "vote_average": 8.433,
  "vote_count": 28456,
  "popularity": 73.52,
  "runtime": 139,
  "budget": 63000000,
  "revenue": 100853753,
  "adult": false,
  "genres": [
    {"id": 18, "name": "Drama"}
  ],
  "cast": [
    {"id": 819, "name": "Edward Norton", "character": "The Narrator", "order": 0},
    {"id": 287, "name": "Brad Pitt", "character": "Tyler Durden", "order": 1}
  ],
  "crew": [
    {"id": 7467, "name": "David Fincher", "job": "Director", "department": "Directing"}
  ],
  "reviews": [
    {
      "id": "5b12...",
      "author": "tmdb_user",
      "author_username": "tmdb_user",
      "content": "Great film...",
      "rating": 9.0,
      "created_at": "2018-06-02T..."
    }
  ],
  "review_count": 1,
  "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
  "backdrop_path": "/hZkgoQYus5dXo3H8T7Uef6DNknx.jpg",
  "production_countries": [
    {"iso_3166_1": "US", "name": "United States of America"}
  ],
  "origin_country": ["US"],
  "homepage": "http://www.foxmovies.com/movies/fight-club",
  "crawled_at": "2026-02-10T15:30:00.000000Z"
}
```

## License

Educational use only. Movie data from TMDB - https://www.themoviedb.org/