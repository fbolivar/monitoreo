# SIMON — Funcionalidades avanzadas (guía operativa)

Mejoras incorporadas sobre la base (FASES 0–6). Todas están en producción en
https://192.168.50.54/. Esta guía resume **qué hacen** y **cómo operarlas**.

| Funcionalidad | Migración | Capas tocadas |
|---|---|---|
| Interfaces SNMP (IF-MIB) | 0004 | worker · API · frontend |
| Dependencias padre→hijo | 0005 | BD · worker · API · frontend |
| Reportes de disponibilidad (SLA) | — | API · frontend |
| Mapa de sedes | — | frontend |
| Bitácora de auditoría | 0006 | BD · API · frontend |
| Interfaces Fase 2 (histórico + alertas) | 0007 | BD · worker · API · frontend |
| Escalado por tiempo (on-call) | 0008 | BD · worker |
| Tablero NOC (wallboard) | — | frontend |
| Grafana | — | infra |
| Receptor de SNMP traps | 0009 | BD · worker (servicio) · API · frontend |
| SSO AD/LDAP + 2FA TOTP | 0010 | BD · API · frontend |

---

## 1. Interfaces SNMP (IF-MIB)

Monitorea los puertos de equipos SNMP: estado oper/admin, **tráfico in/out en Mbps**
(calculado por delta de contadores HC de 64 bits), **utilización %**, errores y velocidad.

**Cómo activarlo en un equipo:** en *Recursos → Editar*, en **Parámetros (JSON)** añade
`"interfaces": true`. En el siguiente ciclo el worker recorre la IF-MIB y muestra la sección
**"Interfaces"** en el detalle del recurso.

- Solo lista interfaces **físicas y agregados** (ethernet, port-channel); descarta VLANs y loopback.
- El throughput requiere 2 ciclos para el primer dato (y tras reiniciar el worker).

## 2. Dependencias padre→hijo (anti-tormenta de alertas)

Evita 30 alertas cuando cae el enlace/firewall de una sede: solo alerta la **causa raíz**.

**Cómo modelarlo:** en *Recursos → Editar*, campo **"Depende de"** → elige el recurso aguas
arriba. Encadena según tu topología, p. ej.:

```
servidores / switches  →  switch core  →  firewall  →  enlace WAN/Starlink
```

Si un **ancestro** está `down`, el worker **suprime** la incidencia y la notificación del hijo
(lo registra como `dependencia_caida`; en el detalle aparece un aviso "alertas silenciadas").
La API rechaza ciclos y autodependencias.

## 3. Reportes de disponibilidad (SLA)

Pantalla **"Reportes"**: disponibilidad por recurso en **24h / 7d / 30d**, ordenado peor-primero,
con KPIs (promedio, incidencias) y **exportar CSV**.

`disponibilidad = (operativo + degradado) / chequeos evaluables` (excluye mantenimiento y sin-dato).

## 4. Mapa de sedes

Pantalla **"Mapa"**: contorno de Colombia (SVG embebido, **funciona sin internet**) con un
marcador por sede, **coloreado por el peor estado** de sus recursos y dimensionado por cantidad.
Requiere latitud/longitud en *Sitios* (los que no las tengan se listan aparte).

## 5. Bitácora de auditoría (solo admin)

Pantalla **"Auditoría"**: registra automáticamente **quién** hizo **qué** y **cuándo**:
crear/actualizar/eliminar de las entidades de gestión (con **diff antes/después**), y logins
(exitosos y fallidos). Filtros por acción, entidad y texto. El actor queda desnormalizado
(`actor_email`) para sobrevivir al borrado del usuario.

> Las escrituras del worker (Python) no generan ruido; solo se auditan las acciones por la API.

## 6. Interfaces Fase 2 — histórico y alertas por puerto

Sobre la funcionalidad 1:

- **Histórico/gráficas:** en el detalle, haz clic en una fila de interfaz para desplegar las
  **gráficas de Entrada/Salida (Mbps)** del puerto (rango 1h/24h/7d). Se guarda en
  `interfaces_historico` (solo puertos oper-up) con **retención de 7 días**.
- **Alerta por puerto:** marca la casilla **"Monitorear"** en los puertos críticos (uplinks/WAN).
  Cuando un puerto monitoreado pasa a **oper-down**, el worker **abre una incidencia**
  ("puerto X caído") y **notifica**; al recuperarse, la **cierra**. Respeta mantenimiento y la
  supresión por dependencia.

## 7. Escalado por tiempo (on-call)

Si una incidencia **abierta no se reconoce** en `ESCALATION_MIN` minutos (def. 15), el worker
reenvía un evento **"⏰ escalada por tiempo"** por los canales activos. **Reconocer la incidencia
detiene el escalado.** Complementa el escalado por severidad ya existente.

Variables (`monitor/.env`): `ESCALATION_MIN` (0 = desactivado), `ESCALATION_CHECK_SEG` (frecuencia
del chequeo). Sugerencia: define un canal (correo/Telegram) con `min_severidad` adecuado para que la
escalada llegue al on-call.

## 8. Tablero NOC (wallboard)

Entrada **"Tablero NOC ↗"** del menú → vista **a pantalla completa** (`/wallboard`, fuera del marco
normal), tema oscuro, **autorefrescante**, con: KPIs globales (operativo/degradado/caído/…), reloj,
indicador EN VIVO y **tiles por sede** coloreados por peor estado (parpadean si hay caídas).
Pensada para proyectar en la sala de operaciones. "Salir" regresa a la app.

## 9. Grafana

Dashboards ricos e históricos largos leyendo **el mismo PostgreSQL** (rol de **solo lectura**).

- Acceso: `http://192.168.50.54:3000` (usuario `admin`/`admin` el primer ingreso → **cámbialo**).
- Trae el dashboard **"SIMON — Visión general"** (estado, incidencias, latencia, throughput).
- Instalación/provisión: `infra/deploy/19_grafana.sh` (rol `grafana_ro`, datasource y dashboard
  automáticos; artefactos en `infra/grafana/`). La clave RO queda en `GRAFANA_RO_PW`.

## 10. Receptor de SNMP traps (tiempo real)

Servicio **`simon-traps`** escuchando **UDP/162**: captura eventos que los equipos envían por su
cuenta (link down/up, cold/warm start, fallas, autenticación) **entre sondeos**, los asocia al
recurso por IP de origen y los registra. Pantalla **"Traps"** (filtro por severidad + varbinds).

**Para que un equipo envíe traps a SIMON:** configura el destino de traps SNMP del equipo apuntando
a la IP del servidor, comunidad `public` (o la que definas en `TRAP_COMMUNITY`). Ej. FortiGate/Dell:
"SNMP trap host = 192.168.50.54". *(Aún no abre incidencias automáticamente; es registro + visibilidad
en tiempo real — el paso a incidencia/alerta queda como mejora futura.)*

## 11. SSO AD/LDAP + 2FA (TOTP)

**2FA (verificación en dos pasos):** cada usuario lo activa en **"Seguridad"** (topbar): se genera un
secreto (clave + enlace `otpauth://` para la app autenticadora — Google/Microsoft Authenticator,
FreeOTP), se confirma con un código de 6 dígitos. A partir de ahí, el login pide el código. Solo
aplica a **cuentas locales**. Implementación propia (RFC 6238), sin dependencias.

**SSO con Active Directory / LDAP** (opcional, *env-gated*): permite entrar con credenciales
corporativas. Desactivado por defecto. Para activarlo, en `api/.env`:

```
AUTH_LDAP_ENABLED=true
AUTH_LDAP_HOST=ldap://controlador.dominio.gov.co
AUTH_LDAP_PORT=389
AUTH_LDAP_TLS=false
AUTH_LDAP_BIND_PATTERN={user}@parques.gov.co   # o '{user}' si se escribe el UPN completo
AUTH_LDAP_ROL_DEFAULT=viewer
```

El login intenta primero la contraseña local (el admin local siempre funciona) y luego LDAP. Al
primer ingreso por LDAP se crea el perfil con `origen='ldap'` y rol por defecto (ajustable luego en
Usuarios). Requiere la extensión `php8.2-ldap` (ya instalada). Los usuarios LDAP usan el 2FA del
directorio, no el de la app.

---

## Despliegue / operación

- Repo en el servidor: `/opt/monitoreo`. Scripts en `infra/deploy/` (numerados por hito).
- Actualizar: `git pull` + aplicar migración pendiente (`psql -f db/migrations/NNNN_*.up.sql`) +
  `php artisan optimize:clear` (API) + `ng build` (frontend) + `systemctl restart monitoreo-worker`.
- Verificación integral (solo lectura): `infra/deploy/verify_consolidado.sh`.
- Secretos del servidor en `/root/monitoreo-secrets.env` (NO en el repo).
