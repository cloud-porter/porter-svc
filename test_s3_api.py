"""
完整的 S3 服務 API 測試腳本
"""
import asyncio
import tempfile
from pathlib import Path
import sys

# 新增路徑
sys.path.append('.')

async def test_s3_api():
    """測試 S3 API 端點"""
    print("🧪 開始 S3 API 測試...")
    
    try:
        # 測試匯入
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # 測試健康檢查
        response = client.get("/health")
        print(f"✅ 健康檢查: {response.status_code}")
        
        # 測試 S3 列表端點（不需要真實 AWS 認證）
        response = client.get("/s3/files")
        print(f"📋 檔案列表端點: {response.status_code}")
        if response.status_code != 200:
            print(f"   回應: {response.json()}")
        
        print("✅ S3 API 測試完成")
        
    except Exception as e:
        print(f"❌ API 測試失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_s3_api())
