#!/usr/bin/env python3
"""
run.py - Automatiza o setup do projeto com Docker, cria tabela, instala dependências, e inicia o Streamlit.
"""

import os
import subprocess
import time
import sys
from pathlib import Path

# === CONFIGURAÇÕES ===
PROJECT_DIR = Path(__file__).parent.resolve()
DOCKER_COMPOSE_FILE = PROJECT_DIR / "docker-compose.yml"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
APP_FILE = PROJECT_DIR / "app/app.py"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "airflow"
DB_USER = "airflow"
DB_PASSWORD = "airflow"

# === Funções utilitárias ===

def run_command(cmd, check=True, shell=True, cwd=None):
    """Executa um comando no terminal com logging."""
    print(f"🔧 Executando: {cmd}")
    result = subprocess.run(
        cmd, shell=shell, cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ Erro ao executar: {cmd}")
        print("Saída de erro:", result.stderr)
        if check:
            sys.exit(1)
    else:
        print("✅ Sucesso")
    return result.stdout

def wait_for_db():
    """Espera até que o PostgreSQL esteja pronto."""
    print("⏳ Esperando o PostgreSQL ficar disponível...")
    max_retries = 30
    for i in range(max_retries):
        try:
            result = subprocess.run(
                ["pg_isready", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print("✅ PostgreSQL está pronto!")
                return True
        except Exception as e:
            pass
        time.sleep(1)
    print("❌ Falha ao conectar ao PostgreSQL após várias tentativas.")
    sys.exit(1)

def create_dolar_data_table():
    """Cria a tabela dolar_data no banco, se não existir."""
    print("🛠 Criando tabela dolar_data no banco...")
    sql = """
    CREATE TABLE IF NOT EXISTS dolar_data (
        data DATE PRIMARY KEY,
        valor DECIMAL(10, 2) NOT NULL
    );
    """
    try:
        # Usa psql para executar SQL
        result = subprocess.run(
            [
                "psql",
                "-h", DB_HOST,
                "-p", DB_PORT,
                "-U", DB_USER,
                "-d", DB_NAME,
                "-c", sql
            ],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Tabela dolar_data criada ou já existente.")
            # Insere dados de exemplo
            insert_sql = """
            INSERT INTO dolar_data (data, valor) VALUES
                ('2024-01-01', 5.80),
                ('2024-01-02', 5.85)
            ON CONFLICT (data) DO NOTHING;
            """
            subprocess.run(
                [
                    "psql",
                    "-h", DB_HOST,
                    "-p", DB_PORT,
                    "-U", DB_USER,
                    "-d", DB_NAME,
                    "-c", insert_sql
                ],
                capture_output=True, text=True
            )
            print("✅ Dados de exemplo inseridos.")
        else:
            print("❌ Erro ao criar tabela:", result.stderr)
            sys.exit(1)
    except Exception as e:
        print("❌ Falha ao conectar ao banco ou executar SQL:", e)
        sys.exit(1)

def install_requirements():
    """Instala dependências do requirements.txt."""
    if REQUIREMENTS_FILE.exists():
        print("📦 Instalando dependências...")
        run_command("pip install -r requirements.txt")
    else:
        print("⚠️  Arquivo requirements.txt não encontrado.")

def start_streamlit():
    """Inicia o Streamlit app."""
    print("🚀 Iniciando o Streamlit...")
    run_command(f"streamlit run {APP_FILE} --server.port 8501", check=False)

# === Função principal ===
def main():
    print("🚀 Iniciando o projeto com Docker e configurações automáticas...")

    # 1. Verifica se docker-compose está instalado
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
    except Exception:
        print("❌ docker-compose não está instalado. Instale-o primeiro.")
        sys.exit(1)

    # 2. Verifica se o Docker está rodando
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
    except Exception:
        print("❌ Docker não está rodando. Inicie o Docker Desktop ou o serviço do Docker.")
        sys.exit(1)

    # 3. Verifica se o arquivo docker-compose.yml existe
    if not DOCKER_COMPOSE_FILE.exists():
        print(f"❌ Arquivo {DOCKER_COMPOSE_FILE} não encontrado.")
        sys.exit(1)

    # 4. Levanta o container do PostgreSQL
    print("🔄 Iniciando o PostgreSQL via docker-compose...")
    run_command("docker-compose up -d postgres")

    # 5. Espera o banco ficar pronto
    wait_for_db()

    # 6. Cria a tabela (se necessário)
    create_dolar_data_table()

    # 7. Instala dependências (se não estiverem instaladas)
    install_requirements()

    # 8. Inicia o Streamlit
    start_streamlit()

# === Executa o script ===
if __name__ == "__main__":
    main()