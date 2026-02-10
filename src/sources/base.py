"""
数据源基类与论文数据模型。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """统一的论文数据结构。"""

    paper_id: str                    # 唯一标识 (arXiv ID / RSS entry id)
    title: str                       # 论文标题
    authors: List[str] = field(default_factory=list)
    abstract: str = ""               # 摘要
    pdf_url: str = ""                # PDF 链接
    html_url: str = ""               # HTML 页面链接
    published: str = ""              # 发布日期 (ISO 格式字符串)
    categories: List[str] = field(default_factory=list)
    source: str = ""                 # 来源标记: "arxiv" / "rss"

    def match_keywords(self, keywords: List[str]) -> bool:
        """检查标题或摘要是否包含任意关键词（不区分大小写）。"""
        text = (self.title + " " + self.abstract).lower()
        return any(kw.lower() in text for kw in keywords)


class PaperSource(ABC):
    """论文数据源抽象基类。"""

    @abstractmethod
    def fetch(self) -> List[Paper]:
        """
        从数据源抓取论文列表。

        Returns:
            List[Paper]: 论文对象列表。
        """
        ...
