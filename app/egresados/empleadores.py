"""Registro de empleadores (PLAN §57, etapa 8): organizaciones donde trabajan los titulados y la persona de contacto a la
que se envían las encuestas a empleadores (`encuesta.publico = 'empleadores'`). El contacto es una persona externa con
correo; solo los activos reciben encuestas. No se eliminan (sus respuestas nominales los referencian): se desactivan."""
import re

from app.comun.db import get_db, transaccion

SECTORES = {"educacion": "Educación", "investigacion": "Investigación", "publico": "Sector público",
            "privado": "Sector privado o empresa", "otro": "Otro"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def listar(activos: bool | None = None) -> list[dict]:
    return get_db().q(
        """SELECT m.*, pe.nombres, pe.apellidos, pe.email FROM empleador m JOIN persona_externa pe ON pe.id = m.externo_id
           WHERE (:a IS NULL OR m.activo = :a) ORDER BY m.activo DESC, m.organizacion, pe.apellidos""",
        {"a": None if activos is None else int(activos)})


def obtener(mid: int) -> dict | None:
    f = get_db().q("""SELECT m.*, pe.nombres, pe.apellidos, pe.email FROM empleador m
                      JOIN persona_externa pe ON pe.id = m.externo_id WHERE m.id = ?""", [mid])
    return f[0] if f else None


def validar(d: dict, mid: int | None = None) -> tuple[dict, list[str]]:
    x = {k: (d.get(k) or "").strip() for k in ("nombres", "apellidos", "email", "organizacion", "cargo", "sector")}
    x["email"] = x["email"].lower()
    errores = []
    if not x["organizacion"]:
        errores.append("Indique la organización.")
    if not x["nombres"] or not x["apellidos"]:
        errores.append("Indique el nombre y los apellidos de la persona de contacto.")
    if not _EMAIL.match(x["email"]):
        errores.append("Indique un correo válido: a él llegan las encuestas.")
    elif get_db().q("""SELECT 1 FROM empleador m JOIN persona_externa pe ON pe.id = m.externo_id
                       WHERE lower(pe.email) = ? AND m.id != ?""", [x["email"], mid or 0]):
        errores.append("Ya hay un empleador registrado con ese correo.")
    if x["sector"] not in SECTORES:
        errores.append("Elija el sector.")
    for k, n in (("organizacion", 200), ("cargo", 200), ("nombres", 100), ("apellidos", 100)):
        x[k] = x[k][:n]
    x["cargo"] = x["cargo"] or None
    return x, errores


def crear(x: dict, uid: int) -> int:
    with transaccion():
        pe = get_db().t.persona_externa.insert(nombres=x["nombres"], apellidos=x["apellidos"], email=x["email"],
                                               institucion=x["organizacion"], creado_por=uid)
        return get_db().t.empleador.insert(externo_id=pe["id"], organizacion=x["organizacion"], sector=x["sector"],
                                           cargo=x["cargo"], registrado_por=uid)["id"]


def actualizar(m: dict, x: dict):
    with transaccion():
        get_db().execute("UPDATE persona_externa SET nombres = ?, apellidos = ?, email = ?, institucion = ? WHERE id = ?",
                         [x["nombres"], x["apellidos"], x["email"], x["organizacion"], m["externo_id"]])
        get_db().execute("UPDATE empleador SET organizacion = ?, sector = ?, cargo = ? WHERE id = ?",
                         [x["organizacion"], x["sector"], x["cargo"], m["id"]])


def cambiar_activo(m: dict) -> bool:
    nuevo = 0 if m["activo"] else 1
    get_db().execute("UPDATE empleador SET activo = ? WHERE id = ?", [nuevo, m["id"]])
    return bool(nuevo)
