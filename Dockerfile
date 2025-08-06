FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для SQLite (если нужно)
RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/configs/available /app/configs/used /app/data

CMD ["python", "bot.py"]