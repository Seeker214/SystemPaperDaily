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
### Context
你是一个辅助系统研究员（Systems Researcher）阅读 arXiv 论文的 AI 助手。目标是快速提炼高价值信息。

### Instruction
请分析以下论文内容，生成**中文**深度摘要。

### Response Format

## 1. Meta Info
- **Type**: (Theory / System Implementation / Measurement Study / Survey)
- **Keywords**: (Top 3 tech keywords)

## 2. The Problem (What & Why)
- **背景**: (简述场景，如：在大规模机器学习训练中...)
- **现有缺陷**: (明确指出 State-of-the-art 的不足，如：通信开销占用了 40% 的训练时间)

## 3. The Solution (How)
- **核心方法**: (详细描述其技术路径，如：通过梯度压缩算法...)
- **系统设计**: (如果有系统架构图的描述，简要概括各组件交互)

## 4. Performance (Results)
*仅根据摘要或原文提供的声明提取*
- **测试环境**: (如：1000 GPUs cluster)
- **关键提升**: (具体数字)

## 5. Critical Takeaway (TL;DR)
- **一句话总结**: (这就好比是 [旧技术] + [新特性]，适合 [什么场景] 的开发者关注。)
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
    else:
        logger.error("[Summarizer] 未知的 LLM_PROVIDER: %s", config.LLM_PROVIDER)
        return f"⚠️ 配置错误: LLM_PROVIDER={config.LLM_PROVIDER}"
