"""
TMDB Crawler Middlewares

Handles special HTTP responses and retry logic.
"""

import time
from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class RateLimitMiddleware(RetryMiddleware):
    """
    Handles TMDB rate limit responses (HTTP 429).
    Waits for the specified retry-after period before retrying.
    """

    def process_response(self, request, response, spider):
        if response.status == 429:
            # Rate limited - get retry-after header
            retry_after = response.headers.get("Retry-After", b"10")
            try:
                wait_time = int(retry_after)
            except (ValueError, TypeError):
                wait_time = 10

            spider.logger.warning(
                f"Rate limited, waiting {wait_time} seconds before retry"
            )
            time.sleep(wait_time)

            # Retry the request
            return self._retry(request, "rate_limited", spider) or response

        return response


class TmdbSpiderMiddleware:
    """
    Spider middleware for TMDB crawler.
    """

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        pass

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info(f"Spider opened: {spider.name}")


class TmdbDownloaderMiddleware:
    """
    Downloader middleware for TMDB crawler.
    """

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass

    def spider_opened(self, spider):
        spider.logger.info(f"Downloader middleware opened: {spider.name}")
