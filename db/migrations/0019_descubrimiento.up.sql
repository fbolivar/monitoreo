-- =====================================================================
-- 0019_descubrimiento.up.sql
-- Auto-descubrimiento de red (estilo LibreNMS/PRTG): un barrido de subred
-- (ping + SNMP sysDescr/sysObjectID/sysName) que PROPONE equipos candidatos
-- para darlos de alta con un clic. El worker ejecuta el barrido; la API/UI
-- lo gestionan. Reduce el onboarding de horas a minutos.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS descubrimiento_escaneos (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subred          text        NOT NULL,                 -- CIDR, p.ej. 192.168.10.0/24
  snmp_version    text        NOT NULL DEFAULT '2c' CHECK (snmp_version IN ('1','2c')),
  secretos        bytea,                                -- {snmp_community} cifrado (pgcrypto)
  estado          text        NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','ejecutando','completado','error')),
  total_vivos     integer,                              -- IPs que respondieron a ping
  total_candidatos integer,                             -- candidatos encontrados
  mensaje         text,                                 -- error / resumen
  perfil_id       uuid,                                 -- quién lo lanzó (auditoría)
  created_at      timestamptz NOT NULL DEFAULT now(),
  completado_at   timestamptz
);
COMMENT ON TABLE descubrimiento_escaneos IS 'Trabajos de barrido de red; los ejecuta el worker.';

CREATE TABLE IF NOT EXISTS descubrimiento_candidatos (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  escaneo_id    bigint      NOT NULL REFERENCES descubrimiento_escaneos(id) ON DELETE CASCADE,
  ip            text        NOT NULL,
  sysname       text,
  sysdescr      text,
  sysobjectid   text,
  tipo_sugerido text,                                   -- codigo de tipo (switch_lan/servidor/...)
  responde_snmp boolean     NOT NULL DEFAULT false,
  latencia_ms   integer,
  estado        text        NOT NULL DEFAULT 'nuevo'
                  CHECK (estado IN ('nuevo','agregado','descartado','existente')),
  recurso_id    bigint      REFERENCES recursos(id) ON DELETE SET NULL,  -- si ya existe o se agregó
  created_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE descubrimiento_candidatos IS 'Equipos detectados en un barrido, para dar de alta o descartar.';
CREATE INDEX IF NOT EXISTS idx_descub_candidatos ON descubrimiento_candidatos(escaneo_id, estado);

COMMIT;
