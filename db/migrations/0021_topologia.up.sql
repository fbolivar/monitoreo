-- =====================================================================
-- 0021_topologia.up.sql
-- Topología L2 automática por LLDP. El worker camina la LLDP-MIB
-- (1.0.8802.1.1.2.1.4) de cada switch por SNMP y registra sus VECINOS
-- (qué equipo/puerto está conectado a cada puerto local). Agregado entre
-- switches => mapa de conexiones físicas, sin dibujarlo a mano.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS lldp_vecinos (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id        bigint      NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,  -- switch local
  local_port_num    integer,                                    -- lldpLocalPortNum (índice LLDP)
  local_port        text,                                       -- nombre del puerto local (p.ej. 'Te 1/1')
  remote_sysname    text,                                       -- nombre del equipo vecino
  remote_chassis    text,                                       -- chassis-id del vecino (MAC normalmente)
  remote_port       text,                                       -- puerto del vecino
  remote_sysdesc    text,
  recurso_remoto_id bigint      REFERENCES recursos(id) ON DELETE SET NULL,  -- si el vecino es un recurso conocido
  ts                timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE lldp_vecinos IS 'Vecinos LLDP por switch (snapshot); base de la topología L2.';
CREATE INDEX IF NOT EXISTS idx_lldp_recurso ON lldp_vecinos(recurso_id);
CREATE INDEX IF NOT EXISTS idx_lldp_remoto  ON lldp_vecinos(recurso_remoto_id);

COMMIT;
