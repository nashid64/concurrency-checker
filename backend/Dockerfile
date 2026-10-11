FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# local-model support is optional (large). Build with:  docker build --build-arg WITH_MODEL=1 -t concurrency-backend .
ARG WITH_MODEL=0
COPY requirements-model.txt .
RUN if [ "$WITH_MODEL" = "1" ]; then pip install --no-cache-dir -r requirements-model.txt; fi
COPY app ./app
COPY models ./models
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
