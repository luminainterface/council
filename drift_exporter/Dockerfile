FROM python:3.11-slim
WORKDIR /app
COPY drift_exporter.py .
RUN pip install --no-cache-dir prometheus_client==0.20.*
CMD ["python", "drift_exporter.py"] 