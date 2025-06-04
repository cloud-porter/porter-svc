import boto3
from config import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from services.s3_service import S3Service

router = APIRouter()

@router.get("/hello")
def hello():
    return JSONResponse({
        "response": "Hello, world cicd github-0527!"
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


@router.get("/generate-presigned-url/")
def generate_presigned_url(file_name: str, file_type: str):
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('put_object',
                                                    Params={'Bucket': 'porter-bucket-01',
                                                            'Key': file_name,
                                                            'ContentType': file_type},
                                                    ExpiresIn=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"url": response}


@router.get("/health")
def health_check():
    return {"status": "ok"}