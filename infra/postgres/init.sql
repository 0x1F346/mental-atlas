-- Runs once, when the local database volume is first created.
-- atlas_owner owns the schema and runs migrations.
-- atlas_app is the application role: no superuser, no BYPASSRLS, so row-level security always applies to it.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE atlas_app LOGIN PASSWORD 'atlas_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE atlas TO atlas_app;
-- A second database for the test suite, so tests never touch development data.
CREATE DATABASE atlas_test OWNER atlas_owner;
GRANT CONNECT ON DATABASE atlas_test TO atlas_app;
\connect atlas_test
CREATE EXTENSION IF NOT EXISTS vector;
