FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NORTHSTAR_DB_PATH=instance/northstar.sqlite3 \
    NORTHSTAR_UPLOAD_DIR=instance/uploads
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p instance/uploads
EXPOSE 8000
CMD ["bash", "-lc", "python -m app.main init-db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
