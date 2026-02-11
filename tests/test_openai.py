"""OpenAI API 配置测试脚本
快速验证您的 OPENAI_API_KEY 和 OPENAI_BASE_URL 是否配置正确。
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    import config
    from openai import OpenAI
except ImportError as e:
    logger.error("导入失败: %s", e)
    logger.error("请先安装依赖: pip install -r requirements.txt")
    sys.exit(1)


def test_openai_config():
    """测试 OpenAI API 配置。"""
    logger.info("=" * 60)
    logger.info("OpenAI API 配置测试")
    logger.info("=" * 60)
    
    # 1. 检查配置
    logger.info("检查环境变量配置...")
    logger.info("  LLM_PROVIDER: %s", config.LLM_PROVIDER)
    logger.info("  OPENAI_API_KEY: %s", 
                "已设置" if config.OPENAI_API_KEY else "❌ 未设置")
    logger.info("  OPENAI_BASE_URL: %s", config.OPENAI_BASE_URL)
    logger.info("  OPENAI_MODEL: %s", config.OPENAI_MODEL)
    
    if not config.OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY 未设置，请在 .env 文件中配置")
        return False
    
    # 2. 初始化客户端
    logger.info("\n初始化 OpenAI 客户端...")
    try:
        client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
        logger.info("✓ 客户端初始化成功")
    except Exception as e:
        logger.error("❌ 客户端初始化失败: %s", e)
        return False
    
    # 3. 测试 API 调用
    logger.info("\n测试 API 调用...")
    test_prompt = "请用中文回复：你好，这是一个测试。"
    
    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            max_tokens=50,
            temperature=0.7,
        )
        
        # 检查响应类型
        logger.info("  响应类型: %s", type(response).__name__)
        
        if isinstance(response, str):
            logger.error("❌ API 返回了字符串而不是对象")
            logger.error("  返回内容: %s", response[:200])
            logger.error("\n可能的原因:")
            logger.error("  1. OPENAI_BASE_URL 配置错误")
            logger.error("  2. OPENAI_API_KEY 无效")
            logger.error("  3. 使用了不兼容的 API 端点")
            return False
        
        if not hasattr(response, 'choices'):
            logger.error("❌ 响应对象缺少 choices 属性")
            logger.error("  对象类型: %s", type(response))
            return False
        
        if not response.choices:
            logger.error("❌ API 返回了空响应")
            return False
        
        # 获取响应内容
        reply = response.choices[0].message.content
        logger.info("✓ API 调用成功！")
        logger.info("  模型回复: %s", reply[:100])
        
        # 4. 显示使用统计
        if hasattr(response, 'usage'):
            logger.info("\n使用统计:")
            logger.info("  Prompt tokens: %s", response.usage.prompt_tokens)
            logger.info("  Completion tokens: %s", response.usage.completion_tokens)
            logger.info("  Total tokens: %s", response.usage.total_tokens)
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ OpenAI API 配置测试通过！")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error("❌ API 调用失败: %s", e, exc_info=True)
        logger.error("\n故障排查建议:")
        logger.error("  1. 检查 OPENAI_API_KEY 是否有效")
        logger.error("  2. 检查 OPENAI_BASE_URL 是否正确")
        logger.error("  3. 确认模型名称 '%s' 可用", config.OPENAI_MODEL)
        logger.error("  4. 检查网络连接和代理设置")
        return False


if __name__ == "__main__":
    success = test_openai_config()
    sys.exit(0 if success else 1)
