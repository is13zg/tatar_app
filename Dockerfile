FROM python:3.12

# Рабочая директория внутри контейнера
WORKDIR /usr/src/app

# Скопировать проект внутрь контейнера
COPY . /usr/src/app

# Установить зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создать папку для данных (будет монтироваться снаружи)
RUN mkdir -p /usr/src/app/data /usr/src/app/static


# Запуск uvicorn при старте контейнера
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
