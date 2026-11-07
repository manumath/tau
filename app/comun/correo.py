"""Envío de correo con modos intercambiables (ver config.CORREO_MODO).

- archivo:     escribe cada mensaje como .eml en <datos>/correos (desarrollo; se abren con
               cualquier cliente de correo).
- smtp:        guarda el mensaje en la cola `correo_pendiente` (en la misma transacción que lo origina: si
               se revierte, no sale) y lo envía por SMTP en un hilo aparte en cuanto se confirma. Si falla,
               `reintentar()` (lo llama el mantenimiento) lo vuelve a intentar con esperas crecientes;
               un rechazo definitivo (5xx) o `MAX_INTENTOS` fallidos lo descartan. Al enviarse, la fila se
               borra: no queda un historial de mensajes (llevan enlaces personales).
- memoria:     guarda los mensajes en `ENVIADOS` (tests).
- desactivado: no hace nada.

Un fallo al enviar nunca rompe la operación que lo originó: se registra en el log.
"""
import email
import email.policy
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid

from app.comun import config
from app.comun.db import AHORA, al_confirmar, dir_datos, get_db, marca_tiempo

log = logging.getLogger("portal.correo")
ENVIADOS: list[EmailMessage] = []
_hilos = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correo")
# Espera antes de cada nuevo intento (el primero es inmediato): unas 5 horas y media en total.
ESPERAS = [timedelta(minutes=m) for m in (1, 5, 15, 60, 240)]
MAX_INTENTOS = len(ESPERAS) + 1
POR_REVISION = 50   # correos que reintenta cada pasada del mantenimiento


def mensaje(para: str, asunto: str, cuerpo: str) -> EmailMessage:
    m = EmailMessage()
    m["From"] = config.CORREO_REMITENTE
    m["To"] = para
    m["Subject"] = asunto
    m["Message-ID"] = make_msgid(domain="portal.local")
    m.set_content(cuerpo + f"\n\n--\n{config.NOMBRE_COMPLETO}\n{config.URL_BASE}\n")
    return m


def _smtp(m: EmailMessage):
    """Envía el mensaje; lanza la excepción de smtplib (o de red) si no se pudo."""
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PUERTO, timeout=20) as s:
        if config.SMTP_STARTTLS:
            s.starttls()
        if config.SMTP_USUARIO:
            s.login(config.SMTP_USUARIO, config.SMTP_CLAVE or "")
        s.send_message(m)


def _definitivo(e: Exception) -> bool:
    """¿El servidor rechazó el mensaje para siempre (código 5xx: destinatario inexistente, etc.)?"""
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return all(codigo >= 500 for codigo, _ in e.recipients.values())
    return isinstance(e, smtplib.SMTPResponseException) and e.smtp_code >= 500


def _encolar(m: EmailMessage) -> int:
    fila = get_db().t.correo_pendiente.insert(para=m["To"], asunto=m["Subject"], mensaje=bytes(m))
    return fila["id"]


def entregar(cid: int) -> bool:
    """Envía el correo `cid` de la cola si le toca. Lo «reserva» antes (corre el próximo intento según la
    espera que corresponde), así otro hilo no lo envía a la vez y, si el proceso muere a medio enviar, se
    reintenta más tarde. True si salió."""
    db = get_db()
    fila = db.q("SELECT intentos FROM correo_pendiente WHERE id = ?", [cid])
    if not fila:
        return False
    intentos = fila[0]["intentos"]
    espera = ESPERAS[min(intentos, len(ESPERAS) - 1)]
    db.execute(f"""UPDATE correo_pendiente SET intentos = intentos + 1, proximo_intento = ?
                   WHERE id = ? AND intentos = ? AND proximo_intento <= {AHORA}""",
               [marca_tiempo(espera), cid, intentos])
    if db.conn.changes() != 1:
        return False   # otro hilo lo tomó, o aún no le toca
    datos = db.q("SELECT para, asunto, mensaje FROM correo_pendiente WHERE id = ?", [cid])[0]
    m = email.message_from_bytes(datos["mensaje"], policy=email.policy.default)
    try:
        _smtp(m)
    except (OSError, smtplib.SMTPException) as e:
        if _definitivo(e) or intentos + 1 >= MAX_INTENTOS:
            db.execute("DELETE FROM correo_pendiente WHERE id = ?", [cid])
            log.error("Se descarta el correo «%s» a %s tras %s intento(s): %s",
                      datos["asunto"], datos["para"], intentos + 1, e)
        else:
            db.execute("UPDATE correo_pendiente SET ultimo_error = ? WHERE id = ?", [str(e)[:500], cid])
            log.warning("No se pudo enviar el correo «%s» a %s (intento %s); se reintentará: %s",
                        datos["asunto"], datos["para"], intentos + 1, e)
        return False
    db.execute("DELETE FROM correo_pendiente WHERE id = ?", [cid])
    return True


def _entregar_en_hilo(cid: int):
    try:
        entregar(cid)
    except Exception:
        log.exception("Falló la entrega del correo %s de la cola", cid)


def reintentar() -> int:
    """Envía los correos de la cola a los que ya les toca (lo llama el mantenimiento). Devuelve cuántos salieron."""
    if config.CORREO_MODO != "smtp":
        return 0
    ids = [f["id"] for f in get_db().q(f"""SELECT id FROM correo_pendiente WHERE proximo_intento <= {AHORA}
                                          ORDER BY id LIMIT ?""", [POR_REVISION])]
    return sum(entregar(cid) for cid in ids)


def pendientes() -> int:
    """Cuántos correos esperan en la cola (enviándose o por reintentar)."""
    return get_db().q("SELECT count(*) AS n FROM correo_pendiente")[0]["n"]


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
            try:
                cid = _encolar(m)
            except Exception:
                # Sin cola (p. ej., la base no responde: justo el aviso de un error): se intenta una vez, directo.
                log.exception("No se pudo guardar en la cola el correo «%s» a %s; se envía sin cola", asunto, para)
                _hilos.submit(_directo, m)
                return
            al_confirmar(lambda: _hilos.submit(_entregar_en_hilo, cid))
    except OSError:
        log.exception("No se pudo registrar el correo «%s» a %s", asunto, para)


def _directo(m: EmailMessage):
    try:
        _smtp(m)
    except (OSError, smtplib.SMTPException):
        log.exception("No se pudo enviar el correo «%s» a %s", m["Subject"], m["To"])
