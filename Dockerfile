FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Copia requirements primeiro para aproveitar o cache de camadas do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Desliga o file watcher do Streamlit (inotify). Em produção não há hot-reload
# e o Render impõe limite baixo de instâncias inotify; sem isso o boot
# crasha com "OSError: [Errno 24] inotify instance limit reached".
ENV STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "main.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.fileWatcherType=none", \
     "--server.runOnSave=false", \
     "--browser.gatherUsageStats=false"]