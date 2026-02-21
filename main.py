"""
SystemPaperDaily — 主编排入口
=============================
流程:
  1. 初始化数据源 (arXiv + RSS)
  2. 抓取论文列表
  3. 关键词过滤
  4. 去重检查 (GitHub Issues)
  5. 调用 Gemini 生成总结
  6. 推送通知 (Discord/Slack)
  7. 归档到 GitHub Issues
"""

from __future__ import annotations

import logging
import sys
import time

# ── 日志配置 (在导入 config 之前设置，以捕获 config 的代理日志) ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ── 导入配置 (会触发代理检测) ──
import config
from src.sources.arxiv_source import ArxivSource
from src.sources.rss_source import RSSSource
from src.sources.base import Paper
from src.deduplicator import Deduplicator
from src.summarizer import summarize
from src.notifier import notify_daily_digest, notify_daily_summary, send_email_digest
from src.pdf_extractor import extract_paper_content


def run() -> None:
    """主流程。"""
    logger.info("=" * 60)
    logger.info("SystemPaperDaily 开始运行")
    logger.info("=" * 60)

    # ── 0. 校验配置 ────────────────────────────────
    if not config.validate():
        logger.error("配置校验失败，退出。")
        sys.exit(1)

    # ── 1. 初始化数据源 ────────────────────────────
    sources = [
        ArxivSource(
            categories=config.ARXIV_CATEGORIES,
            max_results=config.ARXIV_MAX_RESULTS,
            recent_hours=config.ARXIV_RECENT_HOURS,
        ),
    ]

    # 只在配置了 RSS 源时添加
    if config.RSS_FEEDS:
        sources.append(RSSSource(feed_urls=config.RSS_FEEDS))

    # ── 2. 抓取论文 ──────────────────────────────
    all_papers: list[Paper] = []
    for source in sources:
        try:
            papers = source.fetch()
            all_papers.extend(papers)
            logger.info("数据源 %s 返回 %d 篇论文", type(source).__name__, len(papers))
        except Exception as e:
            logger.error("数据源 %s 抓取失败: %s", type(source).__name__, e, exc_info=True)

    logger.info("共抓取到 %d 篇原始论文", len(all_papers))

    # ── 3. 关键词过滤 ────────────────────────────
    filtered: list[Paper] = [p for p in all_papers if p.match_keywords(config.KEYWORDS)]
    logger.info("关键词过滤后: %d 篇", len(filtered))

    if not filtered:
        logger.info("今日无匹配论文，流程结束。")
        notify_daily_summary(total=len(all_papers), processed=0, skipped=0)
        return

    # ── 4. 初始化去重器 ──────────────────────────
    dedup = Deduplicator()

    # ── 5. 逐篇处理: 去重 + 总结 ────────────────
    processed_count = 0
    skipped_count = 0
    # 收集今日新论文 (paper, summary) 用于批量推送
    daily_results: list[tuple[Paper, str]] = []

    for i, paper in enumerate(filtered):
        logger.info(
            "[%d/%d] 处理: %s (%s)",
            i + 1, len(filtered), paper.title[:60], paper.paper_id,
        )

        # 5a. 去重检查
        if dedup.is_paper_processed(paper.paper_id):
            logger.info("  → 已存在，跳过")
            skipped_count += 1
            continue

        # 5b. 提取 PDF 内容 (前3页 + 最后1页)
        logger.info("  → 提取 PDF 内容...")
        pdf_content = extract_paper_content(paper)
        
        # 如果 PDF 提取失败，使用摘要作为后备
        content_for_summary = pdf_content if pdf_content else paper.abstract
        
        # 5c. 调用 LLM 总结
        logger.info("  → 生成 AI 总结...")
        summary = summarize(content_for_summary)

        # 5c. 追加到今日 Daily Issue
        issue_num = dedup.append_paper(paper, summary, index=processed_count + 1)
        if issue_num:
            logger.info("  → 已追加到 Daily Issue #%d", issue_num)
            processed_count += 1
            daily_results.append((paper, summary))
        else:
            logger.warning("  → Issue 追加失败，但流程继续")

        # 5d. Rate Limit 保护
        if i < len(filtered) - 1:
            logger.debug("  → 等待 %d 秒...", config.REQUEST_SLEEP)
            time.sleep(config.REQUEST_SLEEP)

    # ── 6. 更新今日 Issue 头部统计 ───────────────
    dedup.update_daily_header(
        total=len(all_papers),
        processed=processed_count,
        skipped=skipped_count,
    )

    # ── 7. 推送每日汇总 ──────────────────────────
    logger.info("=" * 60)
    logger.info(
        "运行结束: 总计 %d 篇, 新处理 %d 篇, 跳过 %d 篇",
        len(filtered), processed_count, skipped_count,
    )
    logger.info("=" * 60)

    if daily_results:
        # 7a. Webhook 推送 (Discord/Slack)
        notify_daily_digest(daily_results)
        
        # 7b. 邮件日报推送 (QQ 邮箱)
        send_email_digest(daily_results)

    # 7c. 统计信息推送
    notify_daily_summary(
        total=len(all_papers),
        processed=processed_count,
        skipped=skipped_count,
    )


if __name__ == "__main__":
    run()
