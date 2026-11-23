FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    PRISMAFLOW_DATA_DIR=/workspace/data \
    XDG_CONFIG_HOME=/workspace/config
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home prismaflow \
    && install -d -o prismaflow -g prismaflow /workspace
COPY backend/ ./backend/
COPY --from=frontend /build/dist/ ./frontend/dist/
USER prismaflow
EXPOSE 8765
CMD ["uvicorn", "backend.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
