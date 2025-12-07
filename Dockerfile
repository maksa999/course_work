# Этап 1: Сборка (builder) — установка зависимостей и подготовка приложения
FROM python:3.13-slim AS builder

# Устанавливаем системные зависимости для matplotlib, numpy и aiosqlite
# Добавляем g++ и build-essential для C++-компиляции NumPy
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        build-essential \
        libsqlite3-dev \
        libfreetype6-dev \
        libpng-dev \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Этап 2: Финальный образ — минимальный runtime
FROM python:3.13-slim

# Системные зависимости только для runtime matplotlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libfreetype6 \
        libpng16-16 \
        libsqlite3-0 && \
    rm -rf /var/lib/apt/lists/*

# Копируем установленное приложение из builder
# COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app /app
COPY --from=builder /usr/local /usr/local

# Рабочая директория
WORKDIR /app

# Открываем порт
EXPOSE 8000

# Запускаем приложение через uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]