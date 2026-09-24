"""Carga masiva de cuentas desde CSV.

Formato: una fila por persona con columnas `email`, `nombres`, `apellidos` y, opcionalmente,
`investigador` y `admin` (sí/no; por omisión investigador = sí, admin = no). Se aceptan coma,
punto y coma o tabulador como separador, UTF-8 (con o sin BOM) o Latin-1, y encabezados con o
sin tildes ni mayúsculas («Correo», «Nombre», «Apellido» también sirven).

Flujo en dos pasos: `leer` valida y clasifica cada fila (nueva, ya existe, error) sin crear
nada; `crear` da de alta solo las filas nuevas.
"""
import csv
import io
import re
import secrets

from app import usuarios
from app.db import auditar, sin_tildes
from app.seguridad import password_temporal

MAX_BYTES = 1024 * 1024
MAX_FILAS = 500
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALIAS = {
    "email": ("email", "correo", "e-mail", "mail", "correo electronico", "correo institucional"),
    "nombres": ("nombres", "nombre"),
    "apellidos": ("apellidos", "apellido"),
    "investigador": ("investigador", "es investigador", "es_investigador"),
    "admin": ("admin", "administrador", "administradora", "es admin", "es_admin"),
}
SI = {"si", "s", "x", "1", "true", "verdadero", "yes", "y"}
NO = {"no", "n", "0", "false", "falso", ""}
PLANTILLA = ("email,nombres,apellidos,investigador,admin\n"
             "sofia.kovalevskaya@instituto.cl,Sofía,Kovalévskaya,sí,no\n"
             "carl.gauss@instituto.cl,Carl Friedrich,Gauss,sí,no\n")


def _decodificar(contenido: bytes) -> str:
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenido.decode("latin-1")


def _separador(texto: str) -> str:
    primera = texto.splitlines()[0] if texto.strip() else ""
    return max((",", ";", "\t"), key=primera.count)


def _booleano(valor: str, por_omision: bool) -> bool | None:
    v = sin_tildes(valor or "").strip()
    if v == "":
        return por_omision
    if v in SI:
        return True
    if v in NO:
        return False
    return None


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (filas clasificadas, errores generales). Cada fila: linea, email, nombres, apellidos,
    es_investigador, es_admin, estado ('nueva' | 'existe' | 'error') y mensaje."""
    if len(contenido) > MAX_BYTES:
        return [], ["El archivo supera 1 MB."]
    texto = _decodificar(contenido)
    if not texto.strip():
        return [], ["El archivo está vacío."]
    lector = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    encabezados = [sin_tildes(h).strip().replace("﻿", "") for h in next(lector, [])]
    indice = {}
    for campo, alias in ALIAS.items():
        for i, h in enumerate(encabezados):
            if h in alias:
                indice[campo] = i
                break
    faltan = [c for c in ("email", "nombres", "apellidos") if c not in indice]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. La primera fila debe tener los encabezados "
                    "(email, nombres, apellidos, y opcionalmente investigador y admin)."]

    filas, vistos = [], set()
    for n, registro in enumerate(lector, start=2):
        if not any(c.strip() for c in registro):
            continue
        if len(filas) >= MAX_FILAS:
            return filas, [f"Se procesan hasta {MAX_FILAS} filas; divida el archivo."]

        def celda(campo):
            i = indice.get(campo)
            return registro[i].strip() if i is not None and i < len(registro) else ""

        f = {"linea": n, "email": celda("email").lower(), "nombres": celda("nombres"),
             "apellidos": celda("apellidos"),
             "es_investigador": _booleano(celda("investigador"), True),
             "es_admin": _booleano(celda("admin"), False)}
        problemas = []
        if not _RE_EMAIL.match(f["email"]):
            problemas.append("correo no válido")
        if not f["nombres"] or not f["apellidos"]:
            problemas.append("faltan nombres o apellidos")
        if f["es_investigador"] is None or f["es_admin"] is None:
            problemas.append("use sí/no en investigador y admin")
        elif not f["es_investigador"] and not f["es_admin"]:
            problemas.append("debe ser investigador, admin o ambos")
        if f["email"] in vistos:
            problemas.append("correo repetido en el archivo")
        vistos.add(f["email"])
        if problemas:
            f.update(estado="error", mensaje="; ".join(problemas).capitalize() + ".")
        elif usuarios.por_email(f["email"]):
            f.update(estado="existe", mensaje="Ya tiene cuenta: se omite.")
        else:
            f.update(estado="nueva", mensaje="")
        filas.append(f)
    if not filas:
        return [], ["El archivo no tiene filas con datos."]
    return filas, []


def crear(filas: list[dict], invitar: bool, admin_id: int, enviar_invitacion) -> list[dict]:
    """Crea las cuentas de las filas 'nuevas'. Con invitación, cada persona recibe un enlace;
    sin ella, se devuelve una contraseña temporal por cuenta (para entregarla a mano)."""
    creadas = []
    for f in filas:
        if f["estado"] != "nueva" or usuarios.por_email(f["email"]):
            continue
        datos = dict(email=f["email"], nombres=f["nombres"], apellidos=f["apellidos"],
                     es_admin=f["es_admin"], es_investigador=f["es_investigador"])
        if invitar:
            u = usuarios.crear(password=secrets.token_urlsafe(24), debe_cambiar_pass=False, **datos)
            enviar_invitacion(u)
            creadas.append({**u, "password": None})
        else:
            password = password_temporal()
            u = usuarios.crear(password=password, **datos)
            creadas.append({**u, "password": password})
    if creadas:
        auditar(admin_id, "importar_usuarios", "usuario", None,
                f"{len(creadas)} cuenta(s){' con invitación' if invitar else ''}")
    return creadas
