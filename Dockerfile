FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install . --system

COPY app/ ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]