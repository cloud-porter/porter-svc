# AWS S3 檔案操作服務

## 🎯 概述

這是一個完整的 AWS S3 檔案操作服務，基於 FastAPI 和 aioboto3 建構，提供高效能的檔案上傳、下載和管理功能。

## ✨ 核心功能

### 📤 檔案上傳功能
- **標準上傳**: 支援小檔案直接上傳 (<5MB)
- **多部分上傳**: 大檔案自動切分上傳 (>5MB)
- **串流上傳**: 避免記憶體溢出的串流處理
- **進度追蹤**: 實時上傳進度回報
- **自動重試**: 失敗自動重試機制
- **Content-Type 檢測**: 自動檢測檔案類型

### 📥 檔案下載功能
- **Presigned URL**: 生成安全的臨時下載連結
- **串流下載**: 記憶體友善的串流處理
- **範圍下載**: 支援斷點續傳
- **速度限制**: 可配置的下載速度限制

### 🗂️ 檔案管理功能
- **檔案列表**: 支援前綴搜尋和分頁
- **檔案資訊**: 取得詳細的檔案 metadata
- **檔案操作**: 複製、移動、刪除
- **批次操作**: 支援批次檔案管理
- **標籤管理**: S3 物件標籤操作

### 🛡️ 錯誤處理
- **網路錯誤**: 連線逾時、DNS 解析失敗處理
- **AWS 錯誤**: 權限、配額、服務可用性錯誤處理
- **檔案錯誤**: 檔案大小、格式驗證

## 🚀 快速開始

### 1. 環境設定

複製環境變數範例檔案：
```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入你的 AWS 認證資訊：
```env
# AWS 認證
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1

# S3 設定
S3_BUCKET_NAME=your-bucket-name
S3_ENDPOINT_URL=

# 向後相容設定
AK=your_access_key_here
SK=your_secret_key_here
BUCKET_NAME=your-bucket-name
REGION_NAME=us-east-1
```

### 2. 安裝依賴

```bash
pip install aioboto3>=12.3.0 aiofiles>=23.2.1 python-dotenv
```

### 3. 啟動服務

```bash
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 訪問 API 文件

開啟瀏覽器訪問：http://localhost:8000/api/docs

## 📚 API 端點

### 檔案上傳
- `POST /s3/upload` - 上傳檔案
- `POST /s3/upload/multipart` - 多部分上傳
- `POST /s3/upload/stream` - 串流上傳

### 檔案下載
- `GET /s3/download/{object_key}` - 下載檔案
- `GET /s3/presigned-url/{object_key}` - 生成預簽名 URL

### 檔案管理
- `GET /s3/list` - 列出檔案
- `GET /s3/info/{object_key}` - 取得檔案資訊
- `DELETE /s3/delete/{object_key}` - 刪除檔案
- `POST /s3/copy` - 複製檔案
- `POST /s3/move` - 移動檔案

### 批次操作
- `POST /s3/batch/delete` - 批次刪除檔案

## 💻 程式碼範例

### Python 客戶端範例
```python
import asyncio
from app.services.s3_service import S3Service
from app.services.s3_config import S3Config

async def upload_example():
    config = S3Config(
        aws_access_key_id="your_key",
        aws_secret_access_key="your_secret",
        bucket_name="your-bucket"
    )
    
    async with S3Service(config) as s3:
        # 上傳檔案
        result = await s3.upload_file(
            file_path="local_file.txt",
            object_key="uploads/file.txt"
        )
        print(f"上傳成功: {result}")

# 執行範例
asyncio.run(upload_example())
```

### cURL 範例
```bash
# 上傳檔案
curl -X POST "http://localhost:8000/s3/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@test.txt" \
     -F "object_key=uploads/test.txt"

# 列出檔案
curl -X GET "http://localhost:8000/s3/list?prefix=uploads/" \
     -H "accept: application/json"

# 下載檔案
curl -X GET "http://localhost:8000/s3/download/uploads/test.txt" \
     -H "accept: application/json"
```

## ⚙️ 配置選項

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `max_concurrent_uploads` | 10 | 最大並發上傳數 |
| `multipart_threshold` | 5MB | 多部分上傳閾值 |
| `multipart_chunksize` | 8MB | 多部分上傳塊大小 |
| `connect_timeout` | 60秒 | 連線逾時時間 |
| `read_timeout` | 300秒 | 讀取逾時時間 |
| `max_retry_attempts` | 3 | 最大重試次數 |
| `default_presigned_url_expiry` | 3600秒 | 預設 URL 過期時間 |

## 🧪 測試

執行測試套件：
```bash
python -m pytest tests/test_s3_service.py -v
```

執行範例程式：
```bash
python examples/s3_usage_examples.py
```

## 📊 效能特色

- **異步處理**: 使用 asyncio 和 aioboto3 實現高併發
- **記憶體最佳化**: 串流處理避免大檔案記憶體問題
- **智能重試**: 指數退避重試策略
- **連線池管理**: 有效管理 HTTP 連線
- **快取機制**: Metadata 快取減少 API 呼叫

## 🔒 安全性

- **認證管理**: 安全的 AWS 認證處理
- **權限控制**: 細粒度的 S3 權限管理
- **錯誤處理**: 詳細的錯誤分類和處理
- **日誌記錄**: 完整的操作日誌追蹤

## 🛠️ 故障排除

### 常見問題

1. **認證錯誤**: 確認 AWS 認證資訊正確
2. **權限不足**: 檢查 IAM 政策是否包含必要的 S3 權限
3. **Bucket 不存在**: 確認 bucket 名稱正確且存在
4. **網路問題**: 檢查網路連線和防火牆設定

### 日誌查看
服務使用結構化日誌，可以透過以下方式查看：
```bash
tail -f service.log
```

## 📝 版本資訊

- **版本**: 1.0.0
- **Python**: >=3.11
- **FastAPI**: >=0.115.12
- **aioboto3**: >=12.3.0
- **aiofiles**: >=23.2.1

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License
