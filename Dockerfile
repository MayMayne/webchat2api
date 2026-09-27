# Minimal image for Render (free tier).
# Frontend is prebuilt (web_dist); no Node.js build stage needed.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY main.py VERSION ./
COPY api ./api
COPY services ./services
COPY utils ./utils
COPY web_dist ./web_dist

EXPOSE 10000

CMD ["uv", "run", "python", "main.py"]
