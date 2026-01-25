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
| Movies | 45,828 |
| Total Size | 425 MB |

Each movie includes:
- Title, overview, tagline
- Release date, runtime, genres
- Cast and crew (top 20 actors, directors/writers/producers)
- User reviews (up to 10 per movie)
- Ratings and popularity scores

## Project Structure

```
cs242/
├── tmdb_crawler/           # Scrapy crawler
│   └── tmdb_crawler/
│       ├── items.py        # Data models
│       ├── settings.py     # API config, rate limits
│       ├── pipelines.py    # JSON storage
│       └── spiders/
│           ├── discover_spider.py  # Phase 1: Collect IDs
│           └── details_spider.py   # Phase 2: Fetch details
├── data/
│   ├── movie_ids.jsonl     # Discovered movie IDs
│   └── movies/             # Full movie JSON files
└── requirements.txt
```

## Setup & Usage

### 1. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set TMDB API Key
Get a free API key from https://www.themoviedb.org/settings/api

### 3. Run Crawler
```bash
cd tmdb_crawler

# Phase 1: Discover movie IDs
scrapy crawl discover

# Phase 2: Fetch full details
scrapy crawl details -s JOBDIR=crawljob
```

### 4. Monitor Progress
```bash
# Count crawled movies
find ../data/movies -name "*.json" | wc -l

# Check total size
du -sh ../data/
```

## Data Schema

Sample movie JSON structure:
```json
{
  "id": 550,
  "title": "Fight Club",
  "overview": "A depressed man suffering from insomnia...",
  "release_date": "1999-10-15",
  "genres": [{"id": 18, "name": "Drama"}],
  "vote_average": 8.4,
  "cast": [{"name": "Brad Pitt", "character": "Tyler Durden"}],
  "crew": [{"name": "David Fincher", "job": "Director"}],
  "reviews": [{"author": "user", "content": "Great film..."}]
}
```

## License

Educational use only. Movie data from TMDB - https://www.themoviedb.org/
