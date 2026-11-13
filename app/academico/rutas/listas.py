"""Lista de estudiantes por paralelo (PLAN §68, etapa 4): la ven los docentes de ese paralelo; la Dirección de Carrera y la
Coordinación (`gestionar_oferta`) cargan la copia temporal mientras no exista la API del sistema de notas."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Option, P, Response, Select, Span, UploadFile
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import gestiones, listas
from app.comun import formato, permisos
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
BASE = "/docencia/listas"
ROLES = {"titular": "Titular", "auxiliar": "Auxiliar"}


def _puede_cargar(auth) -> bool:
    return permisos.puede(auth, "gestionar_oferta")


@rt(BASE)
def get(auth):
    filas = [fh.Tr(fh.Td(c["gestion"], cls="text-sm whitespace-nowrap"),
                   fh.Td(Span(c["sigla"], cls="font-mono text-sm"), Span(f" {c['nombre']}", cls="text-sm")),
                   fh.Td(c["paralelo"], cls="text-sm"), fh.Td(ROLES[c["rol"]], cls="text-sm"),
                   fh.Td(f"{c['cargados']} estudiantes" if not listas.usa_api() and c["cargados"]
                         else ("Se consulta a Kardex" if listas.usa_api() else insignia("Sin cargar", "ambar", icono="circle-alert")),
                         cls="text-sm"),
                   fh.Td(A("Ver la lista", href=f"{BASE}/{c['oferta_id']}", cls="text-sm text-primary hover:underline")))
            for c in listas.cursos_de(auth["id"])]
    return pagina(
        "Listas de mis cursos", H2("Listas de mis cursos"),
        P("Los estudiantes inscritos en los paralelos que usted dicta, tal como los registra el sistema de notas (Kardex). Solo los "
          "docentes de cada paralelo ven su lista, y cada consulta queda registrada. TAU no guarda notas ni asistencia.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Gestión"), fh.Th("Materia"), fh.Th("Paralelo"), fh.Th("Rol"), fh.Th("Lista"),
                                         fh.Th(""))), fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"),
                 cls="overflow-x-auto")) if filas
        else Card(P("No dicta ningún paralelo en una gestión vigente o en planificación.", cls="text-sm")),
        P(A("Cargar listas", href=f"{BASE}/cargar", cls="text-sm text-primary hover:underline"), cls="mt-4")
        if _puede_cargar(auth) and not listas.usa_api() else "", usuario=auth, seccion="docencia")


def _pagina_carga(auth, g, lista, resultado=None, errores=()):
    abiertas = [x for x in gestiones.listar() if x["estado"] != "concluida"][::-1]
    selector = Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in abiertas],
                      name="gestion", aria_label="Gestión", cls="uk-select w-40", data_navegar=f"{BASE}/cargar?gestion=")
    filas = [fh.Tr(fh.Td(Span(c["sigla"], cls="font-mono text-sm"), Span(f" {c['nombre']}", cls="text-sm")),
                   fh.Td(c["paralelo"], cls="text-sm"), fh.Td(str(c["inscritos"]) if c["inscritos"] is not None else "—", cls="text-sm"),
                   fh.Td(str(c["cargados"]) if c["cargados"] else insignia("Sin cargar", "ambar"), cls="text-sm")) for c in lista]
    return pagina(
        "Cargar listas de cursos",
        A(UkIcon("arrow-left", height=14, width=14), "Listas de mis cursos", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(H2("Cargar listas de cursos"),
                P("Mientras el sistema de notas no ofrezca su API, cargue aquí el CSV que entrega Kardex: una fila por estudiante con "
                  "sigla, paralelo, RU, apellidos, nombres y, si quiere, correo. La lista de cada paralelo del archivo reemplaza la "
                  "anterior y es una copia temporal: se retira al concluir la gestión.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        mensaje_error(*errores),
        Card(P(f"Se cargaron {resultado['estudiantes']} estudiantes en {resultado['paralelos']} paralelo(s)."
               + (f" No están en la oferta y se omitieron: {', '.join(resultado['omitidos'])}." if resultado["omitidos"] else ""),
               cls="text-sm"), cls="mb-4") if resultado else "",
        Card(fh.Form(Input(type="hidden", name="gestion", value=str(g["id"])),
                     Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
                     Div(Button(UkIcon("upload", height=14, width=14), "Cargar", type="submit", cls=ButtonT.primary),
                         A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/plantilla",
                           cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
                         cls="flex flex-wrap items-center gap-4"),
                     method="post", action=f"{BASE}/cargar", enctype="multipart/form-data", cls="space-y-3"), cls="mb-4"),
        Card(H3(f"Paralelos de {gestiones.codigo(g)}", cls="text-base font-semibold"),
             Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Materia"), fh.Th("Paralelo"), fh.Th("Inscritos (oferta)"), fh.Th("Cargados"))),
                          fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto mt-2")) if filas
        else Card(P("Esta gestión aún no tiene oferta.", cls="text-sm")), usuario=auth, seccion="docencia")


def _gestion_de_carga(gestion: str):
    abiertas = [x for x in gestiones.listar() if x["estado"] != "concluida"][::-1]
    return next((x for x in abiertas if str(x["id"]) == gestion), None) or (abiertas[0] if abiertas else None)


@rt(f"{BASE}/cargar")
def get(auth, gestion: str = ""):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    g = _gestion_de_carga(gestion)
    if not g:
        return pagina("Cargar listas de cursos", Card(P("No hay gestiones sin concluir.", cls="text-sm")), usuario=auth,
                      seccion="docencia")
    return _pagina_carga(auth, g, listas.cargadas(g["id"]),
                         errores=["Las listas se consultan al sistema de notas: no hace falta cargarlas."] if listas.usa_api() else ())


@rt(f"{BASE}/cargar")
async def post(auth, gestion: str = "", archivo: UploadFile = None):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else None
    if not g:
        return Response("No encontrado", status_code=404)
    if archivo is None or not archivo.filename:
        return _pagina_carga(auth, g, listas.cargadas(g["id"]), errores=["Seleccione un archivo."])
    contenido = await archivo.read(1024 * 1024 * 5 + 1)
    resumen, errores = listas.cargar(contenido, g["id"], auth["id"])
    return _pagina_carga(auth, g, listas.cargadas(g["id"]), resumen or None, errores)


@rt(f"{BASE}/plantilla")
def get(auth):
    if not _puede_cargar(auth):
        return Response("No autorizado", status_code=403)
    return Response(listas.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-lista-de-curso.csv"'})


@rt(f"{BASE}/{{oid}}")
def get(auth, oid: int):
    r = listas.consultar(auth["id"], oid)
    if r is None:
        return Response("No autorizado", status_code=403)
    from app.academico import oferta
    o = oferta.obtener(oid)
    g = gestiones.obtener(o["gestion_id"])
    filas = [fh.Tr(fh.Td(str(n), cls="text-sm tabular-nums"), fh.Td(e["ru"], cls="text-sm font-mono"),
                   fh.Td(f"{e['apellidos']}, {e['nombres']}", cls="text-sm"), fh.Td(e["correo"] or "—", cls="text-sm"))
            for n, e in enumerate(r["estudiantes"], start=1)]
    return pagina(
        f"Lista de {o['sigla']} {o['paralelo']}",
        A(UkIcon("arrow-left", height=14, width=14), "Listas de mis cursos", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{o['sigla']} · {o['nombre']} · paralelo {o['paralelo']}"),
        P(f"{gestiones.codigo(g)} · {len(r['estudiantes'])} estudiantes" + (
            f" · copia cargada el {formato.fecha_hora(r['cargada_en'])}" if r["cargada_en"] else " · consultada ahora al sistema de notas"),
          cls=(TextPresets.muted_sm, "mb-4")),
        mensaje_error(r["error"]) if r["error"] else "",
        Card(Div(fh.Table(fh.Thead(fh.Tr(fh.Th("N.º"), fh.Th("RU"), fh.Th("Estudiante"), fh.Th("Correo"))), fh.Tbody(*filas),
                          cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")) if filas
        else Card(P("Aún no hay lista para este paralelo." if not r["error"] else "", cls="text-sm")),
        P("Información reservada a los docentes del paralelo: no la comparta ni la publique. Su consulta queda registrada.",
          cls=(TextPresets.muted_sm, "mt-4")), usuario=auth, seccion="docencia")
