FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home monitor && mkdir /data && chown monitor /data
COPY backend /app/backend
COPY frontend /app/frontend
COPY scripts /app/scripts
ENV PYTHONPATH=/app/backend PYTHONUNBUFFERED=1
USER monitor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
