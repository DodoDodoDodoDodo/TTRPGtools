# Stage 1: the 5e character builder (Svelte), built into ttrpgtools/web/static/dnd5e/builder/.
FROM node:22-slim AS frontend
WORKDIR /build/frontend/dnd5e
COPY frontend/dnd5e/package.json frontend/dnd5e/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/dnd5e/ ./
RUN npx vite build

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/ttrpgtools/web/static/dnd5e/builder ttrpgtools/web/static/dnd5e/builder

EXPOSE 5000
# Threads: the explain endpoint streams a model answer for several seconds and must not block a whole worker.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "8", "ttrpgtools.web.app:create_app()"]
