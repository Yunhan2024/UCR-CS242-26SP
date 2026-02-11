# CS242 Part A2: Scalable Index Construction with PyElasticsearch

## 1. Objective

Part A2 requires building an index for the dataset collected in Part A1 using PyLucene, PyElasticsearch, pyserini, or an approved equivalent (excluding Solr).  
This implementation uses **PyElasticsearch** (`elasticsearch` Python client) and focuses on:

- correctness (schema validity, duplicate handling, robust parsing),
- efficiency (parallel bulk ingestion, bounded memory, structured I/O),
- explicit index design rationale (analyzers and field modeling),
- reproducibility (scripted execution with parameterized entry points).

## 2. Requirement-to-Evidence Mapping

| A2 Requirement | Implementation Evidence |
|---|---|
| Use an approved indexing framework (not Solr) | `a2_index/build_es_index.py` uses the official PyElasticsearch client |
| Provide executable entry point with parameters | `indexbuilder.sh` supports `./indexbuilder.sh <input_path> <analyzer_option>` |
| Correctness: duplicate handling | Document IDs are keyed by TMDB `id`; duplicates are removed before indexing |
| Correctness: robust ingestion | Supports `zip/dir/json/jsonl`; filters non-target files; records parse errors |
| Efficiency: throughput-oriented ingestion | Uses `helpers.parallel_bulk` with configurable `threads/chunk-size/queue-size` |
| Explain index design choices | Analyzer strategy, field decomposition, and trade-offs documented below |
| Report index runtime vs document volume (A2 iii) | `a2_index/benchmark_runtime.py`, `a2_index/benchmarks/runtime_points.csv`, `a2_index/benchmarks/runtime_plot.png` |

## 3. Executable Interface (Required by Assignment)

### 3.1 Primary executable

```bash
./indexbuilder.sh <input_path> <analyzer_option>
```

- `input_path`: path to `.zip`, directory, `.json`, or `.jsonl`.
- `analyzer_option`: `english_stem` | `english_no_stem` | `standard`.

### 3.2 Example commands

```bash
cd /bigdata/renlab/rui001/IR/UCR-CS242-26SP
chmod +x indexbuilder.sh

# Validation pass (no indexing write)
DRY_RUN=1 ./indexbuilder.sh /bigdata/renlab/rui001/IR/data.zip english_stem

# Full indexing run
./indexbuilder.sh /bigdata/renlab/rui001/IR/data.zip english_stem
```

### 3.3 Optional environment parameters

- `ES_URL` (default `http://localhost:9200`)
- `INDEX_NAME` (default `tmdb_movies_v1`)
- `THREADS` (default `6`)
- `CHUNK_SIZE` (default `800`)
- `QUEUE_SIZE` (default `12`)
- `SOURCE_SUBPATH` (default `data/movies`)
- `DRY_RUN`, `RECREATE_INDEX`, `INCLUDE_JSONL`

## 4. Data Ingestion and Correctness Strategy

### 4.1 Input handling

The indexer accepts:

- zipped archives (`.zip`),
- directory trees,
- standalone `.json` / `.jsonl`.

For the current TMDB crawl archive, indexing is intentionally constrained to `data/movies` by default to exclude non-target artifacts (e.g., `__MACOSX`, metadata files).

### 4.2 Duplicate control

Duplicate mitigation is implemented at two levels:

- document keying: Elasticsearch `_id` is set to TMDB `id`;
- pre-index deduplication: an in-memory `seen_doc_ids` set prevents duplicate bulk actions in a single run.

### 4.3 Type normalization and schema safety

Before indexing, each record is normalized:

- safe casting for numeric fields (`vote_average`, `vote_count`, `runtime`, `budget`, `revenue`),
- optional field trimming and null suppression,
- release year extraction from `release_date`,
- review truncation via `--max-review-chars`.

Malformed or non-target records are skipped and counted in run statistics.

## 5. Index Design and Analyzer Rationale

### 5.1 Analyzer options

Three analyzer modes are provided:

- `english_stem` (default): lowercase + ASCII folding + stopword removal + stemming,
- `english_no_stem`: lowercase + ASCII folding + stopword removal,
- `standard`: lowercase + ASCII folding only.

**Rationale:**  
`english_stem` increases recall for lexical variants; `english_no_stem` preserves morphology for interpretability; `standard` provides a minimal normalization baseline for ablation.

### 5.2 Field modeling

The schema separates structured metadata from full text:

- full text: `title`, `overview`, `tagline`, `reviews_text`, `all_text`,
- structured/filter fields: `genres`, `genre_ids`, `release_year`, `vote_average`, `vote_count`,
- people fields: `cast_names`, `crew_names`, `crew_jobs`,
- audit fields: `source_path`, `crawled_at`.

**Rationale:**  
This decomposition supports both relevance-oriented retrieval and faceted filtering/sorting without overloading one monolithic text field.

## 6. Efficiency Considerations

### 6.1 Parallel bulk indexing

The pipeline uses Elasticsearch parallel bulk ingestion with configurable:

- `--threads`
- `--chunk-size`
- `--queue-size`

This substantially improves throughput versus per-document writes.

### 6.2 I/O and memory behavior

- Streamed record iteration avoids loading the entire dataset into memory.
- Only IDs used for deduplication are retained in memory.
- Progress logging supports long-running job observability.

## 7. Index Creation Runtime Benchmark (A2 Requirement iii)

To satisfy the requirement of reporting index-creation runtime as a function of document volume, a controlled benchmark was executed using incremental document caps.

### 7.1 Benchmark protocol

- Elasticsearch version: `8.19.3` (single-node local deployment)
- Analyzer: `english_stem`
- Ingestion settings: `threads=6`, `chunk_size=800`, `queue_size=12`
- Source: `/bigdata/renlab/rui001/IR/data.zip` (restricted to `data/movies`)
- Document points: `10,000`, `50,000`, `100,000`, `150,000`, `220,243`

Reproduction command:

```bash
python3 a2_index/benchmark_runtime.py \
  --source /bigdata/renlab/rui001/IR/data.zip \
  --es-url http://127.0.0.1:9200 \
  --doc-points 10000,50000,100000,150000,220243
```

### 7.2 Measured results

| Documents Indexed | Runtime (s) | Throughput (docs/s) |
|---:|---:|---:|
| 10,000 | 5.34 | 1,872.66 |
| 50,000 | 11.27 | 4,436.56 |
| 100,000 | 20.59 | 4,856.73 |
| 150,000 | 30.58 | 4,905.17 |
| 220,243 | 42.93 | 5,130.28 |

### 7.3 Figure and data artifacts

- Runtime plot: `a2_index/benchmarks/runtime_plot.png`
- Raw benchmark points: `a2_index/benchmarks/runtime_points.csv`
- Structured summary: `a2_index/benchmarks/benchmark_summary.json`

Interpretation: runtime increases approximately linearly with corpus size under fixed ingestion settings, while effective throughput improves after warm-up and stabilizes above approximately `4.8k docs/s`.

## 8. Reproducibility and Output Artifacts

Each run emits a JSON report with:

- runtime and timestamps,
- prepared/indexed/failed counts,
- duplicate and parse-error counts,
- execution parameters.

Example report from a successful full run:

- `a2_index/reports/index_report_20260211_225245.json`

Key result in that run:

- `docs_prepared = 220243`
- `docs_indexed = 220243`
- `docs_failed = 0`
- `parse_errors = 0`

## 9. Validation Commands

```bash
curl http://127.0.0.1:9200/tmdb_movies_v1/_count?pretty
curl http://127.0.0.1:9200/_cluster/health?pretty
curl http://127.0.0.1:9200/_cat/indices?v
```

These commands verify index existence, document count, and cluster health.

## 10. File Inventory

- `indexbuilder.sh`: required executable entry point.
- `a2_index/build_es_index.py`: core indexing pipeline.
- `a2_index/benchmark_runtime.py`: runtime benchmarking utility for A2 (iii).
- `a2_index/requirements-index.txt`: A2 dependency list.
- `a2_index/reports/*.json`: indexing run evidence and metrics.
- `a2_index/benchmarks/*`: benchmark logs, CSV data, and runtime plot.

## 11. Notes

- This implementation intentionally uses **PyElasticsearch** (permitted by A2).
- Solr is not used.
- If Elasticsearch is unreachable, ensure the service is running and reachable at the configured `ES_URL`.
