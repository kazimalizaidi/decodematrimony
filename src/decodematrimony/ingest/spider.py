"""🌸 Scrapy spider for PUBLIC statistical tables (SBP/PBS pages you configure). ✨

Reads config/public_sources.json: [{"name": "...", "url": "...", "table_xpath": "//table[1]"}].
We never hardcode URLs we have not verified: you add them, you check the site's terms
and robots.txt (ROBOTSTXT_OBEY is on). Output: JSONL of raw table rows. 🧸
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import scrapy


class PublicTableSpider(scrapy.Spider):
    name = "public_tables"
    custom_settings: dict[str, Any] = {
        "ROBOTSTXT_OBEY": True, "DOWNLOAD_DELAY": 2.0, "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": "DecodeMatrimony-research (academic portfolio project)",
        "FEEDS": {"data/raw/public_tables.jsonl": {"format": "jsonlines", "overwrite": True}},
    }

    def __init__(self, config: str = "config/public_sources.json", **kw: Any) -> None:
        super().__init__(**kw)
        cfg = Path(config)
        if not cfg.exists():
            raise FileNotFoundError(f"💗 {cfg} not found; create it from the README instructions")
        self.sources: list[dict[str, str]] = json.loads(cfg.read_text(encoding="utf-8"))
        if not self.sources:
            raise ValueError("💗 no sources configured")

    def start_requests(self) -> Iterator[scrapy.Request]:
        for s in self.sources:
            yield scrapy.Request(s["url"], cb_kwargs={"src": s})

    def parse(self, response: scrapy.http.Response, src: dict[str, str]) -> Iterator[dict[str, Any]]:
        for i, tr in enumerate(response.xpath(f"{src['table_xpath']}//tr")):
            cells = [" ".join(td.xpath(".//text()").getall()).strip() for td in tr.xpath("./th|./td")]
            if any(cells):
                yield {"source": src["name"], "url": response.url, "row_index": i, "cells": cells}
