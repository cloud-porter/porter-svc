from fastapi import APIRouter
from fastapi.responses import JSONResponse
from config import settings
from services.s3_service import S3Service

router = APIRouter()

@router.get("/hello")
def hello():
    return JSONResponse({
        "response": "Hello, world cicd0526!"
    })

@router.get("/upload")
def upload_file():
    s3_service = S3Service(
        ak=settings.ak,
        sk=settings.sk,
        bucket_name=settings.bucket_name,
        region_name=settings.region_name
    )
    file_path = "./file.txt"
    s3_service.upload_file(file_path, object_name="uploads/file.txt")
    return JSONResponse({
        "response": "File uploaded successfully!"
    })



@router.get("/health")
def health_check():
    return {"status": "ok"}