# Dockerfile para Sistema de Detecção de Desvios - Sentinela BD
FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY scripts/pontos_notaveis/ ./
COPY Grupos.csv ./

# Criar diretório para logs
RUN mkdir -p /app/logs

# Configurar variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Campo_Grande

# Expor porta para health check
EXPOSE 8080

# Script de entrada
CMD ["python", "main.py"]