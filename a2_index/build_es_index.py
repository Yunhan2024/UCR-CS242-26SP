#!/usr/bin/env python3
"""
Build an Elasticsearch index for TMDB crawl data (CS242 Part A2).

Features:
- Supports input from `.zip`, directory, `.json`, or `.jsonl`
- Deduplicates documents by TMDB movie ID
- Uses custom English analyzer (lowercase + stopword removal + stemming)
- Bulk indexes with parallel workers for throughput
- Generates a JSON report for grading/debugging
"""

import argparse
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from zipfile import ZipFile

from elasticsearch import Elasticsearch, helpers

ANALYZER_BASE_NAME = "en_tmdb"
ANALYZER_OPTIONS = ("english_stem", "english_no_stem", "standard")
MAX_ERROR_SAMPLES = 20


@dataclass
class BuildStats:
    files_seen: int = 0
    docs_seen: int = 0
    docs_prepared: int = 0
    docs_indexed: int = 0
    docs_failed: int = 0
    docs_skipped_non_movie: int = 0
    docs_skipped_duplicate: int = 0
    parse_errors: int = 0
    started_at_utc: str = ""
    ended_at_utc: str = ""
    duration_sec: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Elasticsearch index for TMDB crawl output.")
    parser.add_argument(
        "--source",
        required=True,
        help="Path to crawl data (.zip / directory / .json / .jsonl).",
    )
    parser.add_argument("--index-name", default="tmdb_movies_v1", help="Elasticsearch index name.")
    parser.add_argument(
        "--analyzer-option",
        default="english_stem",
        choices=ANALYZER_OPTIONS,
        help="Text analyzer mode: english_stem | english_no_stem | standard.",
    )
    parser.add_argument("--es-url", default="http://localhost:9200", help="Elasticsearch URL.")
    parser.add_argument("--es-user", default="", help="Elasticsearch username (optional).")
    parser.add_argument("--es-password", default="", help="Elasticsearch password (optional).")
    parser.add_argument("--api-key", default="", help="Elasticsearch API key (optional).")
    parser.add_argument(
        "--recreate-index",
        action="store_true",
        help="Delete and recreate index if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and transform documents without indexing into Elasticsearch.",
    )
    parser.add_argument("--max-docs", type=int, default=0, help="Limit prepared documents (0 = no limit).")
    parser.add_argument(
        "--max-review-chars",
        type=int,
        default=2000,
        help="Truncate each review content to this many characters.",
    )
    parser.add_argument("--threads", type=int, default=4, help="Thread count for parallel bulk indexing.")
    parser.add_argument("--chunk-size", type=int, default=500, help="Bulk chunk size.")
    parser.add_argument("--queue-size", type=int, default=8, help="Queue size for parallel bulk.")
    parser.add_argument("--request-timeout", type=int, default=120, help="Elasticsearch request timeout seconds.")
    parser.add_argument("--shards", type=int, default=1, help="Number of index shards.")
    parser.add_argument("--replicas", type=int, default=0, help="Number of index replicas.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for HTTPS clusters.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=5000,
        help="Log progress every N prepared/processed docs.",
    )
    parser.add_argument(
        "--report-path",
        default="",
        help="Output JSON report path. Default: a2_index/reports/index_report_<timestamp>.json",
    )
    parser.add_argument(
        "--source-subpath",
        default="",
        help="Only index files under this relative subpath (useful for zip inputs, e.g., data/movies).",
    )
    parser.add_argument(
        "--include-jsonl",
        action="store_true",
        help="Include JSONL files. Default behavior indexes only .json files for TMDB movie docs.",
    )
    return parser.parse_args()


def analyzer_name_for(option: str) -> str:
    return f"{ANALYZER_BASE_NAME}_{option}"


def analyzer_filters_for(option: str) -> List[str]:
    if option == "english_stem":
        return [
            "lowercase",
            "asciifolding",
            "english_possessive_stemmer",
            "english_stop",
            "english_stemmer",
        ]
    if option == "english_no_stem":
        return [
            "lowercase",
            "asciifolding",
            "english_stop",
        ]
    return [
        "lowercase",
        "asciifolding",
    ]


def index_settings(shards: int, replicas: int, analyzer_option: str) -> Dict[str, Any]:
    analyzer_name = analyzer_name_for(analyzer_option)
    return {
        "number_of_shards": shards,
        "number_of_replicas": replicas,
        "analysis": {
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "english_possessive_stemmer": {
                    "type": "stemmer",
                    "language": "possessive_english",
                },
            },
            "analyzer": {
                analyzer_name: {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": analyzer_filters_for(analyzer_option),
                }
            },
        },
    }


def index_mappings(analyzer_option: str) -> Dict[str, Any]:
    analyzer_name = analyzer_name_for(analyzer_option)
    return {
        "dynamic": False,
        "properties": {
            "movie_id": {"type": "long"},
            "imdb_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": analyzer_name,
                "fields": {"raw": {"type": "keyword", "ignore_above": 512}},
            },
            "original_title": {
                "type": "text",
                "analyzer": analyzer_name,
                "fields": {"raw": {"type": "keyword", "ignore_above": 512}},
            },
            "overview": {"type": "text", "analyzer": analyzer_name},
            "tagline": {"type": "text", "analyzer": analyzer_name},
            "all_text": {"type": "text", "analyzer": analyzer_name},
            "release_date": {"type": "date", "format": "yyyy-MM-dd||strict_date_optional_time"},
            "release_year": {"type": "integer"},
            "status": {"type": "keyword"},
            "original_language": {"type": "keyword"},
            "genres": {"type": "keyword"},
            "genre_ids": {"type": "integer"},
            "cast_names": {
                "type": "text",
                "analyzer": analyzer_name,
                "fields": {"raw": {"type": "keyword", "ignore_above": 512}},
            },
            "cast_characters": {"type": "text", "analyzer": analyzer_name},
            "crew_names": {
                "type": "text",
                "analyzer": analyzer_name,
                "fields": {"raw": {"type": "keyword", "ignore_above": 512}},
            },
            "crew_jobs": {"type": "keyword"},
            "review_authors": {"type": "keyword"},
            "reviews_text": {"type": "text", "analyzer": analyzer_name},
            "review_count": {"type": "integer"},
            "vote_average": {"type": "float"},
            "vote_count": {"type": "integer"},
            "popularity": {"type": "float"},
            "runtime": {"type": "integer"},
            "budget": {"type": "long"},
            "revenue": {"type": "long"},
            "adult": {"type": "boolean"},
            "poster_path": {"type": "keyword"},
            "backdrop_path": {"type": "keyword"},
            "homepage": {"type": "keyword"},
            "crawled_at": {"type": "date", "format": "strict_date_optional_time"},
            "source_path": {"type": "keyword"},
        },
    }


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def unique_non_empty(values: Sequence[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def list_value(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def extract_text_field(items: Sequence[Any], key: str, limit: int = 0) -> List[str]:
    output = []
    rows = items if limit <= 0 else items[:limit]
    for item in rows:
        if not isinstance(item, dict):
            continue
        text = as_text(item.get(key))
        if text:
            output.append(text)
    return output


def extract_int_field(items: Sequence[Any], key: str) -> List[int]:
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = as_int(item.get(key))
        if value is not None:
            output.append(value)
    return output


def parse_release_year(release_date: str) -> Optional[int]:
    if len(release_date) < 4:
        return None
    year = release_date[:4]
    return int(year) if year.isdigit() else None


def is_movie_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    if not as_text(record.get("title")):
        return False
    if record.get("id") is None and not as_text(record.get("imdb_id")):
        return False
    shape_markers = ("release_date", "vote_average", "runtime", "genres", "cast")
    return any(marker in record for marker in shape_markers)


def fallback_doc_id(record: Dict[str, Any]) -> str:
    seed = "|".join(
        [
            as_text(record.get("title")),
            as_text(record.get("original_title")),
            as_text(record.get("release_date")),
            as_text(record.get("imdb_id")),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return "sha1_" + digest


def parse_json_text(blob: str, source_name: str, stats: BuildStats) -> Iterator[Dict[str, Any]]:
    is_jsonl = source_name.lower().endswith(".jsonl")
    if is_jsonl:
        for line_no, line in enumerate(blob.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                stats.parse_errors += 1
                if stats.parse_errors <= 5:
                    logging.warning("JSONL parse error: %s:%d", source_name, line_no)
                continue
            if isinstance(data, dict):
                yield data
        return

    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        stats.parse_errors += 1
        if stats.parse_errors <= 5:
            logging.warning("JSON parse error: %s", source_name)
        return

    if isinstance(data, dict):
        yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item


def should_read_source_name(source_name: str, args: argparse.Namespace) -> bool:
    normalized = source_name.replace("\\", "/")

    if "/__MACOSX/" in normalized or normalized.startswith("__MACOSX/"):
        return False
    base = normalized.rsplit("/", 1)[-1]
    if base.startswith("._"):
        return False

    if args.source_subpath:
        sub = args.source_subpath.strip("/").replace("\\", "/")
        sub_with_slashes = f"/{sub}/"
        if (
            not normalized.startswith(sub + "/")
            and normalized != sub
            and sub_with_slashes not in normalized
            and not normalized.endswith("/" + sub)
        ):
            return False

    lower = normalized.lower()
    if lower.endswith(".json"):
        return True
    if lower.endswith(".jsonl"):
        return bool(args.include_jsonl)
    return False


def iter_records(
    source: Path,
    stats: BuildStats,
    args: argparse.Namespace,
) -> Iterator[Tuple[Dict[str, Any], str]]:
    if source.is_dir():
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            source_name = str(path)
            if not should_read_source_name(source_name, args):
                continue
            stats.files_seen += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                stats.parse_errors += 1
                continue
            for record in parse_json_text(text, source_name, stats):
                yield record, source_name
        return

    if source.is_file() and source.suffix.lower() == ".zip":
        with ZipFile(source) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                source_name = info.filename
                if not should_read_source_name(source_name, args):
                    continue
                stats.files_seen += 1
                try:
                    raw = zf.read(source_name)
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    stats.parse_errors += 1
                    continue
                for record in parse_json_text(text, source_name, stats):
                    yield record, source_name
        return

    if source.is_file() and source.suffix.lower() in (".json", ".jsonl"):
        if not should_read_source_name(str(source), args):
            return
        stats.files_seen += 1
        text = source.read_text(encoding="utf-8", errors="replace")
        for record in parse_json_text(text, str(source), stats):
            yield record, str(source)
        return

    raise ValueError(f"Unsupported source type: {source}")


def transform_record(
    record: Dict[str, Any],
    source_path: str,
    max_review_chars: int,
) -> Tuple[str, Dict[str, Any]]:
    movie_id = as_int(record.get("id"))
    doc_id = str(movie_id) if movie_id is not None else fallback_doc_id(record)

    title = as_text(record.get("title"))
    original_title = as_text(record.get("original_title"))
    overview = as_text(record.get("overview"))
    tagline = as_text(record.get("tagline"))
    release_date = as_text(record.get("release_date"))
    if release_date and len(release_date) < 4:
        release_date = ""

    genres_raw = list_value(record.get("genres"))
    cast_raw = list_value(record.get("cast"))
    crew_raw = list_value(record.get("crew"))
    reviews_raw = list_value(record.get("reviews"))

    genres = unique_non_empty(extract_text_field(genres_raw, "name"))
    genre_ids = extract_int_field(genres_raw, "id")
    cast_names = unique_non_empty(extract_text_field(cast_raw, "name", limit=20))
    cast_characters = unique_non_empty(extract_text_field(cast_raw, "character", limit=20))
    crew_names = unique_non_empty(extract_text_field(crew_raw, "name"))
    crew_jobs = unique_non_empty(extract_text_field(crew_raw, "job"))
    review_authors = unique_non_empty(extract_text_field(reviews_raw, "author", limit=10))

    review_texts = []
    for text in extract_text_field(reviews_raw, "content", limit=10):
        review_texts.append(text[:max_review_chars])

    all_text_parts = [
        title,
        original_title,
        overview,
        tagline,
        " ".join(genres),
        " ".join(cast_names),
        " ".join(crew_names),
        " ".join(review_texts),
    ]
    all_text = " ".join(part for part in all_text_parts if part).strip()

    release_year = parse_release_year(release_date) if release_date else None
    review_count = as_int(record.get("review_count"))
    if review_count is None:
        review_count = len(review_texts)

    doc: Dict[str, Any] = {
        "movie_id": movie_id,
        "imdb_id": as_text(record.get("imdb_id")),
        "title": title,
        "original_title": original_title,
        "overview": overview,
        "tagline": tagline,
        "all_text": all_text,
        "release_date": release_date or None,
        "release_year": release_year,
        "status": as_text(record.get("status")),
        "original_language": as_text(record.get("original_language")),
        "genres": genres,
        "genre_ids": genre_ids,
        "cast_names": cast_names,
        "cast_characters": cast_characters,
        "crew_names": crew_names,
        "crew_jobs": crew_jobs,
        "review_authors": review_authors,
        "reviews_text": review_texts,
        "review_count": review_count,
        "vote_average": as_float(record.get("vote_average")),
        "vote_count": as_int(record.get("vote_count")),
        "popularity": as_float(record.get("popularity")),
        "runtime": as_int(record.get("runtime")),
        "budget": as_int(record.get("budget")),
        "revenue": as_int(record.get("revenue")),
        "adult": bool(record.get("adult", False)),
        "poster_path": as_text(record.get("poster_path")),
        "backdrop_path": as_text(record.get("backdrop_path")),
        "homepage": as_text(record.get("homepage")),
        "crawled_at": as_text(record.get("crawled_at")) or None,
        "source_path": source_path,
    }

    # Drop null and empty string fields to reduce index size.
    compact_doc = {}
    for key, value in doc.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        compact_doc[key] = value

    return doc_id, compact_doc


def action_stream(
    source_records: Iterator[Tuple[Dict[str, Any], str]],
    index_name: str,
    stats: BuildStats,
    max_review_chars: int,
    max_docs: int,
    log_every: int,
) -> Iterator[Dict[str, Any]]:
    seen_doc_ids = set()

    for record, source_path in source_records:
        stats.docs_seen += 1

        if not is_movie_record(record):
            stats.docs_skipped_non_movie += 1
            continue

        doc_id, document = transform_record(record, source_path, max_review_chars)

        if doc_id in seen_doc_ids:
            stats.docs_skipped_duplicate += 1
            continue

        seen_doc_ids.add(doc_id)
        stats.docs_prepared += 1

        if log_every > 0 and stats.docs_prepared % log_every == 0:
            logging.info(
                "Prepared %d docs (seen=%d, duplicates=%d, skipped_non_movie=%d)",
                stats.docs_prepared,
                stats.docs_seen,
                stats.docs_skipped_duplicate,
                stats.docs_skipped_non_movie,
            )

        yield {
            "_op_type": "index",
            "_index": index_name,
            "_id": doc_id,
            "_source": document,
        }

        if max_docs > 0 and stats.docs_prepared >= max_docs:
            break


def create_es_client(args: argparse.Namespace) -> Elasticsearch:
    kwargs: Dict[str, Any] = {
        "hosts": [args.es_url],
        "request_timeout": args.request_timeout,
        "max_retries": 3,
        "retry_on_timeout": True,
    }
    if args.api_key:
        kwargs["api_key"] = args.api_key
    elif args.es_user:
        kwargs["basic_auth"] = (args.es_user, args.es_password)
    if args.insecure:
        kwargs["verify_certs"] = False

    client = Elasticsearch(**kwargs)
    info = client.info()
    version = info.get("version", {}).get("number", "unknown")
    logging.info("Connected to Elasticsearch %s at %s", version, args.es_url)
    return client


def ensure_index(client: Elasticsearch, args: argparse.Namespace) -> None:
    exists = client.indices.exists(index=args.index_name)
    if exists and args.recreate_index:
        logging.info("Deleting existing index: %s", args.index_name)
        client.indices.delete(index=args.index_name)
        exists = False

    if not exists:
        logging.info(
            "Creating index %s (shards=%d, replicas=%d)",
            args.index_name,
            args.shards,
            args.replicas,
        )
        client.indices.create(
            index=args.index_name,
            settings=index_settings(args.shards, args.replicas, args.analyzer_option),
            mappings=index_mappings(args.analyzer_option),
        )
    else:
        logging.info("Index already exists and will be reused: %s", args.index_name)
        logging.warning(
            "Index settings/analyzer are not changed when reusing an existing index. "
            "Use --recreate-index to apply analyzer option '%s'.",
            args.analyzer_option,
        )


def default_report_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("a2_index/reports") / f"index_report_{ts}.json"


def write_report(
    args: argparse.Namespace,
    stats: BuildStats,
    source: Path,
    es_count: Optional[int],
    error_samples: Sequence[Any],
) -> Path:
    report_path = Path(args.report_path) if args.report_path else default_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "index_name": args.index_name,
        "analyzer_option": args.analyzer_option,
        "dry_run": args.dry_run,
        "es_url": args.es_url,
        "es_count": es_count,
        "args": {
            "max_docs": args.max_docs,
            "max_review_chars": args.max_review_chars,
            "threads": args.threads,
            "chunk_size": args.chunk_size,
            "queue_size": args.queue_size,
            "request_timeout": args.request_timeout,
            "shards": args.shards,
            "replicas": args.replicas,
            "recreate_index": args.recreate_index,
            "source_subpath": args.source_subpath,
            "include_jsonl": args.include_jsonl,
        },
        "stats": asdict(stats),
        "error_samples": list(error_samples),
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return report_path


def run(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Source path does not exist: {source}")
    if args.source_subpath:
        logging.info("Restricting input to subpath: %s", args.source_subpath)
    logging.info(
        "Analyzer option: %s (jsonl=%s)",
        args.analyzer_option,
        "enabled" if args.include_jsonl else "disabled",
    )

    stats = BuildStats()
    stats.started_at_utc = datetime.now(timezone.utc).isoformat()
    started_ts = time.time()
    error_samples: List[Any] = []
    es_count: Optional[int] = None

    records = iter_records(source, stats, args)
    actions = action_stream(
        source_records=records,
        index_name=args.index_name,
        stats=stats,
        max_review_chars=args.max_review_chars,
        max_docs=args.max_docs,
        log_every=args.log_every,
    )

    if args.dry_run:
        for _ in actions:
            pass
        stats.docs_indexed = stats.docs_prepared
    else:
        client = create_es_client(args)
        ensure_index(client, args)

        for ok, result in helpers.parallel_bulk(
            client=client,
            actions=actions,
            thread_count=args.threads,
            chunk_size=args.chunk_size,
            queue_size=args.queue_size,
            request_timeout=args.request_timeout,
            raise_on_error=False,
            raise_on_exception=False,
        ):
            if ok:
                stats.docs_indexed += 1
            else:
                stats.docs_failed += 1
                if len(error_samples) < MAX_ERROR_SAMPLES:
                    error_samples.append(result)

            processed = stats.docs_indexed + stats.docs_failed
            if args.log_every > 0 and processed > 0 and processed % args.log_every == 0:
                logging.info(
                    "Indexed=%d failed=%d prepared=%d",
                    stats.docs_indexed,
                    stats.docs_failed,
                    stats.docs_prepared,
                )

        client.indices.refresh(index=args.index_name)
        es_count = client.count(index=args.index_name).get("count")

    stats.duration_sec = round(time.time() - started_ts, 2)
    stats.ended_at_utc = datetime.now(timezone.utc).isoformat()

    report_path = write_report(args, stats, source, es_count, error_samples)
    logging.info("Report saved: %s", report_path)
    logging.info(
        "Done. files=%d seen=%d prepared=%d indexed=%d failed=%d dup=%d non_movie=%d parse_errors=%d",
        stats.files_seen,
        stats.docs_seen,
        stats.docs_prepared,
        stats.docs_indexed,
        stats.docs_failed,
        stats.docs_skipped_duplicate,
        stats.docs_skipped_non_movie,
        stats.parse_errors,
    )
    return 0 if stats.docs_failed == 0 else 2


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
