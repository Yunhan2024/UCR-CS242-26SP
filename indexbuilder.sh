#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./indexbuilder.sh <input_path> <analyzer_option> [extra_build_es_index_args...]

Arguments:
  input_path         Path to .zip / directory / .json / .jsonl
  analyzer_option    english_stem | english_no_stem | standard

Environment variables (optional):
  ES_URL             default: http://localhost:9200
  INDEX_NAME         default: tmdb_movies_v1
  THREADS            default: 6
  CHUNK_SIZE         default: 800
  QUEUE_SIZE         default: 12
  LOG_EVERY          default: 10000
  SOURCE_SUBPATH     default: data/movies
  INCLUDE_JSONL      1 to include .jsonl files (default: 0)
  DRY_RUN            1 for dry-run (default: 0)
  RECREATE_INDEX     1 to recreate index when DRY_RUN=0 (default: 1)
  ES_USER            Elasticsearch username
  ES_PASSWORD        Elasticsearch password
  ES_API_KEY         Elasticsearch API key (takes precedence over user/password)
  REPORT_PATH        Custom report output path

Examples:
  ./indexbuilder.sh /bigdata/renlab/rui001/IR/data.zip english_stem
  DRY_RUN=1 ./indexbuilder.sh /bigdata/renlab/rui001/IR/data.zip english_no_stem
  ES_URL=http://localhost:9200 INDEX_NAME=tmdb_movies_v2 ./indexbuilder.sh /path/to/data standard
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

INPUT_PATH="$1"
ANALYZER_OPTION="$2"
shift 2

case "$ANALYZER_OPTION" in
  english_stem|english_no_stem|standard) ;;
  *)
    echo "Invalid analyzer option: $ANALYZER_OPTION" >&2
    usage
    exit 2
    ;;
esac

if [[ ! -e "$INPUT_PATH" ]]; then
  echo "Input path does not exist: $INPUT_PATH" >&2
  exit 3
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ES_URL="${ES_URL:-http://localhost:9200}"
INDEX_NAME="${INDEX_NAME:-tmdb_movies_v1}"
THREADS="${THREADS:-6}"
CHUNK_SIZE="${CHUNK_SIZE:-800}"
QUEUE_SIZE="${QUEUE_SIZE:-12}"
LOG_EVERY="${LOG_EVERY:-10000}"
SOURCE_SUBPATH="${SOURCE_SUBPATH:-data/movies}"
INCLUDE_JSONL="${INCLUDE_JSONL:-0}"
DRY_RUN="${DRY_RUN:-0}"
RECREATE_INDEX="${RECREATE_INDEX:-1}"
USER_PASSED_DRY_RUN="0"
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    USER_PASSED_DRY_RUN="1"
    break
  fi
done

CMD=(
  python3 a2_index/build_es_index.py
  --source "$INPUT_PATH"
  --analyzer-option "$ANALYZER_OPTION"
  --es-url "$ES_URL"
  --index-name "$INDEX_NAME"
  --threads "$THREADS"
  --chunk-size "$CHUNK_SIZE"
  --queue-size "$QUEUE_SIZE"
  --log-every "$LOG_EVERY"
)

if [[ -n "$SOURCE_SUBPATH" ]]; then
  CMD+=(--source-subpath "$SOURCE_SUBPATH")
fi

if [[ "$INCLUDE_JSONL" == "1" ]]; then
  CMD+=(--include-jsonl)
fi

if [[ "$DRY_RUN" == "1" && "$USER_PASSED_DRY_RUN" == "0" ]]; then
  CMD+=(--dry-run)
fi

if [[ "$DRY_RUN" != "1" && "$USER_PASSED_DRY_RUN" == "0" && "$RECREATE_INDEX" == "1" ]]; then
  CMD+=(--recreate-index)
fi

if [[ -n "${ES_API_KEY:-}" ]]; then
  CMD+=(--api-key "$ES_API_KEY")
elif [[ -n "${ES_USER:-}" ]]; then
  CMD+=(--es-user "$ES_USER" --es-password "${ES_PASSWORD:-}")
fi

if [[ -n "${REPORT_PATH:-}" ]]; then
  CMD+=(--report-path "$REPORT_PATH")
fi

if [[ $# -gt 0 ]]; then
  CMD+=("$@")
fi

echo "[indexbuilder] Running: ${CMD[*]}"
exec "${CMD[@]}"
