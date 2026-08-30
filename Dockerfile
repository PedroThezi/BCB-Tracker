# Use Python 3.11 slim for ETL scripts
FROM python:3.11-slim

# Define o working directory
WORKDIR /app
ENV PYTHONPATH=/app

# Copia apenas o arquivo de dependências
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código
COPY . .

# Comando padrão: roda ETL e cria tabelas
CMD ["sh", "-c", "python -c \"from config.database import create_tables; create_tables()\" && python -c \"from scripts.etl import load_data; load_data()\""]