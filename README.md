# SystemPaperDaily

> 每日自动抓取系统领域 (OSDI/SOSP/EuroSys) 最新论文，**下载 PDF 提取前3页和最后1页**（包含摘要、引言、结论），使用 Gemini/DeepSeek/OpenAI AI 深度总结，推送到 Discord/Slack，归档到 GitHub Issues。

## 架构概览

```
┌─────────────┐     ┌─────────────┐
│  arXiv API  │     │  RSS Feeds  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └───────┬───────────┘
               ▼
        ┌─────────────┐
        │  关键词过滤   │
        └──────┬──────┘
               ▼
        ┌─────────────┐    ┌──────────────────┐
        │  去重检查    │───▶│  GitHub Issues    │
        └──────┬──────┘    │  (State Store)    │
               ▼           └──────────────────┘
        ┌─────────────┐
        │  PDF 提取    │  (前3页 + 最后1页)
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │  LLM 总结    │  (Gemini / DeepSeek)
        └──────┬──────┘
               ▼
        ┌─────────────┐    ┌──────────────────┐
        │  推送通知    │───▶│  Discord / Slack  │
        └──────┬──────┘    └──────────────────┘
               ▼
        ┌─────────────┐
        │  归档 Issue  │
        │  归档 Issue  │
        └─────────────┘
```

## 项目结构

```
SystemPaperDaily/
├── .github/workflows/
│   └── daily.yml           # GitHub Actions 每日定时任务
├── src/
│   ├── sources/
│   │   ├── base.py         # Paper 数据模型 & PaperSource 基类
│   │   ├── arxiv_source.py # arXiv API 数据源
│   │   └── rss_source.py   # RSS Feed 数据源
│   ├── deduplicator.py     # GitHub Issues 去重 & 归档 (每日一个 Issue)
│   ├── pdf_extractor.py    # PDF 内容提取 (前3页 + 最后1页)
│   ├── summarizer.py       # LLM 总结 (Gemini / DeepSeek / OpenAI)
│   └── notifier.py         # Discord/Slack Webhook 推送 & Gmail 邮件日报
├── tests/
│   ├── test_openai.py      # OpenAI API 配置测试
│   ├── test_gmail.py       # Gmail 邮件配置测试
│   └── README.md           # 测试说明文档
├── config.py               # 配置 & 代理检测
├── main.py                 # 主编排入口
├── requirements.txt
├── .env.example            # 环境变量模板
└── README.md
```

## 🚀 核心特性

- **📄 深度内容提取**：不止摘要！自动下载 PDF 并提取前3页（摘要 + 引言）和最后1页（结论），全面理解论文脉络
- **🤖 多 LLM 支持**：支持 Google Gemini、DeepSeek 和 OpenAI ChatGPT，可根据成本和性能需求灵活切换
- **� 邮件日报**：支持 Gmail 邮件日报，每日自动发送精美 HTML 格式的论文汇总到您的邮箱
- **�📅 每日汇总归档**：所有论文汇总到单个 GitHub Issue（按日期），便于长期追踪和回顾
- **🔔 实时推送**：自动推送到 Discord / Slack，第一时间获取最新论文动态
- **♻️ 智能去重**：基于 GitHub Issues 的去重机制，避免重复处理
- **🌐 本地代理支持**：自动检测并配置代理，方便本地开发调试

## 快速开始

### 1. 克隆 & 安装

```bash
git clone https://github.com/your-username/SystemPaperDaily.git
cd SystemPaperDaily
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入真实的 API Key / Token
```

所需密钥：

| 变量 | 说明 | 必须 |
|------|------|------|
| `LLM_PROVIDER` | LLM 提供商 (`gemini` / `deepseek` / `openai`) | ✅ (默认 `deepseek`) |
| `OPENAI_API_KEY` | OpenAI API Key (当 `LLM_PROVIDER=openai`) | 条件必须 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key (当 `LLM_PROVIDER=deepseek`) | 条件必须 |
| `GEMINI_API_KEY` | Google Gemini API Key (当 `LLM_PROVIDER=gemini`) | 条件必须 |
| `GITHUB_TOKEN` | GitHub PAT (需 `repo` 权限) | ✅ |
| `GITHUB_REPOSITORY` | `owner/repo` 格式 | ✅ |
| `EMAIL_ENABLED` | 启用 Gmail 邮件日报 (`true` / `false`) | ❌ (默认 `false`) |
| `GMAIL_USER` | Gmail 发件人邮箱地址 | 条件必须 (当 `EMAIL_ENABLED=true`) |
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码 | 条件必须 (当 `EMAIL_ENABLED=true`) |
| `GMAIL_TO` | 收件人邮箱地址 | 条件必须 (当 `EMAIL_ENABLED=true`) |
| `PDF_EXTRACT_MODE` | PDF 提取模式 (`partial` / `full`) | ❌ (默认 `partial`) |
| `WEBHOOK_URL` | Discord / Slack Webhook URL | ❌ |
| `PROXY_URL` | 自定义代理地址 (默认 `http://127.0.0.1:7890`) | ❌ |

### 3. 本地运行

```bash
python main.py
```

> **代理说明**：本地开发时，如果项目根目录存在 `.env` 文件或设置了 `LOCAL_DEV=true`，会自动配置 HTTP/HTTPS 代理指向 `http://127.0.0.1:7890`。可通过 `PROXY_URL` 环境变量覆盖。

#### LLM 提供商选择

项目支持 **Google Gemini**、**DeepSeek** 和 **OpenAI ChatGPT** 三种 LLM：

| 提供商 | 优势 | 配置 |
|--------|------|------|
| **DeepSeek** (默认) | 性价比高、中文友好、API 稳定 | `LLM_PROVIDER=deepseek` + `DEEPSEEK_API_KEY` |
| **OpenAI** | 效果稳定、生态成熟、GPT-4o 系列 | `LLM_PROVIDER=openai` + `OPENAI_API_KEY` |
| **Gemini** | Google 官方、功能强大 | `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` |

在 `.env` 中设置 `LLM_PROVIDER` 即可切换：

```bash
# 使用 DeepSeek (推荐，性价比)
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxx

# 使用 OpenAI ChatGPT
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o-mini  # 或 gpt-4o, gpt-4-turbo

# 或使用 Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
```

**测试配置**：使用提供的测试脚本验证配置是否正确：

```bash
python tests/test_openai.py  # 测试 OpenAI 配置
```

#### Gmail 邮件日报配置

项目支持通过 Gmail 发送精美的 HTML 格式每日论文汇总邮件。

**启用步骤**：

1. **获取 Gmail 应用专用密码**：
   
   由于 Gmail 不再支持直接使用账户密码登录第三方应用，需要生成应用专用密码：
   
   - 访问 [Google 账户安全设置](https://myaccount.google.com/security)
   - 启用 **两步验证**（如果尚未启用）
   - 点击 **应用专用密码**（App passwords）
   - 选择应用：**邮件**，设备：**其他**（自定义名称如 "SystemPaperDaily"）
   - 复制生成的 16 位密码（无空格）

2. **配置环境变量**：
   
   在 `.env` 文件中添加：
   
   ```bash
   EMAIL_ENABLED=true
   GMAIL_USER=your-email@gmail.com
   GMAIL_APP_PASSWORD=abcdefghijklmnop  # 16位应用专用密码
   GMAIL_TO=recipient@gmail.com  # 可以与 GMAIL_USER 相同
   ```

3. **测试邮件发送**：
   
   使用专门的测试脚本验证配置：
   
   ```bash
   python tests/test_gmail.py
   ```
   
   或运行一次完整流程，检查邮箱是否收到邮件：
   
   ```bash
   python main.py
   ```

**邮件特性**：

- 📧 **精美 HTML 格式**：使用 Markdown 转 HTML，带响应式样式
- 📊 **完整论文信息**：包含标题、作者、分类、链接、AI 总结
- 🎨 **专业排版**：清晰的层级结构，易于阅读
- 📱 **移动友好**：自适应布局，手机阅读体验佳

**邮件示例标题**：`[System Paper Daily] 2026-02-11 (共 5 篇)`

**注意事项**：

- 使用应用专用密码，**不是** Gmail 账户密码
- 确保启用了两步验证
- 如果发送失败，检查日志中的详细错误信息
- Gmail 每日发送限额：500 封（个人账户）

#### PDF 提取模式选择

项目支持 **两种 PDF 内容提取模式**：

| 模式 | 提取内容 | 优势 | Token 消耗 | 适用场景 |
|------|---------|------|-----------|---------|
| **partial** (默认) | 前3页 + 最后1页 | 快速、低成本 | ~4K tokens/篇 | 日常监控、快速浏览 |
| **full** | 完整全文 | 信息完整、深度分析 | ~10-15K tokens/篇 | 重点论文、详细研究 |

在 `.env` 中设置：

```bash
# 部分提取模式 (默认，推荐日常使用)
PDF_EXTRACT_MODE=partial

# 全文提取模式 (深度分析，消耗更多 tokens)
PDF_EXTRACT_MODE=full
```

**建议**：
- 日常自动化运行：使用 `partial` 模式，节省 API 成本
- 重要论文精读：临时切换到 `full` 模式获取完整分析

### 4. GitHub Actions 自动运行

将以下 Secrets 添加到你的 GitHub 仓库 **Settings → Secrets and variables → Actions**：

- `LLM_PROVIDER` (可选，默认 `deepseek`)
- `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `GEMINI_API_KEY` (根据 LLM_PROVIDER 选择)
- `WEBHOOK_URL` (可选)

> `GITHUB_TOKEN` 由 Actions 自动提供，无需手动配置。

工作流将在每天 **UTC 00:00 (北京时间 08:00)** 自动运行，也可通过 **Actions → Run workflow** 手动触发。

## 关键词配置

在 `config.py` 中修改 `KEYWORDS` 列表来定制你关注的论文方向：

```python
KEYWORDS = [
    "distributed systems",
    "operating systems",
    "consensus",
    "RDMA",
    "persistent memory",
    "kernel",
    # ... 添加更多关键词
]
```

## 🧪 测试

项目提供了测试脚本来验证各项配置。所有测试脚本位于 `tests/` 目录。

### OpenAI API 测试

验证 OpenAI/ChatGPT 配置：

```bash
python tests/test_openai.py
```

测试内容：
- ✅ API Key 和 Base URL 配置
- ✅ 客户端连接测试
- ✅ 实际 API 调用
- ✅ 响应格式验证

### Gmail 邮件测试

验证 Gmail 邮件配置并发送测试邮件：

```bash
python tests/test_gmail.py
```

测试内容：
- ✅ Gmail 配置完整性检查
- ✅ SMTP 连接测试
- ✅ 发送测试邮件（包含示例论文）
- ✅ HTML 格式验证

详细测试文档请查看 [tests/README.md](tests/README.md)。

## AI 总结输出格式

每篇论文的 Gemini 总结遵循统一的 Markdown 模板：

```markdown
## 核心痛点
(一句话说明该论文试图解决什么问题)

## 关键设计/创新
- 创新点 1
- 创新点 2

## 评估与性能
(实验/评估数据摘要)

## 个人点评
(工业界落地可能性评价)
```

## License

MIT
