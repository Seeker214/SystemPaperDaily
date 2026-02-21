"""QQ 邮箱发送测试脚本
快速验证您的 QQ 邮箱配置是否正确。
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
    from src.notifier import send_email_digest
    from src.sources.base import Paper
except ImportError as e:
    logger.error("导入失败: %s", e)
    logger.error("请先安装依赖: pip install -r requirements.txt")
    sys.exit(1)


def test_gmail_config():
    """测试 QQ 邮箱配置。"""
    logger.info("=" * 60)
    logger.info("QQ 邮箱配置测试")
    logger.info("=" * 60)
    
    # 1. 检查配置
    logger.info("检查环境变量配置...")
    logger.info("  EMAIL_ENABLED: %s", config.EMAIL_ENABLED)
    logger.info("  QQ_MAIL_USER: %s", 
                config.QQ_MAIL_USER if config.QQ_MAIL_USER else "❌ 未设置")
    logger.info("  QQ_MAIL_AUTH_CODE: %s", 
                "已设置" if config.QQ_MAIL_AUTH_CODE else "❌ 未设置")
    logger.info("  QQ_MAIL_TO: %s", 
                config.QQ_MAIL_TO if config.QQ_MAIL_TO else "❌ 未设置")
    
    if not config.EMAIL_ENABLED:
        logger.warning("⚠️  EMAIL_ENABLED=false，邮件功能未启用")
        logger.info("\n请在 .env 文件中设置 EMAIL_ENABLED=true")
        return False
    
    if not config.QQ_MAIL_USER or not config.QQ_MAIL_AUTH_CODE or not config.QQ_MAIL_TO:
        logger.error("❌ QQ 邮箱配置不完整")
        logger.error("\n请在 .env 文件中设置:")
        logger.error("  QQ_MAIL_USER=your-email@qq.com")
        logger.error("  QQ_MAIL_AUTH_CODE=your-authorization-code")
        logger.error("  QQ_MAIL_TO=recipient@example.com")
        logger.error("\n如何获取 QQ 邮箱授权码:")
        logger.error("  1. 登录 QQ 邮箱 https://mail.qq.com")
        logger.error("  2. 进入 设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务")
        logger.error("  3. 开启 SMTP 服务并获取授权码")
        return False
    
    # 2. 创建测试数据
    logger.info("\n创建测试论文数据...")
    test_papers = [
        (
            Paper(
                paper_id="test-001",
                title="Test Paper: Distributed Systems Architecture",
                authors=["Alice Zhang", "Bob Chen", "Carol Wang"],
                abstract="This is a test paper about distributed systems...",
                categories=["cs.DC", "cs.OS"],
                published="2026-02-11",
                pdf_url="https://arxiv.org/pdf/test-001.pdf",
                html_url="https://arxiv.org/abs/test-001",
            ),
            """## 1. Meta Info
- **Type**: System Implementation
- **Keywords**: Distributed Systems, RDMA, Consensus

## 2. The Problem (What & Why)
- **背景**: 在大规模分布式系统中，传统的网络通信成为性能瓶颈
- **现有缺陷**: TCP/IP 协议栈开销占用了 40% 的 CPU 时间

## 3. The Solution (How)
- **核心方法**: 通过 RDMA 技术实现零拷贝网络传输
- **系统设计**: 采用分层架构，将数据平面与控制平面解耦

## 4. Performance (Results)
- **测试环境**: 100 节点集群
- **关键提升**: 吞吐量提升 5 倍，延迟降低 80%

## 5. Critical Takeaway (TL;DR)
- **一句话总结**: 这是一个通过 RDMA 优化分布式系统性能的创新方案，适合高性能计算场景。
""",
        ),
    ]
    
    # 3. 发送测试邮件
    logger.info("\n发送测试邮件...")
    logger.info("  从: %s", config.QQ_MAIL_USER)
    logger.info("  到: %s", config.QQ_MAIL_TO)
    logger.info("  论文数量: %d", len(test_papers))
    
    try:
        success = send_email_digest(test_papers)
        
        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ QQ 邮箱发送测试通过！")
            logger.info("=" * 60)
            logger.info("\n请检查邮箱 %s 是否收到测试邮件", config.QQ_MAIL_TO)
            logger.info("邮件标题应为: [System Paper Daily] YYYY-MM-DD (共 1 篇)")
            logger.info("\n如果未收到邮件，请检查:")
            logger.info("  1. 垃圾邮件/垃圾箱文件夹")
            logger.info("  2. QQ 邮箱授权码是否正确")
            logger.info("  3. SMTP 服务是否已开启")
            return True
        else:
            logger.error("\n❌ 邮件发送失败")
            logger.error("请查看上方的详细错误日志")
            return False
            
    except Exception as e:
        logger.error("❌ 测试过程中发生错误: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    success = test_gmail_config()
    sys.exit(0 if success else 1)
