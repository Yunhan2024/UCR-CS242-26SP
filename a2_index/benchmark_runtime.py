#!/usr/bin/env python3
"""
Benchmark indexing runtime for different corpus sizes and generate:
1) CSV table
2) Runtime-vs-documents plot (PNG)

This script runs build_es_index.py multiple times with different --max-docs
values and records the reported duration.
"""

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark indexing runtime.")
    parser.add_argument("--source", required=True, help="Path to input data zip/dir.")
    parser.add_argument("--es-url", default="http://127.0.0.1:9200", help="Elasticsearch URL.")
    parser.add_argument(
        "--doc-points",
        default="10000,50000,100000,150000,220243",
        help="Comma-separated max-doc values for benchmark runs.",
    )
    parser.add_argument("--analyzer-option", default="english_stem", help="Analyzer option for build_es_index.")
    parser.add_argument("--threads", type=int, default=6, help="Parallel bulk thread count.")
    parser.add_argument("--chunk-size", type=int, default=800, help="Bulk chunk size.")
    parser.add_argument("--queue-size", type=int, default=12, help="Parallel bulk queue size.")
    parser.add_argument("--source-subpath", default="data/movies", help="Subpath filter used for input files.")
    parser.add_argument(
        "--output-dir",
        default="a2_index/benchmarks",
        help="Directory for benchmark CSV and plot outputs.",
    )
    return parser.parse_args()


def run_one_benchmark(args: argparse.Namespace, max_docs: int, output_dir: Path) -> Dict[str, float]:
    index_name = f"tmdb_runtime_bench_{max_docs}"
    report_path = output_dir / f"run_{max_docs}.json"
    cmd = [
        "python3",
        "a2_index/build_es_index.py",
        "--source",
        args.source,
        "--source-subpath",
        args.source_subpath,
        "--analyzer-option",
        args.analyzer_option,
        "--es-url",
        args.es_url,
        "--index-name",
        index_name,
        "--recreate-index",
        "--max-docs",
        str(max_docs),
        "--threads",
        str(args.threads),
        "--chunk-size",
        str(args.chunk_size),
        "--queue-size",
        str(args.queue_size),
        "--report-path",
        str(report_path),
    ]

    subprocess.run(cmd, check=True)

    with report_path.open("r", encoding="utf-8") as f:
        report = json.load(f)

    stats = report["stats"]
    return {
        "max_docs": max_docs,
        "prepared_docs": stats["docs_prepared"],
        "indexed_docs": stats["docs_indexed"],
        "failed_docs": stats["docs_failed"],
        "duration_sec": stats["duration_sec"],
        "docs_per_sec": round(stats["docs_indexed"] / max(stats["duration_sec"], 1e-6), 2),
    }


def write_csv(rows: List[Dict[str, float]], csv_path: Path) -> None:
    fieldnames = [
        "max_docs",
        "prepared_docs",
        "indexed_docs",
        "failed_docs",
        "duration_sec",
        "docs_per_sec",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_plot(rows: List[Dict[str, float]], plot_path: Path) -> None:
    x = [int(r["indexed_docs"]) for r in rows]
    y = [float(r["duration_sec"]) for r in rows]

    plt.figure(figsize=(8, 5))
    plt.plot(x, y, marker="o", linewidth=2)
    plt.title("Index Build Runtime vs Number of Indexed Documents")
    plt.xlabel("Number of Indexed Documents")
    plt.ylabel("Runtime (seconds)")
    plt.grid(True, alpha=0.3)

    for xi, yi in zip(x, y):
        plt.annotate(f"{yi:.2f}s", (xi, yi), textcoords="offset points", xytext=(0, 8), ha="center")

    plt.tight_layout()
    plt.savefig(plot_path, dpi=180)
    plt.close()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    points = [int(x.strip()) for x in args.doc_points.split(",") if x.strip()]
    rows: List[Dict[str, float]] = []

    for max_docs in points:
        print(f"[benchmark] running max_docs={max_docs}")
        row = run_one_benchmark(args, max_docs, output_dir)
        rows.append(row)
        print(
            "[benchmark] completed",
            f"indexed={row['indexed_docs']}",
            f"duration={row['duration_sec']}s",
            f"throughput={row['docs_per_sec']} docs/s",
        )

    csv_path = output_dir / "runtime_points.csv"
    plot_path = output_dir / "runtime_plot.png"
    write_csv(rows, csv_path)
    write_plot(rows, plot_path)

    summary_path = output_dir / "benchmark_summary.json"
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        "es_url": args.es_url,
        "analyzer_option": args.analyzer_option,
        "doc_points": points,
        "runs": rows,
        "csv": str(csv_path),
        "plot": str(plot_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[benchmark] csv: {csv_path}")
    print(f"[benchmark] plot: {plot_path}")
    print(f"[benchmark] summary: {summary_path}")


if __name__ == "__main__":
    main()
