#!/usr/bin/env bash
set -euo pipefail
cd /opt/monitoreo/monitor
.venv/bin/python <<'PY'
import smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from monitor.config import cargar_settings
from monitor.db import Database
from monitor import repository as repo

s = cargar_settings(); db = Database(s)
ch = [x for x in repo.canales_activos(db, s.app_crypto_key) if x.tipo == "email"]
if not ch:
    print("NO HAY CANAL EMAIL"); raise SystemExit
c = ch[0]; cfg = c.config; sec = c.secretos or {}
host, port = cfg["smtp_host"], int(cfg["smtp_port"])
frm, to = cfg["from"], cfg["destinatarios"]
print(f"host={host} port={port} from={frm} to={to} user={sec.get('smtp_user')} pass_len={len(sec.get('smtp_pass',''))}")

m = MIMEText("Prueba con traza SMTP del Sistema de Monitoreo.", "plain", "utf-8")
m["Subject"] = "[PRUEBA2] Monitoreo TI - traza"
m["From"] = frm
m["To"] = ", ".join(to)
m["Date"] = formatdate(localtime=True)
m["Message-ID"] = make_msgid(domain="parquesnacionales.gov.co")

try:
    srv = smtplib.SMTP(host, port, timeout=25)
    srv.set_debuglevel(1)
    srv.ehlo()
    srv.starttls(context=ssl.create_default_context())
    srv.ehlo()
    srv.login(sec["smtp_user"], sec["smtp_pass"])
    resp = srv.sendmail(frm, to, m.as_string())
    print("SENDMAIL_OK refused=", resp)
    srv.quit()
except Exception as e:
    print("ERROR:", type(e).__name__, e)
db.close()
PY
