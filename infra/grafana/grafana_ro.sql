-- Rol de SOLO LECTURA para Grafana. La contraseña la inyecta 19_grafana.sh.
-- Grafana nunca escribe; solo consulta el histórico/estado.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro') THEN
    CREATE ROLE grafana_ro LOGIN PASSWORD :'gpw';
  ELSE
    ALTER ROLE grafana_ro PASSWORD :'gpw';
  END IF;
END $$;

GRANT CONNECT ON DATABASE monitoreo TO grafana_ro;
GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_ro;

-- Defensa en profundidad: revoca cualquier escritura heredada.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM grafana_ro;
