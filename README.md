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
| Total Size | 1.09 GB raw JSON |

Each movie record includes: title, overview, tagline, release date, runtime, genres, cast (top 20), crew (key roles), user reviews (up to 10), ratings, popularity, budget, revenue, origin country, production countries, and more.

## Project Structure

```
UCR-CS242-26SP/
├── tmdb_crawler/                   # Part A1: Scrapy crawler
│   └── tmdb_crawler/
│       ├── items.py                # MovieItem data model
│       ├── settings.py             # API keys, rate limits, pipelines
│       ├── pipelines.py            # Dedup filter, JSON storage, stats
│       └── spiders/
│           ├── discover_spider.py  # Phase 1: Collect movie IDs
│           └── details_spider.py   # Phase 2: Fetch full details
├── a2_index/                       # Part A2: Elasticsearch indexing
│   ├── build_es_index.py           # Core indexing pipeline
│   ├── benchmark_runtime.py        # Runtime benchmark utility
│   ├── requirements-index.txt
│   └── README_A2.md
├── bert/                           # Part B1: BERT dense indexing
│   ├── CS242_BERT_Indexing.ipynb   # Colab notebook for building FAISS index
│   ├── README_BERT.md              # Detailed B1 docs
├── APP/                            # Part B2: Web application
│   ├── app.py                      # Flask web server
│   ├── config.py                   # Central configuration
│   ├── es_search.py                # Elasticsearch query module
│   ├── bert_search.py              # BERT + FAISS query module
│   ├── build_es_index.py           # ES indexer (with origin_country field)
│   ├── requirements.txt
│   ├── README_B2.md                # Detailed setup & architecture docs
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
├── data/
│   ├── movie_ids.jsonl             # Discovered movie IDs
│   └── movies/                     # Individual movie JSON files (221k+)
└── docker-compose.yml              # (optional) Elasticsearch via Docker
```

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

Open `bert/CS242_BERT_Indexing.ipynb` in Google Colab with GPU runtime, upload and unzip the crawled data, run all cells (~30–40 min on T4 GPU).

---

## Part B2: Web Application

See `APP/README.md` for detailed architecture, file breakdown, setup instructions, and Elasticsearch installation guide.

### Quick start

```bash
# 1. Start Elasticsearch (Docker recommended)
docker run -d --name elasticsearch -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0

# 2. Build ES index (one-time), place BERT files in APP/models/
# 3. Run the web app
pip install -r APP/requirements.txt
cd APP && python app.py
# Visit http://localhost:5000
```

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
