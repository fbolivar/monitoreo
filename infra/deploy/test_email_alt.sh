#!/usr/bin/env bash
set -euo pipefail
DEST="fbolivarb@gmail.com"
cd /opt/monitoreo/monitor
.venv/bin/python - "$DEST" <<'PY'
import sys, smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from monitor.config import cargar_settings
from monitor.db import Database
from monitor import repository as repo

dest = sys.argv[1]
s = cargar_settings(); db = Database(s)
ch = [x for x in repo.canales_activos(db, s.app_crypto_key) if x.tipo == "email"]
if not ch:
    print("NO HAY CANAL EMAIL"); raise SystemExit
c = ch[0]; cfg = c.config; sec = c.secretos or {}
host, port = cfg["smtp_host"], int(cfg["smtp_port"])
frm = cfg["from"]

m = MIMEText(
    "Correo de prueba del Sistema de Monitoreo de Disponibilidad de TI (parques nacionales).\n\n"
    "Si recibes este mensaje, las notificaciones por correo funcionan correctamente.\n"
    "Equipo monitoreado actualmente: FortiGate-Principal (operativo).",
    "plain", "utf-8")
m["Subject"] = "Monitoreo TI - prueba de entrega"
m["From"] = frm
m["To"] = dest
m["Date"] = formatdate(localtime=True)
m["Message-ID"] = make_msgid(domain="parquesnacionales.gov.co")

try:
    srv = smtplib.SMTP(host, port, timeout=25)
    srv.starttls(context=ssl.create_default_context())
    srv.login(sec["smtp_user"], sec["smtp_pass"])
    refused = srv.sendmail(frm, [dest], m.as_string())
    srv.quit()
    print(f"ENVIADO a {dest}  (rechazados={refused})")
except Exception as e:
    print("ERROR:", type(e).__name__, e)
db.close()
PY
