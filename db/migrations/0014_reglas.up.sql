-- =====================================================================
-- 0014_reglas.up.sql
-- Triggers compuestos (multi-condición), estilo expresiones de Zabbix.
-- Un umbral clásico = 1 métrica, 1 operador. Una regla = expresión booleana
-- sobre VARIAS métricas (AND/OR/NOT) que, al cumplirse, eleva el estado a
-- 'degraded' con la severidad indicada. Ej.: "cpu>90 Y mem>85" o "loss>5 O latency>300".
--
-- `expresion` es un AST JSON seguro (sin texto a evaluar). Gramática:
--   hoja:  {"metrica":"cpu","op":">","valor":90}
--   nodo:  {"and":[expr, ...]} | {"or":[expr, ...]} | {"not":expr}
-- El worker lo evalúa con un intérprete puro (monitor/reglas.py). NO se usa eval().
--
-- Igual que `umbrales`, una regla aplica a un recurso concreto (recurso_id) o a
-- todos los de un tipo (tipo_id). Exactamente uno de los dos.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS reglas (
  id                 bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recurso_id         bigint      REFERENCES recursos(id) ON DELETE CASCADE,
  tipo_id            smallint    REFERENCES tipos_recurso(id) ON DELETE CASCADE,
  nombre             text        NOT NULL,
  descripcion        text,
  expresion          jsonb       NOT NULL,                    -- AST: hojas {metrica,op,valor} + and/or/not
  severidad          text        NOT NULL DEFAULT 'warning'
                       CHECK (severidad IN ('info','warning','critical')),
  duracion_segundos  integer     NOT NULL DEFAULT 0           -- sostenido N s antes de disparar
                       CHECK (duracion_segundos >= 0),
  activo             boolean     NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_regla_scope CHECK (
    (recurso_id IS NOT NULL AND tipo_id IS NULL) OR
    (recurso_id IS NULL     AND tipo_id IS NOT NULL)
  )
);
COMMENT ON TABLE reglas IS 'Triggers compuestos (multi-condición) por recurso o tipo. Expresión AST en jsonb.';
COMMENT ON COLUMN reglas.expresion IS 'AST JSON: hoja {metrica,op,valor}; nodos {and:[]},{or:[]},{not:{}}.';

CREATE INDEX IF NOT EXISTS idx_reglas_recurso ON reglas(recurso_id) WHERE recurso_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reglas_tipo    ON reglas(tipo_id)    WHERE tipo_id IS NOT NULL;

CREATE TRIGGER trg_reglas_updated BEFORE UPDATE ON reglas
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
