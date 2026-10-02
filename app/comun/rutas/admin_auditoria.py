"""Registro de auditoría para la administración: quién hizo qué y cuándo.

Filtros por persona, tipo de acción y texto; la lista carga más filas sola al llegar al final
(hx-trigger="revealed"), sin paginación manual.
"""
import json

from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Option, P, Select, Span, Tbody, Td, Thead, Tr
from monsterui.all import H2, Card, Input, Table, TextPresets, Th

from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import fecha_local, url_filtrada
from app.comun.db import get_db, sin_tildes

rt = APIRouter()
POR_PAGINA = 50
ID_TBODY = "filas-auditoria"

ACCIONES = {
    "login": "Ingreso", "cambio_password": "Cambio de contraseña",
    "solicitar_recuperacion": "Pidió recuperar contraseña", "definir_password_enlace": "Definió contraseña por enlace",
    "crear_usuario": "Creó cuenta", "activar_usuario": "Activó cuenta", "desactivar_usuario": "Desactivó cuenta",
    "restablecer_password": "Restableció contraseña", "desbloquear_usuario": "Desbloqueó cuenta",
    "importar_usuarios": "Importó cuentas desde CSV", "importar_bibtex": "Importó productos desde BibTeX",
    "editar_perfil": "Editó perfil", "perfil_publico": "Publicó su perfil", "perfil_privado": "Ocultó su perfil",
    "crear_producto": "Registró producto", "editar_producto": "Editó producto", "eliminar_producto": "Eliminó producto",
    "sumarse_autor": "Se sumó como autor(a)", "crear_actividad": "Registró actividad",
    "editar_actividad": "Editó actividad", "eliminar_actividad": "Eliminó actividad",
    "subir_adjunto": "Subió adjunto", "eliminar_adjunto": "Eliminó adjunto",
    "crear_proyecto": "Creó proyecto", "editar_proyecto": "Editó proyecto",
    "agregar_participante": "Agregó participante", "cambiar_rol": "Cambió rol en proyecto",
    "baja_participante": "Dio de baja a participante", "aprobar": "Aprobó propuesta",
    "rechazar": "Rechazó propuesta", "desvincular": "Desvinculó de proyecto",
}
# Entidad → ruta de su ficha, para enlazar el registro afectado.
FICHAS = {"producto": "/productos/{}", "actividad": "/actividades/{}", "proyecto": "/proyectos/{}",
          "investigador": "/investigadores/{}"}


def consultar(usuario: str = "", accion: str = "", q: str = "", desde: int = 0) -> list[dict]:
    filtros, params = [], {}
    if usuario.isdigit():
        filtros.append("a.usuario_id = :u")
        params["u"] = int(usuario)
    if accion:
        filtros.append("a.accion = :acc")
        params["acc"] = accion
    if q.strip():
        filtros.append("(sin_tildes(a.detalle) LIKE :q OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :q)")
        params["q"] = f"%{sin_tildes(q.strip())}%"
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return get_db().q(
        f"""SELECT a.*, u.nombres, u.apellidos FROM auditoria a LEFT JOIN usuario u ON u.id = a.usuario_id
            {where} ORDER BY a.id DESC LIMIT {POR_PAGINA + 1} OFFSET {int(desde)}""", params)


def filas(usuario, accion, q, desde):
    registros = consultar(usuario, accion, q, desde)
    hay_mas = len(registros) > POR_PAGINA
    res = []
    for i, r in enumerate(registros[:POR_PAGINA]):
        ficha = FICHAS.get(r["entidad"])
        afectado = A(f"{r['entidad']} #{r['entidad_id']}", href=ficha.format(r["entidad_id"]),
                     cls="text-primary hover:underline") if ficha and r["entidad_id"] else \
            Span(f"{r['entidad'] or ''} {('#' + str(r['entidad_id'])) if r['entidad_id'] else ''}")
        extra = {}
        if hay_mas and i == POR_PAGINA - 1:
            # Al hacerse visible la última fila se piden las siguientes (scroll infinito).
            extra = dict(hx_get="/admin/auditoria/filas", hx_trigger="revealed", hx_swap="afterend",
                         hx_vals=json.dumps({"usuario": usuario, "accion": accion, "q": q,
                                             "desde": desde + POR_PAGINA}))
        res.append(Tr(Td(fecha_local(r["fecha"]), cls=(TextPresets.muted_sm, "whitespace-nowrap")),
                      Td(f"{r['nombres']} {r['apellidos']}" if r["nombres"] else "—"),
                      Td(ACCIONES.get(r["accion"], r["accion"])), Td(afectado, cls="text-sm"),
                      Td(r["detalle"] or "", cls=(TextPresets.muted_sm, "break-all")), **extra))
    if not res and desde == 0:
        res.append(Tr(Td("Sin registros.", colspan=5, cls=(TextPresets.muted_sm, "text-center py-6"))))
    return res


@rt("/admin/auditoria")
def get(auth, usuario: str = "", accion: str = "", q: str = ""):
    personas = get_db().q("""SELECT DISTINCT u.id, u.nombres, u.apellidos FROM auditoria a
                             JOIN usuario u ON u.id = a.usuario_id ORDER BY sin_tildes(u.apellidos)""")
    acciones = [r["accion"] for r in get_db().q("SELECT DISTINCT accion FROM auditoria")]
    filtros = Div(
        Select(Option("Todas las personas", value=""),
               *[Option(f"{p['apellidos']}, {p['nombres']}", value=str(p["id"]), selected=str(p["id"]) == usuario)
                 for p in personas], name="usuario", cls="uk-select w-56", aria_label="Persona"),
        Select(Option("Todas las acciones", value=""),
               *[Option(ACCIONES.get(a, a), value=a, selected=a == accion)
                 for a in sorted(acciones, key=lambda a: ACCIONES.get(a, a))],
               name="accion", cls="uk-select w-60", aria_label="Acción"),
        Input(type="search", name="q", value=q, placeholder="Buscar en el detalle…", cls="max-w-xs",
              aria_label="Buscar"),
        id="filtros-auditoria", hx_get="/admin/auditoria/tabla", hx_target=f"#{ID_TBODY}", hx_swap="outerHTML",
        hx_trigger="change, input delay:300ms from:input[name=q], search", hx_include="this",
        cls="flex flex-wrap gap-3 mb-4")
    return pagina(
        "Auditoría",
        Div(H2("Auditoría"), P("Registro de acciones relevantes en el sistema, de la más reciente a la más antigua.",
                               cls=TextPresets.muted_sm), cls="mb-6 space-y-1"),
        filtros,
        Card(Div(Table(Thead(Tr(Th("Fecha"), Th("Persona"), Th("Acción"), Th("Registro"), Th("Detalle"))),
                       Tbody(*filas(usuario, accion, q, 0), id=ID_TBODY),
                       cls="uk-table-divider uk-table-small"), cls="overflow-x-auto")),
        usuario=auth, seccion="auditoria")


@rt("/admin/auditoria/tabla")
def get(usuario: str = "", accion: str = "", q: str = ""):
    return (Tbody(*filas(usuario, accion, q, 0), id=ID_TBODY),
            HtmxResponseHeaders(replace_url=url_filtrada("/admin/auditoria", usuario=usuario, accion=accion, q=q)))


@rt("/admin/auditoria/filas")
def get(usuario: str = "", accion: str = "", q: str = "", desde: int = 0):
    # Filas sueltas: htmx 2 las inserta con hx-swap="afterend" dentro del <tbody>.
    return tuple(filas(usuario, accion, q, desde))
