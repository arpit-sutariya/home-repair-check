FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Download the local models at build time so the first visitor doesn't wait (~700 MB).
ENV MODEL_CACHE=/app/models
RUN python -c "from repaircheck import models; models.warm()"
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
