FROM python:3.12-slim

# Установка зависимостей для OpenCV и PostgreSQL
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка библиотек из requirements.txt
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . /app

# Команда для запуска приложения
CMD ["python3", "bot.py"]
