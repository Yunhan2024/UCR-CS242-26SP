# UCR 2026 Spring CS242 - TMDB Search Engine

A search engine for movie data using PyLucene and BERT, built for CS242 course project.

## Project Overview

This project builds a search engine using data crawled from TMDB (The Movie Database):
- **Part A**: Scrapy crawler to collect 500+ MB of movie data, PyLucene index
- **Part B**: BERT embeddings with FAISS index
- **Web App**: Query interface supporting both index types

## Data Collected

| Metric | Value |
|--------|-------|
| Movies | 220,243 |
| Total Size | 652 MB |

Each movie record includes: title, overview, tagline, release date, runtime, genres, cast (top 20), crew (directors/writers/producers), user reviews (up to 10), ratings, popularity, budget, revenue, and more.

## Crawler Features

- **Two-phase architecture**: Phase 1 discovers movie IDs, Phase 2 fetches full details
- **Multi-strategy discovery**: Genre-based (19 genres), year-based (1970-2026), language-based (10 languages), vote count ranges — collects 220k+ unique IDs
- **Concurrent requests**: 16 parallel requests with auto-throttle for adaptive rate limiting
- **Duplicate handling**: In-memory deduplication during discovery + DuplicateFilterPipeline for details
- **Resumable crawling**: Skips already-downloaded files, safe to interrupt with Ctrl+C and resume later
- **Auto-retry**: Retries on 5xx and 429 errors (up to 3 times)

## Project Structure

```
cs242/
├── tmdb_crawler/
│   └── tmdb_crawler/
│       ├── items.py        # Data models
│       ├── settings.py     # API config, rate limits, pipelines
│       ├── pipelines.py    # Dedup filter, JSON storage, stats
│       └── spiders/
│           ├── discover_spider.py  # Phase 1: Collect movie IDs
│           └── details_spider.py   # Phase 2: Fetch full details
├── data/
│   ├── movie_ids.jsonl     # Discovered movie IDs
│   └── movies/             # Individual movie JSON files
└── requirements.txt
```

## Setup & Usage

### 1. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 2. Set TMDB API Key
```bash
export TMDB_API_KEY="your-api-key"          # Linux/Mac
$env:TMDB_API_KEY="your-api-key"            # Windows PowerShell
```
Get a free key at https://www.themoviedb.org/settings/api

### 3. Run Crawler
```bash
cd tmdb_crawler

# Phase 1: Discover movie IDs (writes to data/movie_ids.jsonl)
scrapy crawl discover

# Phase 2: Fetch full movie details (writes to data/movies/*.json)
scrapy crawl details -s LOG_FILE=../logs/crawler.log
```

## Part A2: Build Elasticsearch Index

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

For field design and indexing choices, see `a2_index/README_A2.md`.

## Data Schema

```json
{
  "id": 550,
  "title": "Fight Club",
  "overview": "A depressed man suffering from insomnia...",
  "release_date": "1999-10-15",
  "genres": [{"id": 18, "name": "Drama"}],
  "vote_average": 8.4,
  "runtime": 139,
  "budget": 63000000,
  "revenue": 100853753,
  "cast": [{"name": "Brad Pitt", "character": "Tyler Durden"}],
  "crew": [{"name": "David Fincher", "job": "Director"}],
  "reviews": [{"author": "user", "content": "Great film...", "rating": 9}],
  "review_count": 1
}
```

## License

Educational use only. Movie data from TMDB - https://www.themoviedb.org/
