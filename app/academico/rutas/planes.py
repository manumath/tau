"""Planes de estudio: lista y ficha por semestre con electivas, requisitos, totales y las
observaciones marcadas para revisión. Los consulta cualquier persona con sesión; las observaciones
las resuelven la Dirección de Carrera y la Coordinación académica."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import planes, reformas
from app.comun import permisos
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/docencia/planes"


def _vigencia(p):
    return f"Vigente desde {p['vigente_desde']}" + (f" (último ingreso: {p['vigente_hasta']})" if p["vigente_hasta"] else "")


def _medida(p):
    if p["sistema"] == "creditos":
        return f"Créditos (1 crédito = {p['horas_por_credito']} horas académicas)"
    return f"Horas semanales · semestres de {p['semanas_semestre']} semanas"


def estado_insignia(p):
    return insignia(planes.ESTADOS[p["estado"]], planes.TONOS_ESTADO[p["estado"]], icono=planes.ICONOS_ESTADO[p["estado"]])


def _filtros(auth, actual):
    """Chips para ver solo los planes de un estado: son enlaces (la página se vuelve a pedir con ?estado=)."""
    opciones = [("", "Todos")] + [(k, v) for k, v in planes.ESTADOS.items()
                                  if k != "elaboracion" or planes.puede_elaborar(auth)]
    return Div(*[A(texto, href=f"{BASE}?estado={clave}" if clave else BASE,
                   aria_current="true" if clave == actual else None,
                   cls="text-sm rounded-full border px-3 py-1 " + (
                       "bg-primary text-primary-foreground border-primary" if clave == actual
                       else "hover:bg-muted")) for clave, texto in opciones],
               cls="flex flex-wrap gap-2 mb-6", role="navigation", aria_label="Filtrar por estado")


@rt(BASE)
def get(auth, estado: str = ""):
    estado = estado if estado in planes.ESTADOS else ""
    if estado == "elaboracion" and not planes.puede_elaborar(auth):
        estado = ""
    reformas = planes.por_reforma(planes.listar(auth, estado or None))
    bloques = []
    for reforma, filas_plan in reformas:
        filas = [fh.Tr(fh.Td(A(p["programa"], href=f"{BASE}/{p['id']}", cls="font-medium hover:underline"),
                             Div(planes.NIVELES[p["nivel"]], cls=TextPresets.muted_sm)),
                       fh.Td(p["nombre"], Div(p["resolucion"] or "", cls=TextPresets.muted_sm)),
                       fh.Td(estado_insignia(p), Div(_vigencia(p), cls=(TextPresets.muted_sm, "mt-1"))),
                       fh.Td(str(p["n_asignaturas"]), cls="text-sm tabular-nums"),
                       fh.Td(insignia(f"{p['n_pendientes']} por revisar", "ambar", icono="circle-alert")
                             if p["n_pendientes"] else insignia("Sin observaciones", "verde", icono="check")))
                 for p in filas_plan]
        bloques.append(Div(
            H3(f"Reforma {reforma['nombre']}", Span(" · ".join(str(x) for x in (reforma["resolucion"],
                                                                                 f"desde {reforma['vigente_desde']}")
                                                               if x), cls=(TextPresets.muted_sm, "ml-2 font-normal")),
               cls="text-base font-semibold mb-2"),
            Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Programa"), fh.Th("Plan"), fh.Th("Estado"), fh.Th("Asignaturas"),
                                        fh.Th("Revisión"))), fh.Tbody(*filas),
                         cls="uk-table uk-table-divider uk-table-middle"), cls="overflow-x-auto"),
            cls="mb-8"))
    return pagina(
        "Planes de estudio",
        H2("Planes de estudio"),
        P("Cada reforma curricular agrupa los planes de los programas de la Carrera. Un plan está en elaboración, "
          "vigente, en proceso de cierre (sin nuevos ingresos) o cerrado. Las inconsistencias de los documentos "
          "quedan marcadas para revisión de la Dirección Académica.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(A(UkIcon("plus", height=14, width=14), "Nueva reforma curricular", href=f"{BASE}/reforma/nueva",
              cls="uk-btn uk-btn-primary inline-flex items-center gap-1"), cls="mb-4")
        if planes.puede_elaborar(auth) else "",
        _filtros(auth, estado),
        *(bloques or [P("No hay planes en este estado.", cls=TextPresets.muted_sm)]),
        usuario=auth, seccion="docencia")


def _horas(f, sistema):
    if sistema == "creditos":
        return [fh.Td(f"{f['creditos']}" if f["creditos"] else "—", cls="tabular-nums w-14")]
    return [fh.Td(str(f[c]) if f[c] else "—", cls="tabular-nums w-14")
            for c in ("horas_teoricas", "horas_practicas", "horas_laboratorio")]


def _fila(f, sistema):
    if f["asignatura_id"] is None:
        nombre = Span(planes.TIPOS[f["tipo"]], cls="italic")
        sigla = ""
    else:
        nombre = Div(f["nombre"], Span(" · la dicta otra unidad", cls=TextPresets.muted_sm)
                     if not f["de_la_carrera"] else "")
        sigla = f["sigla"]
    tipo = "" if f["tipo"] == "obligatoria" else insignia(planes.TIPOS[f["tipo"]],
                                                         "azul" if "electiva" in f["tipo"] else "gris")
    relacion = f.get("linea") or (f"Área de {f['area']}" if f.get("area") else "")
    linea = Div(f.get("linea_formativa") or "—", Div(relacion, cls=TextPresets.muted_sm) if relacion else "")
    return fh.Tr(fh.Td(sigla, cls="font-mono text-sm whitespace-nowrap"), fh.Td(nombre, tipo, cls="text-sm"),
                 *_horas(f, sistema), fh.Td(", ".join(f["requisitos"]) or "—", cls="text-sm whitespace-nowrap"),
                 fh.Td(linea, cls="text-sm"),
                 id=f"asignatura-{sigla}" if sigla else None,  # destino de la búsqueda global
                 cls="target:bg-amber-50 dark:target:bg-amber-950")


def _encabezado(sistema):
    horas = [fh.Th("Créditos", cls="w-14")] if sistema == "creditos" else \
        [fh.Th("T", title="Horas teóricas semanales", cls="w-14"),
         fh.Th("P", title="Horas prácticas semanales", cls="w-14"),
         fh.Th("L", title="Horas de laboratorio semanales", cls="w-14")]
    return fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), *horas, fh.Th("Requisitos"),
                          fh.Th("Línea formativa", title="Y el área o la línea de investigación con que se relaciona")))


def _tabla(filas, sistema):
    return Div(fh.Table(_encabezado(sistema), fh.Tbody(*[_fila(f, sistema) for f in filas]),
                        cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")


def tarjeta_observaciones(p, auth, errores=(), abierta=None):
    obs = planes.observaciones(p["id"])
    if not obs:
        return ""
    revisa = permisos.puede(auth, "revisar_planes")
    items = []
    for o in obs:
        if o["estado"] == "resuelta":
            items.append(Li(Div(insignia("Resuelta", "verde", icono="check"), Span(o["detalle"], cls="text-sm"),
                                cls="flex flex-wrap gap-2 items-start"),
                            P(f"{o['resolucion']} ({o['resuelta_por_nombre']})", cls=(TextPresets.muted_sm, "mt-1")),
                            cls="py-2"))
            continue
        formulario = fh.Form(
            mensaje_error(*(errores if abierta == o["id"] else ())),
            Div(fh.Input(name="resolucion", cls="uk-input", placeholder="Cómo se resolvió…",
                         aria_label="Resolución"),
                Button("Marcar resuelta", type="submit", cls=(ButtonT.default, ButtonT.sm)), cls="flex gap-2"),
            hx_post=f"{BASE}/observaciones/{o['id']}/resolver", hx_target="#observaciones-plan", hx_swap="outerHTML",
            cls="mt-2 space-y-1") if revisa else ""
        items.append(Li(Div(insignia("Por revisar", "ambar", icono="circle-alert"), Span(o["detalle"], cls="text-sm"),
                            cls="flex flex-wrap gap-2 items-start"), formulario, cls="py-2"))
    return Card(H3("Observaciones del documento", cls="text-base font-semibold mb-1"),
                P("Se cargó el plan tal como está en el documento; esto no cuadra y la Dirección Académica debe "
                  "confirmarlo.", cls=(TextPresets.muted_sm, "mb-2")),
                Ul(*items, cls="divide-y divide-border"), id="observaciones-plan")



# --- Nueva reforma curricular (PLAN §65, etapa 2) ------------------------------------------------------------------

def _no_elabora(auth):
    return None if permisos.puede(auth, "elaborar_planes") else Response("No autorizado", status_code=403)


def _form_reforma(auth, errores=(), v=None):
    v = v or {}
    progs = reformas.programas_con_plan()
    planes_ = [(p["id"], f"{p['programa']} · {p['nombre']}") for p in planes.listar(auth)]
    filas = []
    for pr in progs:
        actual = v.get(f"prog_{pr['id']}", "copia")
        filas.append(Div(
            Div(Span(pr["nombre"], cls="font-medium"),
                Div(f"{planes.NIVELES[pr['nivel']]} · {pr['plan']['nombre']} ({planes.ESTADOS[pr['plan']['estado']].lower()}, "
                    f"{pr['plan']['n_asignaturas']} asignaturas)", cls=TextPresets.muted_sm), cls="flex-1"),
            Select(Option("Copiar su plan", value="copia", selected=actual == "copia"),
                   Option("Empezar vacío", value="vacio", selected=actual == "vacio"),
                   Option("No continúa", value="no", selected=actual == "no"),
                   name=f"prog_{pr['id']}", aria_label=f"Qué hacer con {pr['nombre']}", cls="uk-select w-48"),
            cls="flex flex-wrap items-center gap-3 py-2"))
    nuevos = []
    for i in range(3):
        n = {k: (v.get(f"nuevo_{k}") or ["", "", "", "", ""])[i] if isinstance(v.get(f"nuevo_{k}"), list) else ""
             for k in ("nombre", "nivel", "titulo", "sistema", "inicio")}
        nuevos.append(Div(
            campo("Nombre del programa", Input(name="nuevo_nombre", value=n["nombre"], cls="uk-input",
                                               placeholder="Por ejemplo, Licenciatura en Estadística")),
            campo("Nivel", Select(*[Option(t, value=k, selected=k == n["nivel"]) for k, t in planes.NIVELES.items()],
                                  name="nuevo_nivel", cls="uk-select")),
            campo("Título que otorga", Input(name="nuevo_titulo", value=n["titulo"], cls="uk-input")),
            campo("Se mide en", Select(Option("Horas semanales", value="horas", selected=n["sistema"] != "creditos"),
                                       Option("Créditos", value="creditos", selected=n["sistema"] == "creditos"),
                                       name="nuevo_sistema", cls="uk-select")),
            campo("Empezar con", Select(Option("Un plan vacío", value="vacio"),
                                        *[Option(f"Copia de {t}", value=str(i_), selected=str(i_) == n["inicio"])
                                          for i_, t in planes_], name="nuevo_inicio", cls="uk-select")),
            cls="grid grid-cols-1 md:grid-cols-2 gap-3 border border-border rounded-md p-3"))
    return fh.Form(
        mensaje_error(*errores),
        Card(H3("1. Datos de la reforma", cls="text-base font-semibold mb-2"),
             Div(campo("Nombre", Input(name="nombre", value=v.get("nombre", ""), cls="uk-input", required=True,
                                       placeholder="Plan 2027")),
                 campo("Año en que rige", Input(name="anio", value=v.get("anio", ""), cls="uk-input", inputmode="numeric",
                                                required=True)),
                 campo("Resolución (si ya la tiene)", Input(name="resolucion", value=v.get("resolucion", ""),
                                                            cls="uk-input")),
                 cls="grid grid-cols-1 md:grid-cols-3 gap-3")),
        Card(H3("2. Qué programas tendrá", cls="text-base font-semibold mb-1"),
             P("Elija qué hacer con cada programa de la reforma vigente. Para pasar de dos licenciaturas a una, copie "
               "una y marque la otra como «No continúa»; las equivalencias entre materias se registran después.",
               cls=(TextPresets.muted_sm, "mb-2")),
             Div(*filas, cls="divide-y divide-border")),
        Card(fh.Details(fh.Summary("3. Programas nuevos (opcional)", cls="text-base font-semibold cursor-pointer"),
                        P("Una reforma puede crear titulaciones que hoy no existen. Deje en blanco las filas que no "
                          "use.", cls=(TextPresets.muted_sm, "my-2")), Div(*nuevos, cls="space-y-3"),
                        open=any(v.get("nuevo_nombre") or [])
                        and any(x for x in v["nuevo_nombre"]))),
        P("Todos los planes quedan «en elaboración»: solo los ven quienes los elaboran, hasta que la Dirección de "
          "Carrera los ponga en vigencia.", cls=TextPresets.muted_sm),
        Div(Button("Crear la reforma", type="submit", cls=ButtonT.primary),
            A("Cancelar", href=BASE, cls="text-sm text-primary hover:underline"), cls="flex items-center gap-4"),
        hx_post=f"{BASE}/reforma/nueva", hx_target="#form-reforma", hx_swap="outerHTML",
        hx_disabled_elt="find button[type='submit']", id="form-reforma", cls="space-y-4")


@rt(f"{BASE}/reforma/nueva")
def get(auth):
    if (no := _no_elabora(auth)):
        return no
    return pagina("Nueva reforma curricular",
                  A(UkIcon("arrow-left", height=14, width=14), "Planes de estudio", href=BASE,
                    cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2("Nueva reforma curricular"),
                  P("Una reforma agrupa los planes que se aprueban juntos. Este asistente crea los planes en "
                    "elaboración; luego se completan sus datos y su malla.", cls=(TextPresets.muted_sm, "mb-6")),
                  _form_reforma(auth), usuario=auth, seccion="docencia")


@rt(f"{BASE}/reforma/nueva")
async def post(auth, sess, req):
    if (no := _no_elabora(auth)):
        return no
    f = await req.form()
    continuar = {int(k[5:]): f[k] for k in f if k.startswith("prog_") and k[5:].isdigit()}
    n = max(len(f.getlist("nuevo_nombre")), 0)
    nuevos = [{c: (f.getlist(f"nuevo_{c}") + [""] * n)[i] for c in ("nombre", "nivel", "titulo", "sistema", "inicio")}
              for i in range(n)]
    rid, errores = reformas.crear(auth["id"], f.get("nombre", ""), f.get("resolucion", ""), f.get("anio", ""),
                                  continuar, nuevos)
    if errores:
        valores = {k: f.get(k, "") for k in ("nombre", "anio", "resolucion")}
        valores.update({f"prog_{i}": m for i, m in continuar.items()})
        valores.update({f"nuevo_{c}": f.getlist(f"nuevo_{c}") for c in ("nombre", "nivel", "titulo", "sistema", "inicio")})
        return _form_reforma(auth, errores, valores)
    add_toast(sess, "Reforma creada: sus planes están en elaboración.", "success")
    return Redirect(f"{BASE}?estado=elaboracion")


@rt(f"{BASE}/{{pid}}")
def get(auth, pid: int):
    p = planes.obtener(pid)
    if not p or not planes.puede_ver(p, auth):
        return pagina("No encontrado", P("El plan no existe."), usuario=auth)
    sistema = p["sistema"]
    bloques, ciclo_actual = [], None
    for semestre, ciclo, filas in planes.por_semestre(pid):
        if ciclo and ciclo != ciclo_actual:
            bloques.append(H3(f"Ciclo {ciclo}", cls="text-sm font-semibold uppercase tracking-wide text-muted-foreground mt-4"))
            ciclo_actual = ciclo
        bloques.append(Card(H3(f"{planes.ORDINALES[semestre]} semestre", cls="text-base font-semibold mb-2"),
                            _tabla(filas, sistema)))
    electivas = [Card(H3(f"{planes.GRUPOS_ELECTIVAS[g]} ({len(fs)})", cls="text-base font-semibold mb-2"),
                      _tabla(fs, sistema)) for g, fs in planes.electivas(pid).items()]
    tot = planes.totales(pid)
    filas_tot = [fh.Tr(fh.Td(f"Total {k}"), fh.Td(f"{d:,}".replace(",", ".") if d is not None else "—",
                                                  cls="tabular-nums w-14"),
                       fh.Td(f"{c:,}".replace(",", "."), cls="tabular-nums w-14"),
                       fh.Td(insignia("Coincide", "verde", icono="check") if d == c else
                             insignia("No coincide", "ambar", icono="circle-alert") if d is not None else ""))
                 for k, (d, c) in tot.items()]
    return pagina(
        f"{p['programa']} · {p['nombre']}",
        A(UkIcon("arrow-left", height=14, width=14), "Planes de estudio", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{p['programa']}"),
        Div(estado_insignia(p), *_acciones_borrador(p, auth), cls="flex flex-wrap items-center gap-3 mb-2"),
        P(" · ".join(x for x in (p["nombre"], p["resolucion"], _vigencia(p), _medida(p),
                                 f"Nota mínima de aprobación: {p['nota_minima']} %" if p["nota_minima"] else None) if x),
          cls=(TextPresets.muted_sm, "mb-6")),
        Div(tarjeta_observaciones(p, auth),
            Card(H3("Totales", cls="text-base font-semibold mb-2"),
                 fh.Table(fh.Thead(fh.Tr(fh.Th(""), fh.Th("Documento"), fh.Th("Suma del plan"),
                                        fh.Th(""))), fh.Tbody(*filas_tot), cls="uk-table uk-table-small"),
                 P("Horas: suma de las horas semanales de cada semestre (con las casillas de electiva) por las "
                   "semanas del semestre.", cls=TextPresets.muted_sm) if sistema == "horas" else ""),
            *bloques,
            H3("Asignaturas electivas", cls="text-lg font-semibold mt-8") if electivas else "",
            *electivas,
            cls="space-y-4"),
        usuario=auth, seccion="docencia")



def _acciones_borrador(p, auth):
    if p["estado"] != "elaboracion" or not planes.puede_elaborar(auth):
        return []
    return [Button(UkIcon("pencil", height=14, width=14), "Editar datos generales", hx_get=f"{BASE}/{p['id']}/editar",
                   hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", cls=(ButtonT.default, ButtonT.sm)),
            Button(UkIcon("trash-2", height=14, width=14), "Eliminar plan", hx_post=f"{BASE}/{p['id']}/eliminar",
                   hx_confirm="¿Eliminar este plan en elaboración con todas sus asignaturas? No se puede deshacer.",
                   hx_swap="none", cls=(ButtonT.ghost, ButtonT.sm, "text-destructive"))]


def _form_datos(p, errores=(), v=None):
    v = v or {c: ("" if p[c] is None else str(p[c])) for c in (
        "nombre", "resolucion", "vigente_desde", "sistema", "semanas_semestre", "horas_por_credito", "nota_minima",
        "total_teoricas", "total_practicas", "total_laboratorio", "total_creditos")} | {"titulo": p.get("titulo") or ""}
    def entrada(nombre, **kw):
        return Input(name=nombre, value=v.get(nombre, ""), cls="uk-input", **kw)
    return fh.Form(
        mensaje_error(*errores),
        P(f"{p['programa']} · {planes.NIVELES[p['nivel']]}", cls=(TextPresets.muted_sm, "mb-2")),
        Div(campo("Nombre del plan", entrada("nombre", required=True)),
            campo("Año en que rige", entrada("vigente_desde", inputmode="numeric", required=True)),
            campo("Resolución", entrada("resolucion")),
            campo("Título que otorga el programa", entrada("titulo")),
            campo("Se mide en", Select(Option("Horas semanales", value="horas", selected=v.get("sistema") == "horas"),
                                       Option("Créditos", value="creditos", selected=v.get("sistema") == "creditos"),
                                       name="sistema", cls="uk-select")),
            campo("Semanas del semestre (horas)", entrada("semanas_semestre", inputmode="numeric")),
            campo("Horas por crédito (créditos)", entrada("horas_por_credito", inputmode="numeric")),
            campo("Nota mínima de aprobación", entrada("nota_minima", inputmode="numeric")),
            cls="grid grid-cols-1 md:grid-cols-2 gap-3"),
        P("Totales que declara el documento del plan (la carga los compara con la suma de las asignaturas; "
          "déjelos en blanco si no los declara).", cls=(TextPresets.muted_sm, "mt-4 mb-1")),
        Div(campo("Teóricas", entrada("total_teoricas", inputmode="numeric")),
            campo("Prácticas", entrada("total_practicas", inputmode="numeric")),
            campo("Laboratorio", entrada("total_laboratorio", inputmode="numeric")),
            campo("Créditos", entrada("total_creditos", inputmode="numeric")),
            cls="grid grid-cols-2 md:grid-cols-4 gap-3"),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{p['id']}/editar", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_disabled_elt="find button[type='submit']")


@rt(f"{BASE}/{{pid}}/editar")
def get(auth, pid: int):
    if (no := _no_elabora(auth)):
        return no
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return Response("No encontrado", status_code=404)
    return modal("Datos generales del plan", _form_datos(p), ancho="max-w-2xl")


@rt(f"{BASE}/{{pid}}/editar")
async def post(auth, sess, pid: int, req):
    if (no := _no_elabora(auth)):
        return no
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return Response("No encontrado", status_code=404)
    f = dict(await req.form())
    errores = planes.actualizar_datos(pid, f, auth["id"])
    if errores:
        return modal("Datos generales del plan", _form_datos(p, errores, f), ancho="max-w-2xl")
    add_toast(sess, "Datos del plan guardados.", "success")
    return Redirect(f"{BASE}/{pid}")


@rt(f"{BASE}/{{pid}}/eliminar")
def post(auth, sess, pid: int):
    if (no := _no_elabora(auth)):
        return no
    error = planes.eliminar_borrador(pid, auth["id"])
    if error:
        return Response(error, status_code=404)
    add_toast(sess, "Plan en elaboración eliminado.", "success")
    return Redirect(f"{BASE}?estado=elaboracion")


@rt(f"{BASE}/observaciones/{{oid}}/resolver")
def post(auth, sess, oid: int, resolucion: str = ""):
    if not permisos.puede(auth, "revisar_planes"):
        return Response("No autorizado", status_code=403)
    o = planes.observacion(oid)
    if not o:
        return Response("No encontrado", status_code=404)
    p = planes.obtener(o["plan_id"])
    if not planes.puede_ver(p, auth):
        return Response("No encontrado", status_code=404)
    error = planes.resolver(oid, resolucion, auth["id"])
    if error:
        return tarjeta_observaciones(p, auth, [error], oid)
    auditar(auth["id"], "resolver_observacion_plan", "plan_estudios", p["id"], o["detalle"][:120])
    add_toast(sess, "Observación marcada como resuelta.", "success")
    return tarjeta_observaciones(p, auth)
