"""
S3 服務輔助函式
"""
import mimetypes
import hashlib
import os
import random
import time
from typing import Optional, Dict, Any, Union
from pathlib import Path
import asyncio
from ..services.s3_config import S3RetryConfig


def detect_content_type(file_path: Union[str, Path]) -> str:
    """
    自動檢測檔案的 Content-Type
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        Content-Type 字串
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    content_type, _ = mimetypes.guess_type(str(file_path))
    return content_type or "application/octet-stream"


def calculate_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> str:
    """
    計算檔案雜湊值
    
    Args:
        file_path: 檔案路徑
        algorithm: 雜湊演算法 (md5, sha1, sha256)
        
    Returns:
        雜湊值字串
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    hash_func = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def format_file_size(size_bytes: int) -> str:
    """
    格式化檔案大小為人類可讀格式
    
    Args:
        size_bytes: 檔案大小（位元組）
        
    Returns:
        格式化的檔案大小字串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def generate_multipart_key(original_key: str, part_number: int) -> str:
    """
    產生多部分上傳的檔案鍵名
    
    Args:
        original_key: 原始檔案鍵名
        part_number: 部分編號
        
    Returns:
        多部分檔案鍵名
    """
    path = Path(original_key)
    return f"{path.stem}_part_{part_number:04d}{path.suffix}"


def validate_s3_key(key: str) -> bool:
    """
    驗證 S3 物件鍵名是否有效
    
    Args:
        key: S3 物件鍵名
        
    Returns:
        是否有效
    """
    if not key or len(key) > 1024:
        return False
    
    # 檢查禁用字元
    invalid_chars = ["\x00", "\x08", "\x0B", "\x0C", "\x0E", "\x1F"]
    return not any(char in key for char in invalid_chars)


def sanitize_s3_key(key: str) -> str:
    """
    清理 S3 物件鍵名，移除無效字元
    
    Args:
        key: 原始鍵名
        
    Returns:
        清理後的鍵名
    """
    # 移除或替換無效字元
    sanitized = key.replace("\\", "/")
    sanitized = "".join(char for char in sanitized if ord(char) >= 32)
    
    # 移除連續的斜線
    while "//" in sanitized:
        sanitized = sanitized.replace("//", "/")
    
    # 移除開頭的斜線
    if sanitized.startswith("/"):
        sanitized = sanitized[1:]
    
    return sanitized[:1024]  # 限制長度


def create_metadata(
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
    custom_metadata: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    建立 S3 物件 metadata
    
    Args:
        content_type: Content-Type
        cache_control: Cache-Control 標頭
        custom_metadata: 自定義 metadata
        
    Returns:
        metadata 字典
    """
    metadata = {}
    
    if content_type:
        metadata["ContentType"] = content_type
    
    if cache_control:
        metadata["CacheControl"] = cache_control
    
    if custom_metadata:
        for key, value in custom_metadata.items():
            # S3 自定義 metadata 需要 x-amz-meta- 前綴
            if not key.startswith("x-amz-meta-"):
                key = f"x-amz-meta-{key}"
            metadata[key] = str(value)
    
    return metadata


class RetryHandler:
    """重試處理器"""
    
    def __init__(self, config: S3RetryConfig):
        self.config = config
    
    async def execute_with_retry(self, coro_func, *args, **kwargs):
        """
        執行帶重試的異步函式
        
        Args:
            coro_func: 異步函式
            *args: 函式參數
            **kwargs: 函式關鍵字參數
            
        Returns:
            函式執行結果
            
        Raises:
            最後一次執行的例外
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.config.max_attempts - 1:
                    # 最後一次嘗試，不再重試
                    break
                
                # 計算延遲時間
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        計算重試延遲時間（指數退避）
        
        Args:
            attempt: 嘗試次數（從 0 開始）
            
        Returns:
            延遲時間（秒）
        """
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            # 添加隨機抖動以避免雷霆效應
            jitter = delay * 0.1 * random.random()
            delay += jitter
        
        return delay


class ProgressTracker:
    """上傳/下載進度追蹤器"""
    
    def __init__(self, total_size: int, callback=None):
        self.total_size = total_size
        self.uploaded_size = 0
        self.callback = callback
        self.start_time = time.time()
    
    def update(self, bytes_transferred: int):
        """更新已傳輸的位元組數"""
        self.uploaded_size += bytes_transferred
        
        if self.callback:
            progress_info = self.get_progress_info()
            self.callback(progress_info)
    
    def get_progress_info(self) -> Dict[str, Any]:
        """取得進度資訊"""
        elapsed_time = time.time() - self.start_time
        progress_percentage = (self.uploaded_size / self.total_size) * 100 if self.total_size > 0 else 0
        
        # 計算速度（位元組/秒）
        speed = self.uploaded_size / elapsed_time if elapsed_time > 0 else 0
        
        # 估算剩餘時間
        remaining_size = self.total_size - self.uploaded_size
        eta = remaining_size / speed if speed > 0 else 0
        
        return {
            "total_size": self.total_size,
            "uploaded_size": self.uploaded_size,
            "progress_percentage": progress_percentage,
            "speed_bps": speed,
            "speed_readable": format_file_size(int(speed)) + "/s",
            "elapsed_time": elapsed_time,
            "eta": eta,
            "eta_readable": f"{int(eta // 60):02d}:{int(eta % 60):02d}" if eta > 0 else "00:00"
        }
