"""
S3 服務測試案例
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.s3_service import S3Service
from app.services.s3_config import S3Config
from app.services.s3_exceptions import (
    S3ServiceError, S3FileNotFoundError, S3PermissionError,
    S3BucketNotFoundError, S3AuthenticationError
)


@pytest.fixture
def s3_config():
    """測試用 S3 配置"""
    return S3Config(
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        aws_region="us-east-1",
        bucket_name="test-bucket",
        multipart_threshold=5 * 1024 * 1024,
        multipart_chunksize=8 * 1024 * 1024,
        max_concurrent_uploads=3
    )


@pytest.fixture
def mock_s3_client():
    """模擬 S3 客戶端"""
    client = AsyncMock()
    return client


@pytest.fixture
async def s3_service(s3_config, mock_s3_client):
    """測試用 S3 服務實例"""
    service = S3Service(s3_config)
    service._s3_client = mock_s3_client
    return service


class TestS3Service:
    """S3 服務測試類別"""
    
    async def test_upload_small_file(self, s3_service, mock_s3_client):
        """測試小檔案上傳"""
        # 建立臨時檔案
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)
        
        try:
            # 模擬 S3 回應
            mock_s3_client.put_object.return_value = {
                'ETag': '"test-etag"'
            }
            
            # 執行上傳
            result = await s3_service.upload_file(
                file_path=temp_path,
                object_key="test/file.txt"
            )
            
            # 驗證結果
            assert result['object_key'] == "test/file.txt"
            assert result['upload_type'] == "simple"
            assert 'etag' in result
            
            # 驗證 S3 客戶端呼叫
            mock_s3_client.put_object.assert_called_once()
            call_args = mock_s3_client.put_object.call_args
            assert call_args[1]['Bucket'] == "test-bucket"
            assert call_args[1]['Key'] == "test/file.txt"
        
        finally:
            temp_path.unlink()
    
    async def test_upload_large_file_multipart(self, s3_service, mock_s3_client):
        """測試大檔案多部分上傳"""
        # 建立大於閾值的臨時檔案
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 寫入 6MB 資料
            data = b"x" * (6 * 1024 * 1024)
            f.write(data)
            temp_path = Path(f.name)
        
        try:
            # 模擬多部分上傳回應
            mock_s3_client.create_multipart_upload.return_value = {
                'UploadId': 'test-upload-id'
            }
            mock_s3_client.upload_part.return_value = {
                'ETag': '"part-etag"'
            }
            mock_s3_client.complete_multipart_upload.return_value = {}
            
            # 執行上傳
            result = await s3_service.upload_file(
                file_path=temp_path,
                object_key="test/large_file.bin"
            )
            
            # 驗證結果
            assert result['object_key'] == "test/large_file.bin"
            assert result['upload_type'] == "multipart"
            assert result['total_parts'] == 1  # 6MB 會分成 1 個部分
            
            # 驗證多部分上傳呼叫
            mock_s3_client.create_multipart_upload.assert_called_once()
            mock_s3_client.upload_part.assert_called()
            mock_s3_client.complete_multipart_upload.assert_called_once()
        
        finally:
            temp_path.unlink()
    
    async def test_upload_stream(self, s3_service, mock_s3_client):
        """測試串流上傳"""
        # 模擬 S3 回應
        mock_s3_client.put_object.return_value = {
            'ETag': '"stream-etag"'
        }
        
        # 執行串流上傳
        data = b"stream test data"
        result = await s3_service.upload_stream(
            data_stream=data,
            object_key="test/stream.txt",
            content_type="text/plain"
        )
        
        # 驗證結果
        assert result['object_key'] == "test/stream.txt"
        assert result['upload_type'] == "stream"
        assert result['file_size'] == len(data)
        
        # 驗證 S3 客戶端呼叫
        mock_s3_client.put_object.assert_called_once()
    
    async def test_download_file(self, s3_service, mock_s3_client):
        """測試檔案下載"""
        # 模擬檔案資訊
        mock_s3_client.head_object.return_value = {
            'ContentLength': 100,
            'ContentType': 'text/plain',
            'ETag': '"test-etag"',
            'LastModified': None,
            'Metadata': {}
        }
        
        # 模擬下載回應
        mock_response = MagicMock()
        mock_response.__aiter__ = AsyncMock(return_value=iter([b"test content"]))
        mock_s3_client.get_object.return_value = {
            'Body': mock_response
        }
        
        # 建立臨時下載目錄
        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "downloaded_file.txt"
            
            # 執行下載
            result = await s3_service.download_file(
                object_key="test/file.txt",
                local_path=download_path
            )
            
            # 驗證結果
            assert result['object_key'] == "test/file.txt"
            assert result['local_path'] == str(download_path)
            assert download_path.exists()
    
    async def test_generate_presigned_url(self, s3_service, mock_s3_client):
        """測試預簽名 URL 產生"""
        # 模擬預簽名 URL 回應
        mock_s3_client.generate_presigned_url.return_value = "https://test-url.com"
        
        # 執行預簽名 URL 產生
        url = await s3_service.generate_presigned_url(
            object_key="test/file.txt",
            operation="get_object",
            expiry_seconds=3600
        )
        
        # 驗證結果
        assert url == "https://test-url.com"
        
        # 驗證 S3 客戶端呼叫
        mock_s3_client.generate_presigned_url.assert_called_once()
    
    async def test_file_exists_true(self, s3_service, mock_s3_client):
        """測試檔案存在檢查 - 存在"""
        # 模擬檔案存在
        mock_s3_client.head_object.return_value = {}
        
        # 執行檢查
        exists = await s3_service.file_exists("test/file.txt")
        
        # 驗證結果
        assert exists is True
    
    async def test_file_exists_false(self, s3_service, mock_s3_client):
        """測試檔案存在檢查 - 不存在"""
        from botocore.exceptions import ClientError
        
        # 模擬檔案不存在錯誤
        error = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
            operation_name='HeadObject'
        )
        mock_s3_client.head_object.side_effect = error
        
        # 執行檢查
        exists = await s3_service.file_exists("test/nonexistent.txt")
        
        # 驗證結果
        assert exists is False
    
    async def test_get_file_info(self, s3_service, mock_s3_client):
        """測試取得檔案資訊"""
        # 模擬檔案資訊回應
        mock_s3_client.head_object.return_value = {
            'ContentLength': 1024,
            'ContentType': 'text/plain',
            'ETag': '"test-etag"',
            'LastModified': None,
            'Metadata': {'author': 'test'},
            'CacheControl': 'max-age=3600',
            'StorageClass': 'STANDARD'
        }
        
        # 執行取得檔案資訊
        info = await s3_service.get_file_info("test/file.txt")
        
        # 驗證結果
        assert info['object_key'] == "test/file.txt"
        assert info['size'] == 1024
        assert info['content_type'] == 'text/plain'
        assert info['metadata']['author'] == 'test'
    
    async def test_delete_file(self, s3_service, mock_s3_client):
        """測試檔案刪除"""
        # 模擬刪除回應
        mock_s3_client.delete_object.return_value = {}
        
        # 執行刪除
        result = await s3_service.delete_file("test/file.txt")
        
        # 驗證結果
        assert result is True
        
        # 驗證 S3 客戶端呼叫
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt"
        )
    
    async def test_delete_files_batch(self, s3_service, mock_s3_client):
        """測試批次檔案刪除"""
        # 模擬批次刪除回應
        mock_s3_client.delete_objects.return_value = {
            'Deleted': [
                {'Key': 'test/file1.txt'},
                {'Key': 'test/file2.txt'}
            ],
            'Errors': []
        }
        
        # 執行批次刪除
        files_to_delete = ["test/file1.txt", "test/file2.txt"]
        result = await s3_service.delete_files(files_to_delete)
        
        # 驗證結果
        assert result["test/file1.txt"] is True
        assert result["test/file2.txt"] is True
    
    async def test_copy_file(self, s3_service, mock_s3_client):
        """測試檔案複製"""
        # 模擬複製回應
        mock_s3_client.copy_object.return_value = {
            'ETag': '"copy-etag"'
        }
        
        # 執行複製
        result = await s3_service.copy_file(
            source_key="test/source.txt",
            destination_key="test/destination.txt"
        )
        
        # 驗證結果
        assert result['source_key'] == "test/source.txt"
        assert result['destination_key'] == "test/destination.txt"
        assert 'etag' in result
    
    async def test_list_files(self, s3_service, mock_s3_client):
        """測試檔案列表"""
        # 模擬列表回應
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test/file1.txt',
                    'Size': 100,
                    'LastModified': None,
                    'ETag': '"etag1"',
                    'StorageClass': 'STANDARD'
                },
                {
                    'Key': 'test/file2.txt',
                    'Size': 200,
                    'LastModified': None,
                    'ETag': '"etag2"',
                    'StorageClass': 'STANDARD'
                }
            ],
            'IsTruncated': False
        }
        
        # 執行列表
        result = await s3_service.list_files(prefix="test/")
        
        # 驗證結果
        assert result['total_count'] == 2
        assert len(result['files']) == 2
        assert result['files'][0]['object_key'] == 'test/file1.txt'
        assert result['files'][1]['object_key'] == 'test/file2.txt'
    
    async def test_error_handling_bucket_not_found(self, s3_service, mock_s3_client):
        """測試 Bucket 不存在錯誤處理"""
        from botocore.exceptions import ClientError
        
        # 模擬 Bucket 不存在錯誤
        error = ClientError(
            error_response={'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
            operation_name='PutObject'
        )
        mock_s3_client.put_object.side_effect = error
        
        # 執行上傳並預期錯誤
        with pytest.raises(S3BucketNotFoundError):
            await s3_service.upload_stream(
                data_stream=b"test",
                object_key="test/file.txt"
            )
    
    async def test_error_handling_permission_denied(self, s3_service, mock_s3_client):
        """測試權限不足錯誤處理"""
        from botocore.exceptions import ClientError
        
        # 模擬權限不足錯誤
        error = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            operation_name='GetObject'
        )
        mock_s3_client.get_object.side_effect = error
        
        # 執行下載並預期錯誤
        with pytest.raises(S3PermissionError):
            async for _ in s3_service.download_stream("test/file.txt"):
                pass
    
    async def test_progress_callback(self, s3_service, mock_s3_client):
        """測試進度回調"""
        # 建立臨時檔案
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content for progress")
            temp_path = Path(f.name)
        
        try:
            # 模擬 S3 回應
            mock_s3_client.put_object.return_value = {
                'ETag': '"test-etag"'
            }
            
            # 建立進度追蹤器
            progress_calls = []
            
            def progress_callback(progress_info):
                progress_calls.append(progress_info)
            
            # 執行上傳
            await s3_service.upload_file(
                file_path=temp_path,
                object_key="test/file.txt",
                progress_callback=progress_callback
            )
            
            # 驗證進度回調被呼叫
            assert len(progress_calls) > 0
            assert progress_calls[-1]['progress_percentage'] == 100.0
        
        finally:
            temp_path.unlink()


class TestS3Helpers:
    """S3 輔助函式測試類別"""
    
    def test_detect_content_type(self):
        """測試 Content-Type 檢測"""
        from app.utils.s3_helpers import detect_content_type
        
        assert detect_content_type("test.txt") == "text/plain"
        assert detect_content_type("test.jpg") == "image/jpeg"
        assert detect_content_type("test.pdf") == "application/pdf"
        assert detect_content_type("test.unknown") == "application/octet-stream"
    
    def test_format_file_size(self):
        """測試檔案大小格式化"""
        from app.utils.s3_helpers import format_file_size
        
        assert format_file_size(0) == "0 B"
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1024 * 1024) == "1.00 MB"
        assert format_file_size(1024 * 1024 * 1024) == "1.00 GB"
    
    def test_validate_s3_key(self):
        """測試 S3 鍵名驗證"""
        from app.utils.s3_helpers import validate_s3_key
        
        assert validate_s3_key("valid/key.txt") is True
        assert validate_s3_key("another-valid_key.jpg") is True
        assert validate_s3_key("") is False  # 空字串
        assert validate_s3_key("a" * 1025) is False  # 過長
        assert validate_s3_key("invalid\x00key") is False  # 包含無效字元
    
    def test_sanitize_s3_key(self):
        """測試 S3 鍵名清理"""
        from app.utils.s3_helpers import sanitize_s3_key
        
        assert sanitize_s3_key("/folder/file.txt") == "folder/file.txt"
        assert sanitize_s3_key("folder//file.txt") == "folder/file.txt"
        assert sanitize_s3_key("folder\\file.txt") == "folder/file.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
