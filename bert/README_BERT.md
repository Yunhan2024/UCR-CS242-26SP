# Part B1: BERT Dense Indexing

## What This Section Does

This section creates a **dense search index** for our 220,000+ movie dataset using BERT embeddings and FAISS. While the Elasticsearch index from Part A uses traditional keyword matching (sparse retrieval), this BERT index understands the **meaning** behind words (dense retrieval).

The end result is two files:

- **`movie_faiss.index`** — A FAISS vector database containing one 384-dimensional embedding vector per movie. This is the searchable index.
- **`movie_metadata.pkl`** — A Python list where position `i` stores the metadata (title, overview, genres, origin_country, etc.) for the movie whose vector is at position `i` in the FAISS index.

---

## Why We Need This

Elasticsearch (sparse retrieval) works by matching exact words. If a user searches for "funny space adventure," it looks for documents containing those specific words. This has a fundamental limitation: it cannot match **synonyms or related concepts**. A movie described as "a hilarious intergalactic journey" would be a poor match, even though it means the same thing.

BERT (dense retrieval) solves this by converting text into numerical vectors that capture **semantic meaning**. Two pieces of text with similar meanings will produce vectors that are close together in the 384-dimensional space, even if they share no words. This is why the project requires both indexes — we can compare how keyword-based and meaning-based retrieval perform on the same queries.

---

## How It Works — Step by Step

### Step 1: Text Preparation

For each movie, we combine key fields into a single text passage:

```
Title: Fight Club Fight Club Fight Club
Overview: An insomniac office worker and a devil-may-care soap maker...
Tagline: Mischief. Mayhem. Soap.
Genres: Drama
Cast: Brad Pitt Edward Norton Helena Bonham Carter
Director: David Fincher
```

The title is repeated 3 times to increase its weight — this is a simple but effective trick so that title words have more influence on the embedding.

### Step 2: BERT Tokenization and Encoding

The model `sentence-transformers/all-MiniLM-L6-v2` processes each text passage:

1. The **tokenizer** splits the text into sub-word tokens (BERT uses WordPiece tokenization, not simple whitespace splitting). For example, "intergalactic" might become `["inter", "##gal", "##actic"]`.

2. BERT accepts up to **512 tokens**. If a passage is shorter, it pads with zeros; if longer, it truncates. Most movie passages fit within this limit.

3. The **model** processes these tokens through 6 transformer encoder layers, producing a `[512, 384]` tensor — a 384-dimensional vector for each of the 512 token positions.

4. **Mean pooling** averages all token vectors into a single 384-dimensional vector that represents the entire passage. This is the movie's embedding.

### Step 3: FAISS Indexing

Each 384-dim vector is added to a FAISS `IndexFlatL2` index. "Flat" means vectors are stored without compression (exact search, no approximation). "L2" means the index uses Euclidean (L2) distance to measure similarity — smaller distance = more similar.

### Step 4: Saving

The FAISS index is saved to `movie_faiss.index`, and the metadata list is saved to `movie_metadata.pkl` using Python's pickle serialization.

---

## How Search Works at Query Time

1. The user types a query, e.g., "romantic comedy set in Paris"
2. The same BERT model encodes this query into a 384-dim vector
3. FAISS compares this vector against all 220,000 stored vectors and returns the `top_k` closest ones (by L2 distance)
4. We look up each result's position in `movie_metadata` to get the title, overview, etc.
5. L2 distances are converted to similarity scores: `similarity = 1 / (1 + distance)`

---

## Files

| File | Description |
|---|---|
| `CS242_BERT_Indexing.ipynb` | Jupyter notebook that builds the index (run on Google Colab with GPU) |
| `movie_faiss.index` | Output: FAISS vector index (~320 MB) |
| `movie_metadata.pkl` | Output: Metadata list aligned with FAISS positions (~150 MB) |

### Metadata Schema (each entry in the list)

```python
{
    "id": 550,                              # TMDB movie ID
    "imdb_id": "tt0137523",                 # IMDb ID
    "title": "Fight Club",                  # Movie title
    "overview": "An insomniac office...",   # Plot summary
    "genres": ["Drama"],                    # Genre names
    "release_date": "1999-10-15",           # Release date
    "vote_average": 8.433,                  # Average rating (0-10)
    "countries": ["United States of America"],  # Production country names
    "country_codes": ["US"],                # Production country ISO codes
    "origin_country": ["US"],               # Origin country ISO codes
    "reviews": [...]                        # User reviews (list of dicts)
}
```

---

## How to Reproduce (if needed)

1. Upload `movies.zip` (the crawled data) to Google Drive
2. Open `CS242_BERT_Indexing.ipynb` in Google Colab
3. Set runtime to **GPU** (Runtime → Change runtime type → T4 GPU)
4. Update `DATASET_PATH` to point to your unzipped data
5. Run all cells — takes approximately 30-40 minutes on a T4 GPU
6. Download `movie_faiss.index` and `movie_metadata.pkl`
7. Place both files in `backend/models/`

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Model | `all-MiniLM-L6-v2` | 5x faster than `bert-base-uncased`, only 6 layers vs 12, produces 384-dim vectors (smaller index), and is fine-tuned for sentence similarity tasks |
| FAISS index type | `IndexFlatL2` | Exact search with no approximation error; acceptable for 220K documents |
| Distance metric | L2 (Euclidean) | Simple and effective; for normalized vectors, ranking is equivalent to cosine similarity |
| Passage strategy | One passage per movie | Most movie texts (title + overview + cast) fit within 512 tokens, so no splitting is needed |
| Title repetition | 3x | Simple weighting trick to make title words more influential in the embedding |
