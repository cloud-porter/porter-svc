from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from .endpoints import router as endpoint_router

router = APIRouter()

router.include_router(
    endpoint_router,
    tags=["endpoint"],
    prefix="/endpoint"
)

@router.get("/", status_code=status.HTTP_200_OK)
def root():
    return JSONResponse({
        "response": "running"
    })