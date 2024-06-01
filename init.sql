-- Criação do usuário e concessão de privilégios
DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'user') THEN
      CREATE ROLE "user" WITH LOGIN PASSWORD 'password';
   END IF;
END
$do$;

GRANT ALL PRIVILEGES ON DATABASE translations TO "user";

-- Conectar ao banco de dados translations
\c translations

-- Criar a tabela translations dentro do banco de dados translations
CREATE TABLE IF NOT EXISTS translations (
    id SERIAL PRIMARY KEY,
    chave INTEGER NOT NULL UNIQUE, -- Definir chave como única
    comentario TEXT NOT NULL,
    translation TEXT,  -- Adicionando a coluna translation
    time_taken REAL,
    processed BOOLEAN DEFAULT FALSE
);

-- Garantir que o usuário "user" tenha as permissões necessárias
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "user";

-- Ajuste para a criação da sequência
DO
$do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'task_id_sequence') THEN
        CREATE SEQUENCE task_id_sequence;
    END IF;
END
$do$;
