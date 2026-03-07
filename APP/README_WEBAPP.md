# Part B2: Web Application & Integration

## What This Section Does

This section builds the **web application** that connects everything together: the Elasticsearch sparse index (Part A), the BERT dense index (Part B1), and an interactive frontend with a world map visualization (extra credit).

It provides:

- A search interface where users type a query and choose which index to use
- A results display showing movie title, genres, rating, country, and links
- A side-by-side comparison view for evaluating ES vs BERT ranking quality
- A world map colored by how many movies originate from each country

---

## Why We Need This

Parts A and B1 create the indexes, but they have no user interface — you would need to write Python code or curl commands to query them. The project requires a UI (at minimum a terminal interface, extra credit for a web app) that lets a user input a query, choose an index, and see ranked results.

Beyond the basic requirement, the web app serves an important purpose for the **report**: the Compare tab lets us run the same query on both indexes simultaneously and visually compare which one produces better rankings. This directly supports the Part B report requirement of comparing Lucene and BERT output quality.

The world map is an extra-credit feature that takes advantage of the `origin_country` field in our data. Since each movie has a country of origin, we can aggregate and visualize global movie production patterns — which countries produce the most movies, and let users explore movies by country.

---

## How It Works — Architecture Overview

```
User's Browser
    │
    │  HTTP requests
    ▼
┌─────────────────────────────────────┐
│         Flask Web Server            │
│         (app.py)                    │
│                                     │
│  GET /           → index.html       │
│  POST /api/search → search logic    │
│  GET /api/countries → country agg   │
│  GET /api/movie/<id> → movie detail │
└──────────┬──────────────┬───────────┘
           │              │
     ┌─────┴─────┐  ┌─────┴──────┐
     │ es_search  │  │ bert_search │
     │  .py       │  │  .py        │
     └─────┬─────┘  └─────┬──────┘
           │              │
           ▼              ▼
     Elasticsearch   FAISS Index
     (running on     (movie_faiss.index
      port 9200)     + movie_metadata.pkl)
```

When a user searches:

1. The browser sends a POST request to `/api/search` with `{query, index_type, top_k}`
2. `app.py` routes to either `es_search.py` or `bert_search.py`
3. The chosen module queries its index and returns ranked results
4. `app.py` wraps results in JSON with timing info and sends back
5. JavaScript renders the results as cards in the browser

---

## File-by-File Breakdown

### Backend (Python)

**`config.py`** — Central configuration. All file paths, index names, model names, and server settings live here. When deploying on a different machine, this is the only file you need to edit.

**`app.py`** — The Flask web server. It has four URL routes:

- `GET /` — Serves the HTML page
- `POST /api/search` — The main search endpoint. Accepts JSON with query text, index choice (ES or BERT), number of results (top_k), and optional country filter. Returns JSON with results and timing.
- `GET /api/countries` — Returns movie counts per origin country. Tries ES aggregation first (fast), falls back to iterating BERT metadata.
- `GET /api/movie/<id>` — Returns full details for one movie.

The "lazy import" pattern is important: `_get_es_module()` and `_get_bert_module()` catch errors gracefully. If Elasticsearch isn't running, the BERT search still works. If the FAISS files are missing, ES search still works. This makes development much easier.

**`es_search.py`** — Elasticsearch query module. The `search()` function builds a `multi_match` query that searches across multiple fields with different weights:

- `title` gets 3x boost (most important for relevance)
- `original_title` and `overview` get 2x
- `cast_names` gets 1.5x
- `all_text` (the combined field) is the fallback

It uses `fuzziness: AUTO` so minor typos still return results. The `get_country_counts()` function uses an ES `terms` aggregation on the `origin_country` keyword field — Elasticsearch computes this server-side very efficiently.

**`bert_search.py`** — BERT + FAISS query module. On first use, it loads the BERT model, FAISS index, and metadata into memory (this takes a few seconds). After that, each search is fast: encode the query (~20ms), search FAISS (~5ms), look up metadata (~instant). The L2 distances from FAISS are converted to similarity scores using `1 / (1 + distance)`.

### Frontend (HTML + CSS + JS)

**`templates/index.html`** — The single-page HTML structure. It has:

- A search bar with a text input and Search button
- Radio buttons to choose between Elasticsearch and BERT
- A top-k dropdown (5, 10, 20, 50)
- Three tabs: Search Results, World Map, Compare Indexes

**`static/css/style.css`** — Dark theme styling using CSS custom properties (variables). The color scheme uses `--accent: #4f8cff` (blue) for interactive elements, `--green` for ratings and timing, `--orange` for country badges. Cards have a subtle border that turns blue on hover.

**`static/js/app.js`** — Core search logic:

- `handleSearch()` — Reads the form inputs, calls `/api/search`, renders results
- `renderCard()` — Converts one result object into an HTML card with title, year, badges (genre in blue, country in orange, rating in green), overview snippet, and IMDb/TMDB links
- `handleCompare()` — Runs the same query on both indexes in parallel using `Promise.allSettled()`, then renders results side by side
- Tab switching — Toggles visibility of the three content sections

**`static/js/map.js`** — World map visualization:

- Initializes a Leaflet.js map with dark CartoDB tiles
- Fetches `/api/countries` to get movie counts per country
- Loads GeoJSON country boundaries from a public GitHub dataset
- Colors each country using a choropleth scale (darker blue = more movies)
- Adds tooltips showing country name and movie count on hover
- Click handler: clicking a country switches to the Search Results tab and filters results to that country

---

## How to Run

### Prerequisites

- Python 3.8+
- Elasticsearch 8.x running on `localhost:9200`
- `movie_faiss.index` and `movie_metadata.pkl` in `APP/models/`

### Setup

```bash
cd APP
pip install -r requirements.txt
```

### Start the server

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

### If Elasticsearch is on a different host

Edit `config.py`:

```python
ES_HOST = "http://class-0XX.cs.ucr.edu:9200"
ES_INDEX_NAME = "tmdb_movies_s3_v1"
```

---

## What to Capture for the Report

The web app provides everything needed for the Part B report:

1. **Screenshots of the running system** — Search results page, world map, comparison view
2. **Runtime comparison** — The search meta bar shows query time in milliseconds for both ES and BERT
3. **Ranking quality comparison** — Use the Compare tab with queries like:
   - "funny space adventure" (tests semantic understanding)
   - "Brad Pitt" (tests exact name matching)
   - "romantic drama set in Paris" (tests complex intent)
   - "scary horror movie" (tests synonym handling)
4. **World map** — Shows the geographic distribution of movie production

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Web framework | Flask | Lightweight, widely used in CS242, easy to integrate with Python |
| Frontend approach | Single HTML + vanilla JS | No build step needed, easy to demo, no framework dependency |
| Map library | Leaflet.js (CDN) | Free, lightweight, excellent documentation, dark tile support |
| Country field | `origin_country` | Limited to 1 country per movie (cleaner for map), already in both ES and BERT metadata |
| Lazy loading | Backend modules loaded on first request | App starts instantly; missing components fail gracefully |
| Result format | Unified JSON schema | ES and BERT return identical field names so the frontend renders both without branching |
