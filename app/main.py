from fastapi import FastAPI
from .config import settings
from dotenv import load_dotenv
from .middleware.timing import get_request_duration
from .routers.endpoints import router as api_router
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(".env")

app = FastAPI(
    title="Porter",
    description="...",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={
        "syntaxHighlighting": {
            "theme": "obsidian"
        }
    }
)
app.include_router(api_router)
app.middleware('http')(get_request_duration)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)