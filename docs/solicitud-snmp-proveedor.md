# Solicitud de habilitación de SNMP solo-lectura en CPE (MikroTik) de sedes

**De:** Parques Nacionales Naturales de Colombia — Coordinación de Tecnologías de la Información
**Para:** [Proveedor del servicio de conectividad MPLS]
**Asunto:** Habilitación de SNMP solo-lectura en los equipos CPE (MikroTik) para monitoreo de disponibilidad de enlaces
**Fecha:** [completar]
**Referencia contrato/servicio:** [No. de contrato / orden de servicio]

---

## 1. Contexto y justificación

Parques Nacionales opera el servicio de monitoreo **SIMON** para vigilar la disponibilidad
de su infraestructura tecnológica. Los enlaces WAN contratados con ustedes, que dan servicio
a nuestras sedes territoriales y áreas protegidas a través de la red MPLS, **no son visibles
para nuestro sistema de monitoreo**: los equipos CPE (MikroTik) instalados y administrados por
ustedes no responden a ICMP ni exponen ninguna interfaz de consulta desde nuestra central.

Como entidad que **contrata y paga estos enlaces**, requerimos visibilidad del estado y la
disponibilidad de nuestro propio servicio, de forma autónoma y en tiempo casi real, para
cumplir con nuestras obligaciones de continuidad operativa y para la gestión de incidentes.

Por lo anterior, solicitamos formalmente la habilitación de **SNMP en modo solo-lectura** en
los CPE de nuestras sedes, restringido a nuestra plataforma de monitoreo. Esta es una capacidad
nativa de RouterOS (MikroTik), de bajo esfuerzo y sin impacto en el servicio.

## 2. Solicitud técnica

Habilitar **SNMP v2c (o v3) en modo solo-lectura** en los equipos CPE MikroTik de todas las
sedes del servicio, con los siguientes parámetros:

| Parámetro | Valor solicitado |
|---|---|
| Protocolo | SNMP v2c (o v3 si lo prefieren por seguridad) |
| Modo | **Solo lectura** (sin escritura) |
| Community / usuario | Comunidad **dedicada** (NO `public`): _[la define el proveedor y nos la comparte de forma segura]_ |
| IP de origen permitida | **192.168.50.54/32** (servidor de monitoreo SIMON) — únicamente esta IP |
| Puerto | UDP **161** |

**Datos que consultaremos (solo lectura, estándar, sin información sensible de configuración):**
- `1.3.6.1.2.1.1` — Sistema: descripción, *uptime*, nombre (SNMPv2-MIB)
- `1.3.6.1.2.1.2` / `1.3.6.1.2.1.31` — Interfaces (IF-MIB): **estado oper/admin, tráfico in/out, velocidad y errores** por interfaz

No requerimos acceso de escritura, ni a la configuración del equipo, ni a credenciales.

## 3. Configuración sugerida en RouterOS (para facilitar la implementación)

Para minimizar el esfuerzo de su equipo, dejamos la configuración exacta. SNMP v2c solo-lectura,
restringido a nuestra IP:

```
/snmp community
add name=<COMMUNITY_DEDICADA> addresses=192.168.50.54/32 read-access=yes write-access=no
/snmp
set enabled=yes contact="PNN Colombia - Monitoreo SIMON" location="<NOMBRE_SEDE>"
```

Si filtran tráfico en el firewall del CPE, permitir además la consulta SNMP desde nuestra IP:

```
/ip firewall filter
add chain=input protocol=udp dst-port=161 src-address=192.168.50.54 action=accept \
    comment="SNMP monitoreo PNN SIMON" place-before=0
```

*(Opción más segura — SNMP v3 con autenticación: con gusto coordinamos usuario/credenciales
en lugar de community v2c.)*

## 4. Consideraciones de seguridad

La habilitación solicitada es de **mínima exposición**:
- **Solo lectura** — imposible modificar la configuración del equipo.
- **Restringida a una única IP** de origen (192.168.50.54).
- **Comunidad dedicada** (no la `public` por defecto).
- Únicamente datos de **estado y desempeño** de interfaces; ninguna credencial ni configuración sensible.

## 5. Información que requerimos de su parte

Para completar la configuración en SIMON, solicitamos:
1. La **comunidad SNMP** (o usuario/credenciales v3) definida, por canal seguro.
2. La **dirección IP del CPE (gateway LAN) por sede** que responderá a las consultas SNMP, junto
   con el nombre de cada sede, para mapearlas correctamente.
3. Confirmación de la **fecha de habilitación**.

## 6. Alternativa mínima

En caso de no poder habilitar SNMP de forma inmediata, solicitamos como **mínimo** permitir
**ICMP (echo/ping)** hacia la IP del gateway LAN de cada CPE, **únicamente desde 192.168.50.54**,
para al menos disponer de la verificación de disponibilidad (up/down) del enlace mientras se
habilita el monitoreo completo por SNMP.

---

Agradecemos su gestión. Esta visibilidad es parte del aseguramiento del servicio contratado y
nos permite responder oportunamente ante indisponibilidades. Quedamos atentos a la fecha de
implementación y a los parámetros (community e IPs por sede) para activarlo de nuestro lado.

Cordialmente,

**[Nombre]**
**[Cargo] — Tecnologías de la Información**
**Parques Nacionales Naturales de Colombia**
**[Correo] · [Teléfono]**
