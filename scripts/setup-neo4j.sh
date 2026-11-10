#!/usr/bin/env bash
# Prepara tudo de uma vez (macOS/Linux): .env com senha local, Neo4j no Docker,
# dependências em .venv, esquema e ingestão. Pode ser rodado de novo sem problema.
#   bash scripts/setup-neo4j.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Instale o Docker Desktop (https://www.docker.com/products/docker-desktop/), abra-o e rode de novo."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "O Docker está instalado, mas não está rodando. Abra o Docker Desktop, espere ele iniciar e rode de novo."
  exit 1
fi

[ -f .env ] || cp .env.example .env
if grep -q '^NEO4J_PASSWORD=$' .env; then
  PW="$(openssl rand -hex 12)"
  sed "s/^NEO4J_PASSWORD=.*/NEO4J_PASSWORD=$PW/" .env > .env.tmp && mv .env.tmp .env
  echo "Senha local do Neo4j criada em .env (arquivo não versionado)."
fi

echo "1/4 Subindo o Neo4j..."
docker compose up -d

echo "2/4 Instalando dependências em .venv..."
python3 -m venv .venv
.venv/bin/python -m pip install --quiet -r requirements-neo4j.txt

echo "3/4 Aplicando restrições e índices (espera o Neo4j iniciar)..."
.venv/bin/python scripts/neo4j_ingest.py schema --wait 180

echo "4/4 Ingerindo e verificando..."
.venv/bin/python scripts/neo4j_ingest.py ingest --include-sample --wait 180

echo
echo "Pronto. Abra http://localhost:7474  (usuário: neo4j; a senha está no arquivo .env)."
