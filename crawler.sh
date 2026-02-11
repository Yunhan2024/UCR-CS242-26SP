#!/bin/bash
# TMDB Movie Crawler
# Usage: ./crawler.sh <api-key> <seed-file> <num-movies> <strategy> <output-dir>
#
# Parameters:
#   api-key     : TMDB API key (required)
#   seed-file   : Path to movie IDs file (default: data/movie_ids.jsonl)
#   num-movies  : Max number of movies to crawl, 0 = all (default: 0)
#   strategy    : Discovery strategy: genre|year|language|all (default: all)
#   output-dir  : Output directory for movie JSON files (default: data/movies)
#
# Examples:
#   ./crawler.sh YOUR_API_KEY
#   ./crawler.sh YOUR_API_KEY data/movie_ids.jsonl 10000 all data/movies
#   ./crawler.sh YOUR_API_KEY data/movie_ids.jsonl 0 genre data/movies

set -e

API_KEY="${1:?Error: API key is required. Usage: ./crawler.sh <api-key> [seed-file] [num-movies] [strategy] [output-dir]}"
SEED_FILE="${2:-data/movie_ids.jsonl}"
NUM_MOVIES="${3:-0}"
STRATEGY="${4:-all}"
OUTPUT_DIR="${5:-data/movies}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRAWLER_DIR="$SCRIPT_DIR/tmdb_crawler"
LOG_DIR="$SCRIPT_DIR/logs"

export TMDB_API_KEY="$API_KEY"

mkdir -p "$LOG_DIR"
mkdir -p "$OUTPUT_DIR"

echo "=== TMDB Movie Crawler ==="
echo "API Key    : ${API_KEY:0:8}..."
echo "Seed File  : $SEED_FILE"
echo "Num Movies : $( [ "$NUM_MOVIES" -eq 0 ] && echo 'all' || echo "$NUM_MOVIES" )"
echo "Strategy   : $STRATEGY"
echo "Output Dir : $OUTPUT_DIR"
echo ""

# Phase 1: Discover movie IDs
echo "[Phase 1] Discovering movie IDs (strategy: $STRATEGY)..."
cd "$CRAWLER_DIR"
scrapy crawl discover \
    -a strategy="$STRATEGY" \
    -s LOG_FILE="$LOG_DIR/discover.log"

TOTAL_IDS=$(wc -l < "$SCRIPT_DIR/$SEED_FILE" | tr -d ' ')
echo "[Phase 1] Done. Total IDs in seed file: $TOTAL_IDS"
echo ""

# Phase 2: Fetch movie details
echo "[Phase 2] Fetching movie details..."
CLOSE_SETTING=""
if [ "$NUM_MOVIES" -gt 0 ]; then
    CLOSE_SETTING="-s CLOSESPIDER_ITEMCOUNT=$NUM_MOVIES"
fi

scrapy crawl details \
    -a ids_file="$SCRIPT_DIR/$SEED_FILE" \
    -s MOVIES_DIR="$SCRIPT_DIR/$OUTPUT_DIR" \
    -s LOG_FILE="$LOG_DIR/details.log" \
    $CLOSE_SETTING

TOTAL_MOVIES=$(find "$SCRIPT_DIR/$OUTPUT_DIR" -name "*.json" | wc -l | tr -d ' ')
echo ""
echo "=== Crawl Complete ==="
echo "Total movies saved: $TOTAL_MOVIES"
echo "Output directory  : $OUTPUT_DIR"
echo "Logs              : $LOG_DIR/"
