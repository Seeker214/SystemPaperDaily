"""
通知模块 — 推送论文每日汇总到 Discord / Slack Webhook 或 QQ 邮箱邮件。
"""

from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Tuple

import requests

import config
from src.sources.base import Paper

logger = logging.getLogger(__name__)

# 导入 markdown 库（用于邮件 HTML 转换）
try:
    import markdown
except ImportError:
    markdown = None
    logger.warning("[Notifier] 未安装 markdown 库，邮件功能将受限")


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


# ── QQ 邮箱邮件日报 ───────────────────────────────────


def send_email_digest(results: List[Tuple[Paper, str]]) -> bool:
    """
    发送每日论文汇总邮件（通过 QQ 邮箱）。
    
    Args:
        results: [(paper, summary), ...] 列表。
        
    Returns:
        成功返回 True，失败返回 False。
    """
    if not config.EMAIL_ENABLED:
        logger.info("[Notifier] 邮件功能未启用 (EMAIL_ENABLED=false)")
        return False
    
    if not config.QQ_MAIL_USER or not config.QQ_MAIL_AUTH_CODE or not config.QQ_MAIL_TO:
        logger.error("[Notifier] QQ 邮箱配置不完整，跳过邮件发送")
        return False
    
    if not results:
        logger.info("[Notifier] 没有论文需要发送邮件")
        return False
    
    if markdown is None:
        logger.error("[Notifier] markdown 库未安装，无法发送 HTML 邮件")
        return False
    
    try:
        # 构建邮件内容
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        subject = f"[System Paper Daily] {today} (共 {len(results)} 篇)"
        
        # 拼接所有论文的 Markdown 内容
        markdown_content = _build_email_markdown(results, today)
        
        # 转换为 HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=['extra', 'codehilite', 'nl2br']
        )
        
        # 添加 CSS 样式
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
        }}
        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 40px 0;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .paper-meta {{
            background: #ecf0f1;
            padding: 10px 15px;
            border-radius: 4px;
            margin: 10px 0;
            font-size: 0.9em;
        }}
        code {{
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }}
        ul {{
            padding-left: 25px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
        <div class="footer">
            <p>📚 SystemPaperDaily - 自动化论文日报</p>
            <p>由 <a href="https://github.com/{config.GITHUB_REPOSITORY}">{config.GITHUB_REPOSITORY}</a> 生成</p>
        </div>
    </div>
</body>
</html>
"""
        
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = config.QQ_MAIL_USER
        msg['To'] = config.QQ_MAIL_TO
        msg['Subject'] = subject
        
        # 添加纯文本版本（作为后备）
        text_part = MIMEText(markdown_content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # 添加 HTML 版本
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 发送邮件
        logger.info("[Notifier] 正在连接 QQ 邮箱 SMTP 服务器...")
        with smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=30) as server:
            server.login(config.QQ_MAIL_USER, config.QQ_MAIL_AUTH_CODE)
            server.send_message(msg)
        
        logger.info("[Notifier] ✅ 邮件发送成功: %s → %s (%d 篇论文)", 
                    config.QQ_MAIL_USER, config.QQ_MAIL_TO, len(results))
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error("[Notifier] ❌ QQ 邮箱认证失败: %s", e)
        logger.error("请检查：1) QQ_MAIL_USER 是否正确  2) QQ_MAIL_AUTH_CODE 是否是有效的授权码")
        return False
    except smtplib.SMTPException as e:
        logger.error("[Notifier] ❌ SMTP 错误: %s", e)
        return False
    except Exception as e:
        logger.error("[Notifier] ❌ 邮件发送失败: %s", e, exc_info=True)
        return False


def _build_email_markdown(results: List[Tuple[Paper, str]], today: str) -> str:
    """构建邮件的 Markdown 内容。"""
    lines = [
        f"# 📚 SystemPaperDaily — {today}",
        "",
        f"今日新增 **{len(results)}** 篇系统领域论文",
        "",
    ]
    
    for idx, (paper, summary) in enumerate(results, 1):
        lines.append(f"## {idx}. {paper.title}")
        lines.append("")
        
        # 元数据
        meta_items = []
        if paper.authors:
            meta_items.append(f"**作者**: {', '.join(paper.authors[:3])}" + 
                            (" et al." if len(paper.authors) > 3 else ""))
        if paper.categories:
            meta_items.append(f"**分类**: {', '.join(paper.categories)}")
        if paper.published:
            meta_items.append(f"**发布**: {paper.published}")
        
        lines.append('<div class="paper-meta">')
        lines.extend(meta_items)
        lines.append('</div>')
        lines.append("")
        
        # 链接
        if paper.html_url:
            lines.append(f"🔗 [arXiv 页面]({paper.html_url})")
        if paper.pdf_url:
            lines.append(f"📄 [PDF 下载]({paper.pdf_url})")
        lines.append("")
        
        # AI 总结
        lines.append("### 📖 AI 深度总结")
        lines.append("")
        lines.append(summary)
        lines.append("")
        
        # 分隔线（最后一篇不加）
        if idx < len(results):
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)

