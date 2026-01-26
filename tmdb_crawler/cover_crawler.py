"""
Cover Crawler - Download movie poster images from TMDB.

Reads movie data from data/movies/ and downloads poster images to data/covers/.
Uses asyncio for efficient concurrent downloads with rate limiting.

Usage:
    python cover_crawler.py [--size SIZE] [--concurrency N] [--limit N]

Options:
    --size SIZE       Image size: w92, w154, w185, w342, w500, w780, original (default: w500)
    --concurrency N   Number of concurrent downloads (default: 16)
    --limit N         Limit number of downloads (for testing)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

import aiohttp
from aiohttp import ClientTimeout

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# TMDB image base URL
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

# Valid image sizes
VALID_SIZES = ["w92", "w154", "w185", "w342", "w500", "w780", "original"]


class CoverCrawler:
    """Asynchronous movie cover downloader."""

    def __init__(self, movies_dir: Path, covers_dir: Path, size: str = "w500", concurrency: int = 16):
        self.movies_dir = movies_dir
        self.covers_dir = covers_dir
        self.size = size
        self.concurrency = concurrency
        self.semaphore = None

        # Statistics
        self.stats = {
            "total": 0,
            "downloaded": 0,
            "skipped_existing": 0,
            "skipped_no_poster": 0,
            "failed": 0,
        }

    def get_movies_to_download(self, limit: int = None) -> list:
        """Scan movie JSON files and return list of (movie_id, poster_path) tuples."""
        movies = []

        for subdir in self.movies_dir.iterdir():
            if not subdir.is_dir():
                continue

            for json_file in subdir.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    movie_id = data.get("id")
                    poster_path = data.get("poster_path")

                    if movie_id:
                        movies.append((movie_id, poster_path))

                        if limit and len(movies) >= limit:
                            return movies

                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to read {json_file}: {e}")

        return movies

    def get_cover_path(self, movie_id: int) -> Path:
        """Get the local file path for a movie cover."""
        subdir = str(movie_id // 1000)
        return self.covers_dir / subdir / f"{movie_id}.jpg"

    async def download_cover(self, session: aiohttp.ClientSession, movie_id: int, poster_path: str) -> bool:
        """Download a single movie cover."""
        async with self.semaphore:
            # Check if poster_path exists
            if not poster_path:
                self.stats["skipped_no_poster"] += 1
                return False

            # Check if already downloaded
            cover_path = self.get_cover_path(movie_id)
            if cover_path.exists():
                self.stats["skipped_existing"] += 1
                return True

            # Create directory if needed
            cover_path.parent.mkdir(parents=True, exist_ok=True)

            # Build image URL
            url = f"{TMDB_IMAGE_BASE_URL}/{self.size}{poster_path}"

            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()

                        # Write to file
                        with open(cover_path, "wb") as f:
                            f.write(content)

                        self.stats["downloaded"] += 1
                        return True
                    else:
                        logger.warning(f"Failed to download movie {movie_id}: HTTP {response.status}")
                        self.stats["failed"] += 1
                        return False

            except asyncio.TimeoutError:
                logger.warning(f"Timeout downloading movie {movie_id}")
                self.stats["failed"] += 1
                return False
            except Exception as e:
                logger.warning(f"Error downloading movie {movie_id}: {e}")
                self.stats["failed"] += 1
                return False

    async def run(self, limit: int = None):
        """Run the cover crawler."""
        logger.info(f"Scanning movies in {self.movies_dir}...")
        movies = self.get_movies_to_download(limit)
        self.stats["total"] = len(movies)
        logger.info(f"Found {len(movies)} movies to process")

        if not movies:
            logger.info("No movies to download")
            return

        # Create covers directory
        self.covers_dir.mkdir(parents=True, exist_ok=True)

        # Initialize semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(self.concurrency)

        # Configure timeout
        timeout = ClientTimeout(total=30)

        # Create session and download
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # Create download tasks
            tasks = [
                self.download_cover(session, movie_id, poster_path)
                for movie_id, poster_path in movies
            ]

            # Process with progress logging
            completed = 0
            for coro in asyncio.as_completed(tasks):
                await coro
                completed += 1

                # Log progress every 1000 downloads
                if completed % 1000 == 0:
                    logger.info(
                        f"Progress: {completed}/{len(movies)} "
                        f"(downloaded: {self.stats['downloaded']}, "
                        f"skipped: {self.stats['skipped_existing']}, "
                        f"failed: {self.stats['failed']})"
                    )

        # Final statistics
        logger.info("=" * 50)
        logger.info("Cover download complete!")
        logger.info(f"  Total movies: {self.stats['total']}")
        logger.info(f"  Downloaded: {self.stats['downloaded']}")
        logger.info(f"  Skipped (existing): {self.stats['skipped_existing']}")
        logger.info(f"  Skipped (no poster): {self.stats['skipped_no_poster']}")
        logger.info(f"  Failed: {self.stats['failed']}")

        # Save statistics
        stats_file = self.covers_dir / "cover_stats.json"
        self.stats["completed_at"] = datetime.utcnow().isoformat() + "Z"
        self.stats["image_size"] = self.size
        with open(stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)
        logger.info(f"Statistics saved to {stats_file}")


def main():
    parser = argparse.ArgumentParser(description="Download movie poster covers from TMDB")
    parser.add_argument(
        "--size",
        choices=VALID_SIZES,
        default="w500",
        help="Image size (default: w500)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=16,
        help="Number of concurrent downloads (default: 16)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of downloads (for testing)"
    )
    parser.add_argument(
        "--movies-dir",
        type=str,
        default="../data/movies",
        help="Path to movies data directory"
    )
    parser.add_argument(
        "--covers-dir",
        type=str,
        default="../data/covers",
        help="Path to output covers directory"
    )

    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    movies_dir = Path(args.movies_dir)
    covers_dir = Path(args.covers_dir)

    if not movies_dir.is_absolute():
        movies_dir = script_dir / movies_dir
    if not covers_dir.is_absolute():
        covers_dir = script_dir / covers_dir

    # Validate movies directory exists
    if not movies_dir.exists():
        logger.error(f"Movies directory not found: {movies_dir}")
        sys.exit(1)

    logger.info(f"Cover Crawler starting...")
    logger.info(f"  Movies dir: {movies_dir}")
    logger.info(f"  Covers dir: {covers_dir}")
    logger.info(f"  Image size: {args.size}")
    logger.info(f"  Concurrency: {args.concurrency}")

    # Run crawler
    crawler = CoverCrawler(
        movies_dir=movies_dir,
        covers_dir=covers_dir,
        size=args.size,
        concurrency=args.concurrency
    )

    asyncio.run(crawler.run(limit=args.limit))


if __name__ == "__main__":
    main()