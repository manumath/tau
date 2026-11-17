"""Lo que los módulos de servicios aportan al menú (PLAN §73, etapa 2)."""
from app.comun import estudiantes, permisos
from app.comun.calendario import evento, pendiente
from app.comun.certificados import cert
from app.comun.db import get_db
from app.comun.menu import item
from app.servicios import auxiliaturas, comunicados, grado, oportunidades, recursos, temas

G = "Servicios"


def menu_comunicados(auth):
    return [(G, 10, item("comunicados", "Comunicados y eventos", "/servicios/comunicados", "megaphone"))]


def _miembro_auxiliatura(uid: int) -> bool:
    return bool(get_db().q("""SELECT 1 FROM tribunal_auxiliatura t JOIN item_auxiliatura i ON i.id = t.item_id
                              JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                              WHERE t.usuario_id = ? AND c.estado = 'publicada' LIMIT 1""", [uid]))


def menu_auxiliaturas(auth):
    if not (permisos.puede(auth, "gestionar_auxiliaturas") or permisos.puede(auth, "gestionar_auxiliaturas_investigacion")
            or _miembro_auxiliatura(auth["id"])):
        return []
    return [(G, 20, item("auxiliaturas", "Auxiliaturas", "/servicios/auxiliaturas", "badge-check"))]


def _en_grado(uid: int) -> bool:
    """¿Es tutor o tribunal de algún trámite de grado?"""
    return bool(get_db().q("""SELECT 1 FROM tramite_grado WHERE tutor_id = ? AND estado <> 'borrador'
                              UNION SELECT 1 FROM tribunal_grado WHERE usuario_id = ? LIMIT 1""", [uid, uid]))


def menu_grado(auth):
    items = []
    if temas.puede_publicar(auth):
        items.append((G, 50, item("temas", "Temas de grado", "/servicios/temas", "lightbulb")))
    if permisos.puede(auth, "gestionar_grado") or _en_grado(auth["id"]):
        items.append((G, 70, item("grado", "Proyectos de grado", "/servicios/grado", "scroll")))
    return items


def menu_oportunidades(auth):
    items = []
    if recursos.puede_publicar(auth):
        items.append((G, 40, item("recursos", "Biblioteca y recursos", "/servicios/recursos", "library-big")))
    if oportunidades.puede_publicar(auth):
        items.append((G, 60, item("oportunidades", "Oportunidades", "/servicios/oportunidades", "handshake")))
    return items


# El portal del estudiante (PLAN §67).
def portal_comunicados(auth):
    return [(G, 10, item("comunicados", "Comunicados", "/estudiante/comunicados", "megaphone"))]


def portal_auxiliaturas(auth):
    return [(G, 30, item("auxiliaturas", "Auxiliaturas", "/estudiante/auxiliaturas", "badge-check"))]


def portal_oportunidades(auth):
    return [("Mi carrera", 50, item("biblioteca", "Biblioteca", "/estudiante/biblioteca", "library-big")),
            (G, 40, item("oportunidades", "Oportunidades", "/estudiante/oportunidades", "briefcase"))]


def portal_grado(auth):
    return [(G, 50, item("temas", "Temas de grado", "/estudiante/temas", "lightbulb")),
            (G, 70, item("grado", "Grado", "/estudiante/grado", "scroll"))]


# --- Pendientes y fechas (PLAN §73, etapa 3) -------------------------------------------------------------------------

def _usuario_de(externo_id: int) -> int:
    usuario = estudiantes.usuario_de(externo_id)
    return usuario["id"] if usuario else 0


def pendientes_grado(ambito, uid, hoy):
    """El docente: su visto bueno como tutor, sus informes como tribunal y quien pide su tutoría para un tema. El
    estudiante: las observaciones del tribunal por responder y el trámite que le devolvió su tutor."""
    if ambito == "estudiante":
        res = []
        for t in grado.de_estudiante(uid):
            href = f"/estudiante/grado/{t['id']}"
            if t["estado"] == "observado":
                res.append(pendiente("grado", "Responda las observaciones del tribunal "
                                              f"({len(grado.observaciones_pendientes(t))} pendientes)",
                                     f"{grado.TIPOS[t['tipo']]} «{t['titulo']}»", None, href))
            elif t["estado"] == "borrador" and t["comentario_tutor"]:
                res.append(pendiente("grado", "Su tutor le devolvió el trámite", t["comentario_tutor"][:120], None, href))
        return res
    if ambito != "docente":
        return []
    res = [pendiente("grado", f"Su visto bueno: {t['nombres']} {t['apellidos']}", f"{grado.TIPOS[t['tipo']]} «{t['titulo']}»",
                     None, grado.url_staff(t)) for t in grado.de_tutor(uid) if t["estado"] == "con_tutor"]
    res += [pendiente("grado", f"{t['que']}: {t['nombres']} {t['apellidos']}", f"{grado.TIPOS[t['tipo']]} «{t['titulo']}»",
                      t["cuando"], grado.url_staff(t)) for t in grado.pendientes_de(uid)]
    res += [pendiente("tema", f"Pide su tutoría: {s['nombres']} {s['apellidos']}", f"Tema «{s['titulo']}»", None,
                      f"/servicios/temas/{s['tema_id']}")
            for s in get_db().q(
                """SELECT s.id, t.id AS tema_id, t.titulo, pe.nombres, pe.apellidos FROM solicitud_tema s
                   JOIN tema_grado t ON t.id = s.tema_id JOIN persona_externa pe ON pe.id = s.externo_id
                   WHERE t.docente_id = ? AND s.estado = 'pendiente' ORDER BY s.id""", [uid])]
    return res


def eventos_grado(ambito, quien, desde, hasta):
    res = []
    if ambito == "docente":
        vistos = set()
        for t in [*grado.de_tutor(quien), *grado.de_miembro(quien)]:
            if t["id"] in vistos:
                continue
            vistos.add(t["id"])
            href, persona = grado.url_staff(t), f"{t['nombres']} {t['apellidos']}"
            if t["estado"] == "en_revision":
                res.append(evento(t["plazo"], f"Vence la revisión del tribunal: {persona}", "grado", t["titulo"], href))
            res.append(evento(t.get("reunion_en"), f"Reunión con el tribunal: {persona}", "grado", t["titulo"], href))
            res.append(evento(t.get("defensa_en"), f"Defensa: {persona}", "grado", t["titulo"], href))
    elif ambito == "estudiante":
        for t in grado.de_estudiante(quien):
            tipo, href = grado.TIPOS[t["tipo"]], f"/estudiante/grado/{t['id']}"
            if t["estado"] == "en_revision":
                res.append(evento(t["plazo"], f"Vence la revisión del tribunal ({tipo.lower()})", "grado", t["titulo"], href))
            res.append(evento(t.get("reunion_en"), f"Reunión con el tribunal: {t['titulo']}", "grado", "", href))
            res.append(evento(t.get("defensa_en"), f"Defensa: {t['titulo']}", "grado", "", href))
    return res


def pendientes_auxiliaturas(ambito, uid, hoy):
    if ambito == "estudiante":     # su postulación por enviar y, si integra una comisión, lo que debe calificar
        res = [pendiente("auxiliatura", f"Complete y envíe su postulación: {p['item_titulo']}",
                         f"La recepción cierra el {auxiliaturas.hoy_texto(p['cierre'])}", None, f"/estudiante/auxiliaturas/{p['id']}")
               for p in auxiliaturas.de_estudiante(uid) if p["estado"] == "borrador" and auxiliaturas.abierta(p)]
        res += [pendiente("auxiliatura", f"Califique como tribunal: {i['titulo']}", f"{i['por_calificar']} postulante(s) por calificar",
                          None, f"/estudiante/tribunal/{i['id']}")
                for i in auxiliaturas.items_de_miembro(_usuario_de(uid)) if i["por_calificar"]]
        return res
    if ambito != "docente":
        return []
    return [pendiente("auxiliatura", f"Calificar {i['por_calificar']} postulante(s)", i["convocatoria"], None,
                      auxiliaturas.url_miembro(uid, i["id"])) for i in auxiliaturas.items_de_miembro(uid) if i["por_calificar"]]


def eventos_auxiliaturas(ambito, quien, desde, hasta):
    if ambito != "estudiante":
        return []
    res = []
    for c in get_db().q("SELECT * FROM convocatoria_auxiliatura WHERE estado = 'publicada'"):
        res.append(evento(c["cierre"], f"Cierra la recepción: {c['titulo']}", "auxiliatura", c["lugar"] or "",
                          "/estudiante/auxiliaturas"))
        res.append(evento(c["examen"], f"Examen escrito: {c['titulo']}", "auxiliatura", c["lugar"] or "",
                          "/estudiante/auxiliaturas"))
    return res


def pendientes_comunicados(ambito, quien, hoy):
    """El estudiante: los eventos a que lo convocan y aún no confirmó."""
    if ambito != "estudiante":
        return []
    return [pendiente("evento", f"Confirme su asistencia: {c['titulo']}", comunicados.fecha_hora(c["inicio"]), None,
                      f"/estudiante/comunicados/{c['id']}") for c in comunicados.por_confirmar(_usuario_de(quien))]


def eventos_comunicados(ambito, quien, desde, hasta):
    """Los eventos publicados a que convocan a la persona (o a todos)."""
    uid = _usuario_de(quien) if ambito == "estudiante" else quien
    filas = get_db().q(
        """SELECT c.* FROM comunicado c WHERE c.tipo = 'evento' AND c.estado = 'publicado' AND c.inicio IS NOT NULL
           AND (c.para_todos = 1 OR EXISTS (SELECT 1 FROM comunicado_destinatario d WHERE d.comunicado_id = c.id
                                            AND d.usuario_id = ?))""", [uid])
    return [evento(c["inicio"], c["titulo"], "evento", c["lugar"] or "",
                   f"/estudiante/comunicados/{c['id']}" if ambito == "estudiante" else "/avisos") for c in filas]


def eventos_oportunidades(ambito, quien, desde, hasta):
    if ambito != "estudiante":
        return []
    return [evento(o["cierre"], f"Cierra: {o['titulo']}", "oportunidad", oportunidades.TIPOS[o["tipo"]],
                   f"/estudiante/oportunidades/{o['id']}") for o in oportunidades.para_estudiante(quien)]


# --- Lo que queda en curso al apagar un módulo -------------------------------------------------------------------------

def _contar(sql: str) -> int:
    return get_db().q(sql)[0]["n"]


def en_curso_auxiliaturas():
    n = _contar("SELECT COUNT(*) n FROM convocatoria_auxiliatura WHERE estado = 'publicada'")
    return [f"{n} convocatoria(s) a auxiliaturas publicada(s)"] if n else []


def en_curso_grado():
    abiertos = ", ".join(f"'{e}'" for e in grado.ABIERTOS if e != "borrador")
    n = _contar(f"SELECT COUNT(*) n FROM tramite_grado WHERE estado IN ({abiertos})")
    return [f"{n} trámite(s) de grado en curso"] if n else []


def en_curso_oportunidades():
    n = _contar("SELECT COUNT(*) n FROM oportunidad WHERE estado = 'publicada'")
    return [f"{n} oportunidad(es) publicada(s)"] if n else []
MANTENIMIENTO_GRADO = [lambda: grado.recordar()]    # informes de tribunales de grado por vencer o vencidos


# --- Historial docente y certificados (PLAN §68, etapa 6, y §73) ---------------------------------------------------------

CONCLUIDOS = ("aprobado", "defendido", "rechazado", "reprobado")      # estados en que un trámite de grado terminó


def _tramites(uid: int, como: str) -> list[dict]:
    consulta = {"tutor": "SELECT t.id FROM tramite_grado t WHERE t.tutor_id = ? AND t.estado <> 'borrador'",
                "tribunal": "SELECT t.id FROM tramite_grado t JOIN tribunal_grado m ON m.tramite_id = t.id WHERE m.usuario_id = ?"}[como]
    return [grado.obtener(f["id"]) for f in get_db().q(consulta + " ORDER BY t.id DESC", [uid])]


def _fila_tramite(t):
    return {"texto": f"{grado.TIPOS[t['tipo']]} · {t['nombres']} {t['apellidos']}", "detalle": t["titulo"],
            "insignia": (grado.ESTADOS[t["estado"]], "verde" if t["estado"] in ("aprobado", "defendido") else "gris")}


def historial_grado(uid):
    tutor, tribunal = _tramites(uid, "tutor"), _tramites(uid, "tribunal")
    return [{"clave": "tutor", "orden": 10, "titulo": "Tutorías de grado", "vacio": "No tuteló proyectos de grado.",
             "datos": tutor, "filas": [_fila_tramite(t) for t in tutor]},
            {"clave": "tribunal", "orden": 20, "titulo": "Tribunales de grado", "vacio": "No integró tribunales de grado.",
             "datos": tribunal, "filas": [_fila_tramite(t) for t in tribunal]}]


def certificados_grado(uid):
    res = []
    for como, tipo, nombre, verbo in (("tutor", "tutor_grado", "Tutoría de proyecto de grado", "fue tutor(a) del"),
                                      ("tribunal", "tribunal_grado", "Tribunal de proyecto de grado", "integró el tribunal del")):
        for t in _tramites(uid, como):
            if t["estado"] in CONCLUIDOS:
                clase, estudiante, estado = grado.TIPOS[t["tipo"]], f"{t['nombres']} {t['apellidos']}", grado.ESTADOS[t["estado"]]
                res.append(cert(tipo, nombre, t["id"], uid, t["titulo"], f"{clase} de {estudiante}",
                                t.get("defensa_en") or t.get("enviado_en"),
                                f"{verbo} {clase.lower()} «{t['titulo']}» (estudiante: {estudiante}), con estado: {estado.lower()}",
                                estado=estado, clase=clase, estudiante=estudiante))
    return res


def titulares_grado():
    return {f["u"] for f in get_db().q("""SELECT tutor_id AS u FROM tramite_grado WHERE tutor_id IS NOT NULL
                                          UNION SELECT usuario_id FROM tribunal_grado""")}


def historial_auxiliaturas(uid):
    items = auxiliaturas.items_de_miembro(uid)
    return [{"clave": "auxiliaturas", "orden": 30, "titulo": "Tribunales de auxiliaturas",
             "vacio": "No integró tribunales de auxiliaturas.", "datos": items,
             "filas": [{"texto": f"{i['convocatoria']} · {i['mi_tipo']}"} for i in items]}]


def certificados_auxiliaturas(uid):
    filas = get_db().q(
        """SELECT i.id, c.titulo, c.modalidad, c.examen, c.publicacion, g.anio, g.tipo AS gtipo FROM tribunal_auxiliatura m
           JOIN item_auxiliatura i ON i.id = m.item_id JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
           JOIN gestion_academica g ON g.id = c.gestion_id WHERE m.usuario_id = ? AND c.estado = 'concluida'
           ORDER BY c.id DESC""", [uid])
    return [cert("tribunal_auxiliatura", "Tribunal de auxiliaturas", i["id"], uid, i["titulo"], f"Gestión {i['gtipo']}-{i['anio']}",
                 i["examen"] or i["publicacion"],
                 f"integró el tribunal de la convocatoria a auxiliaturas «{i['titulo']}» (gestión {i['gtipo']}-{i['anio']})")
            for i in filas]


def titulares_auxiliaturas():
    return {f["usuario_id"] for f in get_db().q("SELECT DISTINCT usuario_id FROM tribunal_auxiliatura")}

