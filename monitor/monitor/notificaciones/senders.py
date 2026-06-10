"""Emisores por canal (E/S aislada). Cada uno devuelve (ok, error, destino).

Config (no sensible) y secretos (descifrados) viven en el objeto Canal:
- email:    config{smtp_host, smtp_port, from, destinatarios[]}  secretos{smtp_user, smtp_pass}
- telegram: config{chat_id}                                      secretos{bot_token}
- webhook:  config{url}                                          secretos{token}
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText

from ..models import Canal


def enviar(canal: Canal, msg: dict) -> tuple[bool, str | None, str | None]:
    if canal.tipo == "email":
        return _email(canal, msg)
    if canal.tipo == "telegram":
        return _telegram(canal, msg)
    if canal.tipo == "webhook":
        return _webhook(canal, msg)
    return False, f"tipo de canal no soportado: {canal.tipo}", None


def _email(canal: Canal, msg: dict):
    cfg = canal.config or {}
    sec = canal.secretos or {}
    host = cfg.get("smtp_host")
    port = int(cfg.get("smtp_port", 587))
    remitente = cfg.get("from") or sec.get("smtp_user")
    destinatarios = cfg.get("destinatarios") or []
    if not host or not destinatarios or not remitente:
        return False, "config de email incompleta (smtp_host/from/destinatarios)", None

    mime = MIMEText(msg["texto"], "plain", "utf-8")
    mime["Subject"] = msg["asunto"]
    mime["From"] = remitente
    mime["To"] = ", ".join(destinatarios)
    destino = ", ".join(destinatarios)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as s:
                if sec.get("smtp_user"):
                    s.login(sec["smtp_user"], sec.get("smtp_pass", ""))
                s.sendmail(remitente, destinatarios, mime.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls(context=ssl.create_default_context())
                if sec.get("smtp_user"):
                    s.login(sec["smtp_user"], sec.get("smtp_pass", ""))
                s.sendmail(remitente, destinatarios, mime.as_string())
        return True, None, destino
    except Exception as e:  # noqa: BLE001
        return False, str(e), destino


def _telegram(canal: Canal, msg: dict):
    import httpx

    cfg = canal.config or {}
    sec = canal.secretos or {}
    token = sec.get("bot_token")
    chat = cfg.get("chat_id")
    if not token or not chat:
        return False, "config de telegram incompleta (bot_token/chat_id)", None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    texto = f"{msg['asunto']}\n{msg['texto']}"
    try:
        r = httpx.post(url, json={"chat_id": chat, "text": texto}, timeout=15)
        r.raise_for_status()
        return True, None, str(chat)
    except Exception as e:  # noqa: BLE001
        return False, str(e), str(chat)


def _webhook(canal: Canal, msg: dict):
    import httpx

    cfg = canal.config or {}
    sec = canal.secretos or {}
    url = cfg.get("url")
    if not url:
        return False, "config de webhook incompleta (url)", None

    headers = {}
    if sec.get("token"):
        headers["Authorization"] = f"Bearer {sec['token']}"
    try:
        r = httpx.post(url, json=msg, headers=headers, timeout=15)
        r.raise_for_status()
        return True, None, url
    except Exception as e:  # noqa: BLE001
        return False, str(e), url
