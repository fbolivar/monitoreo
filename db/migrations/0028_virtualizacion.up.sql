-- =====================================================================
-- 0028_virtualizacion.up.sql — Virtualización (#9)
-- Inventario por-VM de un host de virtualización (VMware vCenter por REST, o
-- Hyper-V reportado por el agente). Pasa de "el host está UP" a "qué VMs hay,
-- cuáles están encendidas y su consumo".
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS vm_inventario (
  id              bigserial PRIMARY KEY,
  host_recurso_id bigint NOT NULL REFERENCES recursos(id) ON DELETE CASCADE,
  vm_id           text NOT NULL,
  nombre          text,
  power_state     text,             -- POWERED_ON | POWERED_OFF | SUSPENDED
  cpu_count       integer,
  memoria_mb      integer,
  guest_os        text,
  ts              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (host_recurso_id, vm_id)
);
CREATE INDEX IF NOT EXISTS idx_vm_host ON vm_inventario(host_recurso_id);

COMMENT ON TABLE vm_inventario IS 'Inventario de máquinas virtuales por host (vCenter/Hyper-V).';

COMMIT;
