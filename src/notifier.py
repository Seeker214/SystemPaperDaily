"""
通知模块 — 推送论文每日汇总到 Discord / Slack Webhook。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Tuple

import requests

import config
from src.sources.base import Paper

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int) -> str:
    """截断文本，保留末尾省略号。"""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _detect_platform(url: str) -> str:
    """根据 Webhook URL 简单判断平台。"""
    if "discord" in url.lower():
        return "discord"
    return "slack"


def _post_webhook(payload: dict) -> bool:
    """发送 Webhook 请求。"""
    webhook_url = config.WEBHOOK_URL
    if not webhook_url:
        logger.info("[Notifier] 未配置 WEBHOOK_URL，跳过推送")
        return False

    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            return True
        else:
            logger.warning("[Notifier] 推送失败 [%d]: %s", resp.status_code, resp.text[:200])
            return False
    except requests.RequestException as e:
        logger.error("[Notifier] 网络错误: %s", e)
        return False


# ── 每日批量汇总推送 ──────────────────────────────


def notify_daily_digest(results: List[Tuple[Paper, str]]) -> bool:
    """
    将当日所有新论文汇总为一条消息推送到 Webhook。

    Args:
        results: [(paper, summary), ...] 列表。
    """
    webhook_url = config.WEBHOOK_URL
    if not webhook_url or not results:
        return False

    platform = _detect_platform(webhook_url)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if platform == "discord":
        return _notify_discord_digest(results, today)
    else:
        return _notify_slack_digest(results, today)


def _notify_discord_digest(results: List[Tuple[Paper, str]], today: str) -> bool:
    """Discord: 一条主消息 + 每篇论文一个 embed (Discord 限制 10 embeds/msg)。"""
    # Discord 单消息最多 10 个 embed，按批次发送
    batch_size = 10
    success = True

    for batch_start in range(0, len(results), batch_size):
        batch = results[batch_start: batch_start + batch_size]
        embeds = []

        # 第一批加一个头部
        if batch_start == 0:
            embeds.append({
                "title": f"📚 SystemPaperDaily — {today}",
                "description": f"今日新增 **{len(results)}** 篇系统领域论文",
                "color": 0x57F287,  # Green
            })

        for paper, summary in batch:
            # 精简摘要，只取核心痛点部分
            short_summary = summary
            if "## 核心痛点" in summary:
                lines = summary.split("\n")
                key_lines = []
                capture = False
                for line in lines:
                    if "核心痛点" in line:
                        capture = True
                        continue
                    if capture and line.startswith("## "):
                        break
                    if capture and line.strip():
                        key_lines.append(line.strip())
                if key_lines:
                    short_summary = " ".join(key_lines)

            embed = {
                "title": _truncate(paper.title, 256),
                "url": paper.html_url or paper.pdf_url,
                "description": _truncate(short_summary, 1024),
                "color": 0x5865F2,
                "fields": [],
            }
            if paper.pdf_url:
                embed["fields"].append({"name": "📄 PDF", "value": paper.pdf_url, "inline": True})
            if paper.categories:
                embed["fields"].append({"name": "🏷️", "value": ", ".join(paper.categories[:3]), "inline": True})
            embeds.append(embed)

        if not _post_webhook({"embeds": embeds}):
            success = False

    logger.info("[Notifier] Discord 每日汇总推送完成 (%d 篇)", len(results))
    return success


def _notify_slack_digest(results: List[Tuple[Paper, str]], today: str) -> bool:
    """Slack: Block Kit 格式汇总。"""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📚 SystemPaperDaily — {today}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"今日新增 *{len(results)}* 篇系统领域论文"},
        },
        {"type": "divider"},
    ]

    for paper, summary in results:
        # 精简为一行概要
        short = _truncate(summary.split("\n")[0] if summary else "", 200)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{paper.html_url or paper.pdf_url}|{_truncate(paper.title, 120)}>*\n{short}",
            },
        })

    # Slack blocks 上限 50
    blocks = blocks[:50]
    ok = _post_webhook({"blocks": blocks})
    logger.info("[Notifier] Slack 每日汇总推送完成 (%d 篇)", len(results))
    return ok


# ── 每日统计推送 ──────────────────────────────────


def notify_daily_summary(total: int, processed: int, skipped: int) -> bool:
    """推送每日汇总统计。"""
    webhook_url = config.WEBHOOK_URL
    if not webhook_url:
        return False

    platform = _detect_platform(webhook_url)

    text = (
        f"📊 **SystemPaperDaily 每日报告**\n"
        f"- 抓取论文总数: **{total}**\n"
        f"- 新处理: **{processed}**\n"
        f"- 已跳过 (重复): **{skipped}**"
    )

    if platform == "discord":
        payload = {"content": text}
    else:
        payload = {"text": text}

    return _post_webhook(payload)
