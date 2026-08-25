#!/usr/bin/env python3
"""
run.py - Inicializa o banco de dados e inicia o Streamlit no Render.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# === CONFIGURAÇÕES DO RENDER ===
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# === Caminhos ===
SCRIPT_DIR = Path(__file__).parent
APP_FILE = SCRIPT_DIR / "app/app.py"

# === Funções ===


def run_command(cmd, check=True, shell=True):
    """Executa comando com logging."""
    print(f"🔧 Executando: {cmd}")
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Erro: {result.stderr}")
        if check:
            sys.exit(1)
    else:
        print("✅ Sucesso")
    return result.stdout


def wait_for_db():
    """Aguarda o PostgreSQL ficar disponível."""
    print("⏳ Esperando o PostgreSQL ficar pronto...")
    max_retries = 30
    for i in range(max_retries):
        try:
            result = subprocess.run(
                [
                    "psql",
                    f"host={DB_HOST}",
                    f"port={DB_PORT}",
                    f"dbname={DB_NAME}",
                    f"user={DB_USER}",
                    f"password={DB_PASSWORD}",
                    "-c",
                    "SELECT 1;",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                print("✅ PostgreSQL está pronto!")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("❌ Falha ao conectar ao PostgreSQL após várias tentativas.")
    sys.exit(1)


def create_table_if_not_exists():
    """Cria a tabela dolar_data diretamente via comando SQL."""
    print("🛠 Criando tabela dolar_data...")

    # Comando SQL executado diretamente pelo psql
    sql_query = """
        CREATE TABLE IF NOT EXISTS dolar_data (
            data DATE PRIMARY KEY,
            valor DECIMAL(10, 2) NOT NULL
        );
    """

    try:
        # Passa o comando SQL diretamente com a flag -c
        run_command(
            [
                "psql",
                f"host={DB_HOST}",
                f"port={DB_PORT}",
                f"dbname={DB_NAME}",
                f"user={DB_USER}",
                f"password={DB_PASSWORD}",
                "-c",
                sql_query,
            ]
        )
        print("✅ Tabela criada ou já existente.")
    except Exception as e:
        print("❌ Falha ao criar a tabela:", e)
        sys.exit(1)


def start_streamlit():
    """Inicia o Streamlit."""
    print("🚀 Iniciando Streamlit...")
    run_command(f"streamlit run {APP_FILE} --server.port 8501", check=False)


# === Função principal ===
def main():
    print("🚀 Iniciando o projeto no Render...")

    # 1. Verifica se o banco de dados está disponível
    wait_for_db()

    # 2. Cria a tabela diretamente no código
    create_table_if_not_exists()

    # 3. Inicia o Streamlit
    start_streamlit()


# === Executa ===
if __name__ == "__main__":
    main()