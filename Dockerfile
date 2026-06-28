FROM python:3.11-slim

WORKDIR /app

# Evitar que Python escriba archivos .pyc en el disco del contenedor
ENV PYTHONDONTWRITEBYTECODE 1
# Evitar que Python haga buffer de los outputs
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port $PORT