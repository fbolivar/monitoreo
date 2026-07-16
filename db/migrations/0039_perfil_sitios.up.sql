-- =====================================================================
-- 0039_perfil_sitios.up.sql
-- Alcance por usuario: a qué sitios (territoriales) puede acceder un perfil.
--
-- Motivo: cualquier usuario autenticado veía TODA la entidad. Con 6 direcciones
-- territoriales se necesita que cada una vea lo suyo — y como barrera REAL, no
-- cosmética: se aplica en la API, no ocultando en la UI.
--
-- Reglas (deliberadas):
--   * SIN filas para un perfil = SIN restricción (retrocompatible: hoy nadie está
--     acotado y todo sigue igual). Acotar es opt-in explícito.
--   * Los ADMIN nunca se acotan: administran el sistema y asignan estos alcances.
--     El alcance aplica a 'operador' y 'viewer'.
--   * Un recurso sin sitio (sitio_id NULL) NO es visible para un perfil acotado:
--     no pertenece a ninguna territorial.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS perfil_sitios (
  perfil_id  uuid    NOT NULL REFERENCES perfiles(id) ON DELETE CASCADE,
  sitio_id   integer NOT NULL REFERENCES sitios(id)   ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (perfil_id, sitio_id)
);

-- Se consulta en cada petición (el alcance del usuario autenticado).
CREATE INDEX IF NOT EXISTS ix_perfil_sitios_perfil ON perfil_sitios (perfil_id);

COMMENT ON TABLE perfil_sitios IS 'Sitios a los que un perfil tiene acceso. Sin filas = sin restriccion. Los admin nunca se acotan.';

COMMIT;
