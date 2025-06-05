"""
S3 服務相關例外類別
"""
from typing import Optional


class S3ServiceError(Exception):
    """S3 服務基礎例外"""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class S3ConnectionError(S3ServiceError):
    """S3 連線錯誤"""
    pass


class S3AuthenticationError(S3ServiceError):
    """S3 認證錯誤"""
    pass


class S3BucketNotFoundError(S3ServiceError):
    """S3 Bucket 不存在錯誤"""
    pass


class S3FileNotFoundError(S3ServiceError):
    """S3 檔案不存在錯誤"""
    pass


class S3PermissionError(S3ServiceError):
    """S3 權限不足錯誤"""
    pass


class S3FileTooLargeError(S3ServiceError):
    """檔案過大錯誤"""
    pass


class S3UploadError(S3ServiceError):
    """檔案上傳錯誤"""
    pass


class S3DownloadError(S3ServiceError):
    """檔案下載錯誤"""
    pass


class S3MultipartUploadError(S3ServiceError):
    """多部分上傳錯誤"""
    pass


class S3NetworkError(S3ServiceError):
    """網路錯誤"""
    pass


class S3QuotaExceededError(S3ServiceError):
    """配額超限錯誤"""
    pass


class S3ServiceUnavailableError(S3ServiceError):
    """服務暫時不可用錯誤"""
    pass
