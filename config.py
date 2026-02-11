"""
SystemPaperDaily - 配置与环境管理
=========================================
- 加载环境变量 (支持 .env 本地文件)
- 本地开发代理自动检测与设置
- 关键词 / RSS 源 / arXiv 分类等全局配置
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  1. 本地代理检测逻辑 (必须在最早阶段执行)
# ──────────────────────────────────────────────

_project_root = Path(__file__).resolve().parent
_dotenv_path = _project_root / ".env"

# 判断是否处于本地开发环境：
#   条件 1: 项目根目录存在 .env 文件
#   条件 2: 环境变量 LOCAL_DEV 被显式设为 "true"
_is_local_dev = _dotenv_path.exists() or os.getenv("LOCAL_DEV", "").lower() == "true"

if _is_local_dev:
    # 加载 .env 文件（如果存在），不覆盖已有环境变量
    load_dotenv(dotenv_path=_dotenv_path, override=False)

    # 代理地址：优先使用 .env / 环境变量中自定义的值，否则使用默认值
    _default_proxy = "http://127.0.0.1:7890"
    _proxy = os.getenv("PROXY_URL", _default_proxy)

    # 仅在尚未设置代理时自动注入
    if not os.environ.get("http_proxy"):
        os.environ["http_proxy"] = _proxy
        logger.info("[config] 本地开发模式 - 已设置 http_proxy  = %s", _proxy)
    if not os.environ.get("https_proxy"):
        os.environ["https_proxy"] = _proxy
        logger.info("[config] 本地开发模式 - 已设置 https_proxy = %s", _proxy)
    if not os.environ.get("HTTP_PROXY"):
        os.environ["HTTP_PROXY"] = _proxy
    if not os.environ.get("HTTPS_PROXY"):
        os.environ["HTTPS_PROXY"] = _proxy
else:
    # CI / 服务器环境：仅加载已存在的环境变量
    logger.info("[config] 检测到 CI/服务器环境，跳过代理设置")


# ──────────────────────────────────────────────
#  2. 核心密钥 / Token
# ──────────────────────────────────────────────

GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")            # Discord / Slack Webhook
GITHUB_REPOSITORY: str = os.getenv("GITHUB_REPOSITORY", "")  # owner/repo 格式

# ──────────────────────────────────────────────
#  2.1 LLM 提供商选择 (gemini / deepseek / openai)
# ──────────────────────────────────────────────

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").lower()  # gemini / deepseek / openai

# Gemini 配置
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# DeepSeek 配置
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# OpenAI / ChatGPT 配置
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE: float = 1.0

# ──────────────────────────────────────────────
#  3. arXiv 查询分类
# ──────────────────────────────────────────────

ARXIV_CATEGORIES: list[str] = [
    "cs.OS",   # Operating Systems
    "cs.DC",   # Distributed, Parallel, and Cluster Computing
    "cs.NI",   # Networking and Internet Architecture
]

# 每个分类最大获取论文数
ARXIV_MAX_RESULTS: int = 30

# 只关注最近 N 小时内提交的论文 (默认 48h)
ARXIV_RECENT_HOURS: int = 48

# ──────────────────────────────────────────────
#  4. RSS 源 (USENIX / 会议)
# ──────────────────────────────────────────────

RSS_FEEDS: list[str] = [
    # USENIX OSDI
    "https://www.usenix.org/blog/feed",
    # 可按需添加更多 RSS 源：
    # "https://dl.acm.org/action/showFeed?...",
]

# ──────────────────────────────────────────────
#  5. 论文过滤关键词
# ──────────────────────────────────────────────

KEYWORDS: list[str] = [
    "distributed systems",
    "operating systems",
    "consensus",
    "RDMA",
    "persistent memory",
    "kernel",
    "file system",
    "storage",
    "fault tolerance",
    "replication",
    "scheduling",
    "virtualization",
    "container",
    "serverless",
    "disaggregated memory",
    "CXL",
]

# ──────────────────────────────────────────────
#  6. PDF 内容提取配置
# ──────────────────────────────────────────────

PDF_EXTRACT_MODE: str = "partial"  # "partial" (部分) | "full" (全文)
PDF_FIRST_N_PAGES: int = 3        # 提取前 N 页 (摘要 + 引言, partial 模式)
PDF_LAST_N_PAGES: int = 1         # 提取最后 N 页 (结论, partial 模式)
PDF_TIMEOUT: int = 30              # PDF 下载超时 (秒)
PDF_MAX_CHARS: int = 50000         # 提取内容最大字符数 (全文模式下需要更大)

# ──────────────────────────────────────────────
#  7. LLM 重试配置
# ──────────────────────────────────────────────

LLM_MAX_RETRIES: int = 3          # 最大重试次数
LLM_RETRY_BASE_DELAY: int = 30    # 首次重试等待秒数 (指数退避基数)

# LLM 输出 token 限制 (影响总结详细程度)
GEMINI_MAX_OUTPUT_TOKENS: int = 3072   # Gemini 输出限制 (~2000 字)
DEEPSEEK_MAX_TOKENS: int = 3000        # DeepSeek 输出限制 (~2000 字)
OPENAI_MAX_TOKENS: int = 3000          # OpenAI 输出限制 (~2000 字)

# ──────────────────────────────────────────────
#  8. 杂项
# ──────────────────────────────────────────────

# 请求间隔 (秒)，避免 API Rate Limit
REQUEST_SLEEP: int = 20

# GitHub Issue 标签
ISSUE_LABEL_DAILY: str = "daily-paper"


def validate() -> bool:
    """检查必要配置是否齐全，返回 True 表示通过。"""
    ok = True
    
    # 根据 LLM 提供商检查对应的 API Key
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            logger.error("[config] LLM_PROVIDER=gemini 但缺少 GEMINI_API_KEY")
            ok = False
    elif LLM_PROVIDER == "deepseek":
        if not DEEPSEEK_API_KEY:
            logger.error("[config] LLM_PROVIDER=deepseek 但缺少 DEEPSEEK_API_KEY")
            ok = False
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            logger.error("[config] LLM_PROVIDER=openai 但缺少 OPENAI_API_KEY")
            ok = False
    else:
        logger.error("[config] LLM_PROVIDER 必须为 'gemini'、'deepseek' 或 'openai'，当前值: %s", LLM_PROVIDER)
        ok = False
    
    if not GITHUB_TOKEN:
        logger.error("[config] 缺少 GITHUB_TOKEN")
        ok = False
    if not GITHUB_REPOSITORY:
        logger.error("[config] 缺少 GITHUB_REPOSITORY (格式: owner/repo)")
        ok = False
    if not WEBHOOK_URL:
        logger.warning("[config] 未设置 WEBHOOK_URL，将跳过消息推送")
    return ok
