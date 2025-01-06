FROM python:3.11-slim

# Установите dockerize
RUN apt-get update && apt-get install -y wget
RUN wget https://github.com/jwilder/dockerize/releases/download/v0.6.1/dockerize-linux-amd64-0.6.1.tar.gz && \
    tar -xvzf dockerize-linux-amd64-0.6.1.tar.gz && \
    mv dockerize /usr/local/bin/

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    libpq-dev gcc ffmpeg libsm6 libxext6 && \
    apt-get clean

# Создаём рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt requirements.txt

# Устанавливаем зависимости проекта и OpenCV
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir opencv-python-headless

# Копируем код приложения
COPY . .

# Команда запуска
CMD dockerize -wait tcp://db:5432 -timeout 30s python bot.py
#CMD ["python", "bot.py"]
