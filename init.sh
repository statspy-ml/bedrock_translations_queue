#!/bin/bash
set -e

# Função para criar o banco de dados se ele não existir
create_db() {
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        SELECT 'CREATE DATABASE translations'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'translations')\gexec
EOSQL
}

# Chama a função
create_db

# Execute o script init.sql se existir
if [ -f /docker-entrypoint-initdb.d/init.sql ]; then
    psql --username "$POSTGRES_USER" --dbname "translations" -a -f /docker-entrypoint-initdb.d/init.sql
fi

