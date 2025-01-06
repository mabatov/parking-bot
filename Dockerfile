# Используем базовый образ Python
FROM python:3.12-slim

# Устанавливаем необходимые зависимости для компиляции psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем проект в контейнер
WORKDIR /app
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду запуска приложения
CMD ["python", "bot.py"]
