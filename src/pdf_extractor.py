"""PDF 内容提取模块 - 支持全文或部分提取。
- partial 模式：提取前N页和最后N页（摘要+引言+结论）
- full 模式：提取完整论文内容
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import requests

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import config
from src.sources.base import Paper

logger = logging.getLogger(__name__)


def extract_paper_content(
    paper: Paper,
    extract_mode: Optional[str] = None,
    first_n_pages: Optional[int] = None,
    last_n_pages: Optional[int] = None,
    timeout: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> Optional[str]:
    """
        从论文 PDF 提取文本内容。

    Args:
        paper: 论文对象，包含 pdf_url。
        extract_mode: 提取模式 ("partial" | "full")，默认从 config 读取。
        first_n_pages: 提取前 N 页（partial 模式），默认从 config 读取。
        last_n_pages: 提取最后 N 页（partial 模式），默认从 config 读取。
        timeout: HTTP 请求超时（秒），默认从 config 读取。
        max_chars: 提取内容的最大字符数，默认从 config 读取。

    Returns:
        提取的文本内容，失败返回 None。
    """
    # 从 config 读取默认值
    extract_mode = extract_mode or config.PDF_EXTRACT_MODE
    first_n_pages = first_n_pages or config.PDF_FIRST_N_PAGES
    last_n_pages = last_n_pages or config.PDF_LAST_N_PAGES
    timeout = timeout or config.PDF_TIMEOUT
    max_chars = max_chars or config.PDF_MAX_CHARS
    if not paper.pdf_url:
        logger.warning("[PDF Extractor] 论文无 PDF 链接: %s", paper.title[:60])
        return None

    if fitz is None:
        logger.error("[PDF Extractor] PyMuPDF 未安装，请运行: pip install PyMuPDF")
        return None

    try:
        # 1. 下载 PDF
        logger.info("[PDF Extractor] 下载 PDF: %s", paper.pdf_url)
        response = requests.get(
            paper.pdf_url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (research bot)"},
        )
        response.raise_for_status()

        # 2. 解析 PDF
        pdf_bytes = io.BytesIO(response.content)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = doc.page_count

        # 3. 根据模式提取页面文本
        extracted_text_parts = []

        if extract_mode == "full":
            # 全文模式：提取所有页面
            logger.info(
                "[PDF Extractor] PDF 总页数: %d，全文提取模式",
                total_pages,
            )
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                extracted_text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")
        
        else:
            # 部分模式：提取前 N 页 + 最后 N 页
            logger.info(
                "[PDF Extractor] PDF 总页数: %d，提取前 %d 页 + 最后 %d 页",
                total_pages, first_n_pages, last_n_pages,
            )
            
            # 提取前 N 页
            for page_num in range(min(first_n_pages, total_pages)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                extracted_text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")

            # 提取最后 N 页（避免与前 N 页重复）
            last_start = max(first_n_pages, total_pages - last_n_pages)
            for page_num in range(last_start, total_pages):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                extracted_text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")

        doc.close()

        # 4. 合并并截断
        full_text = "\n".join(extracted_text_parts)
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n[... 内容已截断 ...]"

        logger.info(
            "[PDF Extractor] 成功提取 %d 字符 (论文: %s)",
            len(full_text), paper.title[:60],
        )
        return full_text

    except requests.RequestException as e:
        logger.error(
            "[PDF Extractor] 下载失败 (%s): %s",
            paper.pdf_url, e,
        )
        return None

    except Exception as e:
        logger.error(
            "[PDF Extractor] 解析 PDF 失败 (%s): %s",
            paper.title[:60], e, exc_info=True,
        )
        return None
