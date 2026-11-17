"""Oportunidades para estudiantes y egresados (PLAN §67, etapa 4): becas, movilidad, pasantías, ayudantías de investigación y
empleo. Las publica la Dirección de Carrera o la Coordinación académica (el empleo, a nombre de un empleador registrado; sin
cuentas nuevas) y, las ayudantías, el responsable del proyecto. El estudiante (o el egresado, si es empleo) postula y quien
publica decide; la persona recibe un aviso."""
from datetime import date

from app.comun import estudiantes, notificaciones, permisos, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion

TIPOS = {"beca": "Beca", "movilidad": "Movilidad", "pasantia": "Pasantía", "ayudantia": "Ayudantía de investigación",
         "empleo": "Empleo"}
PARA = {"estudiantes": "Estudiantes", "egresados": "Egresados", "todos": "Estudiantes y egresados"}
ESTADOS = {"borrador": "Borrador", "publicada": "Publicada", "cerrada": "Cerrada"}
ESTADOS_POSTULACION = {"postulada": "Postulada", "preseleccionada": "Preseleccionada", "seleccionada": "Seleccionada",
                       "no_seleccionada": "No seleccionada", "retirada": "Retirada"}
DECISIONES = ("preseleccionada", "seleccionada", "no_seleccionada")
PARA_POR_OMISION = {"empleo": "egresados"}


def _es_responsable(auth: dict, proyecto_id: int | None) -> bool:
    from app.investigacion import proyectos
    return bool(proyecto_id) and proyectos.puede_gestionar(proyecto_id, auth)


def proyectos_que_dirige(auth: dict) -> list[dict]:
    """Proyectos de los que la persona es responsable vigente (para publicar ayudantías de investigación)."""
    from app.investigacion import proyectos
    return [p for p in proyectos.de_investigador(auth["id"]) if p["vigente"] and p["estado"] != "finalizado"
            and proyectos.puede_gestionar(p["id"], auth)]


def puede_publicar(auth: dict | None) -> bool:
    """¿Aparece «Oportunidades» en su menú? La Dirección y la Coordinación, y quien dirige un proyecto."""
    return bool(auth) and (permisos.puede(auth, "gestionar_oportunidades") or bool(proyectos_que_dirige(auth)))


def puede_gestionar(auth: dict | None, o: dict) -> bool:
    """Editar, publicar, cerrar y decidir: la Dirección y la Coordinación, o el responsable del proyecto de una ayudantía."""
    if not auth:
        return False
    if permisos.puede(auth, "gestionar_oportunidades"):
        return True
    return o["tipo"] == "ayudantia" and _es_responsable(auth, o["proyecto_id"])


def obtener(oid: int) -> dict | None:
    f = get_db().q("""SELECT o.*, p.nombre AS proyecto, e.organizacion AS empleador FROM oportunidad o
                      LEFT JOIN proyecto p ON p.id = o.proyecto_id LEFT JOIN empleador e ON e.id = o.empleador_id
                      WHERE o.id = ?""", [oid])
    return f[0] if f else None


def listar(auth: dict) -> list[dict]:
    filas = get_db().q(
        """SELECT o.*, (SELECT COUNT(*) FROM postulacion_oportunidad x WHERE x.oportunidad_id = o.id AND x.estado <> 'retirada')
                       AS n_postulaciones FROM oportunidad o ORDER BY o.estado = 'cerrada', o.estado = 'borrador' DESC, o.id DESC""")
    return [o for o in filas if puede_gestionar(auth, o)]


def validar(d: dict, auth: dict) -> tuple[dict, list[str]]:
    errores = []
    tipo = d.get("tipo")
    if tipo not in TIPOS:
        errores.append("Elija el tipo de oportunidad.")
    titulo = (d.get("titulo") or "").strip()
    if not titulo or len(titulo) > 200:
        errores.append("El título es obligatorio (hasta 200 caracteres).")
    para = d.get("para") if d.get("para") in PARA else PARA_POR_OMISION.get(tipo, "estudiantes")
    cierre = (d.get("cierre") or "").strip()
    if cierre:
        try:
            date.fromisoformat(cierre)
        except ValueError:
            errores.append("La fecha de cierre no es válida.")
    enlace = (d.get("enlace") or "").strip()
    if enlace and not enlace.lower().startswith(("http://", "https://")):
        errores.append("El enlace debe empezar con http:// o https://.")
    plazas = (d.get("plazas") or "").strip()
    if plazas and (not plazas.isdigit() or int(plazas) < 1):
        errores.append("Las plazas son un número entero mayor que cero.")
    proyecto_id = int(d["proyecto_id"]) if str(d.get("proyecto_id") or "").isdigit() else None
    empleador_id = int(d["empleador_id"]) if str(d.get("empleador_id") or "").isdigit() else None
    if tipo == "ayudantia":
        if not proyecto_id:
            errores.append("Una ayudantía de investigación se publica sobre un proyecto.")
        elif not (permisos.puede(auth, "gestionar_oportunidades") or _es_responsable(auth, proyecto_id)):
            errores.append("Solo el responsable del proyecto (o la Dirección de Carrera) publica sus ayudantías.")
    elif tipo in TIPOS and not permisos.puede(auth, "gestionar_oportunidades"):
        errores.append("Este tipo de oportunidad lo publica la Dirección de Carrera o la Coordinación académica.")
    if tipo != "ayudantia":
        proyecto_id = None
    if tipo != "empleo":
        empleador_id = None
    for campo, limite in (("descripcion", 5000), ("requisitos", 3000), ("organizacion", 200), ("contacto", 300)):
        if len((d.get(campo) or "")) > limite:
            errores.append(f"«{campo}» admite hasta {limite} caracteres.")
    return ({"tipo": tipo, "titulo": titulo, "descripcion": (d.get("descripcion") or "").strip() or None,
             "requisitos": (d.get("requisitos") or "").strip() or None,
             "organizacion": (d.get("organizacion") or "").strip() or None, "empleador_id": empleador_id,
             "proyecto_id": proyecto_id, "plazas": int(plazas) if plazas.isdigit() else None, "cierre": cierre or None,
             "enlace": enlace or None, "contacto": (d.get("contacto") or "").strip() or None, "para": para}, errores)


def crear(d: dict, auth: dict) -> tuple[int | None, list[str]]:
    x, errores = validar(d, auth)
    if errores:
        return None, errores
    with transaccion():
        oid = get_db().t.oportunidad.insert(creada_por=auth["id"], **x)["id"]
        auditar(auth["id"], "crear_oportunidad", "oportunidad", oid, f"{TIPOS[x['tipo']]}: {x['titulo']}")
    return oid, []


def actualizar(oid: int, d: dict, auth: dict) -> list[str]:
    o = obtener(oid)
    if not o or not puede_gestionar(auth, o):
        return ["No puede editar esa oportunidad."]
    if o["estado"] == "cerrada":
        return ["Una oportunidad cerrada no se edita."]
    x, errores = validar({**d, "tipo": o["tipo"]}, auth)
    if errores:
        return errores
    get_db().t.oportunidad.update(id=oid, **x)
    auditar(auth["id"], "editar_oportunidad", "oportunidad", oid, x["titulo"])
    return []


def cambiar_estado(oid: int, estado: str, auth: dict) -> list[str]:
    o = obtener(oid)
    if not o or not puede_gestionar(auth, o):
        return ["No puede cambiar esa oportunidad."]
    if estado == "publicada" and o["estado"] == "borrador":
        if o["cierre"] and o["cierre"] < date.today().isoformat():
            return ["La fecha de cierre ya pasó: corríjala para publicar."]
        get_db().execute(f"UPDATE oportunidad SET estado = 'publicada', publicada_en = {AHORA} WHERE id = ?", [oid])
    elif estado == "cerrada" and o["estado"] == "publicada":
        get_db().execute("UPDATE oportunidad SET estado = 'cerrada' WHERE id = ?", [oid])
    else:
        return ["Ese cambio de estado no corresponde."]
    auditar(auth["id"], f"{'publicar' if estado == 'publicada' else 'cerrar'}_oportunidad", "oportunidad", oid, o["titulo"])
    return []


# --- Estudiantes y egresados ----------------------------------------------------------------------------------------------

def _audiencia(externo_id: int) -> tuple[str, ...]:
    return ("egresados", "todos") if estudiantes.es_egresado(externo_id) else ("estudiantes", "todos")


def abierta(o: dict) -> bool:
    return o["estado"] == "publicada" and (not o["cierre"] or o["cierre"] >= date.today().isoformat())


def para_estudiante(externo_id: int, tipo: str = "") -> list[dict]:
    """Oportunidades publicadas y abiertas que le corresponden (por ser estudiante o egresado)."""
    aud = _audiencia(externo_id)
    filas = get_db().q("SELECT * FROM oportunidad WHERE estado = 'publicada' ORDER BY cierre IS NULL, cierre, id DESC")
    return [o for o in filas if abierta(o) and o["para"] in aud and (not tipo or o["tipo"] == tipo)]


def visible_para(externo_id: int, o: dict) -> bool:
    """Una publicada que le corresponde, abierta o no (para ver el estado de su postulación)."""
    return o["estado"] != "borrador" and o["para"] in _audiencia(externo_id)


def postulacion_de(oid: int, externo_id: int) -> dict | None:
    f = get_db().q("SELECT * FROM postulacion_oportunidad WHERE oportunidad_id = ? AND externo_id = ?", [oid, externo_id])
    return f[0] if f else None


def mis_postulaciones(externo_id: int) -> list[dict]:
    return get_db().q("""SELECT x.*, o.titulo, o.tipo, o.cierre FROM postulacion_oportunidad x
                         JOIN oportunidad o ON o.id = x.oportunidad_id WHERE x.externo_id = ? ORDER BY x.id DESC""", [externo_id])


def postular(oid: int, externo_id: int, mensaje: str) -> list[str]:
    o = obtener(oid)
    if not o or not visible_para(externo_id, o):
        return ["Esa oportunidad no está disponible."]
    if not abierta(o):
        return ["La convocatoria ya cerró."]
    mensaje = (mensaje or "").strip()
    if len(mensaje) > 1000:
        return ["El mensaje admite hasta 1.000 caracteres."]
    previa = postulacion_de(oid, externo_id)
    if previa and previa["estado"] != "retirada":
        return ["Ya postuló a esta oportunidad."]
    with transaccion():
        if previa:
            get_db().execute("UPDATE postulacion_oportunidad SET estado = 'postulada', mensaje = ?, nota = NULL, "
                             "decidida_en = NULL, decidida_por = NULL WHERE id = ?", [mensaje or None, previa["id"]])
        else:
            get_db().t.postulacion_oportunidad.insert(oportunidad_id=oid, externo_id=externo_id, mensaje=mensaje or None)
        p = get_db().q("SELECT nombres, apellidos FROM persona_externa WHERE id = ?", [externo_id])[0]
        notificaciones.avisar(usuarios.por_id(o["creada_por"]), f"Postulación: {o['titulo']}",
                              f"{p['nombres']} {p['apellidos']} postuló.", f"/servicios/oportunidades/{oid}")
    return []


def retirar(oid: int, externo_id: int) -> list[str]:
    p = postulacion_de(oid, externo_id)
    if not p or p["estado"] not in ("postulada", "preseleccionada"):
        return ["No hay una postulación para retirar."]
    get_db().execute("UPDATE postulacion_oportunidad SET estado = 'retirada' WHERE id = ?", [p["id"]])
    return []


# --- Quien publica: postulaciones y decisión ---------------------------------------------------------------------------------

def postulaciones(oid: int) -> list[dict]:
    return get_db().q(
        """SELECT x.*, pe.nombres, pe.apellidos, pe.email, es.registro_universitario FROM postulacion_oportunidad x
           JOIN persona_externa pe ON pe.id = x.externo_id
           LEFT JOIN estudiante es ON es.id = (SELECT MAX(id) FROM estudiante WHERE externo_id = pe.id)
           WHERE x.oportunidad_id = ? AND x.estado <> 'retirada' ORDER BY x.id""", [oid])


def decidir(pid: int, estado: str, nota: str, auth: dict) -> list[str]:
    f = get_db().q("SELECT * FROM postulacion_oportunidad WHERE id = ?", [pid])
    o = obtener(f[0]["oportunidad_id"]) if f else None
    if not f or not o or not puede_gestionar(auth, o):
        return ["No puede decidir sobre esa postulación."]
    if estado not in DECISIONES or f[0]["estado"] == "retirada":
        return ["Elija una decisión."]
    nota = (nota or "").strip()[:500]
    with transaccion():
        get_db().execute(f"UPDATE postulacion_oportunidad SET estado = ?, nota = ?, decidida_en = {AHORA}, decidida_por = ? "
                         "WHERE id = ?", [estado, nota or None, auth["id"], pid])
        notificaciones.avisar(estudiantes.usuario_de(f[0]["externo_id"]), f"{ESTADOS_POSTULACION[estado]}: {o['titulo']}",
                              nota or f"Su postulación quedó «{ESTADOS_POSTULACION[estado].lower()}».", "/estudiante/oportunidades")
        auditar(auth["id"], "decidir_postulacion_oportunidad", "oportunidad", o["id"], f"{o['titulo']}: {estado}")
    return []
