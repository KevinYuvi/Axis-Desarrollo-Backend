FROM python:3.11-slim

WORKDIR /app

# Evitar que Python escriba archivos .pyc en el disco del contenedor
ENV PYTHONDONTWRITEBYTECODE 1
# Evitar que Python haga buffer de los outputs
ENV PYTHONUNBUFFERED 1

# Dependencias de sistema requeridas por opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
