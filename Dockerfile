FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
# Threads: the explain endpoint streams a model answer for several seconds and must not block a whole worker.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "8", "ttrpgtools.web.app:create_app()"]
