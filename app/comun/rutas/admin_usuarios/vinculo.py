"""Historial de vínculo con la Carrera: periodos, categoría, carga horaria contratada, cambios,
término y correcciones. Solo la Dirección de Carrera."""
from datetime import date

import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Option, P, Response, Select, Span, Template, Thead, Tr
from monsterui.all import Button, ButtonT, Form, FormLabel, LabelInput, Table, Tbody, Td, Th, TextPresets, UkIcon

from app.comun import usuarios, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal
from app.comun.db import auditar
from app.comun.rutas.admin_usuarios.comun import BASE, SIN_PERMISO, fila, gestiona_vinculos, opciones_categoria

rt = APIRouter()

AYUDA_TERMINO = ("Contratados, interinos e invitados: con fecha de término (periodo definido). Titular: sin "
                 "término; si se retira, renuncia o fallece, use «Terminar el vínculo».")


def _campos_periodo(d, con_nota=True, sufijo=""):
    return Div(
        Div(Div(FormLabel("Categoría"), Select(*opciones_categoria(d.get("categoria"), vacia="— Elija —"),
                                               name="categoria", cls="uk-select"), cls="space-y-1"),
            LabelInput("Desde", id=f"desde{sufijo}", name="desde", type="date", value=d.get("desde") or ""),
            LabelInput("Hasta", id=f"hasta{sufijo}", name="hasta", type="date", value=d.get("hasta") or ""),
            LabelInput("Nota", id=f"nota{sufijo}", name="nota", value=d.get("nota") or "",
                       placeholder="Resolución, contrato…") if con_nota else "",
            cls="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end"),
        P(AYUDA_TERMINO, cls=(TextPresets.muted_sm, "mt-1")))


def _campo_motivo(nombre="motivo", actual="", sufijo=""):
    return Div(FormLabel("Motivo", fr=f"{nombre}{sufijo}"),
               Select(Option("— Elija —", value=""),
                      *[Option(t, value=k, selected=k == actual) for k, t in vinculos.MOTIVOS_TERMINO.items()],
                      name=nombre, id=f"{nombre}{sufijo}", cls="uk-select", required=True),
               cls="space-y-1")


CAMPOS_CARGA = ("horas", *vinculos.ACTIVIDADES, *(f"detalle_{k}" for k in vinculos.CON_DETALLE))
EJEMPLO_DETALLE = {"investigacion": "Proyecto o línea", "extension": "Programa o servicio (se muestra en el perfil)",
                   "gestion": "Cargo o comisión (se muestra en el perfil)", "otras": "Descripción"}


def _datos_carga(v) -> dict:
    """Valores del formulario a partir de un periodo (o {} si no tiene carga)."""
    c = vinculos.carga_de(v)
    if not c:
        return {}
    return {"horas": str(c["horas"]), **{k: str(h) for k, h in c["actividades"].items()},
            **{f"detalle_{k}": t or "" for k, t in c["detalles"].items()}}


def _campos_carga(d, sufijo=""):
    """Carga contratada y su distribución por actividad (solo en el vínculo con la Carrera)."""
    def horas(nombre, etiqueta, opciones, vacia):
        actual = str(d.get(nombre) or "")
        return Div(FormLabel(etiqueta, fr=f"{nombre}{sufijo}"),
                   Select(Option(vacia, value=""),
                          *[Option(f"{h} h/mes", value=str(h), selected=str(h) == actual) for h in opciones],
                          name=nombre, id=f"{nombre}{sufijo}", cls="uk-select"), cls="space-y-1")
    return fh.Fieldset(
        fh.Legend("Carga horaria contratada", cls="text-sm font-medium px-1"),
        P("Total contratado y su distribución por actividad, en múltiplos de 32 h/mes; la distribución debe sumar "
          "el total (por ejemplo, 160 = docencia 64 + investigación 64 + extensión 32). Cada materia asignada como "
          "titular son 32 h/mes de docencia. Déjelo en blanco en periodos sin carga registrada.",
          cls=(TextPresets.muted_sm, "mb-2")),
        Div(horas("horas", "Total contratado", vinculos.CARGAS, "— Sin registrar —"),
            horas("docencia", "Docencia", vinculos.CARGAS, "0"),
            cls="grid grid-cols-2 sm:grid-cols-3 gap-3 items-end"),
        *[Div(horas(k, vinculos.ACTIVIDADES[k], vinculos.CARGAS, "0"),
              Div(LabelInput("Detalle", id=f"detalle_{k}{sufijo}", name=f"detalle_{k}",
                             value=d.get(f"detalle_{k}") or "", placeholder=EJEMPLO_DETALLE[k], maxlength=200),
                  cls="sm:col-span-2"),
              cls="grid grid-cols-2 sm:grid-cols-3 gap-3 items-end mt-3") for k in vinculos.CON_DETALLE],
        cls="rounded-md border border-border p-3 mt-3")


def modal_vinculo(u, auth, errores=(), editar=None, datos=None):
    """Historial de periodos de vínculo y acciones: cambio de categoría o de carga, término, periodo
    histórico, corrección. Solo para quien gestiona los vínculos (la Dirección de Carrera)."""
    uid = u["id"]
    datos = datos or {}
    periodos = vinculos.listar(uid)
    vig = vinculos.vigente(uid)
    filas = []
    for v in periodos:
        if editar == v["id"]:
            filas.append(Tr(Td(Form(
                _campos_periodo({"categoria": v["categoria"], "desde": v["fecha_inicio"], "hasta": v["fecha_fin"],
                                 "jornada": v["jornada_horas"], "nota": v["nota"], **datos}, sufijo=f"-{v["id"]}"),
                _campos_carga(datos or _datos_carga(v), sufijo=f"-{v["id"]}"),
                Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                           hx_get=f"{BASE}/{uid}/vinculo", hx_target=f"#{ID_MODAL}"),
                    Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                    cls="flex justify-end gap-2 mt-2"),
                hx_put=f"{BASE}/vinculo/{v["id"]}", hx_target=f"#{ID_MODAL}"), colspan=6)))
            continue
        filas.append(Tr(
            Td(vinculos.CATEGORIAS[v["categoria"]], Span(" · vigente", cls="text-xs text-green-700") if vig and v["id"] == vig["id"] else ""),
            Td(v["fecha_inicio"] or Span("sin registrar", cls="text-amber-700"), cls="whitespace-nowrap"),
            Td(v["fecha_fin"] or "—",
               Div(vinculos.MOTIVOS_TERMINO[v["motivo_termino"]], cls=TextPresets.muted_sm) if v["motivo_termino"] else "",
               cls="whitespace-nowrap"),
            Td(Span(vinculos.texto_carga(v) or "—", cls="text-sm")),
            Td(Span(v["nota"] or "—", cls="text-sm"),
               Span(f" · jornada según RR. HH.: {v['jornada_horas']} h/semana", cls=TextPresets.muted_sm)
               if v["jornada_horas"] else ""),
            Td(Div(Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Corregir",
                          title="Corregir", hx_get=f"{BASE}/vinculo/{v["id"]}/editar", hx_target=f"#{ID_MODAL}"),
                   Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon), aria_label="Eliminar",
                          title="Eliminar (solo para corregir errores)", hx_delete=f"{BASE}/vinculo/{v["id"]}",
                          hx_target=f"#{ID_MODAL}", hx_confirm="¿Eliminar este periodo? Úselo solo para corregir errores."),
                   cls="flex justify-end"))))
    tabla = Table(Thead(Tr(Th("Categoría"), Th("Desde"), Th("Hasta"), Th("Carga (h/mes)"), Th("Nota"), Th(""))),
                  Tbody(*filas) if filas else Tbody(Tr(Td("Sin periodos registrados.", colspan=6,
                                                          cls=TextPresets.muted_sm))),
                  cls="uk-table-divider uk-table-small")

    def accion(titulo, *campos, url, boton):
        return fh.Details(fh.Summary(titulo, cls="cursor-pointer text-sm font-medium text-primary"),
                          Form(*campos,
                               Div(Button(boton, type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                                   cls="flex justify-end mt-2"),
                               hx_post=url, hx_target=f"#{ID_MODAL}", cls="mt-2"),
                          cls="rounded-md border border-border p-3")
    acciones = [
        accion("Cambiar de categoría o de carga (ascenso, nuevo contrato)",
               P("Cierra el periodo vigente el día anterior y abre uno nuevo.", cls=TextPresets.muted_sm),
               _campos_periodo(datos or {"categoria": vig["categoria"]}, con_nota=False, sufijo="-cambio"),
               _campos_carga(datos or _datos_carga(vig), sufijo="-cambio"),
               url=f"{BASE}/{uid}/vinculo/cambio", boton="Registrar cambio") if vig else "",
        accion("Terminar el vínculo (fin de contrato, retiro, renuncia, despido, fallecimiento)",
               Div(LabelInput("Último día", id="fecha-termino", name="fecha", type="date",
                              value=date.today().isoformat()),
                   _campo_motivo(sufijo="-termino"), cls="grid grid-cols-2 gap-3 items-end"),
               url=f"{BASE}/{uid}/vinculo/termino", boton="Terminar") if vig else "",
        accion("Agregar un periodo (histórico o nuevo ingreso)",
               _campos_periodo(datos, sufijo="-nuevo"), _campos_carga(datos, sufijo="-nuevo"),
               url=f"{BASE}/{uid}/vinculo/periodo", boton="Agregar"),
    ]
    return modal(
        f"Vínculo de {u['nombres']} {u['apellidos']}",
        mensaje_error(*errores),
        P("Periodos de vínculo con la Carrera de Matemática (el Instituto forma parte de ella: es una sola "
          "dependencia), con su categoría y su carga horaria contratada. Lo define la Dirección de Carrera. La "
          "categoría a la fecha de cada producto o actividad es la que cuenta en los informes. Para cargar el "
          "historial de muchas personas, use «Importar historial» en el listado.",
          cls=(TextPresets.muted_sm, "mb-3")),
        Div(tabla, cls="overflow-x-auto mb-4"),
        Div(*acciones, cls="space-y-2"),
        Div(Button("Listo", type="button", cls=ButtonT.default, data_accion="cerrar-modal"), cls="flex justify-end mt-4"),
        Template(fila(usuarios.con_perfil(uid), auth)(hx_swap_oob="true")),
        ancho="max-w-4xl")


def _investigador(uid):
    """La persona (con o sin perfil de investigación: los docentes también tienen vínculo)."""
    return usuarios.con_perfil(uid)


def _form_carga(req_form) -> dict:
    return {k: req_form.get(k, "") for k in CAMPOS_CARGA}


@rt(BASE + "/{uid}/vinculo")
def get(auth, uid: int):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    return modal_vinculo(u, auth) if gestiona_vinculos(auth) else SIN_PERMISO


@rt(BASE + "/{uid}/vinculo/cambio")
async def post(auth, req, uid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.cambiar_categoria(uid, categoria, desde, jornada or None, auth["id"], carga=carga,
                                         hasta=hasta or None)
    if not errores:
        auditar(auth["id"], "cambiar_categoria", "investigador", uid, f"{categoria} desde {desde}"
                + (f"; carga {vinculos.texto_carga(vinculos.vigente(uid, desde))}" if carga else ""))
    return modal_vinculo(u, auth, errores,
                         datos={"categoria": categoria, "desde": desde, "hasta": hasta, "jornada": jornada, **fc}
                         if errores else None)


@rt(BASE + "/{uid}/vinculo/termino")
def post(auth, uid: int, fecha: str = "", motivo: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    errores = ["Indique el motivo del término."] if not motivo else vinculos.terminar(uid, fecha, motivo)
    if not errores:
        auditar(auth["id"], "terminar_vinculo", "investigador", uid,
                f"{fecha} ({vinculos.MOTIVOS_TERMINO[motivo].lower()})")
    return modal_vinculo(u, auth, errores)


@rt(BASE + "/{uid}/vinculo/periodo")
async def post(auth, req, uid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "",
               nota: str = ""):
    u = _investigador(uid)
    if not u:
        return Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return SIN_PERMISO
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.agregar(uid, categoria, desde or None, hasta or None, jornada or None, nota, auth["id"],
                               carga=carga)
    if not errores:
        auditar(auth["id"], "agregar_vinculo", "investigador", uid,
                f"{categoria} {desde or '?'} a {hasta or 'hoy'}" + (f"; carga {carga['horas']} h/mes" if carga else ""))
    datos = dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota, **fc) if errores else None
    return modal_vinculo(u, auth, errores, datos=datos)


def _periodo_o_error(vid, auth):
    """(periodo, None) si existe y quien pide gestiona los vínculos; (None, respuesta) si no."""
    v = vinculos.obtener(vid)
    if not v:
        return None, Response("No encontrado", status_code=404)
    if not gestiona_vinculos(auth):
        return None, SIN_PERMISO
    return v, None


@rt(BASE + "/vinculo/{vid}/editar")
def get(auth, vid: int):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    return modal_vinculo(_investigador(v["usuario_id"]), auth, editar=vid)


@rt(BASE + "/vinculo/{vid}")
async def put(auth, req, vid: int, categoria: str = "", desde: str = "", hasta: str = "", jornada: str = "",
              nota: str = ""):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    fc = _form_carga(await req.form())
    carga = vinculos.leer_carga(fc)
    errores = vinculos.editar(vid, categoria, desde or None, hasta or None, jornada or None, nota, carga=carga)
    if not errores:
        auditar(auth["id"], "corregir_vinculo", "investigador", v["usuario_id"],
                f"{categoria} {desde or '?'} a {hasta or 'hoy'}" + (f"; carga {carga['horas']} h/mes" if carga else ""))
    u = _investigador(v["usuario_id"])
    if errores:
        return modal_vinculo(u, auth, errores, editar=vid,
                             datos=dict(categoria=categoria, desde=desde, hasta=hasta, jornada=jornada, nota=nota, **fc))
    return modal_vinculo(u, auth)


@rt(BASE + "/vinculo/{vid}")
def delete(auth, vid: int):
    v, error = _periodo_o_error(vid, auth)
    if error:
        return error
    vinculos.eliminar(vid)
    auditar(auth["id"], "eliminar_vinculo", "investigador", v["usuario_id"], vinculos.texto_periodo(v))
    return modal_vinculo(_investigador(v["usuario_id"]), auth)
