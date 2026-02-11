"""
Discover Spider - Phase 1

Collects 200,000+ unique movie IDs from TMDB using multiple strategies:
1. Genre-based filtering (19 genres)
2. Year-based filtering (1970-2026)
3. Vote count ranges (to reduce overlap)
4. Language-based filtering (10 major languages)
"""

import json
import scrapy
from scrapy import signals
from tmdb_crawler.items import MovieIdItem


class DiscoverSpider(scrapy.Spider):
    name = "discover"
    allowed_domains = ["api.themoviedb.org"]

    # All TMDB genre IDs
    GENRES = [28, 12, 16, 35, 80, 99, 18, 10751, 14, 36, 27, 10402, 9648, 10749, 878, 10770, 53, 10752, 37]

    # Year ranges for fine-grained discovery
    YEARS = list(range(1970, 2027))  # 1970-2026

    # Vote count ranges to segment results
    VOTE_RANGES = [
        (0, 10),
        (10, 100),
        (100, 1000),
        (1000, 100000),
    ]

    # Major languages for additional coverage
    LANGUAGES = ["en", "es", "fr", "de", "ja", "ko", "zh", "hi", "it", "pt"]

    def __init__(self, strategy="all", *args, **kwargs):
        """
        Args:
            strategy: 'genre', 'year', 'language', or 'all'
        """
        super().__init__(*args, **kwargs)
        self.strategy = strategy
        self.seen_ids = set()
        self.stats = {
            "total_discovered": 0,
            "unique_discovered": 0,
            "duplicates_skipped": 0,
        }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        """Log final statistics when spider closes."""
        self.logger.info(f"Discovery complete: {self.stats}")

    def start_requests(self):
        """Generate discovery requests based on strategy."""
        api_key = self.settings.get("TMDB_API_KEY")
        base_url = self.settings.get("TMDB_BASE_URL")

        if self.strategy in ["genre", "all"]:
            # Strategy 1: Genre + Vote range combinations
            for genre_id in self.GENRES:
                for vote_min, vote_max in self.VOTE_RANGES:
                    for page in range(1, 501):
                        url = (
                            f"{base_url}/discover/movie"
                            f"?api_key={api_key}"
                            f"&with_genres={genre_id}"
                            f"&vote_count.gte={vote_min}"
                            f"&vote_count.lte={vote_max}"
                            f"&sort_by=popularity.desc"
                            f"&page={page}"
                        )
                        yield scrapy.Request(
                            url,
                            callback=self.parse,
                            meta={"strategy": f"genre_{genre_id}_vote_{vote_min}_{vote_max}", "page": page},
                            dont_filter=True,
                        )

        if self.strategy in ["year", "all"]:
            # Strategy 2: Year-based (single year for precision)
            for year in self.YEARS:
                for page in range(1, 501):
                    url = (
                        f"{base_url}/discover/movie"
                        f"?api_key={api_key}"
                        f"&primary_release_year={year}"
                        f"&sort_by=popularity.desc"
                        f"&page={page}"
                    )
                    yield scrapy.Request(
                        url,
                        callback=self.parse,
                        meta={"strategy": f"year_{year}", "page": page},
                        dont_filter=True,
                    )

        if self.strategy in ["language", "all"]:
            # Strategy 3: Language-based
            for lang in self.LANGUAGES:
                for page in range(1, 501):
                    url = (
                        f"{base_url}/discover/movie"
                        f"?api_key={api_key}"
                        f"&with_original_language={lang}"
                        f"&sort_by=popularity.desc"
                        f"&page={page}"
                    )
                    yield scrapy.Request(
                        url,
                        callback=self.parse,
                        meta={"strategy": f"lang_{lang}", "page": page},
                        dont_filter=True,
                    )

    def parse(self, response):
        """Parse discover response and yield unique movie IDs."""
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON from {response.url}")
            return

        results = data.get("results", [])
        total_pages = data.get("total_pages", 0)
        current_page = response.meta.get("page", 0)

        # Stop early if we've exceeded available pages
        if current_page > total_pages:
            return

        for movie in results:
            movie_id = movie.get("id")
            if not movie_id:
                continue

            self.stats["total_discovered"] += 1

            # Deduplicate
            if movie_id in self.seen_ids:
                self.stats["duplicates_skipped"] += 1
                continue

            self.seen_ids.add(movie_id)
            self.stats["unique_discovered"] += 1

            yield MovieIdItem(
                movie_id=movie_id,
                vote_count=movie.get("vote_count", 0),
                popularity=movie.get("popularity", 0),
            )

        # Log progress periodically
        if self.stats["unique_discovered"] % 10000 == 0:
            self.logger.info(
                f"Progress: {self.stats['unique_discovered']} unique movies discovered "
                f"(duplicates: {self.stats['duplicates_skipped']})"
            )
