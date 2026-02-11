"""LLM 总结模块 - 支持多个 LLM 提供商 (Gemini / DeepSeek)。
自动重试 + 指数退避以应对 429 Rate Limit。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

import config

logger = logging.getLogger(__name__)

# ── System Prompt ──────────────────────────────────────

SYSTEM_PROMPT = """\
### Role
你担任 OSDI/SOSP 等顶级系统会议的 Senior PC Member（高级评审）。你的任务是向工业界资深架构师推荐每日新论文。
你的风格应当是：**技术硬核、言简意赅、拒绝套话**。

### Task
阅读输入的论文摘要（或片段），输出一份**中文**技术简报。

### Output Rules
1. **严格遵循 Markdown 格式**。
2. **拒绝废话**：不要说“这篇论文非常有意义”，直接说它解决了什么具体的死锁问题或内存瓶颈。
3. **量化指标**：如果原文有数字（如 "2.5x speedup", "99% tail latency reduction"），必须提取出来。
4. **处理缺失**：如果摘要里没提到的细节（如具体算法），不要编造，直接写 "N/A"。

### Output Format
请严格按以下模版输出：

# 📄 [中文标题] (原文标题)

**🏷️ 领域标签**: (例如: Distributed Consensus / NVMe / Serverless / Kernel)

## 🎯 核心痛点 (Problem)
(用一句话精准描述现有技术的具体瓶颈，例如："现有 Raft 协议在跨数据中心高延迟网络下的 Leader 选举过慢，导致服务不可用时间长。")

## 💡 关键创新 (Key Insight)
- **架构/机制**: (不要只写名字，要写原理。例如："引入一种基于 RDMA 的共享日志层，绕过 CPU 处理...")
- **核心差异**: (相比 SOTA 方案，它做对了什么？例如："相比 Spanner，它牺牲了部分写吞吐换取了更低的读延迟。")

## 📊 评估 (Evaluation)
- **基准**: (对比了什么系统？如 Redis, RocksDB)
- **核心数据**: (列出 1-2 个最亮眼的提升数据)

## 💬 落地一句话点评
(从工业界角度评价：是纯理论创新？还是能直接换掉生产环境的某个组件？或是解决了某个特定场景的痛点？)
"""


def _init_model() -> genai.GenerativeModel:
    """初始化 Gemini 模型。"""
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    return model


# 模块级 lazy 单例
_gemini_model: Optional["genai.GenerativeModel"] = None
_deepseek_client: Optional[OpenAI] = None
_openai_client: Optional[OpenAI] = None


def _get_gemini_model() -> "genai.GenerativeModel":
    """获取 Gemini 模型单例。"""
    global _gemini_model
    if _gemini_model is None:
        _gemini_model = _init_model()
    return _gemini_model


def _get_deepseek_client() -> OpenAI:
    """获取 DeepSeek OpenAI 客户端单例。"""
    global _deepseek_client
    if _deepseek_client is None:
        if OpenAI is None:
            raise ImportError("请安装 openai 库: pip install openai")
        _deepseek_client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        logger.info("[Summarizer] DeepSeek 客户端已初始化")
    return _deepseek_client


def _get_openai_client() -> OpenAI:
    """获取 OpenAI (ChatGPT) 客户端单例。"""
    global _openai_client
    if _openai_client is None:
        if OpenAI is None:
            raise ImportError("请安装 openai 库: pip install openai")
        
        # 配置验证
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")
        
        logger.info(
            "[Summarizer] 初始化 OpenAI 客户端 - Model: %s, Base URL: %s",
            config.OPENAI_MODEL, config.OPENAI_BASE_URL
        )
        
        _openai_client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
        logger.info("[Summarizer] OpenAI 客户端已初始化")
    return _openai_client


def _summarize_with_gemini(text_content: str, max_retries: int, base_delay: int) -> str:
    """使用 Gemini 生成总结（带重试）。"""
    if genai is None:
        return "⚠️ 未安装 google-generativeai 库"
    
    model = _get_gemini_model()
    
    # 根据 PDF 提取模式调整提示词
    if config.PDF_EXTRACT_MODE == "full":
        content_desc = "以下是一篇系统领域论文的完整全文内容"
        char_limit = 30000  # 全文模式下提取更多字符
    else:
        content_desc = "以下是一篇系统领域论文的前3页和最后1页内容（包含摘要、引言和结论）"
        char_limit = 12000
    
    user_prompt = (
        f"{content_desc}，请按照要求生成深度摘要：\n\n"
        f"```\n{text_content[:char_limit]}\n```"
    )

    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=config.TEMPERATURE,
                    max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKENS,
                ),
            )

            # 检查是否被安全过滤器拦截
            if not response.candidates:
                logger.warning("[Summarizer] Gemini 返回空候选，可能被安全过滤器拦截")
                return "⚠️ 无法生成总结（内容被安全过滤器拦截）"

            candidate = response.candidates[0]

            # 检查 finish_reason
            if hasattr(candidate, "finish_reason") and candidate.finish_reason not in (None, 1):
                logger.warning(
                    "[Summarizer/Gemini] finish_reason=%s", candidate.finish_reason
                )

            text = response.text.strip()
            if not text:
                return "⚠️ 无法生成总结（模型返回空文本）"

            logger.info("[Summarizer/Gemini] 成功生成总结 (%d 字符)", len(text))
            return text

        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "ResourceExhausted" in error_str

            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[Summarizer/Gemini] Rate Limit，第 %d/%d 次重试，等待 %ds...",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                continue

            logger.error("[Summarizer/Gemini] 调用失败: %s", e, exc_info=True)
            return f"⚠️ Gemini 调用失败: {type(e).__name__}"

    return "⚠️ Gemini 重试次数耗尽"


def _summarize_with_deepseek(text_content: str, max_retries: int, base_delay: int) -> str:
    """使用 DeepSeek 生成总结（带重试）。"""
    client = _get_deepseek_client()
    
    # 根据 PDF 提取模式调整提示词
    if config.PDF_EXTRACT_MODE == "full":
        content_desc = "以下是一篇系统领域论文的完整全文内容"
        char_limit = 30000  # 全文模式下提取更多字符
    else:
        content_desc = "以下是一篇系统领域论文的前3页和最后1页内容（包含摘要、引言和结论）"
        char_limit = 12000
    
    user_prompt = (
        f"{content_desc}，请按照要求生成深度摘要：\n\n"
        f"```\n{text_content[:char_limit]}\n```"
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.TEMPERATURE,
                max_tokens=config.DEEPSEEK_MAX_TOKENS,
            )

            if not response.choices:
                logger.warning("[Summarizer/DeepSeek] 返回空候选")
                return "⚠️ DeepSeek 返回空响应"

            text = response.choices[0].message.content.strip()
            if not text:
                return "⚠️ DeepSeek 返回空文本"

            logger.info("[Summarizer/DeepSeek] 成功生成总结 (%d 字符)", len(text))
            return text

        except Exception as e:
            error_str = str(e)
            # DeepSeek 也会返回 429 / rate_limit_exceeded
            is_rate_limit = (
                "429" in error_str 
                or "rate_limit" in error_str.lower()
                or "RateLimitError" in str(type(e).__name__)
            )

            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[Summarizer/DeepSeek] Rate Limit，第 %d/%d 次重试，等待 %ds...",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                continue

            logger.error("[Summarizer/DeepSeek] 调用失败: %s", e, exc_info=True)
            return f"⚠️ DeepSeek 调用失败: {type(e).__name__}"

    return "⚠️ DeepSeek 重试次数耗尽"


def _summarize_with_openai(text_content: str, max_retries: int, base_delay: int) -> str:
    """使用 OpenAI ChatGPT 生成总结（带重试）。"""
    client = _get_openai_client()

    if config.PDF_EXTRACT_MODE == "full":
        content_desc = "以下是一篇系统领域论文的完整全文内容"
        char_limit = 30000
    else:
        content_desc = "以下是一篇系统领域论文的前3页和最后1页内容（包含摘要、引言和结论）"
        char_limit = 12000

    user_prompt = (
        f"{content_desc}，请按照要求生成深度摘要：\n\n"
        f"```\n{text_content[:char_limit]}\n```"
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.TEMPERATURE,
                max_tokens=config.OPENAI_MAX_TOKENS,
            )

            # 类型检查：确保返回的是正确的对象
            if isinstance(response, str):
                logger.error("[Summarizer/OpenAI] API 返回了字符串而非对象: %s", response[:200])
                return f"⚠️ OpenAI API 配置错误，返回: {response[:100]}"
            
            if not hasattr(response, 'choices'):
                logger.error("[Summarizer/OpenAI] 响应对象缺少 choices 属性，类型: %s", type(response))
                return f"⚠️ OpenAI API 响应格式错误 (类型: {type(response).__name__})"

            if not response.choices:
                logger.warning("[Summarizer/OpenAI] 返回空候选")
                return "⚠️ OpenAI 返回空响应"

            text = response.choices[0].message.content
            if not text:
                return "⚠️ OpenAI 返回空文本"
            
            text = text.strip()
            logger.info("[Summarizer/OpenAI] 成功生成总结 (%d 字符)", len(text))
            return text

        except AttributeError as e:
            logger.error(
                "[Summarizer/OpenAI] 属性访问错误 (可能 API 配置有误): %s, response type: %s",
                e, type(response).__name__ if 'response' in locals() else 'undefined'
            )
            return f"⚠️ OpenAI API 配置错误: {str(e)}"
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower()

            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[Summarizer/OpenAI] Rate Limit，第 %d/%d 次重试，等待 %ds...",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                continue

            logger.error("[Summarizer/OpenAI] 调用失败: %s", e, exc_info=True)
            return f"⚠️ OpenAI 调用失败: {type(e).__name__}"

    return "⚠️ OpenAI 重试次数耗尽"


def summarize(text_content: str) -> str:
    """
    调用配置的 LLM 提供商对论文文本进行总结。

    Args:
        text_content: 论文摘要或全文片段。

    Returns:
        Markdown 格式的中文简报。失败时返回占位文本。
    """
    if not text_content or not text_content.strip():
        return "_无内容可供总结_"

    max_retries = config.LLM_MAX_RETRIES
    base_delay = config.LLM_RETRY_BASE_DELAY

    if config.LLM_PROVIDER == "gemini":
        return _summarize_with_gemini(text_content, max_retries, base_delay)
    elif config.LLM_PROVIDER == "deepseek":
        return _summarize_with_deepseek(text_content, max_retries, base_delay)
    elif config.LLM_PROVIDER == "openai":
        return _summarize_with_openai(text_content, max_retries, base_delay)
    else:
        logger.error("[Summarizer] 未知的 LLM_PROVIDER: %s", config.LLM_PROVIDER)
        return f"⚠️ 配置错误: LLM_PROVIDER={config.LLM_PROVIDER}"
