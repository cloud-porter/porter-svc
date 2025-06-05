#!/usr/bin/env python3
"""
S3 服務整合測試
"""
import asyncio
import sys
from pathlib import Path

# 新增路徑以匯入 app 模組
sys.path.append(str(Path(__file__).parent / "app"))

try:
    from services.s3_service import S3Service
    from services.s3_config import S3Config
    print("✅ S3 服務模組匯入成功")
except ImportError as e:
    print(f"❌ S3 服務模組匯入失敗: {e}")
    sys.exit(1)

async def test_s3_service():
    """測試 S3 服務基本功能"""
    print("🧪 開始 S3 服務測試...")
    
    # 建立測試配置
    config = S3Config(
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        aws_region="us-east-1",
        bucket_name="test-bucket"
    )
    print("✅ S3 配置建立成功")
    
    # 建立 S3 服務實例
    s3_service = S3Service(config)
    print("✅ S3 服務實例建立成功")
    
    # 測試配置訪問
    print(f"📊 Bucket 名稱: {s3_service.config.bucket_name}")
    print(f"📊 AWS 區域: {s3_service.config.aws_region}")
    print(f"📊 多部分上傳閾值: {s3_service.config.multipart_threshold:,} bytes")
    print(f"📊 最大並發上傳數: {s3_service.config.max_concurrent_uploads}")
    
    print("✅ S3 服務整合測試完成")

if __name__ == "__main__":
    asyncio.run(test_s3_service())
