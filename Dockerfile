FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANALYSIS_API_HOST=0.0.0.0 \
    ANALYSIS_API_PORT=8000 \
    ANALYSIS_API_WORKERS=1 \
    TRADINGAGENTS_REPORTS_DIR=/app/reports

WORKDIR /app

COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY analyze.py main.py ./
COPY cli ./cli
COPY tradingagents ./tradingagents

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

RUN mkdir -p /app/reports

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "tradingagents.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
