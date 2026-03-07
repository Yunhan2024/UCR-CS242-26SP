#!/bin/bash
# ──────────────────────────────────────────────────────
# start_app.sh — One-click startup for the TMDB Search Engine
#
# Place this script in the project root (UCR-CS242-26SP/).
# Usage: ./start_app.sh
# ──────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/APP"
DATA_DIR="$SCRIPT_DIR/data/movies"
MODELS_DIR="$APP_DIR/models"
ES_INDEX="tmdb_movies_v2"
ES_URL="http://localhost:9200"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "  TMDB Movie Search Engine — Startup"
echo "=================================================="

# ── 1. Check Python ──────────────────────────────────
echo ""
echo -e "${YELLOW}[1/6] Checking Python...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}Python not found. Please install Python 3.8+.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1)
echo -e "${GREEN}  ✓ $PYTHON_VERSION${NC}"

# ── 2. Check data folder ────────────────────────────
echo -e "${YELLOW}[2/6] Checking crawled data...${NC}"
if [ ! -d "$DATA_DIR" ]; then
    echo -e "${RED}  ✗ data/movies/ folder not found!${NC}"
    echo "    The crawled movie JSON files must be in: $DATA_DIR"
    echo "    If the data is in a zip file, extract it first."
    exit 1
fi
FILE_COUNT=$(find "$DATA_DIR" -name "*.json" | head -1000 | wc -l | tr -d ' ')
echo -e "${GREEN}  ✓ Found movie data ($FILE_COUNT+ JSON files)${NC}"

# ── 3. Check BERT model files ───────────────────────
echo -e "${YELLOW}[3/6] Checking BERT index files...${NC}"
BERT_OK=true
if [ ! -f "$MODELS_DIR/movie_faiss.index" ]; then
    echo -e "${RED}  ✗ APP/models/movie_faiss.index not found${NC}"
    BERT_OK=false
fi
if [ ! -f "$MODELS_DIR/movie_metadata.pkl" ]; then
    echo -e "${RED}  ✗ APP/models/movie_metadata.pkl not found${NC}"
    BERT_OK=false
fi
if [ "$BERT_OK" = true ]; then
    echo -e "${GREEN}  ✓ BERT index files present${NC}"
else
    echo -e "${YELLOW}  ⚠ BERT files missing — BERT search will be unavailable.${NC}"
    echo "    Get them from whoever ran CS242_BERT_Indexing.ipynb."
fi

# ── 4. Install dependencies ─────────────────────────
echo -e "${YELLOW}[4/6] Installing Python dependencies...${NC}"
pip install -q -r "$APP_DIR/requirements.txt" 2>&1 | tail -1
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

# ── 5. Check / Start Elasticsearch ──────────────────
echo -e "${YELLOW}[5/6] Checking Elasticsearch...${NC}"
ES_RUNNING=false
if curl -s "$ES_URL" > /dev/null 2>&1; then
    ES_RUNNING=true
    echo -e "${GREEN}  ✓ Elasticsearch is running at $ES_URL${NC}"
else
    echo "  Elasticsearch is not running."
    # Try to start via Docker
    if command -v docker &> /dev/null; then
        echo "  Attempting to start via Docker..."
        # Check if container exists but is stopped
        if docker ps -a --format '{{.Names}}' | grep -q '^elasticsearch$'; then
            docker start elasticsearch > /dev/null 2>&1
            echo "  Restarted existing container."
        else
            docker run -d \
                --name elasticsearch \
                -p 9200:9200 \
                -e "discovery.type=single-node" \
                -e "xpack.security.enabled=false" \
                -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
                docker.elastic.co/elasticsearch/elasticsearch:8.17.0 \
                > /dev/null 2>&1
            echo "  Created and started new ES container."
        fi
        # Wait for ES to be ready
        echo -n "  Waiting for ES to start"
        for i in $(seq 1 30); do
            if curl -s "$ES_URL" > /dev/null 2>&1; then
                ES_RUNNING=true
                break
            fi
            echo -n "."
            sleep 2
        done
        echo ""
        if [ "$ES_RUNNING" = true ]; then
            echo -e "${GREEN}  ✓ Elasticsearch started${NC}"
        else
            echo -e "${YELLOW}  ⚠ ES failed to start within 60s. ES search will be unavailable.${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ Docker not found. Install Docker Desktop to run Elasticsearch.${NC}"
        echo "    BERT search will still work without ES."
    fi
fi

# ── 6. Check if ES index exists, build if needed ────
if [ "$ES_RUNNING" = true ]; then
    echo -e "${YELLOW}[6/6] Checking ES index...${NC}"
    INDEX_COUNT=$(curl -s "$ES_URL/$ES_INDEX/_count" 2>/dev/null | python -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")

    if [ "$INDEX_COUNT" -gt 0 ] 2>/dev/null; then
        echo -e "${GREEN}  ✓ Index '$ES_INDEX' has $INDEX_COUNT documents${NC}"
    else
        echo "  Index '$ES_INDEX' not found or empty."
        echo "  Building ES index from data/movies/ (this takes ~45 seconds)..."
        cd "$APP_DIR"
        python build_es_index.py \
            --source "$DATA_DIR" \
            --analyzer-option english_stem \
            --es-url "$ES_URL" \
            --index-name "$ES_INDEX" \
            --recreate-index \
            --threads 6 \
            --chunk-size 800 \
            --queue-size 12
        echo -e "${GREEN}  ✓ ES index built${NC}"
        cd "$SCRIPT_DIR"
    fi
else
    echo -e "${YELLOW}[6/6] Skipping ES index check (ES not running)${NC}"
fi

# ── Launch ───────────────────────────────────────────
echo ""
echo "=================================================="
echo "  Starting Flask server..."
echo "=================================================="
cd "$APP_DIR"
exec python app.py