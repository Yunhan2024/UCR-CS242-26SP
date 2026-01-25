"""
TMDB Crawler Pipelines

Handles data processing and storage of crawled items.
"""

import json
import os
from pathlib import Path

from itemadapter import ItemAdapter
from tmdb_crawler.items import MovieItem, MovieIdItem


class JsonWriterPipeline:
    """
    Writes MovieItem objects to individual JSON files.
    Files are organized into subdirectories to avoid filesystem limits.
    """

    def __init__(self, movies_dir):
        self.movies_dir = Path(movies_dir)
        self.items_saved = 0

    @classmethod
    def from_crawler(cls, crawler):
        movies_dir = crawler.settings.get("MOVIES_DIR", "../data/movies")
        return cls(movies_dir)

    def open_spider(self, spider):
        """Ensure output directory exists."""
        self.movies_dir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item, spider):
        """Save MovieItem to JSON file."""
        # Only process MovieItem, not MovieIdItem
        if not isinstance(item, MovieItem):
            return item

        adapter = ItemAdapter(item)
        movie_id = adapter.get("id")

        if not movie_id:
            spider.logger.warning("Skipping item with no ID")
            return item

        # Organize into subdirectories (e.g., movies/550/550.json for movie 550)
        # Using movie_id // 1000 to create ~1000 files per directory
        subdir = str(movie_id // 1000)
        output_dir = self.movies_dir / subdir
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / f"{movie_id}.json"

        # Write JSON with pretty formatting
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(adapter.asdict(), f, ensure_ascii=False, indent=2)

        self.items_saved += 1
        return item

    def close_spider(self, spider):
        """Log final count."""
        spider.logger.info(f"JsonWriterPipeline: Saved {self.items_saved} movies to {self.movies_dir}")


class StatsPipeline:
    """
    Tracks and reports crawl statistics.
    """

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.stats = {
            "movies_processed": 0,
            "movies_with_reviews": 0,
            "total_reviews": 0,
            "total_cast": 0,
            "total_crew": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        data_dir = crawler.settings.get("DATA_DIR", "../data")
        return cls(data_dir)

    def process_item(self, item, spider):
        """Collect statistics from each item."""
        if not isinstance(item, MovieItem):
            return item

        adapter = ItemAdapter(item)

        self.stats["movies_processed"] += 1

        reviews = adapter.get("reviews", [])
        if reviews:
            self.stats["movies_with_reviews"] += 1
            self.stats["total_reviews"] += len(reviews)

        cast = adapter.get("cast", [])
        self.stats["total_cast"] += len(cast)

        crew = adapter.get("crew", [])
        self.stats["total_crew"] += len(crew)

        return item

    def close_spider(self, spider):
        """Log and save final statistics."""
        spider.logger.info(f"Crawl Statistics: {self.stats}")

        # Calculate storage size
        movies_dir = self.data_dir / "movies"
        if movies_dir.exists():
            total_size = sum(f.stat().st_size for f in movies_dir.rglob("*.json"))
            size_mb = total_size / (1024 * 1024)
            self.stats["total_size_bytes"] = total_size
            self.stats["total_size_mb"] = round(size_mb, 2)
            spider.logger.info(f"Total data size: {size_mb:.2f} MB")

        # Save stats to file
        stats_file = self.data_dir / "crawl_stats.json"
        with open(stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)


class DuplicateFilterPipeline:
    """
    Filters duplicate items based on movie ID.
    Useful when running multiple discovery strategies.
    """

    def __init__(self):
        self.seen_ids = set()
        self.duplicates = 0

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Handle both MovieItem and MovieIdItem
        movie_id = adapter.get("id") or adapter.get("movie_id")

        if movie_id in self.seen_ids:
            self.duplicates += 1
            raise DropItem(f"Duplicate movie ID: {movie_id}")

        self.seen_ids.add(movie_id)
        return item

    def close_spider(self, spider):
        spider.logger.info(f"DuplicateFilterPipeline: Filtered {self.duplicates} duplicates")


class DropItem(Exception):
    """Exception to drop an item from the pipeline."""
    pass
