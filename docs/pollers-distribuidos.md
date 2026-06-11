# Pollers distribuidos (worker por sede/parque)

**Problema:** los equipos de los parques remotos están detrás de NAT / Starlink (CGNAT),
así que el worker central **no los alcanza** directo. Solución: un worker **en cada sede**
que monitorea localmente y **escribe en la BD central** (a la que sí llega por internet/VPN).

## Cómo funciona
El mismo código del worker (`/monitor`) corre en cada sede con dos diferencias en su `.env`:

- `WORKER_SITIOS=3` → ese worker **solo** atiende los recursos cuyo `sitio_id` esté en la lista
  (separados por coma, ej. `3,7`). Así el worker local solo chequea SUS equipos.
- `DB_HOST` / `DB_*` → apunta a la **BD central** (PostgreSQL de SIMON), accesible desde la sede.

El worker **central** se configura para **excluir** las sedes remotas (poniendo en su
`WORKER_SITIOS` solo los sitios que él sí alcanza), de modo que no intente chequear equipos
remotos que no ve.

## Despliegue de un poller remoto (resumen)
1. En la sede, instala Python 3.11 + el paquete `/monitor` (igual que el central).
2. `.env` del poller:
   ```
   DB_HOST=<ip/host central>      # la BD central, alcanzable desde la sede
   DB_PORT=5432
   DB_DATABASE=monitoreo
   DB_USERNAME=monitoreo
   DB_PASSWORD=...
   DB_SSLMODE=require             # recomendado sobre internet
   APP_CRYPTO_KEY=...             # misma clave para descifrar secretos
   WORKER_SITIOS=3                # el/los sitio(s) de esta sede
   TRAPS_ENABLED=false           # opcional: traps solo en el central
   ```
3. Servicio systemd igual que el central (`monitoreo-worker`).
4. En el **central**, ajusta `WORKER_SITIOS` para que NO incluya las sedes remotas.

## Seguridad / red
- La BD central debe estar accesible solo desde las sedes (firewall) y con `sslmode=require`.
- Alternativa más segura: exponer la BD por **VPN** (IPsec/WireGuard) sede→central en vez de internet.
- Cada poller usa la misma `APP_CRYPTO_KEY` para descifrar los secretos de sus recursos (pgcrypto).

## Estado
Base implementada: filtrado de recursos por sitio (`WORKER_SITIOS`). Pendiente como mejora:
registro de "qué poller hizo cada chequeo" (columna `poller` en `chequeos`) y un canal de reporte
vía API en lugar de conexión directa a la BD (para sedes sin acceso de BD).
