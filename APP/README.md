# TMDB Movie Search Engine — CS242 Group 7

A search engine for 220,000+ movies from The Movie Database (TMDB).  
Supports **sparse search** (Elasticsearch) and **dense search** (BERT + FAISS), with an interactive world map visualization.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Make sure Elasticsearch 8.x is running

```bash
# Check if Elasticsearch is reachable
curl http://localhost:9200
```

### 3. Build the Elasticsearch index (Part A)

```bash
./indexbuilder.sh data/movies/ english_stem
```

### 4. Build the BERT + FAISS index (Part B)

```bash
./indexer.sh data/movies/ backend/models/
```

This will generate three files in `backend/models/`:
- `faiss_index.bin` — The FAISS vector index
- `passage_map.pkl` — Maps passage indices to movie IDs
- `movie_metadata.pkl` — Quick-lookup movie details

### 5. Run the web application

```bash
cd backend
python app.py
```

Visit **http://localhost:5000** in your browser.

---

## Project Structure

```
movie-search-engine/
├── crawler.sh                  # Part A — run the crawler
├── indexbuilder.sh             # Part A — build ES index
├── indexer.sh                  # Part B — build BERT/FAISS index
├── requirements.txt
├── data/
│   └── movies/                 # 220,000+ movie JSON files
├── backend/
│   ├── app.py                  # Flask web server
│   ├── config.py               # All configuration
│   ├── es_search.py            # Elasticsearch query module
│   ├── bert_search.py          # BERT + FAISS query module
│   ├── build_bert_index.py     # Index builder script
│   ├── models/                 # Generated index files
│   ├── templates/
│   │   └── index.html          # Main page
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js          # Search & results logic
│           └── map.js          # World map (Leaflet.js)
└── README.md
```

---

## Features

- **Dual-index search**: Toggle between Elasticsearch (BM25) and BERT + FAISS (cosine similarity)
- **Side-by-side comparison**: Compare results from both indexes for the same query
- **World map**: Choropleth visualization of movie production countries; click a country to filter results
- **Search timing**: Displays query execution time for performance comparison

---

## Configuration

Edit `backend/config.py` to change:
- Elasticsearch host, index name, and credentials
- BERT model name and embedding dimension
- File paths for FAISS index and metadata
- Flask host and port

---

## Team

| Member | Role |
|---|---|
| Yunhan Chang | Crawler + GitHub setup |
| Rui Liu | Elasticsearch indexing |
| Colin Kou | Testing + report |
| Zichuan Zhou | Testing + report |
