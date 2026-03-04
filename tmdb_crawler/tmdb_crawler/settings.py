"""
Scrapy settings for TMDB crawler.
"""

import os

# Project identity
BOT_NAME = "tmdb_crawler"
SPIDER_MODULES = ["tmdb_crawler.spiders"]
NEWSPIDER_MODULE = "tmdb_crawler.spiders"

# TMDB API Configuration
TMDB_API_KEY = [
    os.getenv("TMDB_API_KEY"),
    os.getenv("TMDB_API_KEY_2"),
    os.getenv("TMDB_API_KEY_3"),
]
TMDB_API_KEY = [key for key in TMDB_API_KEY if key]

if not TMDB_API_KEY:
    TMDB_API_KEY = ["your_api_key_here"]
    
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Crawl responsibly - identify yourself
USER_AGENT = "TMDB-Crawler/1.0 (CS242 Search Engine Project; +https://github.com)"

# Obey robots.txt (TMDB API doesn't use this, but good practice)
ROBOTSTXT_OBEY = False

# Rate limiting - TMDB allows ~50 req/sec, we use 16 to be safe
CONCURRENT_REQUESTS = 32
DOWNLOAD_DELAY = 0.1  # 100ms between requests
CONCURRENT_REQUESTS_PER_DOMAIN = 32

# Auto-throttle for adaptive rate limiting
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.1
AUTOTHROTTLE_MAX_DELAY = 2.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 32
AUTOTHROTTLE_DEBUG = False

# Retry configuration
RETRY_ENABLED = True
RETRY_TIMES = 10
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]

# Timeouts
DOWNLOAD_TIMEOUT = 30

# Disable cookies (not needed for API)
COOKIES_ENABLED = False

# Enable pipelines
ITEM_PIPELINES = {
    "tmdb_crawler.pipelines.DuplicateFilterPipeline": 100,
    "tmdb_crawler.pipelines.JsonWriterPipeline": 300,
    "tmdb_crawler.pipelines.StatsPipeline": 400,
}

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "../logs/crawler.log"

# Data storage paths
DATA_DIR = "../data"
MOVIES_DIR = "../data/movies"

# Request fingerprinting (Scrapy 2.7+)
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

# Twisted reactor (for better async performance)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Feed export settings (for discover spider output)
FEEDS = {
    "../data/movie_ids.jsonl": {
        "format": "jsonlines",
        "encoding": "utf-8",
        "overwrite": False,
    }
}
