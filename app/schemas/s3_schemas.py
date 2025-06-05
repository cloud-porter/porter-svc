"""
S3 檔案操作相關的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FileUploadResponse(BaseModel):
    """檔案上傳回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    object_key: str = Field(..., description="S3 物件鍵名")
    file_size: int = Field(..., description="檔案大小（位元組）")
    upload_type: str = Field(..., description="上傳類型 (simple/multipart/stream)")
    etag: Optional[str] = Field(None, description="檔案 ETag")
    total_parts: Optional[int] = Field(None, description="多部分上傳的總部分數")


class FileInfoResponse(BaseModel):
    """檔案資訊回應"""
    object_key: str = Field(..., description="S3 物件鍵名")
    size: int = Field(..., description="檔案大小（位元組）")
    size_readable: str = Field(..., description="人類可讀的檔案大小")
    content_type: str = Field(..., description="Content-Type")
    etag: str = Field(..., description="檔案 ETag")
    last_modified: Optional[datetime] = Field(None, description="最後修改時間")
    metadata: Dict[str, str] = Field(default_factory=dict, description="自定義 metadata")
    storage_class: str = Field(..., description="儲存類別")
    cache_control: Optional[str] = Field(None, description="Cache-Control 標頭")
    content_encoding: Optional[str] = Field(None, description="Content-Encoding 標頭")


class FileItemResponse(BaseModel):
    """檔案項目回應"""
    object_key: str = Field(..., description="S3 物件鍵名")
    size: int = Field(..., description="檔案大小（位元組）")
    size_readable: str = Field(..., description="人類可讀的檔案大小")
    last_modified: Optional[datetime] = Field(None, description="最後修改時間")
    etag: str = Field(..., description="檔案 ETag")
    storage_class: str = Field(..., description="儲存類別")


class FileListResponse(BaseModel):
    """檔案列表回應"""
    files: List[FileItemResponse] = Field(..., description="檔案列表")
    total_count: int = Field(..., description="返回的檔案數量")
    is_truncated: bool = Field(..., description="是否還有更多檔案")
    next_continuation_token: Optional[str] = Field(None, description="下一頁的標記")
    prefix: str = Field(..., description="搜尋前綴")


class PresignedUrlResponse(BaseModel):
    """預簽名 URL 回應"""
    url: str = Field(..., description="預簽名 URL")
    object_key: str = Field(..., description="S3 物件鍵名")
    operation: str = Field(..., description="操作類型")
    expiry_seconds: int = Field(..., description="過期時間（秒）")


class FileOperationResponse(BaseModel):
    """檔案操作回應"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="回應訊息")
    object_key: str = Field(..., description="S3 物件鍵名")
    details: Optional[Dict[str, Any]] = Field(None, description="操作詳細資訊")


class FileUploadRequest(BaseModel):
    """檔案上傳請求"""
    object_key: Optional[str] = Field(None, description="S3 物件鍵名，如果未提供則使用檔案名")
    content_type: Optional[str] = Field(None, description="Content-Type")
    metadata: Optional[Dict[str, str]] = Field(None, description="自定義 metadata")
    cache_control: Optional[str] = Field(None, description="Cache-Control 標頭")


class FileStreamUploadRequest(BaseModel):
    """檔案串流上傳請求"""
    object_key: str = Field(..., description="S3 物件鍵名")
    content_type: Optional[str] = Field(None, description="Content-Type")
    metadata: Optional[Dict[str, str]] = Field(None, description="自定義 metadata")


class FileCopyRequest(BaseModel):
    """檔案複製請求"""
    source_key: str = Field(..., description="來源檔案鍵名")
    destination_key: str = Field(..., description="目標檔案鍵名")
    source_bucket: Optional[str] = Field(None, description="來源 Bucket，如果為 None 則使用當前 Bucket")


class FileMoveRequest(BaseModel):
    """檔案移動請求"""
    source_key: str = Field(..., description="來源檔案鍵名")
    destination_key: str = Field(..., description="目標檔案鍵名")


class FileBatchDeleteRequest(BaseModel):
    """批次檔案刪除請求"""
    object_keys: List[str] = Field(..., description="要刪除的檔案鍵名列表", max_items=1000)


class PresignedUrlRequest(BaseModel):
    """預簽名 URL 請求"""
    object_key: str = Field(..., description="S3 物件鍵名")
    operation: str = Field(default="get_object", description="操作類型 (get_object, put_object)")
    expiry_seconds: int = Field(default=3600, description="過期時間（秒）", ge=1, le=604800)
    conditions: Optional[Dict[str, Any]] = Field(None, description="額外條件")


class FileMetadataUpdateRequest(BaseModel):
    """檔案 metadata 更新請求"""
    object_key: str = Field(..., description="S3 物件鍵名")
    metadata: Dict[str, str] = Field(..., description="新的 metadata")
    content_type: Optional[str] = Field(None, description="新的 Content-Type")


class S3ConfigResponse(BaseModel):
    """S3 配置回應"""
    bucket_name: str = Field(..., description="Bucket 名稱")
    aws_region: str = Field(..., description="AWS 區域")
    max_concurrent_uploads: int = Field(..., description="最大並發上傳數")
    multipart_threshold: int = Field(..., description="多部分上傳閾值（位元組）")
    multipart_chunksize: int = Field(..., description="多部分上傳塊大小（位元組）")
    default_presigned_url_expiry: int = Field(..., description="預設預簽名 URL 過期時間（秒）")


class UploadProgressResponse(BaseModel):
    """上傳進度回應"""
    object_key: str = Field(..., description="S3 物件鍵名")
    total_size: int = Field(..., description="總檔案大小（位元組）")
    uploaded_size: int = Field(..., description="已上傳大小（位元組）")
    progress_percentage: float = Field(..., description="進度百分比")
    speed_bps: float = Field(..., description="上傳速度（位元組/秒）")
    speed_readable: str = Field(..., description="人類可讀的上傳速度")
    elapsed_time: float = Field(..., description="已耗時（秒）")
    eta: float = Field(..., description="預估剩餘時間（秒）")
    eta_readable: str = Field(..., description="人類可讀的預估剩餘時間")


class S3ErrorResponse(BaseModel):
    """S3 錯誤回應"""
    error_code: str = Field(..., description="錯誤代碼")
    error_message: str = Field(..., description="錯誤訊息")
    object_key: Optional[str] = Field(None, description="相關的物件鍵名")
    operation: str = Field(..., description="失敗的操作")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="錯誤發生時間")


class S3StatsResponse(BaseModel):
    """S3 統計資訊回應"""
    total_files: int = Field(..., description="總檔案數")
    total_size: int = Field(..., description="總檔案大小（位元組）")
    total_size_readable: str = Field(..., description="人類可讀的總檔案大小")
    storage_classes: Dict[str, int] = Field(..., description="各儲存類別的檔案數")
    content_types: Dict[str, int] = Field(..., description="各內容類型的檔案數")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="統計更新時間")
