"""
Elasticsearch search module.
Handles sparse (BM25/TF-IDF) search against the Elasticsearch index.
"""

from elasticsearch import Elasticsearch
import config


def get_es_client():
    """Create and return an Elasticsearch client."""
    kwargs = {"hosts": [config.ES_HOST]}
    if config.ES_PASSWORD:
        kwargs["basic_auth"] = (config.ES_USER, config.ES_PASSWORD)
        kwargs["verify_certs"] = False
    return Elasticsearch(**kwargs)


def search(query: str, top_k: int = 10, country_filter: str = None) -> list:
    """
    Run a multi-match query across title, overview, cast, crew, and all_text.

    Args:
        query:          The user's search string.
        top_k:          Number of results to return.
        country_filter: Optional ISO 3166-1 country code (e.g. "US") to filter by.

    Returns:
        A list of result dicts:
        [{"movie_id", "title", "overview", "score", "genres", "countries", "rating", "release_year"}, ...]
    """
    es = get_es_client()

    # ── Build the query body ──────────────────────────
    must_clause = {
        "multi_match": {
            "query": query,
            "fields": [
                "title^3",         # boost title matches
                "overview^2",
                "cast^1.5",
                "crew",
                "all_text",
            ],
            "type": "best_fields",
            "fuzziness": "AUTO",
        }
    }

    body = {
        "size": top_k,
        "query": {
            "bool": {
                "must": [must_clause],
            }
        },
    }

    # Optional country filter
    if country_filter:
        body["query"]["bool"]["filter"] = [
            {"term": {"production_countries.iso_3166_1": country_filter}}
        ]

    response = es.search(index=config.ES_INDEX_NAME, body=body)

    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        results.append({
            "movie_id": src.get("id", hit["_id"]),
            "title": src.get("title", "Unknown"),
            "overview": src.get("overview", "")[:300],
            "score": round(hit["_score"], 4),
            "genres": src.get("genres", []),
            "countries": src.get("production_countries", []),
            "rating": src.get("vote_average", 0),
            "release_year": src.get("release_date", "")[:4],
        })

    return results


def get_country_counts() -> list:
    """
    Use an Elasticsearch aggregation to count movies per production country.
    Returns a list of {"country_code": "US", "country_name": "...", "count": 12345}.
    """
    es = get_es_client()

    body = {
        "size": 0,
        "aggs": {
            "countries": {
                "terms": {
                    "field": "production_countries.iso_3166_1",
                    "size": 300,  # enough for all countries
                }
            }
        },
    }

    response = es.search(index=config.ES_INDEX_NAME, body=body)

    country_counts = []
    for bucket in response["aggregations"]["countries"]["buckets"]:
        country_counts.append({
            "country_code": bucket["key"],
            "count": bucket["doc_count"],
        })

    return country_counts
