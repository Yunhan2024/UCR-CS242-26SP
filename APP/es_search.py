"""
Elasticsearch search module.
Handles sparse (BM25/TF-IDF) search against the Elasticsearch index.

Field names match build_es_index.py schema:
  - title, original_title, overview, tagline (text, analyzed)
  - cast_names, crew_names (text, analyzed)
  - genres (keyword), original_language (keyword)
  - origin_country (keyword) ← NEW: ["US"], ["GB"], etc.
  - all_text (text, analyzed — combined field)
  - release_year (integer), vote_average (float)
  - movie_id (long)
"""

from elasticsearch import Elasticsearch
import config


def get_es_client():
    """Create and return an Elasticsearch client."""
    return Elasticsearch(
        hosts=[config.ES_HOST],
        request_timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )


def search(query: str, top_k: int = 10, country_filter: str = None) -> list:
    """
    Run a multi-match query across the ES index fields.

    Args:
        query:          The user's search string.
        top_k:          Number of results to return.
        country_filter: Optional ISO 3166-1 country code (e.g. "US").
    """
    es = get_es_client()

    must_clause = {
        "multi_match": {
            "query": query,
            "fields": [
                "title^3",
                "original_title^2",
                "overview^2",
                "tagline^1.5",
                "cast_names^1.5",
                "crew_names",
                "all_text",
            ],
            "type": "best_fields",
            "fuzziness": "AUTO",
        }
    }

    body = {
        "size": top_k,
        "_source": [
            "movie_id", "title", "overview", "genres",
            "vote_average", "release_year", "release_date",
            "cast_names", "crew_names", "original_language",
            "origin_country", "poster_path", "imdb_id",
        ],
        "query": {
            "bool": {
                "must": [must_clause],
            }
        },
    }

    # Filter by origin_country (keyword field)
    if country_filter:
        body["query"]["bool"]["filter"] = [
            {"term": {"origin_country": country_filter}}
        ]

    response = es.search(index=config.ES_INDEX_NAME, body=body)

    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        release_year = src.get("release_year")
        if release_year is None:
            rd = src.get("release_date", "")
            release_year = str(rd)[:4] if rd else ""
        else:
            release_year = str(release_year)

        results.append({
            "movie_id": src.get("movie_id", hit["_id"]),
            "title": src.get("title", "Unknown"),
            "overview": (src.get("overview") or "")[:300],
            "score": round(hit["_score"], 4),
            "genres": src.get("genres", []),
            "countries": src.get("origin_country", []),
            "rating": src.get("vote_average", 0),
            "release_year": release_year,
            "cast": (src.get("cast_names") or [])[:5],
            "imdb_id": src.get("imdb_id", ""),
            "poster_path": src.get("poster_path", ""),
        })

    return results


def get_country_counts() -> list:
    """
    Aggregate movies by origin_country.
    Returns [{"country_code": "US", "count": 52340}, ...].
    """
    es = get_es_client()

    body = {
        "size": 0,
        "aggs": {
            "countries": {
                "terms": {
                    "field": "origin_country",
                    "size": 300,
                }
            }
        },
    }

    response = es.search(index=config.ES_INDEX_NAME, body=body)

    counts = []
    for bucket in response["aggregations"]["countries"]["buckets"]:
        counts.append({
            "country_code": bucket["key"],
            "count": bucket["doc_count"],
        })

    return counts
