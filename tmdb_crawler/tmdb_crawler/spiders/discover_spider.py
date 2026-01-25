"""
Discover Spider - Phase 1

Collects movie IDs from TMDB's discover endpoint.
Uses multiple strategies to overcome the 500-page limit and collect 50,000+ unique movies.
"""

import json
import scrapy
from scrapy import signals
from tmdb_crawler.items import MovieIdItem


class DiscoverSpider(scrapy.Spider):
    name = "discover"
    allowed_domains = ["api.themoviedb.org"]

    # Discovery strategies to get more than 10,000 movies
    SORT_OPTIONS = [
        "popularity.desc",
        "vote_count.desc",
        "revenue.desc",
        "primary_release_date.desc",
    ]

    YEAR_RANGES = [
        (1900, 1990),
        (1991, 2000),
        (2001, 2005),
        (2006, 2010),
        (2011, 2015),
        (2016, 2018),
        (2019, 2021),
        (2022, 2025),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        """Generate all discovery requests."""
        api_key = self.settings.get("TMDB_API_KEY")
        base_url = self.settings.get("TMDB_BASE_URL")

        # Strategy 1: Different sort orders (each can yield up to 10,000 movies)
        for sort_by in self.SORT_OPTIONS:
            for page in range(1, 501):  # 500 pages max per query
                url = (
                    f"{base_url}/discover/movie"
                    f"?api_key={api_key}"
                    f"&sort_by={sort_by}"
                    f"&vote_count.gte=10"  # Filter low-quality entries
                    f"&page={page}"
                )
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    meta={"strategy": f"sort_{sort_by}", "page": page},
                    dont_filter=True,
                )

        # Strategy 2: Year-based filtering
        for start_year, end_year in self.YEAR_RANGES:
            for page in range(1, 201):  # 200 pages per year range
                url = (
                    f"{base_url}/discover/movie"
                    f"?api_key={api_key}"
                    f"&primary_release_date.gte={start_year}-01-01"
                    f"&primary_release_date.lte={end_year}-12-31"
                    f"&sort_by=popularity.desc"
                    f"&vote_count.gte=5"
                    f"&page={page}"
                )
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    meta={"strategy": f"year_{start_year}_{end_year}", "page": page},
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
        if self.stats["unique_discovered"] % 5000 == 0:
            self.logger.info(
                f"Progress: {self.stats['unique_discovered']} unique movies discovered"
            )
