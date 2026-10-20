import scrapy


class BookItem(scrapy.Item):
    """Container for the data collected about a single book."""

    title = scrapy.Field()
    price = scrapy.Field()
    availability = scrapy.Field()
    product_url = scrapy.Field()
    image_url = scrapy.Field()
    category = scrapy.Field()
