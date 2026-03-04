"""
Details Spider - Phase 2

Fetches full movie details including credits and reviews for each discovered movie ID.
Uses callback chaining to merge multiple API responses into a single MovieItem.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy import signals
from tmdb_crawler.items import MovieItem


class DetailsSpider(scrapy.Spider):
    name = "details"
    allowed_domains = ["api.themoviedb.org"]

    def __init__(self, ids_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids_file = ids_file or "../data/movie_ids.jsonl"
        self.stats = {
            "total_ids": 0,
            "skipped_existing": 0,
            "fetched": 0,
            "failed": 0,
        }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        """Log final statistics."""
        self.logger.info(f"Details fetch complete: {self.stats}")

    def start_requests(self):
        """Load movie IDs and generate detail requests."""
        api_key = self.settings.get("TMDB_API_KEY")
        base_url = self.settings.get("TMDB_BASE_URL")
        movies_dir = Path(self.settings.get("MOVIES_DIR", "../data/movies"))

        # Load movie IDs from discovery output
        movie_ids = self._load_movie_ids()
        self.stats["total_ids"] = len(movie_ids)
        self.logger.info(f"Loaded {len(movie_ids)} movie IDs to process")

        for movie_id in movie_ids:
            # Skip if already crawled (resume support)
            subdir = str(movie_id // 1000)
            filepath = movies_dir / subdir / f"{movie_id}.json"
            if filepath.exists():
                self.stats["skipped_existing"] += 1
                continue

            url = f"{base_url}/movie/{movie_id}?api_key={api_key}"
            yield scrapy.Request(
                url,
                callback=self.parse_movie,
                meta={"movie_id": movie_id},
                errback=self.handle_error,
            )

    def _load_movie_ids(self):
        """Load movie IDs from the JSONL file produced by discover spider."""
        movie_ids = []
        ids_path = Path(self.ids_file)

        if not ids_path.exists():
            self.logger.error(f"Movie IDs file not found: {ids_path}")
            return movie_ids

        with open(ids_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    movie_id = data.get("movie_id")
                    if movie_id:
                        movie_ids.append(movie_id)
                except json.JSONDecodeError:
                    continue

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for mid in movie_ids:
            if mid not in seen:
                seen.add(mid)
                unique_ids.append(mid)

        return unique_ids

    def parse_movie(self, response):
        """Parse movie details and chain request for credits."""
        movie_id = response.meta["movie_id"]

        try:
            movie_data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse movie {movie_id}")
            self.stats["failed"] += 1
            return

        # Check for API error
        if "status_code" in movie_data and movie_data.get("success") is False:
            self.logger.warning(f"API error for movie {movie_id}: {movie_data.get('status_message')}")
            self.stats["failed"] += 1
            return

        # Chain request for credits
        api_key = self.settings.get("TMDB_API_KEY")
        base_url = self.settings.get("TMDB_BASE_URL")
        credits_url = f"{base_url}/movie/{movie_id}/credits?api_key={api_key}"

        yield scrapy.Request(
            credits_url,
            callback=self.parse_credits,
            meta={"movie_id": movie_id, "movie_data": movie_data},
            errback=self.handle_error,
        )

    def parse_credits(self, response):
        """Parse credits and chain request for reviews."""
        movie_id = response.meta["movie_id"]
        movie_data = response.meta["movie_data"]

        try:
            credits_data = json.loads(response.text)
        except json.JSONDecodeError:
            credits_data = {}

        # Extract top 20 cast members
        cast = credits_data.get("cast", [])[:20]
        movie_data["cast"] = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "character": c.get("character"),
                "order": c.get("order"),
            }
            for c in cast
        ]

        # Extract key crew members (directors, writers, producers)
        key_jobs = {"Director", "Writer", "Screenplay", "Producer", "Executive Producer"}
        crew = credits_data.get("crew", [])
        movie_data["crew"] = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "job": c.get("job"),
                "department": c.get("department"),
            }
            for c in crew
            if c.get("job") in key_jobs
        ]

        # Chain request for reviews
        api_key = self.settings.get("TMDB_API_KEY")
        base_url = self.settings.get("TMDB_BASE_URL")
        reviews_url = f"{base_url}/movie/{movie_id}/reviews?api_key={api_key}"

        yield scrapy.Request(
            reviews_url,
            callback=self.parse_reviews,
            meta={"movie_id": movie_id, "movie_data": movie_data},
            errback=self.handle_error,
        )

    def parse_reviews(self, response):
        """Parse reviews and yield final MovieItem."""
        movie_id = response.meta["movie_id"]
        movie_data = response.meta["movie_data"]

        try:
            reviews_data = json.loads(response.text)
        except json.JSONDecodeError:
            reviews_data = {}

        # Extract up to 10 reviews (get as many as available, up to 10)
        reviews = reviews_data.get("results", [])[:10]
        movie_data["reviews"] = [
            {
                "id": r.get("id"),
                "author": r.get("author"),
                "author_username": r.get("author_details", {}).get("username"),
                "content": r.get("content"),
                "rating": r.get("author_details", {}).get("rating"),
                "created_at": r.get("created_at"),
            }
            for r in reviews
        ]
        movie_data["review_count"] = len(movie_data["reviews"])

        # Add crawl metadata
        movie_data["crawled_at"] = datetime.utcnow().isoformat() + "Z"

        # Create and yield MovieItem
        item = MovieItem(
            id=movie_data.get("id"),
            imdb_id=movie_data.get("imdb_id"),
            title=movie_data.get("title"),
            original_title=movie_data.get("original_title"),
            original_language=movie_data.get("original_language"),
            overview=movie_data.get("overview"),
            tagline=movie_data.get("tagline"),
            release_date=movie_data.get("release_date"),
            status=movie_data.get("status"),
            vote_average=movie_data.get("vote_average"),
            vote_count=movie_data.get("vote_count"),
            popularity=movie_data.get("popularity"),
            runtime=movie_data.get("runtime"),
            budget=movie_data.get("budget"),
            revenue=movie_data.get("revenue"),
            adult=movie_data.get("adult"),
            genres=movie_data.get("genres", []),
            cast=movie_data.get("cast", []),
            crew=movie_data.get("crew", []),
            reviews=movie_data.get("reviews", []),
            review_count=movie_data.get("review_count", 0),
            poster_path=movie_data.get("poster_path"),
            backdrop_path=movie_data.get("backdrop_path"),
            production_countries=movie_data.get("production_countries", []),
            origin_country=movie_data.get("origin_country", []),
            homepage=movie_data.get("homepage"),
            crawled_at=movie_data.get("crawled_at"),
        )

        self.stats["fetched"] += 1

        # Log progress periodically
        if self.stats["fetched"] % 1000 == 0:
            self.logger.info(
                f"Progress: {self.stats['fetched']} movies fetched, "
                f"{self.stats['failed']} failed"
            )

        yield item

    def handle_error(self, failure):
        """Handle request errors."""
        movie_id = failure.request.meta.get("movie_id", "unknown")
        self.logger.error(f"Request failed for movie {movie_id}: {failure.value}")
        self.stats["failed"] += 1
