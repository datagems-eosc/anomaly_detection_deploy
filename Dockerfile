FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir psycopg2-binary stumpy

COPY . .

# 采集器：默认持续运行；pg url 由环境变量生成
CMD ["python", "streaming_collector_sqlite.py", "--continuous", "--interval", "600"]
