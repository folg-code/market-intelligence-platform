# Single `app` image (ADR-0013): FastAPI + APScheduler + the processing
# cycle, all in one stateless container. All durable state lives in the
# `db` service's named volume, not here.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "moj_projekt.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
