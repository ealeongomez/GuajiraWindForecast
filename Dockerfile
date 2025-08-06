# Dockerfile para el proyecto GuajiraWindForecast
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["python", "main.py"] 