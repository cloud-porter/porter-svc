from time import time
from fastapi import Request
from utils.logger import logger

async def get_request_duration(request: Request, call_next):
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    logger.info(
        f"{request.method} {request.url.path} took {process_time:.3f} seconds to complete"
    )
    response.headers["X-Process-Time"] = str(process_time)
    return response