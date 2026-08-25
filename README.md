# 📊 DolarTracker - Monitoramento de Cotação do Dólar

Projeto de análise de dados de cotação do dólar usando Airflow, PostgreSQL e Streamlit.

## 🛠️ Funcionalidades

- Baixa dados diários do dólar do BCB (Banco Central do Brasil)
- Armazena em PostgreSQL
- Visualiza dados em tempo real com Streamlit
- Segurança: variáveis sensíveis no `.env`, protegidas no `.gitignore`

## 🏗️ Arquitetura: dev vs. produção

O projeto roda em dois modos, por causa das limitações do plano free do Render
(sem background workers/cron jobs nativos, web services gratuitos hibernam):

| | Local (dev/portfólio) | Produção (Render) |
|---|---|---|
| Orquestração | Airflow completo (`docker-compose.yml`) | GitHub Actions (`.github/workflows/update_dolar.yml`) |
| Script de ETL | `airflow/dags/fetch_dolar_data.py` | `scripts/fetch_dolar_data.py` (standalone, mesma lógica) |
| Banco | Postgres em container | Postgres gerenciado do Render |
| Dashboard | Streamlit local | Streamlit como Web Service (Docker) |

Em produção, o GitHub Actions dispara o script de ETL 1x/dia direto no runner
do GitHub — sem precisar de nenhum processo do Airflow rodando 24/7 no Render.
O Airflow fica disponível para rodar localmente via Docker, demonstrando a
orquestração completa.

## 📦 Requisitos

- Docker
- Docker Compose
- Python 3.11

## 🚀 Como Rodar Localmente

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/dolartracker.git
   cd dolartracker
   ```

2. Crie o arquivo `.env` com base no exemplo:
   ```bash
   cp .env.example .env
   ```

3. Gere uma chave Fernet segura:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Substitua `your-fernet-key-here` no `.env`.

4. Inicie os serviços:
   ```bash
   docker-compose up -d
   ```

5. Acesse:
   - Airflow: [http://localhost:8080](http://localhost:8080) (user: `airflow`, pass: `airflow`)
   - Streamlit: [http://localhost:8501](http://localhost:8501)

## 📁 Estrutura

- `airflow/dags/`: DAGs do Airflow
- `app/`: Aplicação Streamlit
- `docker-compose.yml`: Orquestração com Docker
- `.env`: Variáveis sensíveis (não versionadas)

## 🔐 Segurança

- Todas as variáveis sensíveis estão no `.env`
- `.gitignore` protege arquivos sensíveis
- Nada é commitado no GitHub

## 🌐 Deploy no Render

- Substitua as variáveis no painel do Render (não no código)
- Use `.env` no painel de variáveis de ambiente

---

> ✅ Projeto pronto para deploy, seguro e escalável.