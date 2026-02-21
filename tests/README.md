# SystemPaperDaily 测试脚本

本目录包含各种测试脚本，用于验证项目配置和功能。

## 测试脚本列表

### 1. `test_openai.py` - OpenAI API 配置测试

验证 OpenAI/ChatGPT API 配置是否正确。

**运行方式**：
```bash
python tests/test_openai.py
```

**检查项目**：
- ✅ 环境变量配置（API Key、Base URL、Model）
- ✅ 客户端初始化
- ✅ API 调用测试
- ✅ 响应格式验证

### 2. `test_gmail.py` - QQ 邮箱配置测试

验证 QQ 邮箱邮件日报配置是否正确。

**运行方式**：
```bash
python tests/test_gmail.py
```

**检查项目**：
- ✅ QQ 邮箱配置完整性
- ✅ SMTP 连接测试
- ✅ 发送测试邮件
- ✅ HTML 格式验证

## 配置要求

所有测试脚本都需要在项目根目录下有正确配置的 `.env` 文件。

### OpenAI 测试所需配置：
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### QQ 邮箱测试所需配置：
```bash
EMAIL_ENABLED=true
QQ_MAIL_USER=your-email@qq.com
QQ_MAIL_AUTH_CODE=your-authorization-code
QQ_MAIL_TO=recipient@example.com
```

## 故障排查

如果测试失败，请查看测试脚本输出的详细日志，通常会包含：
- 具体错误原因
- 配置检查结果
- 故障排查建议

## 从项目根目录运行

所有测试脚本都可以从项目根目录运行：
```bash
# 从根目录运行
python tests/test_openai.py
python tests/test_gmail.py
```
