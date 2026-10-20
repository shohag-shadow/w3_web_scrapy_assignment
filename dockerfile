
FROM python:3.12-slim AS builder

WORKDIR /workdir


RUN pip install --no-cache-dir scrapyd-client

COPY . .
RUN scrapyd-deploy --build-egg=books.egg

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
    && pip install --no-cache-dir scrapyd \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY scrapyd.conf /etc/scrapyd/


RUN mkdir -p /src/eggs/w3_web_scrapy_assignment
COPY --from=builder /workdir/books.egg /src/eggs/w3_web_scrapy_assignment/1.egg


VOLUME ["/var/lib/scrapyd"]

EXPOSE 6800

ENTRYPOINT ["scrapyd", "--pidfile="]