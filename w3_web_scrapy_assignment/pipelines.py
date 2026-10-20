import logging
import re
import sqlite3
import unicodedata
from pathlib import Path

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class CleaningPipeline:
    TEXT_FIELDS = ("title", "product_url", "image_url", "category")

    def process_item(self, item, spider):
        for field in self.TEXT_FIELDS:
            item[field] = self.clean_text(item.get(field))

        try:
            item["price"] = self.clean_price(item.get("price"))
        except ValueError as error:
            raise DropItem(
                f"Bad price for {item.get('product_url')}: {error}"
            ) from error

        item["availability"] = self.clean_availability(item.get("availability"))
        return item

    @staticmethod
    def clean_text(value):
        if value is None:
            return None
        value = unicodedata.normalize("NFC", str(value))
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def clean_price(value):
        number = re.sub(r"[^\d.]", "", str(value or ""))
        if not number:
            raise ValueError(f"no number found in {value!r}")
        return round(float(number), 2)

    @classmethod
    def clean_availability(cls, value):
        text = cls.clean_text(value) or ""
        return text.casefold().startswith("in stock")


class ValidationPipeline:
    REQUIRED_FIELDS = (
        "title",
        "price",
        "availability",
        "product_url",
        "image_url",
        "category",
    )

    def process_item(self, item, spider):
        missing = [
            field
            for field in self.REQUIRED_FIELDS
            if item.get(field) in (None, "")
        ]
        if missing:
            raise DropItem(
                f"Missing fields {missing} in {item.get('product_url')}"
            )

        if item["price"] < 0:
            raise DropItem(f"Negative price in {item['product_url']}")

        for field in ("product_url", "image_url"):
            if not item[field].startswith(("http://", "https://")):
                raise DropItem(
                    f"{field} is not an absolute URL in {item['product_url']}"
                )
        return item


class SQLitePipeline:
    CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS books (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            price        REAL    NOT NULL,
            availability INTEGER NOT NULL,
            product_url  TEXT    NOT NULL UNIQUE,
            image_url    TEXT    NOT NULL,
            category     TEXT    NOT NULL
        )
    """
    INSERT = """
        INSERT INTO books
            (title, price, availability, product_url, image_url, category)
        VALUES
            (:title, :price, :availability, :product_url, :image_url, :category)
    """

    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.connection = None

    @classmethod
    def from_crawler(cls, crawler):
        """Read DATABASE_PATH from settings, defaulting to 'books.db'."""
        return cls(crawler.settings.get("DATABASE_PATH", "books.db"))

    def open_spider(self, spider):
        """Open the database and empty the table so it mirrors this run."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        with self.connection:
            self.connection.execute(self.CREATE_TABLE)
            self.connection.execute("DELETE FROM books")
        logger.info("SQLite database ready at %s", self.database_path)

    def close_spider(self, spider):
        """Log how many books were stored and close the database."""
        if self.connection is None:
            return
        count = self.connection.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]
        logger.info("Stored %d books in the database", count)
        self.connection.close()

    def process_item(self, item, spider):
        try:
            with self.connection:
                self.connection.execute(self.INSERT, dict(item))
        except sqlite3.Error as error:
            logger.error("Database insert failed: %s", error)
            raise DropItem(f"Database insert failed: {error}") from error
        return item