"""Trámites de proyecto de grado (PLAN §58, servicio 2), según el Reglamento General de Tipos y Modalidades de
Graduación (CEUB): perfil y documento final.

- El estudiante arma su **perfil** por secciones (las obligatorias de la Carrera más las que elija; decisión 2 del
  7-nov-2026) y el sistema genera la nota de presentación y el perfil en LaTeX con la plantilla de la Carrera.
- Flujo: borrador → visto bueno del tutor → enviado → la Dirección de Carrera o la Coordinación académica designa el
  tribunal → revisión. **Todos los miembros** dictaminan (decisión 4) en **15 días hábiles** (decisión 3): con alguna
  observación vuelve al estudiante, que responde cada una y reenvía; con todos aprobados queda favorable; con algún «no
  aprobado», rechazado. El perfil se aprueba al registrar el número de la resolución (el PDF es opcional; decisión 5).
- El **documento final** sigue el mismo flujo sobre un PDF; después se registra la reunión del tribunal con el
  postulante y el tutor (art. 34), la defensa y la nota de cada miembro (1–100): la nota final es el promedio.
"""
import json
from datetime import date, timedelta

from app.comun import estudiantes, formato, notificaciones, permisos, usuarios
from app.comun.db import AHORA, get_db, transaccion
from app.servicios.auxiliaturas import habiles_entre, sumar_habiles

MODALIDADES = {"proyecto_grado": "Proyecto de grado", "tesis": "Tesis de grado"}
TIPOS = {"perfil": "Perfil", "final": "Documento final"}
DIAS_REVISION = 15            # días hábiles del tribunal por revisión (decisión 3 del 7-nov-2026)
DIAS_AVISO = 3                # recordatorio antes del plazo
MIN_TRIBUNAL = 2
# clave → (título, obligatoria, ayuda). Orden del documento.
SECCIONES = {
    "introduccion": ("Introducción", True, "Contexto del tema y por qué interesa."),
    "antecedentes": ("Antecedentes", False, "Trabajos previos sobre el tema."),
    "planteamiento": ("Planteamiento del problema", True, "Qué problema se estudia, con precisión."),
    "objetivo_general": ("Objetivo general", True, "Lo que se logrará con el trabajo."),
    "objetivos_especificos": ("Objetivos específicos", True, "Uno por línea; cada uno verificable."),
    "justificacion": ("Justificación", False, "Por qué vale la pena el trabajo."),
    "hipotesis": ("Hipótesis", False, "Si corresponde."),
    "marco_teorico": ("Marco teórico", False, "Conceptos y resultados en que se apoya."),
    "alcances": ("Alcances y limitaciones", False, "Qué entra y qué no."),
    "metodologia": ("Metodología", True, "Cómo se llegará a los objetivos."),
    "resultados_esperados": ("Resultados esperados", False, "Qué se espera demostrar u obtener."),
    "calendario": ("Calendario", True, "Una actividad por línea: «mes 1–2: revisión bibliográfica»."),
    "bibliografia": ("Bibliografía", True, "Una referencia por línea, o entradas BibTeX (@article{…})."),
}
OBLIGATORIAS = [k for k, (_, o, _) in SECCIONES.items() if o]
ASPECTOS = {"validez": "Validez y vigencia del tema", "fundamentacion": "Fundamentación, planificación y programación",
            "coherencia": "Coherencia teórica y metodológica", "aporte": "Aporte académico"}   # art. 35
DICTAMENES = {"aprobado": "Aprobado sin observaciones", "observado": "Aprobado con observaciones (vuelve al postulante)",
              "no_aprobado": "No aprobado"}
ESTADOS = {"borrador": "Borrador", "con_tutor": "Con el tutor", "enviado": "Espera la designación del tribunal",
           "en_revision": "En revisión del tribunal", "observado": "Con observaciones", "favorable": "Dictamen favorable",
           "aprobado": "Aprobado", "rechazado": "No aprobado", "defendido": "Defendido", "reprobado": "Reprobado"}
ABIERTOS = ("borrador", "con_tutor", "enviado", "en_revision", "observado", "favorable")


def calificacion_literal(n: float) -> str:
    if n >= 90:
        return "Excelente"
    if n >= 80:
        return "Sobresaliente"
    if n >= 51:
        return "Bueno"
    return "Reprobado"


def gestiona(auth: dict) -> bool:
    return permisos.puede(auth, "gestionar_grado")


def gestores() -> list[dict]:
    vistos, res = set(), []
    for rol in ("direccion_carrera", "coordinacion_academica"):
        for u in permisos.con_rol(rol):
            if u["id"] not in vistos:
                vistos.add(u["id"])
                res.append(u)
    return res


def _avisar_gestores(asunto, texto, url):
    for u in gestores():
        notificaciones.avisar(u, asunto, texto, url)


def _avisar_estudiante(t, asunto, texto):
    notificaciones.avisar(estudiantes.usuario_de(t["externo_id"]), asunto, texto, f"/estudiante/grado/{t['id']}")


def url_staff(t) -> str:
    return f"/servicios/grado/{t['id']}"


# --- Consultas -----------------------------------------------------------------------------------------------------

def obtener(tid: int) -> dict | None:
    filas = get_db().q("""SELECT t.*, pe.nombres, pe.apellidos, pe.email,
                                 u.nombres AS tutor_nombres, u.apellidos AS tutor_apellidos,
                                 (SELECT registro_universitario FROM estudiante e WHERE e.externo_id = t.externo_id
                                    AND registro_universitario IS NOT NULL LIMIT 1) AS ru
                          FROM tramite_grado t JOIN persona_externa pe ON pe.id = t.externo_id
                          LEFT JOIN usuario u ON u.id = t.tutor_id WHERE t.id = ?""", [tid])
    if not filas:
        return None
    t = filas[0]
    t["secciones"] = json.loads(t["secciones"] or "{}")
    return t


def de_estudiante(externo_id: int) -> list[dict]:
    return [obtener(f["id"]) for f in get_db().q(
        "SELECT id FROM tramite_grado WHERE externo_id = ? ORDER BY id DESC", [externo_id])]


def listar() -> list[dict]:
    return [obtener(f["id"]) for f in get_db().q(
        """SELECT id FROM tramite_grado WHERE estado <> 'borrador'
           ORDER BY estado NOT IN ('enviado', 'favorable'), estado IN ('aprobado', 'rechazado', 'defendido', 'reprobado'), id DESC""")]


def de_tutor(uid: int) -> list[dict]:
    return [obtener(f["id"]) for f in get_db().q(
        "SELECT id FROM tramite_grado WHERE tutor_id = ? AND estado <> 'borrador' ORDER BY estado <> 'con_tutor', id DESC", [uid])]


def tribunal(tid: int) -> list[dict]:
    return get_db().q("""SELECT t.*, u.nombres, u.apellidos, u.email FROM tribunal_grado t JOIN usuario u ON u.id = t.usuario_id
                         WHERE t.tramite_id = ? ORDER BY u.apellidos""", [tid])


def es_miembro(tid: int, uid: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM tribunal_grado WHERE tramite_id = ? AND usuario_id = ?", [tid, uid]))


def de_miembro(uid: int) -> list[dict]:
    return [obtener(f["id"]) for f in get_db().q(
        """SELECT t.id FROM tramite_grado t JOIN tribunal_grado m ON m.tramite_id = t.id WHERE m.usuario_id = ?
           ORDER BY t.plazo IS NULL, t.plazo, t.id DESC""", [uid])]


def informes(tid: int, ronda: int | None = None) -> list[dict]:
    filas = get_db().q("""SELECT i.*, u.nombres, u.apellidos FROM informe_grado i JOIN usuario u ON u.id = i.miembro_id
                          WHERE i.tramite_id = ? AND (? IS NULL OR i.ronda = ?) ORDER BY i.ronda, i.id""", [tid, ronda, ronda])
    for i in filas:
        i["aspectos"] = json.loads(i["aspectos"] or "{}")
        i["observaciones"] = get_db().q("SELECT * FROM observacion_grado WHERE informe_id = ? ORDER BY numero", [i["id"]])
    return filas


def informe_de(tid: int, ronda: int, uid: int) -> dict | None:
    return next((i for i in informes(tid, ronda) if i["miembro_id"] == uid), None)


def observaciones_pendientes(t: dict) -> list[dict]:
    """Observaciones de la última ronda sin respuesta (las ve el estudiante cuando el tribunal terminó)."""
    if t["estado"] != "observado":
        return []
    return [o for i in informes(t["id"], t["ronda"]) for o in i["observaciones"] if not (o["respuesta"] or "").strip()]


def puede_ver(auth: dict, t: dict) -> bool:
    return gestiona(auth) or t["tutor_id"] == auth["id"] or es_miembro(t["id"], auth["id"])


def tutores() -> list[dict]:
    return [u for u in usuarios.listar() if u["activo"] and u["categoria"]]


def documentos(t: dict) -> list[dict]:
    from app.comun import adjuntos
    return adjuntos.listar("tramite_grado", t["id"])


# --- Estudiante: armar y enviar --------------------------------------------------------------------------------------

def seleccion(t: dict) -> list[str]:
    """Secciones del perfil, en el orden del documento: las obligatorias y las que el estudiante eligió."""
    return [k for k in SECCIONES if k in OBLIGATORIAS or k in t["secciones"]]


def validar_datos(d: dict) -> tuple[dict, list[str]]:
    errores = []
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        errores.append("Escriba el título del trabajo.")
    modalidad = d.get("modalidad") if d.get("modalidad") in MODALIDADES else "proyecto_grado"
    try:
        tutor = int(d.get("tutor_id") or 0) or None
    except ValueError:
        tutor = None
    if tutor and tutor not in {u["id"] for u in tutores()}:
        errores.append("El tutor debe ser un docente con vínculo vigente con la Carrera.")
    return {"titulo": titulo[:300], "modalidad": modalidad, "tutor_id": tutor}, errores


def crear_perfil(externo_id: int, d: dict, opcionales: list[str]) -> tuple[int | None, list[str]]:
    if any(t["tipo"] == "perfil" and t["estado"] in ABIERTOS + ("aprobado",) for t in de_estudiante(externo_id)):
        return None, ["Ya tiene un perfil en curso o aprobado."]
    x, errores = validar_datos(d)
    if errores:
        return None, errores
    secciones = {k: "" for k in SECCIONES if k in OBLIGATORIAS or k in opcionales}
    tid = get_db().t.tramite_grado.insert(externo_id=externo_id, tipo="perfil", secciones=json.dumps(secciones), **x)["id"]
    return tid, []


def editable(t: dict) -> bool:
    return t["estado"] in ("borrador", "observado")


def guardar(t: dict, d: dict, textos: dict, opcionales: list[str] | None = None) -> list[str]:
    if not editable(t):
        return ["En este momento el trámite no se puede modificar."]
    x, errores = validar_datos(d)
    if errores:
        return errores
    elegidas = set(OBLIGATORIAS) | set(opcionales if opcionales is not None else t["secciones"])
    secciones = {k: (textos.get(k, t["secciones"].get(k, "")) or "").strip()[:20000] for k in SECCIONES if k in elegidas}
    if t["tipo"] == "final":
        secciones = {}
    get_db().t.tramite_grado.update(id=t["id"], secciones=json.dumps(secciones), **x)
    return []


def faltantes(t: dict) -> list[str]:
    f = []
    if not t["tutor_id"]:
        f.append("Elegir al tutor")
    if t["tipo"] == "perfil":
        f += [f"Escribir «{SECCIONES[k][0]}»" for k in OBLIGATORIAS if not (t["secciones"].get(k) or "").strip()]
    elif not documentos(t):
        f.append("Subir el documento final (PDF)")
    if t["estado"] == "observado":
        n = len(observaciones_pendientes(t))
        if n:
            f.append(f"Responder {n} observación(es) del tribunal")
    return f


def pedir_visto_bueno(t: dict) -> list[str]:
    if t["estado"] != "borrador":
        return ["Ya lo envió al tutor."]
    if (f := faltantes(t)):
        return ["Falta: " + "; ".join(f) + "."]
    with transaccion():
        get_db().execute("UPDATE tramite_grado SET estado = 'con_tutor', comentario_tutor = NULL WHERE id = ?", [t["id"]])
        notificaciones.avisar(usuarios.por_id(t["tutor_id"]), f"Visto bueno: {TIPOS[t['tipo']].lower()} de {t['nombres']} {t['apellidos']}",
                              f"«{t['titulo']}». Revíselo y dé su visto bueno o devuélvalo con un comentario.", url_staff(t))
    return []


def responder_observacion(t: dict, oid: int, texto: str) -> list[str]:
    ids = {o["id"] for i in informes(t["id"], t["ronda"]) for o in i["observaciones"]}
    if t["estado"] != "observado" or oid not in ids:
        return ["Esa observación no está pendiente."]
    get_db().execute(f"UPDATE observacion_grado SET respuesta = ?, respondida_en = {AHORA} WHERE id = ?",
                     [(texto or "").strip()[:4000] or None, oid])
    return []


def _nueva_ronda(t: dict, ronda: int):
    plazo = sumar_habiles(date.today(), DIAS_REVISION).isoformat()
    get_db().execute(f"""UPDATE tramite_grado SET estado = 'en_revision', ronda = ?, plazo = ?, enviado_en = {AHORA}
                         WHERE id = ?""", [ronda, plazo, t["id"]])
    for m in tribunal(t["id"]):
        notificaciones.avisar(usuarios.por_id(m["usuario_id"]), f"Revisión: {TIPOS[t['tipo']].lower()} de {t['nombres']} {t['apellidos']}",
                              f"«{t['titulo']}». Su informe vence el {formato.fecha(plazo)} ({DIAS_REVISION} días hábiles).", url_staff(t))
    return plazo


def reenviar(t: dict) -> list[str]:
    if t["estado"] != "observado":
        return ["Solo se reenvía un trámite con observaciones."]
    if (f := faltantes(t)):
        return ["Falta: " + "; ".join(f) + "."]
    with transaccion():
        _nueva_ronda(t, t["ronda"] + 1)
    return []


# --- Tutor ---------------------------------------------------------------------------------------------------------

def responder_tutor(t: dict, uid: int, aprueba: bool, comentario: str) -> list[str]:
    if t["estado"] != "con_tutor" or t["tutor_id"] != uid:
        return ["Este trámite no espera su visto bueno."]
    if not aprueba and not (comentario or "").strip():
        return ["Escriba qué debe corregir el estudiante."]
    with transaccion():
        if aprueba:
            get_db().execute(f"UPDATE tramite_grado SET estado = 'enviado', enviado_en = {AHORA} WHERE id = ?", [t["id"]])
            _avisar_estudiante(t, "Su tutor dio el visto bueno", f"«{t['titulo']}» pasó a la Dirección de Carrera para designar el tribunal.")
            _avisar_gestores(f"Designar tribunal: {t['nombres']} {t['apellidos']}", f"{TIPOS[t['tipo']]} «{t['titulo']}».", url_staff(t))
        else:
            get_db().execute("UPDATE tramite_grado SET estado = 'borrador', comentario_tutor = ? WHERE id = ?",
                             [comentario.strip()[:2000], t["id"]])
            _avisar_estudiante(t, "Su tutor le devolvió el trámite", comentario.strip()[:300])
    return []


# --- Dirección: tribunal y resolución ----------------------------------------------------------------------------------

def designar_tribunal(t: dict, uids: list[int], por: int) -> list[str]:
    uids = list(dict.fromkeys(u for u in uids if u))
    if t["estado"] != "enviado":
        return ["El tribunal se designa cuando el trámite tiene el visto bueno del tutor."]
    if len(uids) < MIN_TRIBUNAL:
        return [f"Designe al menos {MIN_TRIBUNAL} docentes."]
    if t["tutor_id"] in uids:
        return ["El tutor no integra el tribunal."]
    if not set(uids) <= {u["id"] for u in tutores()}:
        return ["Los miembros deben ser docentes con vínculo vigente con la Carrera."]
    with transaccion():
        get_db().execute("DELETE FROM tribunal_grado WHERE tramite_id = ?", [t["id"]])
        for u in uids:
            get_db().t.tribunal_grado.insert(tramite_id=t["id"], usuario_id=u, designado_por=por)
        plazo = _nueva_ronda(t, 1)
        _avisar_estudiante(t, "Se designó su tribunal", f"El tribunal revisará «{t['titulo']}» hasta el {plazo}.")
    return []


def registrar_resolucion(t: dict, numero: str) -> list[str]:
    if t["tipo"] != "perfil" or t["estado"] != "favorable":
        return ["La resolución se registra con el dictamen favorable del tribunal."]
    if not (numero or "").strip():
        return ["Escriba el número de la resolución."]
    with transaccion():
        get_db().execute(f"UPDATE tramite_grado SET estado = 'aprobado', resolucion = ?, cerrado_en = {AHORA} WHERE id = ?",
                         [numero.strip()[:120], t["id"]])
        _avisar_estudiante(t, "Su perfil fue aprobado", f"Resolución {numero.strip()}. Ya puede preparar el documento final.")
    return []


def iniciar_final(perfil: dict) -> tuple[int | None, list[str]]:
    if perfil["tipo"] != "perfil" or perfil["estado"] != "aprobado":
        return None, ["El documento final se presenta sobre un perfil aprobado."]
    if any(t["tipo"] == "final" and t["perfil_id"] == perfil["id"] and t["estado"] != "reprobado"
           for t in de_estudiante(perfil["externo_id"])):
        return None, ["Ya tiene un documento final en curso."]
    tid = get_db().t.tramite_grado.insert(externo_id=perfil["externo_id"], tipo="final", perfil_id=perfil["id"],
                                          modalidad=perfil["modalidad"], titulo=perfil["titulo"], tutor_id=perfil["tutor_id"])["id"]
    return tid, []


def registrar_defensa(t: dict, reunion_en: str, defensa_en: str) -> list[str]:
    if t["tipo"] != "final" or t["estado"] != "favorable":
        return ["La defensa se programa con el dictamen favorable del tribunal."]
    if not reunion_en or not defensa_en or defensa_en < reunion_en:
        return ["Indique la fecha de la reunión con el postulante y el tutor (art. 34) y la de la defensa, posterior."]
    get_db().execute("UPDATE tramite_grado SET reunion_en = ?, defensa_en = ? WHERE id = ?", [reunion_en, defensa_en, t["id"]])
    _avisar_estudiante(t, "Defensa programada", f"Reunión con el tribunal: {reunion_en}. Defensa: {defensa_en}.")
    return []


def calificar_defensa(t: dict, uid: int, valor) -> list[str]:
    if t["tipo"] != "final" or t["estado"] != "favorable" or not t["defensa_en"]:
        return ["La defensa aún no está programada."]
    if not es_miembro(t["id"], uid):
        return ["Solo califican los miembros del tribunal."]
    if t["defensa_en"] > date.today().isoformat():
        return [f"La defensa es el {t['defensa_en']}."]
    try:
        n = int(str(valor).strip())
    except ValueError:
        return ["La nota es un número entero de 1 a 100."]
    if not 1 <= n <= 100:
        return ["La nota es un número entero de 1 a 100."]
    with transaccion():
        get_db().execute("UPDATE tribunal_grado SET nota_defensa = ? WHERE tramite_id = ? AND usuario_id = ?", [n, t["id"], uid])
        notas = [m["nota_defensa"] for m in tribunal(t["id"])]
        if all(x is not None for x in notas):
            final = nota_final(t["id"])
            estado = "defendido" if final >= 51 else "reprobado"
            get_db().execute(f"UPDATE tramite_grado SET estado = ?, cerrado_en = {AHORA} WHERE id = ?", [estado, t["id"]])
            _avisar_estudiante(t, "Resultado de su defensa", f"Nota {final}: {calificacion_literal(final)}.")
    return []


def nota_final(tid: int) -> float | None:
    notas = [m["nota_defensa"] for m in tribunal(tid) if m["nota_defensa"] is not None]
    return round(sum(notas) / len(notas), 1) if notas else None


# --- Tribunal: informe -----------------------------------------------------------------------------------------------------

def enviar_informe(t: dict, uid: int, aspectos: dict, dictamen: str, fundamento: str, observaciones: list[str]) -> list[str]:
    if t["estado"] != "en_revision":
        return ["El trámite no está en revisión."]
    if not es_miembro(t["id"], uid):
        return ["Solo informan los miembros del tribunal."]
    if informe_de(t["id"], t["ronda"], uid):
        return ["Ya envió su informe de esta revisión."]
    errores = []
    if set(aspectos) != set(ASPECTOS) or not set(aspectos.values()) <= {"suficiente", "observado"}:
        errores.append("Marque cada aspecto como suficiente u observado.")
    if dictamen not in DICTAMENES:
        errores.append("Elija su dictamen.")
    obs = [o.strip() for o in observaciones if o.strip()]
    if dictamen == "observado" and not obs:
        errores.append("Escriba al menos una observación.")
    if dictamen == "no_aprobado" and not (fundamento or "").strip():
        errores.append("Fundamente por qué no aprueba.")
    if dictamen == "aprobado" and "observado" in aspectos.values():
        errores.append("Con un aspecto observado el dictamen no puede ser «sin observaciones».")
    if errores:
        return errores
    with transaccion():
        iid = get_db().t.informe_grado.insert(tramite_id=t["id"], ronda=t["ronda"], miembro_id=uid,
                                               aspectos=json.dumps(aspectos), dictamen=dictamen,
                                               fundamento=(fundamento or "").strip()[:4000] or None)["id"]
        for n, o in enumerate(obs, 1):
            get_db().t.observacion_grado.insert(informe_id=iid, numero=n, texto=o[:2000])
        _cerrar_ronda_si_corresponde(obtener(t["id"]))
    return []


def _cerrar_ronda_si_corresponde(t: dict):
    miembros = {m["usuario_id"] for m in tribunal(t["id"])}
    hechos = informes(t["id"], t["ronda"])
    if {i["miembro_id"] for i in hechos} != miembros:
        return
    dictamenes = {i["dictamen"] for i in hechos}
    if "no_aprobado" in dictamenes:
        get_db().execute(f"UPDATE tramite_grado SET estado = 'rechazado', cerrado_en = {AHORA} WHERE id = ?", [t["id"]])
        _avisar_estudiante(t, "El tribunal no aprobó su trámite", "Vea los informes y converse con su tutor.")
        _avisar_gestores(f"No aprobado: {t['nombres']} {t['apellidos']}", f"«{t['titulo']}».", url_staff(t))
    elif "observado" in dictamenes:
        get_db().execute("UPDATE tramite_grado SET estado = 'observado' WHERE id = ?", [t["id"]])
        n = sum(len(i["observaciones"]) for i in hechos)
        _avisar_estudiante(t, "El tribunal envió observaciones", f"{n} observación(es). Responda cada una, corrija y reenvíe.")
    else:
        get_db().execute("UPDATE tramite_grado SET estado = 'favorable' WHERE id = ?", [t["id"]])
        _avisar_estudiante(t, "Dictamen favorable del tribunal", f"«{t['titulo']}».")
        que = "registrar la resolución" if t["tipo"] == "perfil" else "programar la defensa"
        _avisar_gestores(f"Dictamen favorable: {t['nombres']} {t['apellidos']}", f"Falta {que}.", url_staff(t))


def pendientes_de(uid: int) -> list[dict]:
    """Lo que el miembro del tribunal debe hacer: informes por enviar y notas de defensa."""
    res = []
    for t in de_miembro(uid):
        if t["estado"] == "en_revision" and not informe_de(t["id"], t["ronda"], uid):
            res.append({**t, "que": "Su informe", "cuando": t["plazo"]})
        elif t["estado"] == "favorable" and t["defensa_en"] and \
                next((m for m in tribunal(t["id"]) if m["usuario_id"] == uid), {}).get("nota_defensa") is None:
            res.append({**t, "que": "Su nota de defensa", "cuando": t["defensa_en"]})
    return res


def dias_para(plazo: str | None) -> int | None:
    if not plazo:
        return None
    p, hoy = date.fromisoformat(plazo), date.today()
    return habiles_entre(hoy, p) if p >= hoy else -habiles_entre(p, hoy)


# --- Recordatorios (mantenimiento periódico) ------------------------------------------------------------------------------

def recordar(hoy: date | None = None) -> int:
    """Avisa a los miembros con el informe pendiente 3 días hábiles antes del plazo y, al vencer, también a la Dirección.
    Una vez por ronda y persona. → cuántos avisos."""
    hoy = hoy or date.today()
    n = 0
    limite = (hoy + timedelta(days=10)).isoformat()
    for f in get_db().q("SELECT id FROM tramite_grado WHERE estado = 'en_revision' AND plazo IS NOT NULL AND plazo <= ?", [limite]):
        t = obtener(f["id"])
        plazo = date.fromisoformat(t["plazo"])
        tipo = "vencido" if hoy > plazo else "por_vencer" if habiles_entre(hoy, plazo) <= DIAS_AVISO else None
        if not tipo:
            continue
        pendientes = [m for m in tribunal(t["id"]) if not informe_de(t["id"], t["ronda"], m["usuario_id"])]
        for m in pendientes:
            if get_db().q("SELECT 1 FROM recordatorio_grado WHERE tramite_id = ? AND ronda = ? AND usuario_id = ? AND tipo = ?",
                          [t["id"], t["ronda"], m["usuario_id"], tipo]):
                continue
            get_db().t.recordatorio_grado.insert(tramite_id=t["id"], ronda=t["ronda"], usuario_id=m["usuario_id"], tipo=tipo)
            asunto = ("Venció el plazo de su informe" if tipo == "vencido" else "Su informe vence pronto") + f": {t['nombres']} {t['apellidos']}"
            notificaciones.avisar(usuarios.por_id(m["usuario_id"]), asunto, f"«{t['titulo']}» · plazo {formato.fecha(t['plazo'])}.", url_staff(t))
            n += 1
            if tipo == "vencido":
                _avisar_gestores(f"Informe vencido: {m['nombres']} {m['apellidos']}",
                                 f"Tribunal de {t['nombres']} {t['apellidos']} («{t['titulo']}»), plazo {t['plazo']}.", url_staff(t))
    return n
