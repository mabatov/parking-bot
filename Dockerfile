FROM python:3.11-slim

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
CMD ["python3", "bot.py"]
