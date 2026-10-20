from setuptools import setup, find_packages

setup(
    name="w3_web_scrapy_assignment",
    version="1.0",
    packages=find_packages(),
    entry_points={"scrapy": ["settings = w3_web_scrapy_assignment.settings"]},
)