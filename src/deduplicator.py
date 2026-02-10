"""
去重模块 — 基于 GitHub Issues 实现论文去重与每日归档。

每日一个 Issue，所有论文汇总到同一个 Issue 中:
  - Title: [Daily] YYYY-MM-DD SystemPaperDaily
  - Body:  当日所有论文的 Markdown 总结
  - Labels: daily-paper

去重逻辑: 在所有 daily-paper Issue 的 body 中搜索 paper_id。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from github import Github, GithubException
from github.Issue import Issue
from github.Repository import Repository

import config
from src.sources.base import Paper

logger = logging.getLogger(__name__)


def _format_paper_section(paper: Paper, summary: str, index: int) -> str:
    """将单篇论文格式化为 Markdown 区块，用于拼接到 Daily Issue body。"""
    lines = [
        f"## {index}. {paper.title}",
        "",
        f"- **Paper ID**: `{paper.paper_id}`",
        f"- **Authors**: {', '.join(paper.authors) if paper.authors else 'N/A'}",
        f"- **Published**: {paper.published or 'N/A'}",
        f"- **Source**: {paper.source}",
        f"- **Categories**: {', '.join(paper.categories) if paper.categories else 'N/A'}",
        f"- **PDF**: {paper.pdf_url}",
        f"- **URL**: {paper.html_url}",
        "",
        "### AI 总结",
        "",
        summary,
        "",
        "<details><summary>原始摘要</summary>",
        "",
        paper.abstract[:3000] if paper.abstract else "_无摘要_",
        "",
        "</details>",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


class Deduplicator:
    """使用 GitHub Issues 进行论文去重与每日汇总归档。"""

    def __init__(self):
        self._gh = Github(config.GITHUB_TOKEN)
        self._repo: Optional[Repository] = None
        self._today_issue: Optional[Issue] = None
        self._processed_ids_cache: Optional[set[str]] = None

    @property
    def repo(self) -> Repository:
        if self._repo is None:
            self._repo = self._gh.get_repo(config.GITHUB_REPOSITORY)
            logger.info("[Deduplicator] 已连接仓库: %s", config.GITHUB_REPOSITORY)
        return self._repo

    # ── 日期标题 ────────────────────────────────
    @staticmethod
    def _daily_title(date: Optional[datetime] = None) -> str:
        """生成当日 Issue 标题。"""
        d = date or datetime.now(timezone.utc)
        return f"[Daily] {d.strftime('%Y-%m-%d')} SystemPaperDaily"

    # ── 确保标签存在 ────────────────────────────
    def _ensure_label(self, name: str, color: str = "0075ca") -> None:
        """如果标签不存在则创建。"""
        try:
            self.repo.get_label(name)
        except GithubException:
            try:
                self.repo.create_label(name=name, color=color)
                logger.info("[Deduplicator] 创建标签: %s", name)
            except GithubException as e:
                logger.warning("[Deduplicator] 创建标签失败 (%s): %s", name, e)

    # ── 加载已处理的 paper_id 集合 ──────────────
    def _load_processed_ids(self) -> set[str]:
        """
        遍历所有 daily-paper 标签的 Issue，
        从 body 中提取 `Paper ID`: `xxx` 来构建已处理 ID 集合。
        """
        if self._processed_ids_cache is not None:
            return self._processed_ids_cache

        ids: set[str] = set()
        try:
            self._ensure_label(config.ISSUE_LABEL_DAILY)
            issues = self.repo.get_issues(
                labels=[self.repo.get_label(config.ISSUE_LABEL_DAILY)],
                state="all",
            )
            for issue in issues:
                body = issue.body or ""
                # 提取所有 **Paper ID**: `xxx` 模式
                for line in body.split("\n"):
                    if "**Paper ID**" in line and "`" in line:
                        # 格式: - **Paper ID**: `2301.12345`
                        start = line.index("`") + 1
                        end = line.index("`", start)
                        ids.add(line[start:end])
        except GithubException as e:
            logger.error("[Deduplicator] 加载已处理 ID 失败: %s", e)

        logger.info("[Deduplicator] 已加载 %d 个已处理 paper_id", len(ids))
        self._processed_ids_cache = ids
        return ids

    # ── 去重查询 ──────────────────────────────
    def is_paper_processed(self, paper_id: str) -> bool:
        """检查 paper_id 是否已出现在任何 daily Issue 中。"""
        processed = self._load_processed_ids()
        if paper_id in processed:
            logger.info("[Deduplicator] 论文已存在: %s", paper_id)
            return True
        return False

    # ── 获取或创建今日 Issue ─────────────────────
    def _get_or_create_daily_issue(self) -> Issue:
        """获取今日的 Daily Issue，不存在则创建。"""
        if self._today_issue is not None:
            return self._today_issue

        today_title = self._daily_title()
        self._ensure_label(config.ISSUE_LABEL_DAILY)

        # 搜索今日 Issue
        query = f'repo:{config.GITHUB_REPOSITORY} in:title "{today_title}"'
        try:
            results = self._gh.search_issues(query=query)
            for issue in results:
                if issue.title.strip() == today_title:
                    logger.info("[Deduplicator] 找到今日 Issue #%d", issue.number)
                    self._today_issue = issue
                    return issue
        except GithubException as e:
            logger.warning("[Deduplicator] 搜索今日 Issue 失败: %s", e)

        # 不存在则创建
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        header = (
            f"# 📚 SystemPaperDaily — {today_str}\n\n"
            f"> 自动抓取的系统领域 (OSDI/SOSP/EuroSys) 最新论文每日汇总。\n\n"
            f"---\n\n"
        )
        try:
            issue = self.repo.create_issue(
                title=today_title,
                body=header,
                labels=[config.ISSUE_LABEL_DAILY],
            )
            logger.info("[Deduplicator] 创建今日 Issue #%d: %s", issue.number, today_title)
            self._today_issue = issue
            return issue
        except GithubException as e:
            logger.error("[Deduplicator] 创建今日 Issue 失败: %s", e, exc_info=True)
            raise

    # ── 归档 (追加到今日 Issue) ─────────────────
    def append_paper(
        self,
        paper: Paper,
        summary: str,
        index: int = 1,
    ) -> Optional[int]:
        """
        将论文总结追加到今日的 Daily Issue 中。

        Args:
            paper:   论文对象。
            summary: AI 生成的总结。
            index:   论文在当日列表中的序号。

        Returns:
            Issue 编号，失败返回 None。
        """
        try:
            issue = self._get_or_create_daily_issue()
        except Exception:
            return None

        section = _format_paper_section(paper, summary, index)
        new_body = (issue.body or "") + section

        # GitHub Issue body 有 65536 字符限制
        if len(new_body) > 65000:
            logger.warning("[Deduplicator] Issue body 接近长度上限，截断处理")
            new_body = new_body[:65000] + "\n\n> ⚠️ 已达 Issue 长度上限，后续论文请查看下一个 Issue。"

        try:
            issue.edit(body=new_body)
            # 更新缓存
            if self._processed_ids_cache is not None:
                self._processed_ids_cache.add(paper.paper_id)
            logger.info(
                "[Deduplicator] 论文已追加到 Issue #%d: %s",
                issue.number, paper.title[:60],
            )
            return issue.number
        except GithubException as e:
            logger.error("[Deduplicator] 更新 Issue 失败: %s", e, exc_info=True)
            return None

    # ── 更新今日 Issue 头部统计 ─────────────────
    def update_daily_header(self, total: int, processed: int, skipped: int) -> None:
        """在今日 Issue 顶部追加统计信息。"""
        if self._today_issue is None:
            return

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        header = (
            f"# 📚 SystemPaperDaily — {today_str}\n\n"
            f"> 自动抓取的系统领域 (OSDI/SOSP/EuroSys) 最新论文每日汇总。\n\n"
            f"| 指标 | 数量 |\n"
            f"|------|------|\n"
            f"| 抓取总数 | {total} |\n"
            f"| 新处理 | {processed} |\n"
            f"| 跳过 (重复) | {skipped} |\n\n"
            f"---\n\n"
        )

        body = self._today_issue.body or ""
        # 替换第一个 --- 之前的内容为新 header
        separator = "---\n\n"
        first_sep = body.find(separator)
        if first_sep != -1:
            # 保留 --- 之后的论文内容
            papers_content = body[first_sep + len(separator):]
            new_body = header + papers_content
        else:
            new_body = header + body

        try:
            self._today_issue.edit(body=new_body)
            logger.info("[Deduplicator] 已更新今日 Issue 头部统计")
        except GithubException as e:
            logger.error("[Deduplicator] 更新头部统计失败: %s", e)
