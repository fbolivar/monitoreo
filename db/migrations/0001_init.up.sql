-- =====================================================================
-- 0001_init.up.sql
-- Esquema núcleo del Sistema de Monitoreo de Disponibilidad de TI.
--
-- Portabilidad: Postgres 14+ estándar. Solo se usa la extensión contrib
-- `pgcrypto` (disponible tanto en Supabase como en Postgres puro). NO se
-- usan tipos ni funciones propietarias de Supabase.
--
-- Catálogo de ESTADOS (propuesto; no estaba definido en CLAUDE.md):
--   recurso / chequeo:
--     up           -> operativo, responde dentro de umbrales
--     degraded     -> responde pero alguna métrica fuera de umbral (warning)
--     down         -> no responde / caído (critical)
--     unknown      -> sin datos o no evaluable (probe falló por causa interna)
--     maintenance  -> en ventana de mantenimiento (alertas silenciadas)
--   incidencia:        abierta | reconocida | resuelta
--   severidad:         info | warning | critical
--   notificación:      pendiente | enviada | fallida
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Extensiones
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() + cifrado simétrico

-- ---------------------------------------------------------------------
-- MECANISMO DE CIFRADO DE SECRETOS  (propuesta)
-- ---------------------------------------------------------------------
-- Cada recurso tiene parámetros de conexión NO sensibles en `recursos.parametros`
-- (jsonb, en claro: puerto, versión SNMP, OIDs, path HTTP, etc.) y los SECRETOS
-- (community SNMP, api_key, password, token...) en `recursos.secretos` (bytea),
-- cifrados con cifrado simétrico autenticado de pgcrypto (pgp_sym_encrypt).
--
-- La CLAVE MAESTRA nunca se almacena en la base de datos: la posee la API
-- (Laravel .env -> APP_CRYPTO_KEY) y se pasa como argumento en cada llamada.
-- Los workers Python que necesiten un secreto lo solicitan a la API, o reciben
-- la clave por su propio entorno; jamás se persiste en una tabla ni en logs.
--
-- Helpers (azúcar sobre pgp_sym_encrypt/decrypt). El secreto se modela como
-- jsonb para alojar múltiples claves (p.ej. {"snmp_community":"...","password":"..."}).
CREATE OR REPLACE FUNCTION cifrar_secreto(p_secreto jsonb, p_clave text)
RETURNS bytea
LANGUAGE sql
AS $$
  SELECT pgp_sym_encrypt(p_secreto::text, p_clave, 'cipher-algo=aes256, compress-algo=0');
$$;

CREATE OR REPLACE FUNCTION descifrar_secreto(p_cifrado bytea, p_clave text)
RETURNS jsonb
LANGUAGE sql
AS $$
  SELECT CASE
           WHEN p_cifrado IS NULL THEN NULL
           ELSE pgp_sym_decrypt(p_cifrado, p_clave)::jsonb
         END;
$$;

COMMENT ON FUNCTION cifrar_secreto(jsonb, text) IS
  'Cifra un jsonb de secretos con pgp_sym_encrypt (AES-256). La clave la provee la app, nunca se guarda en BD.';
COMMENT ON FUNCTION descifrar_secreto(bytea, text) IS
  'Descifra un secreto cifrado con cifrar_secreto(). Devuelve NULL si la entrada es NULL.';

-- ---------------------------------------------------------------------
-- Trigger genérico para updated_at
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- =====================================================================
-- CATÁLOGOS
-- =====================================================================

-- Tipos de recurso (firewall, servidor, switch_lan, nas, switch_san, ups,
-- starlink, fibra_wan, sitio_web). Catálogo extensible.
CREATE TABLE tipos_recurso (
  id               smallint     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo           text         NOT NULL UNIQUE,        -- p.ej. 'firewall'
  nombre           text         NOT NULL,               -- p.ej. 'Firewall (FortiGate)'
  descripcion      text,
  protocolo_default text        NOT NULL DEFAULT 'icmp' -- icmp | snmp | http | tcp
                     CHECK (protocolo_default IN ('icmp','snmp','http','https','tcp','starlink')),
  icono            text,
  created_at       timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE tipos_recurso IS 'Catálogo de tipos de recurso monitoreables.';

-- Sitios / ubicaciones físicas donde viven los recursos.
CREATE TABLE sitios (
  id           integer      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo       text         NOT NULL UNIQUE,
  nombre       text         NOT NULL,
  direccion    text,
  ciudad       text,
  latitud      numeric(9,6),
  longitud     numeric(9,6),
  descripcion  text,
  activo       boolean      NOT NULL DEFAULT true,
  created_at   timestamptz  NOT NULL DEFAULT now(),
  updated_at   timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE sitios IS 'Ubicaciones físicas (sedes, datacenters) de los recursos.';
CREATE TRIGGER trg_sitios_updated BEFORE UPDATE ON sitios
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- PERFILES DE USUARIO
-- =====================================================================
-- `id` es un uuid que coincide con auth.users.id de Supabase, PERO NO se
-- declara FK a auth.users para mantener portabilidad a Postgres puro.
-- La integridad con Supabase Auth se gestiona en la capa API (valida el JWT).
CREATE TABLE perfiles (
  id          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  email       text         NOT NULL UNIQUE,
  nombre      text,
  rol         text         NOT NULL DEFAULT 'viewer'
                CHECK (rol IN ('admin','operador','viewer')),
  activo      boolean      NOT NULL DEFAULT true,
  created_at  timestamptz  NOT NULL DEFAULT now(),
  updated_at  timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE perfiles IS 'Perfiles de usuario. id = auth.users.id de Supabase (sin FK por portabilidad).';
COMMENT ON COLUMN perfiles.rol IS 'admin (todo) | operador (reconoce/gestiona incidencias) | viewer (solo lectura).';
CREATE TRIGGER trg_perfiles_updated BEFORE UPDATE ON perfiles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- RECURSOS
-- =====================================================================
CREATE TABLE recursos (
  id                 bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo_id            smallint     NOT NULL REFERENCES tipos_recurso(id) ON DELETE RESTRICT,
  sitio_id           integer      REFERENCES sitios(id) ON DELETE SET NULL,
  nombre             text         NOT NULL,
  hostname           text,                                  -- FQDN o IP de gestión
  descripcion        text,
  -- Parámetros de conexión NO sensibles (en claro):
  --   {"port":161,"snmp_version":"2c","oids":{...},"http_path":"/health","expected_status":200,...}
  parametros         jsonb        NOT NULL DEFAULT '{}'::jsonb,
  -- Secretos cifrados (community SNMP, api_key, password...). bytea = pgp_sym_encrypt.
  secretos           bytea,
  intervalo_segundos integer      NOT NULL DEFAULT 60
                       CHECK (intervalo_segundos BETWEEN 5 AND 86400),
  activo             boolean      NOT NULL DEFAULT true,
  -- Estado cacheado (denormalizado para el dashboard; la verdad histórica vive en `chequeos`)
  estado_actual      text         NOT NULL DEFAULT 'unknown'
                       CHECK (estado_actual IN ('up','degraded','down','unknown','maintenance')),
  ultimo_chequeo_at  timestamptz,
  created_at         timestamptz  NOT NULL DEFAULT now(),
  updated_at         timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE recursos IS 'Recursos de TI monitoreados.';
COMMENT ON COLUMN recursos.parametros IS 'Parámetros de conexión NO sensibles (jsonb en claro).';
COMMENT ON COLUMN recursos.secretos   IS 'Secretos cifrados con cifrar_secreto() (pgp_sym_encrypt/AES-256). Clave provista por la app.';
CREATE INDEX idx_recursos_tipo   ON recursos(tipo_id);
CREATE INDEX idx_recursos_sitio  ON recursos(sitio_id);
CREATE INDEX idx_recursos_activo ON recursos(activo) WHERE activo;
CREATE INDEX idx_recursos_estado ON recursos(estado_actual);
CREATE TRIGGER trg_recursos_updated BEFORE UPDATE ON recursos
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- CHEQUEOS  (resultado crudo de cada probe)
-- =====================================================================
CREATE TABLE chequeos (
  id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id  bigint       NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  ts          timestamptz  NOT NULL DEFAULT now(),
  estado      text         NOT NULL
                CHECK (estado IN ('up','degraded','down','unknown','maintenance')),
  latencia_ms integer      CHECK (latencia_ms IS NULL OR latencia_ms >= 0),
  detalle     jsonb        NOT NULL DEFAULT '{}'::jsonb  -- código, mensaje, error, payload del probe
);
COMMENT ON TABLE chequeos IS 'Histórico crudo de cada chequeo. Retención: 30 días (ver fn_purgar_datos).';
CREATE INDEX idx_chequeos_recurso_ts ON chequeos(recurso_id, ts DESC);
CREATE INDEX idx_chequeos_ts         ON chequeos(ts);

-- =====================================================================
-- UMBRALES  (reglas de alerta por métrica)
-- =====================================================================
-- Un umbral puede aplicar a un recurso concreto (recurso_id) o, por defecto,
-- a todos los recursos de un tipo (tipo_id). Exactamente uno de los dos.
CREATE TABLE umbrales (
  id                 bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id         bigint      REFERENCES recursos(id) ON DELETE CASCADE,
  tipo_id            smallint    REFERENCES tipos_recurso(id) ON DELETE CASCADE,
  metrica            text        NOT NULL,                   -- 'cpu','mem','latency','loss','temp'...
  operador           text        NOT NULL DEFAULT '>'
                       CHECK (operador IN ('>','>=','<','<=','==','!=')),
  valor_warning      double precision,
  valor_critical     double precision,
  duracion_segundos  integer     NOT NULL DEFAULT 0          -- sostenido N s antes de disparar
                       CHECK (duracion_segundos >= 0),
  activo             boolean     NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_umbral_scope CHECK (
    (recurso_id IS NOT NULL AND tipo_id IS NULL) OR
    (recurso_id IS NULL     AND tipo_id IS NOT NULL)
  ),
  CONSTRAINT chk_umbral_valor CHECK (valor_warning IS NOT NULL OR valor_critical IS NOT NULL)
);
COMMENT ON TABLE umbrales IS 'Umbrales de alerta por métrica, a nivel de recurso o de tipo.';
CREATE UNIQUE INDEX uq_umbral_recurso ON umbrales(recurso_id, metrica) WHERE recurso_id IS NOT NULL;
CREATE UNIQUE INDEX uq_umbral_tipo    ON umbrales(tipo_id, metrica)    WHERE tipo_id IS NOT NULL;
CREATE TRIGGER trg_umbrales_updated BEFORE UPDATE ON umbrales
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- INCIDENCIAS  (eventos de indisponibilidad/degradación)
-- =====================================================================
CREATE TABLE incidencias (
  id                  bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id          bigint       NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  estado              text         NOT NULL DEFAULT 'abierta'
                        CHECK (estado IN ('abierta','reconocida','resuelta')),
  severidad           text         NOT NULL DEFAULT 'warning'
                        CHECK (severidad IN ('info','warning','critical')),
  titulo              text         NOT NULL,
  descripcion         text,
  chequeo_apertura_id bigint       REFERENCES chequeos(id) ON DELETE SET NULL,
  abierta_at          timestamptz  NOT NULL DEFAULT now(),
  reconocida_at       timestamptz,
  reconocida_por      uuid         REFERENCES perfiles(id) ON DELETE SET NULL,
  resuelta_at         timestamptz,
  created_at          timestamptz  NOT NULL DEFAULT now(),
  updated_at          timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE incidencias IS 'Incidencias abiertas por degradación/caída. Se conservan indefinidamente (histórico).';
-- Una sola incidencia abierta por recurso a la vez:
CREATE UNIQUE INDEX uq_incidencia_abierta ON incidencias(recurso_id)
  WHERE estado <> 'resuelta';
CREATE INDEX idx_incidencias_recurso ON incidencias(recurso_id, abierta_at DESC);
CREATE INDEX idx_incidencias_estado  ON incidencias(estado);
CREATE TRIGGER trg_incidencias_updated BEFORE UPDATE ON incidencias
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- MANTENIMIENTOS  (ventanas que silencian alertas)
-- =====================================================================
-- Aplica a un recurso, a un sitio entero, o global (ambos NULL).
CREATE TABLE mantenimientos (
  id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id  bigint       REFERENCES recursos(id) ON DELETE CASCADE,
  sitio_id    integer      REFERENCES sitios(id) ON DELETE CASCADE,
  inicio      timestamptz  NOT NULL,
  fin         timestamptz  NOT NULL,
  motivo      text         NOT NULL,
  creado_por  uuid         REFERENCES perfiles(id) ON DELETE SET NULL,
  created_at  timestamptz  NOT NULL DEFAULT now(),
  CONSTRAINT chk_mant_rango CHECK (fin > inicio)
);
COMMENT ON TABLE mantenimientos IS 'Ventanas de mantenimiento programado; durante ellas se silencian alertas.';
CREATE INDEX idx_mant_recurso ON mantenimientos(recurso_id);
CREATE INDEX idx_mant_sitio   ON mantenimientos(sitio_id);
CREATE INDEX idx_mant_rango   ON mantenimientos(inicio, fin);

-- =====================================================================
-- CANALES DE NOTIFICACIÓN
-- =====================================================================
CREATE TABLE canales_notificacion (
  id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo        text         NOT NULL
                CHECK (tipo IN ('email','sms','webhook','slack','telegram')),
  nombre      text         NOT NULL,
  -- config NO sensible: destinatarios, url base, etc.
  config      jsonb        NOT NULL DEFAULT '{}'::jsonb,
  -- secretos cifrados: tokens/api keys del canal
  secretos    bytea,
  activo      boolean      NOT NULL DEFAULT true,
  created_at  timestamptz  NOT NULL DEFAULT now(),
  updated_at  timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE canales_notificacion IS 'Canales de salida de notificaciones. secretos = cifrar_secreto().';
CREATE TRIGGER trg_canales_updated BEFORE UPDATE ON canales_notificacion
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- NOTIFICACIONES  (entregas concretas hacia un canal)
-- =====================================================================
CREATE TABLE notificaciones (
  id            bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  incidencia_id bigint       NOT NULL REFERENCES incidencias(id) ON DELETE CASCADE,
  canal_id      bigint       NOT NULL REFERENCES canales_notificacion(id) ON DELETE CASCADE,
  estado        text         NOT NULL DEFAULT 'pendiente'
                  CHECK (estado IN ('pendiente','enviada','fallida')),
  destino       text,                                        -- email/teléfono/url concretos
  payload       jsonb        NOT NULL DEFAULT '{}'::jsonb,
  intentos      integer      NOT NULL DEFAULT 0,
  error         text,
  enviada_at    timestamptz,
  created_at    timestamptz  NOT NULL DEFAULT now()
);
COMMENT ON TABLE notificaciones IS 'Registro de notificaciones emitidas por incidencia y canal.';
CREATE INDEX idx_notif_incidencia ON notificaciones(incidencia_id);
CREATE INDEX idx_notif_canal      ON notificaciones(canal_id);
CREATE INDEX idx_notif_estado     ON notificaciones(estado) WHERE estado = 'pendiente';

COMMIT;
