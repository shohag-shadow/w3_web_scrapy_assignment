import random
from urllib.parse import urlparse

import scrapy

from w3_web_scrapy_assignment.items import BookItem


class BooksSpider(scrapy.Spider):
    name = "books"

    default_start_url = "https://books.toscrape.com/index.html"
    min_categories = 5
    max_categories = 10
    books_per_category = 5

    def __init__(self, start_url=None, seed=None, **kwargs):
        super().__init__(**kwargs)
        self.start_urls = [start_url or self.default_start_url]
        self.allowed_domains = [urlparse(self.start_urls[0]).hostname]
        # A dedicated RNG. Passing a seed makes choices repeatable.
        self.rng = random.Random(int(seed) if seed else None)

    def parse(self, response):
        categories = []
        links = response.css("div.side_categories ul.nav-list > li > ul > li > a")
        for link in links:
            name = link.css("::text").get("")
            name = " ".join(name.split())
            url = response.urljoin(link.attrib["href"])
            categories.append({"name": name, "url": url})

        self.logger.info("Found %d categories", len(categories))
        if not categories:
            self.logger.error("No categories found - did the page layout change?")
            return

        self.rng.shuffle(categories)
        number_to_pick = self.rng.randint(self.min_categories, self.max_categories)
        number_to_pick = min(number_to_pick, len(categories))
        chosen = categories[:number_to_pick]

        self.logger.info(
            "Selected %d categories: %s",
            len(chosen),
            ", ".join(c["name"] for c in chosen),
        )

        for category in chosen:
            yield scrapy.Request(
                category["url"],
                callback=self.parse_category,
                errback=self.on_category_error,
                cb_kwargs={"category": category, "book_urls": []},
            )

    def parse_category(self, response, category, book_urls):
        new_links = response.css("article.product_pod h3 a::attr(href)").getall()
        for href in new_links:
            book_urls.append(response.urljoin(href))

        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page),
                callback=self.parse_category,
                errback=self.on_category_error,
                cb_kwargs={"category": category, "book_urls": list(book_urls)},
            )
            return

        unique_urls = []
        for url in book_urls:
            if url not in unique_urls:
                unique_urls.append(url)

        if not unique_urls:
            self.logger.warning(
                "Category '%s' has no books, skipping", category["name"]
            )
            return

        take = min(self.books_per_category, len(unique_urls))
        chosen = self.rng.sample(unique_urls, take)
        self.logger.info(
            "Category '%s': %d books found, %d selected",
            category["name"],
            len(unique_urls),
            take,
        )

        for url in chosen:
            yield scrapy.Request(
                url,
                callback=self.parse_book,
                errback=self.on_book_error,
                cb_kwargs={"category": category["name"]},
            )

    def parse_book(self, response, category):
        item = BookItem()

        image = response.css("#product_gallery img::attr(src)").get()

        item["title"] = response.css("div.product_main h1::text").get()
        item["price"] = response.css("div.product_main p.price_color::text").get()

        availability_parts = response.css(
            "div.product_main p.availability::text"
        ).getall()
        item["availability"] = " ".join(availability_parts)

        item["product_url"] = response.url
        item["image_url"] = response.urljoin(image) if image else None
        item["category"] = category

        yield item

    def on_category_error(self, failure):
        category = failure.request.cb_kwargs["category"]
        self.logger.error(
            "Category '%s' failed: %s", category["name"], failure.value
        )

    def on_book_error(self, failure):
        self.logger.error(
            "Book request failed %s: %s", failure.request.url, failure.value
        )