from ..config import settings
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..services.s3_service import S3Service
from .s3_router import router as s3_router

router = APIRouter()

# 包含 S3 路由
router.include_router(s3_router)

@router.get("/hello")
def hello():
    return JSONResponse({
        "response": "Hello, world cicd github-0527!"
    })

@router.get("/upload")
async def upload_file():
    """舊版上傳端點 - 保留向後相容性"""
    async with S3Service(settings.s3_config) as s3_service:
        try:
            # 這裡應該有實際的檔案，這只是範例
            file_path = "./file.txt"
            result = await s3_service.upload_file(
                file_path=file_path, 
                object_key="uploads/file.txt"
            )
            return JSONResponse({
                "response": "File uploaded successfully!",
                "details": result
            })
        except Exception as e:
            return JSONResponse({
                "response": f"Upload failed: {str(e)}"
            }, status_code=500)



@router.get("/health")
def health_check():
    return {"status": "ok"}