"""Envío de correo con modos intercambiables (ver config.CORREO_MODO).

- archivo:     escribe cada mensaje como .eml en <datos>/correos (desarrollo; se abren con
               cualquier cliente de correo).
- smtp:        envía por SMTP en un hilo aparte, para no demorar la respuesta al usuario.
- memoria:     guarda los mensajes en `ENVIADOS` (tests).
- desactivado: no hace nada.

Un fallo al enviar nunca rompe la operación que lo originó: se registra en el log.
"""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid

from app import config
from app.db import dir_datos

log = logging.getLogger("portal.correo")
ENVIADOS: list[EmailMessage] = []
_hilos = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correo")


def mensaje(para: str, asunto: str, cuerpo: str) -> EmailMessage:
    m = EmailMessage()
    m["From"] = config.CORREO_REMITENTE
    m["To"] = para
    m["Subject"] = asunto
    m["Message-ID"] = make_msgid(domain="portal.local")
    m.set_content(cuerpo + f"\n\n--\n{config.NOMBRE_INSTITUTO} · Portal de Investigación\n{config.URL_BASE}\n")
    return m


def _smtp(m: EmailMessage):
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PUERTO, timeout=20) as s:
            if config.SMTP_STARTTLS:
                s.starttls()
            if config.SMTP_USUARIO:
                s.login(config.SMTP_USUARIO, config.SMTP_CLAVE or "")
            s.send_message(m)
    except (OSError, smtplib.SMTPException):
        log.exception("No se pudo enviar el correo «%s» a %s", m["Subject"], m["To"])


def enviar(para: str, asunto: str, cuerpo: str):
    m = mensaje(para, asunto, cuerpo)
    modo = config.CORREO_MODO
    try:
        if modo == "memoria":
            ENVIADOS.append(m)
        elif modo == "archivo":
            carpeta = dir_datos() / "correos"
            carpeta.mkdir(parents=True, exist_ok=True)
            nombre = f"{datetime.now():%Y%m%d-%H%M%S-%f}.eml"
            (carpeta / nombre).write_bytes(bytes(m))
            log.info("Correo guardado en %s (para %s: %s)", carpeta / nombre, para, asunto)
        elif modo == "smtp":
            _hilos.submit(_smtp, m)
    except OSError:
        log.exception("No se pudo registrar el correo «%s» a %s", asunto, para)
