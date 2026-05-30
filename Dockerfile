FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (cache layer — requirements 변경 시만 재빌드)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build
COPY frontend/site/package.json frontend/site/package-lock.json* frontend/site/
RUN cd frontend/site && npm install --prefer-offline

COPY frontend/site/ frontend/site/
RUN cd frontend/site && npm run build

# App code
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
