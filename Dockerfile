FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Создаем папки для данных и сертификатов
RUN mkdir -p /app/data /app/certs

# Запускаем скрипт напрямую, чтобы отработала проверка SSL в коде
CMD ["python", "main.py"]