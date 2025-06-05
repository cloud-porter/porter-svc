"""
S3 檔案操作 API 路由
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from typing import Optional, List
import tempfile
from pathlib import Path

from ..config import settings
from ..services.s3_service import S3Service
from ..services.s3_exceptions import S3ServiceError, S3FileNotFoundError
from ..schemas.s3_schemas import (
    FileUploadResponse, FileInfoResponse, FileListResponse,
    PresignedUrlResponse, FileOperationResponse
)

router = APIRouter(prefix="/s3", tags=["S3 檔案操作"])


async def get_s3_service() -> S3Service:
    """取得 S3 服務依賴"""
    service = S3Service(settings.s3_config)
    try:
        await service._ensure_client()
        yield service
    finally:
        await service._close_client()


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    object_key: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    s3_service: S3Service = Depends(get_s3_service)
) -> FileUploadResponse:
    """
    上傳檔案到 S3
    
    Args:
        file: 上傳的檔案
        object_key: S3 物件鍵名，如果未提供則使用檔案名
        metadata: JSON 格式的自定義 metadata
        s3_service: S3 服務依賴
    
    Returns:
        上傳結果
    """
    try:
        # 解析 metadata
        file_metadata = None
        if metadata:
            import json
            try:
                file_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="metadata 必須是有效的 JSON 格式"
                )
        
        # 設定物件鍵名
        if object_key is None:
            object_key = file.filename
        
        # 使用臨時檔案儲存上傳內容
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        
        try:
            # 執行上傳
            result = await s3_service.upload_file(
                file_path=temp_path,
                object_key=object_key,
                content_type=file.content_type,
                metadata=file_metadata
            )
            
            return FileUploadResponse(
                success=True,
                message="檔案上傳成功",
                object_key=result['object_key'],
                file_size=result['file_size'],
                upload_type=result['upload_type'],
                etag=result.get('etag')
            )
        
        finally:
            # 清理臨時檔案
            temp_path.unlink()
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上傳失敗: {str(e)}")


@router.post("/upload-stream", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_stream(
    file: UploadFile = File(...),
    object_key: str = Form(...),
    content_type: Optional[str] = Form(None),
    s3_service: S3Service = Depends(get_s3_service)
) -> FileUploadResponse:
    """
    以串流方式上傳檔案到 S3
    
    Args:
        file: 上傳的檔案
        object_key: S3 物件鍵名
        content_type: Content-Type
        s3_service: S3 服務依賴
    
    Returns:
        上傳結果
    """
    try:
        # 讀取檔案內容
        content = await file.read()
        
        # 執行串流上傳
        result = await s3_service.upload_stream(
            data_stream=content,
            object_key=object_key,
            content_type=content_type or file.content_type
        )
        
        return FileUploadResponse(
            success=True,
            message="串流上傳成功",
            object_key=result['object_key'],
            file_size=result['file_size'],
            upload_type=result['upload_type'],
            etag=result.get('etag')
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"串流上傳失敗: {str(e)}")


@router.get("/download/{object_key:path}")
async def download_file(
    object_key: str,
    s3_service: S3Service = Depends(get_s3_service)
) -> StreamingResponse:
    """
    下載檔案
    
    Args:
        object_key: S3 物件鍵名
        s3_service: S3 服務依賴
    
    Returns:
        檔案串流回應
    """
    try:
        # 檢查檔案是否存在
        if not await s3_service.file_exists(object_key):
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 取得檔案資訊
        file_info = await s3_service.get_file_info(object_key)
        
        # 建立串流生成器
        async def generate():
            async for chunk in s3_service.download_stream(object_key):
                yield chunk
        
        # 設定回應標頭
        headers = {
            "Content-Length": str(file_info['size']),
            "Content-Type": file_info['content_type'] or "application/octet-stream"
        }
        
        return StreamingResponse(
            generate(),
            media_type=file_info['content_type'],
            headers=headers
        )
    
    except S3FileNotFoundError:
        raise HTTPException(status_code=404, detail="檔案不存在")
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下載失敗: {str(e)}")


@router.get("/info/{object_key:path}", response_model=FileInfoResponse)
async def get_file_info(
    object_key: str,
    s3_service: S3Service = Depends(get_s3_service)
) -> FileInfoResponse:
    """
    取得檔案資訊
    
    Args:
        object_key: S3 物件鍵名
        s3_service: S3 服務依賴
    
    Returns:
        檔案資訊
    """
    try:
        file_info = await s3_service.get_file_info(object_key)
        
        return FileInfoResponse(
            object_key=file_info['object_key'],
            size=file_info['size'],
            size_readable=file_info['size_readable'],
            content_type=file_info['content_type'],
            etag=file_info['etag'],
            last_modified=file_info['last_modified'],
            metadata=file_info['metadata'],
            storage_class=file_info['storage_class']
        )
    
    except S3FileNotFoundError:
        raise HTTPException(status_code=404, detail="檔案不存在")
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=FileListResponse)
async def list_files(
    prefix: str = "",
    max_keys: int = 100,
    continuation_token: Optional[str] = None,
    s3_service: S3Service = Depends(get_s3_service)
) -> FileListResponse:
    """
    列出檔案
    
    Args:
        prefix: 檔案前綴
        max_keys: 最大返回數量
        continuation_token: 分頁標記
        s3_service: S3 服務依賴
    
    Returns:
        檔案列表
    """
    try:
        result = await s3_service.list_files(
            prefix=prefix,
            max_keys=min(max_keys, 1000),
            continuation_token=continuation_token
        )
        
        return FileListResponse(
            files=result['files'],
            total_count=result['total_count'],
            is_truncated=result['is_truncated'],
            next_continuation_token=result.get('next_continuation_token'),
            prefix=result['prefix']
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def generate_presigned_url(
    object_key: str = Form(...),
    operation: str = Form(default="get_object"),
    expiry_seconds: int = Form(default=3600),
    s3_service: S3Service = Depends(get_s3_service)
) -> PresignedUrlResponse:
    """
    產生預簽名 URL
    
    Args:
        object_key: S3 物件鍵名
        operation: 操作類型 (get_object, put_object)
        expiry_seconds: 過期時間（秒）
        s3_service: S3 服務依賴
    
    Returns:
        預簽名 URL
    """
    try:
        if operation not in ["get_object", "put_object"]:
            raise HTTPException(
                status_code=400,
                detail="operation 必須是 'get_object' 或 'put_object'"
            )
        
        url = await s3_service.generate_presigned_url(
            object_key=object_key,
            operation=operation,
            expiry_seconds=expiry_seconds
        )
        
        return PresignedUrlResponse(
            url=url,
            object_key=object_key,
            operation=operation,
            expiry_seconds=expiry_seconds
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{object_key:path}", response_model=FileOperationResponse)
async def delete_file(
    object_key: str,
    s3_service: S3Service = Depends(get_s3_service)
) -> FileOperationResponse:
    """
    刪除檔案
    
    Args:
        object_key: S3 物件鍵名
        s3_service: S3 服務依賴
    
    Returns:
        操作結果
    """
    try:
        success = await s3_service.delete_file(object_key)
        
        return FileOperationResponse(
            success=success,
            message="檔案刪除成功" if success else "檔案刪除失敗",
            object_key=object_key
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-batch", response_model=dict)
async def delete_files_batch(
    object_keys: List[str],
    s3_service: S3Service = Depends(get_s3_service)
) -> dict:
    """
    批次刪除檔案
    
    Args:
        object_keys: S3 物件鍵名列表
        s3_service: S3 服務依賴
    
    Returns:
        批次刪除結果
    """
    try:
        if len(object_keys) > 1000:
            raise HTTPException(
                status_code=400,
                detail="一次最多只能刪除 1000 個檔案"
            )
        
        results = await s3_service.delete_files(object_keys)
        
        success_count = sum(1 for success in results.values() if success)
        
        return {
            "success": True,
            "message": f"批次刪除完成，成功: {success_count}/{len(object_keys)}",
            "results": results,
            "total_files": len(object_keys),
            "success_count": success_count,
            "failed_count": len(object_keys) - success_count
        }
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy", response_model=FileOperationResponse)
async def copy_file(
    source_key: str = Form(...),
    destination_key: str = Form(...),
    s3_service: S3Service = Depends(get_s3_service)
) -> FileOperationResponse:
    """
    複製檔案
    
    Args:
        source_key: 來源檔案鍵名
        destination_key: 目標檔案鍵名
        s3_service: S3 服務依賴
    
    Returns:
        操作結果
    """
    try:
        result = await s3_service.copy_file(source_key, destination_key)
        
        return FileOperationResponse(
            success=True,
            message="檔案複製成功",
            object_key=result['destination_key'],
            details=result
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move", response_model=FileOperationResponse)
async def move_file(
    source_key: str = Form(...),
    destination_key: str = Form(...),
    s3_service: S3Service = Depends(get_s3_service)
) -> FileOperationResponse:
    """
    移動檔案
    
    Args:
        source_key: 來源檔案鍵名
        destination_key: 目標檔案鍵名
        s3_service: S3 服務依賴
    
    Returns:
        操作結果
    """
    try:
        result = await s3_service.move_file(source_key, destination_key)
        
        return FileOperationResponse(
            success=True,
            message="檔案移動成功",
            object_key=result['destination_key'],
            details=result
        )
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exists/{object_key:path}")
async def check_file_exists(
    object_key: str,
    s3_service: S3Service = Depends(get_s3_service)
) -> dict:
    """
    檢查檔案是否存在
    
    Args:
        object_key: S3 物件鍵名
        s3_service: S3 服務依賴
    
    Returns:
        檔案存在狀態
    """
    try:
        exists = await s3_service.file_exists(object_key)
        
        return {
            "object_key": object_key,
            "exists": exists
        }
    
    except S3ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
