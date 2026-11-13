"""Biblioteca y recursos (PLAN §67, etapa 10): apuntes, guías, exámenes pasados, libros y enlaces que suben los docentes con vínculo
con la Carrera y consultan los estudiantes, por asignatura. El autor edita y retira lo suyo; la Dirección de Carrera y la
Coordinación académica retiran cualquiera. Los archivos son adjuntos del sistema (PDF, PNG o JPG)."""
from datetime import date

from app.comun import permisos
from app.comun.db import AHORA, auditar, get_db, sin_tildes, transaccion
from app.investigacion import adjuntos
from app.servicios import grado

TIPOS = {"apunte": "Apuntes", "guia": "Guía de ejercicios", "examen": "Examen pasado", "libro": "Libro o texto",
         "enlace": "Enlace", "otro": "Otro"}


def puede_publicar(auth: dict | None) -> bool:
    """Docentes con vínculo vigente con la Carrera y quienes gestionan los recursos."""
    return bool(auth) and (auth["id"] in {u["id"] for u in grado.tutores()} or permisos.puede(auth, "gestionar_recursos"))


def puede_gestionar(auth: dict | None, r: dict) -> bool:
    return bool(auth) and (r["autor_id"] == auth["id"] or permisos.puede(auth, "gestionar_recursos"))


def asignaturas_de(rid: int) -> list[dict]:
    return get_db().q("""SELECT a.id, a.sigla, a.nombre FROM recurso_asignatura ra JOIN asignatura a ON a.id = ra.asignatura_id
                         WHERE ra.recurso_id = ? ORDER BY a.sigla""", [rid])


def archivos(rid: int) -> list[dict]:
    return adjuntos.listar("recurso", rid)


def obtener(rid: int) -> dict | None:
    f = get_db().q("""SELECT r.*, u.nombres, u.apellidos FROM recurso r JOIN usuario u ON u.id = r.autor_id WHERE r.id = ?""", [rid])
    if not f:
        return None
    f[0]["asignaturas"] = asignaturas_de(rid)
    f[0]["archivos"] = archivos(rid)
    return f[0]


def validar(d: dict, asignaturas: list[str]) -> tuple[dict, list[int], list[str]]:
    errores = []
    if d.get("tipo") not in TIPOS:
        errores.append("Elija el tipo de recurso.")
    titulo = (d.get("titulo") or "").strip()
    if not titulo or len(titulo) > 200:
        errores.append("El título es obligatorio (hasta 200 caracteres).")
    enlace = (d.get("enlace") or "").strip()
    if enlace and not enlace.lower().startswith(("http://", "https://")):
        errores.append("El enlace debe empezar con http:// o https://.")
    anio = (d.get("anio") or "").strip()
    if anio and (not anio.isdigit() or not 1990 <= int(anio) <= date.today().year + 1):
        errores.append("El año no es válido.")
    if len(d.get("descripcion") or "") > 3000:
        errores.append("La descripción admite hasta 3.000 caracteres.")
    ids = sorted({int(a) for a in asignaturas if str(a).isdigit()})
    existentes = {f["id"] for f in get_db().q("SELECT id FROM asignatura")}
    if any(i not in existentes for i in ids):
        errores.append("Una asignatura no existe.")
    return ({"tipo": d.get("tipo"), "titulo": titulo, "descripcion": (d.get("descripcion") or "").strip() or None,
             "enlace": enlace or None, "anio": int(anio) if anio.isdigit() else None}, ids, errores)


def crear(d: dict, asignaturas: list[str], auth: dict, archivo: tuple[bytes, str] | None) -> tuple[int | None, list[str]]:
    """`archivo`: (contenido, nombre) opcional. Hace falta un archivo o un enlace."""
    if not puede_publicar(auth):
        return None, ["Solo los docentes con vínculo con la Carrera suben recursos."]
    x, ids, errores = validar(d, asignaturas)
    if not x["enlace"] and not archivo:
        errores.append("Suba un archivo (PDF, PNG o JPG) o escriba un enlace.")
    if errores:
        return None, errores
    if archivo and not adjuntos.detectar_tipo(archivo[0]):
        return None, ["Solo se admiten archivos PDF, PNG o JPG."]
    with transaccion():
        rid = get_db().t.recurso.insert(autor_id=auth["id"], **x)["id"]
        for i in ids:
            get_db().t.recurso_asignatura.insert(recurso_id=rid, asignatura_id=i)
        if archivo:
            adjuntos.guardar("recurso", rid, archivo[1], archivo[0], auth["id"])
        auditar(auth["id"], "crear_recurso", "recurso", rid, x["titulo"])
    return rid, []


def retirar(rid: int, auth: dict) -> list[str]:
    r = obtener(rid)
    if not r or not puede_gestionar(auth, r) or r["estado"] == "retirado":
        return ["No puede retirar ese recurso."]
    get_db().execute(f"UPDATE recurso SET estado = 'retirado', retirado_en = {AHORA}, retirado_por = ? WHERE id = ?", [auth["id"], rid])
    auditar(auth["id"], "retirar_recurso", "recurso", rid, r["titulo"])
    return []


def mis_recursos(auth: dict) -> list[dict]:
    filas = get_db().q("""SELECT r.*, u.nombres, u.apellidos FROM recurso r JOIN usuario u ON u.id = r.autor_id
                          ORDER BY r.estado = 'retirado', r.id DESC""")
    return [r for r in filas if puede_gestionar(auth, r)]


def buscar(texto: str = "", asignatura: str = "", tipo: str = "") -> list[dict]:
    """Recursos publicados para los estudiantes, con sus asignaturas."""
    filas = get_db().q("""SELECT r.*, u.nombres, u.apellidos FROM recurso r JOIN usuario u ON u.id = r.autor_id
                          WHERE r.estado = 'publicado' ORDER BY r.id DESC""")
    texto = (sin_tildes(texto) or "").lower().strip()
    res = []
    for r in filas:
        r["asignaturas"] = asignaturas_de(r["id"])
        if asignatura.isdigit() and int(asignatura) not in {a["id"] for a in r["asignaturas"]}:
            continue
        if tipo and r["tipo"] != tipo:
            continue
        if texto and texto not in (sin_tildes(f"{r['titulo']} {r['descripcion'] or ''} {r['apellidos']} "
                                    + " ".join(a["sigla"] + a["nombre"] for a in r["asignaturas"])) or "").lower():
            continue
        res.append(r)
    return res
