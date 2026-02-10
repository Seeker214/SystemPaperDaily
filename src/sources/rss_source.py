"""
RSS 数据源 — 解析 USENIX / 会议级 RSS Feed。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from email.utils import parsedate_to_datetime

from .base import Paper, PaperSource

logger = logging.getLogger(__name__)


def _parse_pub_date(entry) -> Optional[datetime]:
    """尝试从 RSS entry 中解析发布时间。"""
    for field in ("published", "updated", "created"):
        raw = getattr(entry, field, None) or entry.get(field)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass

    # feedparser 解析的 struct_time
    for field in ("published_parsed", "updated_parsed"):
        st = entry.get(field)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    return None


def _entry_id(entry) -> str:
    """为 RSS 条目生成稳定 ID。"""
    raw_id = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]


class RSSSource(PaperSource):
    """从 RSS Feed URL 列表获取论文。"""

    def __init__(
        self,
        feed_urls: List[str],
        recent_hours: int = 72,
    ):
        self.feed_urls = feed_urls
        self.recent_hours = recent_hours

    def fetch(self) -> List[Paper]:
        papers: List[Paper] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recent_hours)

        for url in self.feed_urls:
            logger.info("[RSSSource] 正在解析 Feed: %s", url)
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                logger.error("[RSSSource] 解析失败 %s: %s", url, e)
                continue

            if feed.bozo and feed.bozo_exception:
                logger.warning("[RSSSource] Feed 解析警告 (%s): %s", url, feed.bozo_exception)

            for entry in feed.entries:
                pub_date = _parse_pub_date(entry)
                if pub_date and pub_date < cutoff:
                    continue

                title = (entry.get("title") or "Untitled").strip()
                abstract = (entry.get("summary") or entry.get("description") or "").strip()
                link = entry.get("link") or ""

                # 尝试提取 PDF 链接
                pdf_url = ""
                for enc in entry.get("links", []):
                    if enc.get("type", "").endswith("pdf") or enc.get("href", "").endswith(".pdf"):
                        pdf_url = enc["href"]
                        break

                paper = Paper(
                    paper_id=f"rss-{_entry_id(entry)}",
                    title=title.replace("\n", " "),
                    authors=[],
                    abstract=abstract[:2000],
                    pdf_url=pdf_url or link,
                    html_url=link,
                    published=pub_date.isoformat() if pub_date else "",
                    categories=[],
                    source="rss",
                )
                papers.append(paper)

            logger.info("[RSSSource] %s 获取到 %d 条", url, len(papers))

        return papers
