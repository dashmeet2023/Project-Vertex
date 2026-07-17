-- =============================================================================
-- Docker init script: runs once on first container start.
-- Creates the application roles with passwords and the database.
-- The superuser (postgres) runs this.
-- =============================================================================

-- Create vertex application database (if not already the default)
-- (The POSTGRES_DB env var already creates 'vertex', so this is a no-op guard)
SELECT 'CREATE DATABASE vertex' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'vertex'
)\gexec

\c vertex

-- Create roles with login capability
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_admin') THEN
        CREATE ROLE app_admin NOINHERIT;
    END IF;
    -- Login roles that assume app_user / app_admin via SET ROLE
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vertex_app') THEN
        CREATE ROLE vertex_app LOGIN PASSWORD 'changeme_dev' IN ROLE app_user;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vertex_admin') THEN
        CREATE ROLE vertex_admin LOGIN PASSWORD 'changeme_app_admin' IN ROLE app_admin;
    END IF;
END
$$;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO app_user;
GRANT USAGE ON SCHEMA public TO app_admin;
GRANT CREATE ON SCHEMA public TO app_user;
GRANT CREATE ON SCHEMA public TO app_admin;

-- Grant memberships so login roles can perform SET ROLE switches
GRANT app_user TO vertex_app;
GRANT app_admin TO vertex_app;
GRANT app_user TO vertex_admin;
GRANT app_admin TO vertex_admin;

