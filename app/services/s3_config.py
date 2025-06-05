"""
S3 服務配置設定
"""
from pydantic import BaseModel, Field
from typing import Optional


class S3Config(BaseModel):
    """S3 服務配置"""
    
    # AWS 認證資訊
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    aws_region: str = Field(default="us-east-1", description="AWS 區域")
    
    # S3 設定
    bucket_name: str = Field(..., description="S3 Bucket 名稱")
    endpoint_url: Optional[str] = Field(default=None, description="自定義 S3 端點 URL")
    
    # 效能設定
    max_concurrent_uploads: int = Field(default=10, description="最大並發上傳數")
    multipart_threshold: int = Field(default=5 * 1024 * 1024, description="多部分上傳閾值 (bytes)")
    multipart_chunksize: int = Field(default=8 * 1024 * 1024, description="多部分上傳塊大小 (bytes)")
    max_bandwidth: Optional[int] = Field(default=None, description="最大頻寬限制 (bytes/s)")
    
    # 連線設定
    connect_timeout: int = Field(default=60, description="連線逾時時間 (秒)")
    read_timeout: int = Field(default=300, description="讀取逾時時間 (秒)")
    max_retry_attempts: int = Field(default=3, description="最大重試次數")
    
    # Presigned URL 設定
    default_presigned_url_expiry: int = Field(default=3600, description="預設 Presigned URL 過期時間 (秒)")
    max_presigned_url_expiry: int = Field(default=7 * 24 * 3600, description="最大 Presigned URL 過期時間 (秒)")
    
    # 快取設定
    metadata_cache_ttl: int = Field(default=300, description="Metadata 快取過期時間 (秒)")
    enable_metadata_cache: bool = Field(default=True, description="是否啟用 Metadata 快取")
    
    class Config:
        # 移除 env 相關設定，改為手動處理
        pass


class S3RetryConfig:
    """S3 重試策略配置"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
