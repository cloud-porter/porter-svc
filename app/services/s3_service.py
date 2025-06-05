"""
完整的 AWS S3 檔案操作服務
支援高效能檔案上傳、下載與管理
"""
import asyncio
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, List, Any, Union, Callable, AsyncGenerator
from urllib.parse import urlparse

import aioboto3
import aiofiles
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from .s3_config import S3Config, S3RetryConfig
from .s3_exceptions import (
    S3ServiceError, S3ConnectionError, S3AuthenticationError,
    S3BucketNotFoundError, S3FileNotFoundError, S3PermissionError,
    S3FileTooLargeError, S3UploadError, S3DownloadError,
    S3MultipartUploadError, S3NetworkError, S3QuotaExceededError,
    S3ServiceUnavailableError
)
from ..utils.s3_helpers import (
    detect_content_type, calculate_file_hash, format_file_size,
    generate_multipart_key, validate_s3_key, sanitize_s3_key,
    create_metadata, RetryHandler, ProgressTracker
)
from ..utils.logger import logger


class S3Service:
    """AWS S3 檔案操作服務"""
    
    def __init__(self, config: S3Config):
        self.config = config
        self.retry_handler = RetryHandler(S3RetryConfig(
            max_attempts=config.max_retry_attempts
        ))
        self._metadata_cache: Dict[str, Dict] = {}
        self._session = None
        self._s3_client = None
        
        # 設定 boto3 配置
        self._boto_config = Config(
            region_name=config.aws_region,
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            max_pool_connections=config.max_concurrent_uploads,
            retries={'max_attempts': 0}  # 使用自定義重試邏輯
        )
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        await self._close_client()
    
    async def _ensure_client(self):
        """確保 S3 客戶端已初始化"""
        if self._s3_client is None:
            self._session = aioboto3.Session()
            self._s3_client = await self._session.client(
                's3',
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
                endpoint_url=self.config.endpoint_url,
                config=self._boto_config
            ).__aenter__()
    
    async def _close_client(self):
        """關閉 S3 客戶端"""
        if self._s3_client:
            try:
                await self._s3_client.__aexit__(None, None, None)
            except Exception:
                pass  # 忽略關閉時的錯誤
            finally:
                self._s3_client = None
                self._session = None
    
    def _handle_s3_error(self, error: Exception, operation: str) -> Exception:
        """處理 S3 錯誤並轉換為自定義例外"""
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            error_message = error.response['Error']['Message']
            
            if error_code == 'NoSuchBucket':
                return S3BucketNotFoundError(f"Bucket '{self.config.bucket_name}' 不存在")
            elif error_code == 'NoSuchKey':
                return S3FileNotFoundError(f"檔案不存在: {error_message}")
            elif error_code == 'AccessDenied':
                return S3PermissionError(f"權限不足: {error_message}")
            elif error_code == 'InvalidAccessKeyId':
                return S3AuthenticationError(f"認證失敗: 無效的 Access Key")
            elif error_code == 'SignatureDoesNotMatch':
                return S3AuthenticationError(f"認證失敗: 簽名不匹配")
            elif error_code == 'RequestTimeTooSkewed':
                return S3AuthenticationError(f"認證失敗: 時間偏差過大")
            elif error_code == 'ServiceUnavailable':
                return S3ServiceUnavailableError(f"S3 服務暫時不可用")
            elif error_code == 'SlowDown' or error_code == 'RequestLimitExceeded':
                return S3QuotaExceededError(f"請求頻率過高，請稍後重試")
            else:
                return S3ServiceError(f"{operation} 失敗: {error_message}", error_code)
        
        elif isinstance(error, BotoCoreError):
            return S3NetworkError(f"網路錯誤: {str(error)}")
        
        return S3ServiceError(f"{operation} 失敗: {str(error)}")
    
    # === 檔案上傳功能 ===
    
    async def upload_file(
        self,
        file_path: Union[str, Path],
        object_key: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        上傳檔案到 S3
        
        Args:
            file_path: 本地檔案路徑
            object_key: S3 物件鍵名，如果為 None 則使用檔案名
            content_type: Content-Type，如果為 None 則自動檢測
            metadata: 自定義 metadata
            progress_callback: 進度回調函式
            
        Returns:
            上傳結果資訊
        """
        await self._ensure_client()
        
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        if not file_path.exists():
            raise S3FileNotFoundError(f"本地檔案不存在: {file_path}")
        
        file_size = file_path.stat().st_size
        
        # 檢查檔案大小
        if file_size > 5 * 1024 * 1024 * 1024:  # 5GB 限制
            raise S3FileTooLargeError(f"檔案過大: {format_file_size(file_size)} > 5GB")
        
        # 設定物件鍵名
        if object_key is None:
            object_key = file_path.name
        
        object_key = sanitize_s3_key(object_key)
        
        if not validate_s3_key(object_key):
            raise S3ServiceError(f"無效的物件鍵名: {object_key}")
        
        # 自動檢測 Content-Type
        if content_type is None:
            content_type = detect_content_type(file_path)
        
        # 建立 metadata
        upload_metadata = create_metadata(
            content_type=content_type,
            custom_metadata=metadata
        )
        
        try:
            # 根據檔案大小選擇上傳方式
            if file_size >= self.config.multipart_threshold:
                return await self._multipart_upload(
                    file_path, object_key, upload_metadata, progress_callback
                )
            else:
                return await self._simple_upload(
                    file_path, object_key, upload_metadata, progress_callback
                )
        
        except Exception as e:
            error = self._handle_s3_error(e, "檔案上傳")
            logger.error(f"檔案上傳失敗: {file_path} -> {object_key}, 錯誤: {error}")
            raise error
    
    async def _simple_upload(
        self,
        file_path: Path,
        object_key: str,
        metadata: Dict[str, str],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """簡單檔案上傳"""
        file_size = file_path.stat().st_size
        
        if progress_callback:
            tracker = ProgressTracker(file_size, progress_callback)
        
        async with aiofiles.open(file_path, 'rb') as f:
            file_data = await f.read()
            
            if progress_callback:
                tracker.update(file_size)
        
        response = await self.retry_handler.execute_with_retry(
            self._s3_client.put_object,
            Bucket=self.config.bucket_name,
            Key=object_key,
            Body=file_data,
            **metadata
        )
        
        return {
            'object_key': object_key,
            'file_size': file_size,
            'etag': response.get('ETag', '').strip('"'),
            'upload_type': 'simple',
            'upload_time': datetime.utcnow().isoformat()
        }
    
    async def _multipart_upload(
        self,
        file_path: Path,
        object_key: str,
        metadata: Dict[str, str],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """多部分檔案上傳"""
        file_size = file_path.stat().st_size
        chunk_size = self.config.multipart_chunksize
        
        if progress_callback:
            tracker = ProgressTracker(file_size, progress_callback)
        
        try:
            # 初始化多部分上傳
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.create_multipart_upload,
                Bucket=self.config.bucket_name,
                Key=object_key,
                **metadata
            )
            
            upload_id = response['UploadId']
            parts = []
            
            # 計算分片數量
            total_parts = (file_size + chunk_size - 1) // chunk_size
            
            async with aiofiles.open(file_path, 'rb') as f:
                # 限制並發上傳數量
                semaphore = asyncio.Semaphore(self.config.max_concurrent_uploads)
                
                async def upload_part(part_number: int, start_pos: int, end_pos: int):
                    async with semaphore:
                        await f.seek(start_pos)
                        chunk_data = await f.read(end_pos - start_pos)
                        
                        response = await self.retry_handler.execute_with_retry(
                            self._s3_client.upload_part,
                            Bucket=self.config.bucket_name,
                            Key=object_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=chunk_data
                        )
                        
                        if progress_callback:
                            tracker.update(len(chunk_data))
                        
                        return {
                            'ETag': response['ETag'],
                            'PartNumber': part_number
                        }
                
                # 建立所有上傳任務
                tasks = []
                for i in range(total_parts):
                    start_pos = i * chunk_size
                    end_pos = min((i + 1) * chunk_size, file_size)
                    part_number = i + 1
                    
                    task = upload_part(part_number, start_pos, end_pos)
                    tasks.append(task)
                
                # 並行執行所有上傳任務
                parts = await asyncio.gather(*tasks)
            
            # 完成多部分上傳
            await self.retry_handler.execute_with_retry(
                self._s3_client.complete_multipart_upload,
                Bucket=self.config.bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            return {
                'object_key': object_key,
                'file_size': file_size,
                'upload_type': 'multipart',
                'total_parts': total_parts,
                'upload_time': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            # 清理未完成的多部分上傳
            try:
                await self._s3_client.abort_multipart_upload(
                    Bucket=self.config.bucket_name,
                    Key=object_key,
                    UploadId=upload_id
                )
            except:
                pass
            
            raise S3MultipartUploadError(f"多部分上傳失敗: {str(e)}")
    
    async def upload_stream(
        self,
        data_stream: Union[bytes, BytesIO, AsyncGenerator[bytes, None]],
        object_key: str,
        content_length: Optional[int] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        上傳資料串流到 S3
        
        Args:
            data_stream: 資料串流
            object_key: S3 物件鍵名
            content_length: 內容長度
            content_type: Content-Type
            metadata: 自定義 metadata
            
        Returns:
            上傳結果資訊
        """
        await self._ensure_client()
        
        object_key = sanitize_s3_key(object_key)
        
        if not validate_s3_key(object_key):
            raise S3ServiceError(f"無效的物件鍵名: {object_key}")
        
        # 建立 metadata
        upload_metadata = create_metadata(
            content_type=content_type or "application/octet-stream",
            custom_metadata=metadata
        )
        
        try:
            if isinstance(data_stream, bytes):
                body = data_stream
            elif isinstance(data_stream, BytesIO):
                body = data_stream.getvalue()
            else:
                # 處理異步生成器
                chunks = []
                async for chunk in data_stream:
                    chunks.append(chunk)
                body = b''.join(chunks)
            
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.put_object,
                Bucket=self.config.bucket_name,
                Key=object_key,
                Body=body,
                **upload_metadata
            )
            
            return {
                'object_key': object_key,
                'file_size': len(body),
                'etag': response.get('ETag', '').strip('"'),
                'upload_type': 'stream',
                'upload_time': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            error = self._handle_s3_error(e, "串流上傳")
            logger.error(f"串流上傳失敗: {object_key}, 錯誤: {error}")
            raise error
    
    # === 檔案下載功能 ===
    
    async def download_file(
        self,
        object_key: str,
        local_path: Union[str, Path],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        從 S3 下載檔案
        
        Args:
            object_key: S3 物件鍵名
            local_path: 本地儲存路徑
            progress_callback: 進度回調函式
            
        Returns:
            下載結果資訊
        """
        await self._ensure_client()
        
        if isinstance(local_path, str):
            local_path = Path(local_path)
        
        # 確保目錄存在
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 取得檔案資訊
            file_info = await self.get_file_info(object_key)
            file_size = file_info['size']
            
            if progress_callback:
                tracker = ProgressTracker(file_size, progress_callback)
            
            # 下載檔案
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.get_object,
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            
            async with aiofiles.open(local_path, 'wb') as f:
                async for chunk in response['Body']:
                    await f.write(chunk)
                    if progress_callback:
                        tracker.update(len(chunk))
            
            return {
                'object_key': object_key,
                'local_path': str(local_path),
                'file_size': file_size,
                'download_time': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            error = self._handle_s3_error(e, "檔案下載")
            logger.error(f"檔案下載失敗: {object_key} -> {local_path}, 錯誤: {error}")
            raise error
    
    async def download_stream(
        self,
        object_key: str,
        start_byte: Optional[int] = None,
        end_byte: Optional[int] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        以串流方式下載檔案
        
        Args:
            object_key: S3 物件鍵名
            start_byte: 開始位元組位置
            end_byte: 結束位元組位置
            
        Yields:
            檔案資料塊
        """
        await self._ensure_client()
        
        try:
            kwargs = {
                'Bucket': self.config.bucket_name,
                'Key': object_key
            }
            
            # 設定範圍下載
            if start_byte is not None or end_byte is not None:
                range_header = f"bytes={start_byte or 0}-"
                if end_byte is not None:
                    range_header += str(end_byte)
                kwargs['Range'] = range_header
            
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.get_object,
                **kwargs
            )
            
            async for chunk in response['Body']:
                yield chunk
        
        except Exception as e:
            error = self._handle_s3_error(e, "串流下載")
            logger.error(f"串流下載失敗: {object_key}, 錯誤: {error}")
            raise error
    
    async def generate_presigned_url(
        self,
        object_key: str,
        operation: str = 'get_object',
        expiry_seconds: Optional[int] = None,
        conditions: Optional[Dict] = None
    ) -> str:
        """
        產生預簽名 URL
        
        Args:
            object_key: S3 物件鍵名
            operation: 操作類型 (get_object, put_object)
            expiry_seconds: 過期時間（秒）
            conditions: 額外條件
            
        Returns:
            預簽名 URL
        """
        await self._ensure_client()
        
        if expiry_seconds is None:
            expiry_seconds = self.config.default_presigned_url_expiry
        
        if expiry_seconds > self.config.max_presigned_url_expiry:
            raise S3ServiceError(f"過期時間過長: {expiry_seconds} > {self.config.max_presigned_url_expiry}")
        
        try:
            params = {
                'Bucket': self.config.bucket_name,
                'Key': object_key
            }
            
            if conditions:
                params.update(conditions)
            
            url = await self.retry_handler.execute_with_retry(
                self._s3_client.generate_presigned_url,
                operation,
                Params=params,
                ExpiresIn=expiry_seconds
            )
            
            return url
        
        except Exception as e:
            error = self._handle_s3_error(e, "產生預簽名 URL")
            logger.error(f"產生預簽名 URL 失敗: {object_key}, 錯誤: {error}")
            raise error
    
    # === 檔案管理功能 ===
    
    async def delete_file(self, object_key: str) -> bool:
        """
        刪除檔案
        
        Args:
            object_key: S3 物件鍵名
            
        Returns:
            是否成功刪除
        """
        await self._ensure_client()
        
        try:
            await self.retry_handler.execute_with_retry(
                self._s3_client.delete_object,
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            
            # 清除快取
            self._metadata_cache.pop(object_key, None)
            
            logger.info(f"檔案已刪除: {object_key}")
            return True
        
        except Exception as e:
            error = self._handle_s3_error(e, "檔案刪除")
            logger.error(f"檔案刪除失敗: {object_key}, 錯誤: {error}")
            raise error
    
    async def delete_files(self, object_keys: List[str]) -> Dict[str, bool]:
        """
        批次刪除檔案
        
        Args:
            object_keys: S3 物件鍵名列表
            
        Returns:
            刪除結果字典
        """
        await self._ensure_client()
        
        if len(object_keys) > 1000:
            raise S3ServiceError("一次最多只能刪除 1000 個檔案")
        
        try:
            delete_objects = [{'Key': key} for key in object_keys]
            
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.delete_objects,
                Bucket=self.config.bucket_name,
                Delete={'Objects': delete_objects}
            )
            
            # 處理結果
            result = {}
            
            # 成功刪除的檔案
            for deleted in response.get('Deleted', []):
                key = deleted['Key']
                result[key] = True
                self._metadata_cache.pop(key, None)
            
            # 刪除失敗的檔案
            for error in response.get('Errors', []):
                key = error['Key']
                result[key] = False
                logger.error(f"檔案刪除失敗: {key}, 錯誤: {error['Message']}")
            
            # 未在回應中的檔案視為成功
            for key in object_keys:
                if key not in result:
                    result[key] = True
                    self._metadata_cache.pop(key, None)
            
            return result
        
        except Exception as e:
            error = self._handle_s3_error(e, "批次刪除檔案")
            logger.error(f"批次刪除檔案失敗, 錯誤: {error}")
            raise error
    
    async def copy_file(
        self,
        source_key: str,
        destination_key: str,
        source_bucket: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        複製檔案
        
        Args:
            source_key: 來源檔案鍵名
            destination_key: 目標檔案鍵名
            source_bucket: 來源 Bucket，如果為 None 則使用當前 Bucket
            
        Returns:
            複製結果資訊
        """
        await self._ensure_client()
        
        if source_bucket is None:
            source_bucket = self.config.bucket_name
        
        destination_key = sanitize_s3_key(destination_key)
        
        if not validate_s3_key(destination_key):
            raise S3ServiceError(f"無效的目標鍵名: {destination_key}")
        
        try:
            copy_source = {
                'Bucket': source_bucket,
                'Key': source_key
            }
            
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.copy_object,
                CopySource=copy_source,
                Bucket=self.config.bucket_name,
                Key=destination_key
            )
            
            return {
                'source_key': source_key,
                'destination_key': destination_key,
                'source_bucket': source_bucket,
                'destination_bucket': self.config.bucket_name,
                'etag': response.get('ETag', '').strip('"'),
                'copy_time': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            error = self._handle_s3_error(e, "檔案複製")
            logger.error(f"檔案複製失敗: {source_key} -> {destination_key}, 錯誤: {error}")
            raise error
    
    async def move_file(self, source_key: str, destination_key: str) -> Dict[str, Any]:
        """
        移動檔案（複製後刪除）
        
        Args:
            source_key: 來源檔案鍵名
            destination_key: 目標檔案鍵名
            
        Returns:
            移動結果資訊
        """
        try:
            # 先複製檔案
            copy_result = await self.copy_file(source_key, destination_key)
            
            # 再刪除原檔案
            await self.delete_file(source_key)
            
            copy_result['operation'] = 'move'
            copy_result['move_time'] = datetime.utcnow().isoformat()
            
            return copy_result
        
        except Exception as e:
            logger.error(f"檔案移動失敗: {source_key} -> {destination_key}, 錯誤: {e}")
            raise e
    
    async def file_exists(self, object_key: str) -> bool:
        """
        檢查檔案是否存在
        
        Args:
            object_key: S3 物件鍵名
            
        Returns:
            檔案是否存在
        """
        await self._ensure_client()
        
        try:
            await self.retry_handler.execute_with_retry(
                self._s3_client.head_object,
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            return True
        
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return False
            else:
                error = self._handle_s3_error(e, "檔案存在性檢查")
                raise error
        
        except Exception as e:
            error = self._handle_s3_error(e, "檔案存在性檢查")
            raise error
    
    async def get_file_info(self, object_key: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        取得檔案資訊
        
        Args:
            object_key: S3 物件鍵名
            use_cache: 是否使用快取
            
        Returns:
            檔案資訊
        """
        await self._ensure_client()
        
        # 檢查快取
        if use_cache and self.config.enable_metadata_cache:
            cached_info = self._metadata_cache.get(object_key)
            if cached_info and time.time() - cached_info['cached_at'] < self.config.metadata_cache_ttl:
                return cached_info['data']
        
        try:
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.head_object,
                Bucket=self.config.bucket_name,
                Key=object_key
            )
            
            file_info = {
                'object_key': object_key,
                'size': response.get('ContentLength', 0),
                'size_readable': format_file_size(response.get('ContentLength', 0)),
                'content_type': response.get('ContentType', ''),
                'etag': response.get('ETag', '').strip('"'),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {}),
                'cache_control': response.get('CacheControl', ''),
                'content_encoding': response.get('ContentEncoding', ''),
                'storage_class': response.get('StorageClass', 'STANDARD')
            }
            
            # 更新快取
            if use_cache and self.config.enable_metadata_cache:
                self._metadata_cache[object_key] = {
                    'data': file_info,
                    'cached_at': time.time()
                }
            
            return file_info
        
        except Exception as e:
            error = self._handle_s3_error(e, "取得檔案資訊")
            logger.error(f"取得檔案資訊失敗: {object_key}, 錯誤: {error}")
            raise error
    
    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出檔案
        
        Args:
            prefix: 檔案前綴
            max_keys: 最大返回數量
            continuation_token: 分頁標記
            
        Returns:
            檔案列表和分頁資訊
        """
        await self._ensure_client()
        
        try:
            kwargs = {
                'Bucket': self.config.bucket_name,
                'Prefix': prefix,
                'MaxKeys': min(max_keys, 1000)
            }
            
            if continuation_token:
                kwargs['ContinuationToken'] = continuation_token
            
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.list_objects_v2,
                **kwargs
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'object_key': obj['Key'],
                    'size': obj['Size'],
                    'size_readable': format_file_size(obj['Size']),
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"'),
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })
            
            return {
                'files': files,
                'total_count': len(files),
                'is_truncated': response.get('IsTruncated', False),
                'next_continuation_token': response.get('NextContinuationToken'),
                'prefix': prefix
            }
        
        except Exception as e:
            error = self._handle_s3_error(e, "列出檔案")
            logger.error(f"列出檔案失敗: prefix={prefix}, 錯誤: {error}")
            raise error
    
    async def update_file_metadata(
        self,
        object_key: str,
        metadata: Dict[str, str],
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新檔案 metadata
        
        Args:
            object_key: S3 物件鍵名
            metadata: 新的 metadata
            content_type: 新的 Content-Type
            
        Returns:
            更新結果資訊
        """
        await self._ensure_client()
        
        try:
            # 取得現有檔案資訊
            current_info = await self.get_file_info(object_key, use_cache=False)
            
            # 建立複製來源
            copy_source = {
                'Bucket': self.config.bucket_name,
                'Key': object_key
            }
            
            # 準備新的 metadata
            new_metadata = create_metadata(
                content_type=content_type or current_info['content_type'],
                custom_metadata=metadata
            )
            
            # 使用 copy_object 來更新 metadata
            response = await self.retry_handler.execute_with_retry(
                self._s3_client.copy_object,
                CopySource=copy_source,
                Bucket=self.config.bucket_name,
                Key=object_key,
                MetadataDirective='REPLACE',
                **new_metadata
            )
            
            # 清除快取
            self._metadata_cache.pop(object_key, None)
            
            return {
                'object_key': object_key,
                'etag': response.get('ETag', '').strip('"'),
                'updated_metadata': metadata,
                'update_time': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            error = self._handle_s3_error(e, "更新檔案 metadata")
            logger.error(f"更新檔案 metadata 失敗: {object_key}, 錯誤: {error}")
            raise error
    
    def clear_metadata_cache(self):
        """清除 metadata 快取"""
        self._metadata_cache.clear()
        logger.info("Metadata 快取已清除")