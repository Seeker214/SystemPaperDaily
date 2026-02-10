"""
arXiv 数据源 — 查询 cs.OS / cs.DC / cs.NI 最近论文。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import arxiv

from .base import Paper, PaperSource

logger = logging.getLogger(__name__)


class ArxivSource(PaperSource):
    """从 arXiv API 获取最近论文。"""

    def __init__(
        self,
        categories: List[str],
        max_results: int = 30,
        recent_hours: int = 48,
    ):
        self.categories = categories
        self.max_results = max_results
        self.recent_hours = recent_hours

    def fetch(self) -> List[Paper]:
        """查询多个 arXiv 分类，返回指定时间窗口内的论文。"""
        papers: List[Paper] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recent_hours)

        # 构建 OR 查询: cat:cs.OS OR cat:cs.DC OR cat:cs.NI
        query = " OR ".join(f"cat:{cat}" for cat in self.categories)
        logger.info("[ArxivSource] 查询: %s  (截止: %s)", query, cutoff.isoformat())

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            for result in client.results(search):
                # 发布时间早于截止线则跳过
                pub_time = result.published.replace(tzinfo=timezone.utc)
                if pub_time < cutoff:
                    logger.debug("[ArxivSource] 跳过旧论文: %s (%s)", result.title, pub_time)
                    continue

                paper = Paper(
                    paper_id=result.entry_id.split("/abs/")[-1],
                    title=result.title.strip().replace("\n", " "),
                    authors=[a.name for a in result.authors],
                    abstract=result.summary.strip().replace("\n", " "),
                    pdf_url=result.pdf_url or "",
                    html_url=result.entry_id,
                    published=pub_time.isoformat(),
                    categories=[c for c in result.categories],
                    source="arxiv",
                )
                papers.append(paper)

            logger.info("[ArxivSource] 获取到 %d 篇论文", len(papers))
        except Exception as e:
            logger.error("[ArxivSource] arXiv 查询失败: %s", e, exc_info=True)

        return papers
