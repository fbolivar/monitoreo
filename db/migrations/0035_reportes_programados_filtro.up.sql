-- =====================================================================
-- 0035_reportes_programados_filtro.up.sql
-- Filtro opcional (tipo de recurso / sitio) en los reportes programados.
--
-- Motivo: el informe programado incluía SIEMPRE todos los recursos, así que no
-- se podía enviar un reporte acotado a una audiencia concreta. Caso real: mandar
-- al PROVEEDOR la disponibilidad de sus enlaces Starlink — con la tabla anterior
-- habría que enviarle también servidores, firewall y switches (fuga de info de
-- la infraestructura interna). NULL = todos (comportamiento previo).
-- =====================================================================
BEGIN;

ALTER TABLE reportes_programados
  ADD COLUMN IF NOT EXISTS tipo_id  smallint REFERENCES tipos_recurso(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS sitio_id integer  REFERENCES sitios(id)        ON DELETE SET NULL;

COMMENT ON COLUMN reportes_programados.tipo_id  IS 'Filtro opcional: solo recursos de este tipo (NULL = todos).';
COMMENT ON COLUMN reportes_programados.sitio_id IS 'Filtro opcional: solo recursos de este sitio (NULL = todos).';

COMMIT;
