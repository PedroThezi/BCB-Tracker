# Use Python 3.11 slim
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

# Expõe a porta do Streamlit
EXPOSE 8501

# Comando para rodar o app
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]