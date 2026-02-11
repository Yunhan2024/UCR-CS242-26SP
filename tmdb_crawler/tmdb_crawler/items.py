"""
TMDB Crawler Items

Defines the data structure for crawled movies.
"""

import scrapy


class MovieItem(scrapy.Item):
    """Data model for a movie with all required fields for indexing."""

    # Identifiers
    id = scrapy.Field()
    imdb_id = scrapy.Field()

    # Core info
    title = scrapy.Field()
    original_title = scrapy.Field()
    original_language = scrapy.Field()
    overview = scrapy.Field()
    tagline = scrapy.Field()

    # Dates & status
    release_date = scrapy.Field()
    status = scrapy.Field()

    # Ratings & popularity
    vote_average = scrapy.Field()
    vote_count = scrapy.Field()
    popularity = scrapy.Field()

    # Technical details
    runtime = scrapy.Field()
    budget = scrapy.Field()
    revenue = scrapy.Field()
    adult = scrapy.Field()

    # Classifications
    genres = scrapy.Field()  # List of {id, name}

    # Credits
    cast = scrapy.Field()  # List of {id, name, character, order}
    crew = scrapy.Field()  # List of {id, name, job, department}

    # User content
    reviews = scrapy.Field()  # List of {id, author, content, rating, created_at}, max 10
    review_count = scrapy.Field()  # Number of reviews fetched (0 if none)

    # Media paths
    poster_path = scrapy.Field()
    backdrop_path = scrapy.Field()
    homepage = scrapy.Field()

    # Crawler metadata
    crawled_at = scrapy.Field()


class MovieIdItem(scrapy.Item):
    """Lightweight item for Phase 1 discovery."""

    movie_id = scrapy.Field()
    vote_count = scrapy.Field()
    popularity = scrapy.Field()
