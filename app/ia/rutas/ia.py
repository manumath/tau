"""Pantallas de la IA con criterio humano (PLAN §59, etapa 0b).

- `/ia`: «Uso de IA en TAU», para toda persona con cuenta del personal (las cuentas de estudiante no llegan: auth.
  RUTAS_ESTUDIANTE). Política vigente, funciones activas, qué datos usan, si salen del sistema y quién responde.
- `/ia/admin` (`gestionar_ia`, Dirección de Carrera): versiones de la política, activación y responsables.
- `/ia/usos` (`ver_uso_ia`): resultados del piloto, usos recientes, decisiones de cierre y reporte de sesgos.
- `/ia/uso/{id}/panel` y `/ia/uso/{id}/decidir`: el panel de revisión de un borrador (lo usan todas las pantallas).
- `/ia/guia`: la guía breve de uso crítico (ventana).
"""
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Table, Tbody, Td, Th, \
    Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, TextArea, TextPresets, UkIcon

from app.comun import permisos, usuarios
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import fecha_local, insignia
from app.ia import clasificacion, medicion, servicio
from app.ia.funciones import FUNCIONES, VEDADOS, obtener as funcion
from app.ia.rutas.panel import panel, volver_seguro

rt = APIRouter()
BASE = "/ia"
ESTADOS = {"generando": ("En preparación", "gris"), "borrador_ia": ("Por revisar", "ambar"),
           "aprobada": ("Aprobada sin cambios", "verde"), "editada": ("Aprobada con cambios", "verde"),
           "rechazada": ("Descartada", "gris"), "error": ("Error", "rojo")}


def _fecha(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"


def _sale(f) -> str:
    """Si los datos de la función pueden salir del sistema, en palabras."""
    if not f.externa:
        return "No: solo el modelo instalado en la universidad."
    if f.nivel_max <= clasificacion.INTERNO:
        return "Puede ir a un proveedor externo con retención cero (no guarda ni entrena con los datos)."
    return "Solo seudonimizados (sin nombres) a un proveedor externo con retención cero; si no, el modelo local."


def _nombre(uid):
    u = usuarios.por_id(uid) if uid else None
    return f"{u['nombres']} {u['apellidos']}" if u else "—"


def _texto_politica(p):
    return Div(p["texto"], cls="text-sm whitespace-pre-line")


# --- Página «Uso de IA en TAU» --------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    pol = servicio.politica_vigente()
    funciones = sorted(FUNCIONES.values(), key=lambda f: f.nombre)
    accesos = []
    if permisos.puede(auth, "gestionar_ia"):
        accesos.append(A("Administrar", href=f"{BASE}/admin", cls="uk-btn uk-btn-default uk-btn-sm"))
    if permisos.puede(auth, "ver_uso_ia"):
        accesos.append(A("Resultados del piloto", href=f"{BASE}/usos", cls="uk-btn uk-btn-default uk-btn-sm"))

    def tarjeta(f):
        e = servicio.estado_funcion(f.clave)
        return Li(
            Div(Span(f.nombre, cls="font-medium"),
                insignia("Activa", "verde", icono="circle-check") if e["activa"] else
                insignia("Apagada", "gris", icono="circle-slash"), cls="flex flex-wrap items-center gap-2"),
            P(f.descripcion, cls="text-sm mt-1"),
            Ul(Li(Span("Datos que usa: ", cls="font-medium"), f.datos),
               Li(Span("¿Salen del sistema? ", cls="font-medium"), _sale(f)),
               Li(Span("Revisa y aprueba: ", cls="font-medium"), f.revisor),
               Li(Span("Responsable: ", cls="font-medium"), _nombre(e["responsable_id"])) if e["activa"] else "",
               cls="text-sm text-muted-foreground mt-2 space-y-1"),
            cls="py-4")
    return pagina(
        "Uso de IA en TAU",
        Div(Div(H2("Uso de IA en TAU"),
                P("Cómo y para qué usa inteligencia artificial el sistema. La IA sugiere y la persona decide: ningún "
                  "borrador surte efecto sin que alguien lo apruebe, y todo texto aprobado lleva su marca.",
                  cls=TextPresets.muted_sm)),
            Div(*accesos, cls="flex gap-2"), cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(Div(Card(H3("Funciones", cls="text-base font-semibold"),
                     Ul(*[tarjeta(f) for f in funciones], cls="divide-y divide-border")),
                cls="lg:col-span-2 space-y-6"),
            Div(Card(H3("Política de uso", cls="text-base font-semibold mb-2"),
                     Div(P(f"Versión {pol['version']}, aprobada el {_fecha(pol['fecha_aprobacion'])}.",
                           cls=(TextPresets.muted_sm, "mb-2")), _texto_politica(pol)) if pol else
                     P("La Dirección de Carrera aún no aprobó la política de uso: todas las funciones están apagadas.",
                       cls=TextPresets.muted_sm)),
                Card(H3("Dónde no se usa", cls="text-base font-semibold mb-2"),
                     P("La IA no interviene en decisiones sobre personas. Está bloqueada en:", cls="text-sm mb-2"),
                     Ul(*[Li(v) for v in VEDADOS.values()], cls="list-disc pl-5 text-sm space-y-1"),
                     P("Nunca recibe fechas de nacimiento, notas de tutoría, respuestas anónimas sueltas ni datos de "
                       "contacto.", cls="text-sm mt-2")),
                Card(H3("Guía de uso crítico", cls="text-base font-semibold mb-2"),
                     P("Qué revisar antes de aprobar un borrador.", cls="text-sm mb-2"),
                     A("Abrir la guía", href="#", hx_get=f"{BASE}/guia", hx_target=f"#{ID_MODAL}",
                       cls="text-sm text-primary hover:underline")),
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


# --- Guía de uso crítico (etapa 4) ------------------------------------------------------------------------------------

@rt(f"{BASE}/guia")
def get(auth):
    return modal(
        "Guía de uso crítico de la IA",
        Div(P("La IA redacta rápido, pero se equivoca con seguridad. Antes de aprobar un borrador:", cls="text-sm"),
            Ul(Li(Span("Compruebe cada afirmación. ", cls="font-medium"),
                  "Si el borrador dice algo que usted no puede respaldar con un registro, quítelo."),
               Li(Span("Las cifras salen de la base. ", cls="font-medium"),
                  "Donde vea «[cifra por verificar]», el modelo escribió un número por su cuenta: complételo con el "
                  "dato real o borre la frase."),
               Li(Span("Nombres y atribuciones. ", cls="font-medium"),
                  "Verifique que cada logro se atribuya a quien corresponde y que no falte nadie."),
               Li(Span("Tono y sesgos. ", cls="font-medium"),
                  "Evite exageraciones y juicios sobre personas; revise que no se privilegie un área o un tipo de "
                  "trabajo sobre otro."),
               Li(Span("Sugerencias de opciones. ", cls="font-medium"),
                  "Las líneas o evidencias sugeridas son un punto de partida: marque solo las que usted confirme."),
               Li(Span("Responsabilidad. ", cls="font-medium"),
                  "Al aprobar, el texto pasa a ser suyo; queda la marca «Elaborado con apoyo de IA; revisado por…»."),
               Li(Span("Valore el borrador. ", cls="font-medium"),
                  "La valoración y el motivo de un descarte sirven para decidir si la función sigue, se ajusta o se "
                  "retira."),
               cls="list-disc pl-5 text-sm space-y-2"),
            P("Para formarse en IA y competencias digitales, registre sus cursos en Capacitación (área «IA y "
              "competencias digitales»).", cls=TextPresets.muted_sm),
            Div(Button("Cerrar", type="button", cls=ButtonT.primary, data_accion="cerrar-modal"),
                cls="flex justify-end"),
            cls="space-y-3"),
        ancho="max-w-xl")


# --- Panel de un borrador -----------------------------------------------------------------------------------------

def _uso_visible(uso_id, auth):
    uso = servicio.obtener(uso_id)
    if not uso:
        return None, Response("No encontrado", status_code=404)
    f = funcion(uso["funcion_clave"])
    if uso["usuario_id"] != auth["id"] and not (f and f.puede_aprobar(auth, uso)):
        return None, Response("No autorizado", status_code=403)
    return uso, None


@rt(f"{BASE}/uso/{{uso_id}}/panel")
def get(auth, uso_id: int, volver: str = "/"):
    uso, error = _uso_visible(uso_id, auth)
    return error or panel(uso, auth, volver)


@rt(f"{BASE}/uso/{{uso_id}}/decidir")
def post(auth, sess, uso_id: int, decision: str = "", texto_final: str = "", elegido: list[str] = None,
         motivo: str = "", valoracion: str = "", volver: str = "/"):
    uso, error = _uso_visible(uso_id, auth)
    if error:
        return error
    f = funcion(uso["funcion_clave"])
    if f.opciones:
        marcados = set(elegido or [])
        texto_final = ",".join(v for v, _, _ in f.opciones(uso) if v in marcados)
        if decision == "aprobar" and not texto_final:
            return panel(uso, auth, volver, ["Marque al menos una opción, o descarte la sugerencia."])
    errores = servicio.decidir(uso_id, auth, decision, texto_final, motivo, valoracion)
    if errores:
        return panel(servicio.obtener(uso_id), auth, volver, errores)
    add_toast(sess, "Borrador aprobado." if decision == "aprobar" else "Borrador descartado.", "success")
    return Redirect(volver_seguro(volver))


# --- Administración (Dirección de Carrera) ------------------------------------------------------------------------

def _solo(auth, accion):
    return None if permisos.puede(auth, accion) else Response("No autorizado", status_code=403)


def _personal_activo():
    """Personas del personal (investigadores, con vínculo o con un rol): las cuentas de estudiante no responden."""
    return [u for u in usuarios.listar()
            if u["activo"] and (u["es_investigador"] or u["categoria"] or permisos.roles_vigentes(u["id"]))]


def _fila_funcion(f, personas):
    e = servicio.estado_funcion(f.clave)
    if e["activa"]:
        accion = Div(Span(_nombre(e["responsable_id"]), cls="text-sm"),
                     Button("Apagar", cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"{BASE}/admin/{f.clave}/apagar",
                            hx_confirm=f"¿Apagar «{f.nombre}»? Los borradores en curso se conservan."),
                     cls="flex flex-wrap items-center gap-2")
    else:
        accion = Form(Select(Option("Responsable…", value=""),
                             *[Option(f"{u['apellidos']}, {u['nombres']}", value=str(u["id"]),
                                      selected=u["id"] == e["responsable_id"]) for u in personas],
                             name="responsable_id", cls="uk-select uk-form-small", aria_label="Responsable"),
                      Button("Activar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                      hx_post=f"{BASE}/admin/{f.clave}/activar", cls="flex flex-wrap items-center gap-2")
    return Tr(Td(Div(f.nombre, cls="font-medium"), Div(f.descripcion, cls=TextPresets.muted_sm)),
              Td(clasificacion.NIVELES[f.nivel_max], cls="text-sm"),
              Td(insignia("Activa", "verde") if e["activa"] else insignia("Apagada", "gris")), Td(accion))


@rt(f"{BASE}/admin")
def get(auth):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    pol = servicio.politica_vigente()
    versiones = servicio.politicas()
    personas = _personal_activo()
    return pagina(
        "Administrar la IA",
        Div(H2("Administrar la IA"),
            P("La Dirección de Carrera aprueba la política de uso, activa cada función y designa a su responsable. "
              "Todas nacen apagadas.", cls=TextPresets.muted_sm), cls="mb-6"),
        Div(Card(H3("Funciones", cls="text-base font-semibold mb-2"),
                 P("Activar exige una política aprobada.", cls=TextPresets.muted_sm) if not pol else "",
                 Div(Table(Thead(Tr(Th("Función"), Th("Datos hasta"), Th("Estado"), Th("Responsable"))),
                           Tbody(*[_fila_funcion(f, personas) for f in sorted(FUNCIONES.values(), key=lambda f: f.nombre)]),
                           cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto"),
                 cls="lg:col-span-2"),
            Div(Card(H3("Política de uso", cls="text-base font-semibold mb-2"),
                     Ul(*[Li(Div(Span(f"Versión {p['version']}", cls="font-medium"),
                                 insignia("Vigente", "verde") if p["vigente"] else
                                 insignia("Aprobada", "gris") if p["fecha_aprobacion"] else insignia("Borrador", "ambar"),
                                 Button("Aprobar", cls=(ButtonT.primary, ButtonT.sm),
                                        hx_post=f"{BASE}/admin/politica/{p['id']}/aprobar",
                                        hx_confirm="¿Aprobar esta versión? Pasa a ser la vigente.")
                                 if not p["fecha_aprobacion"] else "",
                                 cls="flex flex-wrap items-center gap-2"),
                             P(f"Creada el {_fecha(p['creado_en'])}" +
                               (f"; aprobada el {_fecha(p['fecha_aprobacion'])}" if p["fecha_aprobacion"] else ""),
                               cls=TextPresets.muted_sm),
                             Div(p["texto"][:400] + ("…" if len(p["texto"]) > 400 else ""),
                                 cls="text-sm whitespace-pre-line mt-1"), cls="py-2")
                          for p in versiones], cls="divide-y divide-border") if versiones else
                     P("Aún no hay versiones.", cls=TextPresets.muted_sm),
                     Button(UkIcon("plus", height=14, width=14), "Nueva versión", cls=(ButtonT.default, ButtonT.sm, "mt-3"),
                            hx_get=f"{BASE}/admin/politica/nueva", hx_target=f"#{ID_MODAL}")),
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


POLITICA_SUGERIDA = """1. Finalidad. La IA se usa en TAU para preparar borradores y sugerencias que una persona revisa. No reemplaza el juicio de nadie.
2. Decisión humana. Ningún borrador surte efecto sin la aprobación de quien corresponde; el texto aprobado lleva la marca «Elaborado con apoyo de IA; revisado por…».
3. Vedados. La IA no se usa en auxiliaturas, asignación docente y carga horaria, evaluación del desempeño, tutoría, tribunales de grado ni en decisiones sobre una persona identificada.
4. Datos. Solo se envían los datos que cada función declara. Nunca fechas de nacimiento, notas de tutoría, respuestas anónimas sueltas ni datos de contacto. Los datos personales van seudonimizados o al modelo local.
5. Proveedores. Un modelo instalado en la universidad o un proveedor externo con retención cero de datos.
6. Trazabilidad. Cada uso queda registrado con la versión de las instrucciones, el proveedor y la decisión humana.
7. Medición. Cada función es un piloto: al cerrarlo, la Dirección de Carrera decide ampliarla, ajustarla o retirarla, con los resultados a la vista.
8. Revisión. Esta política se revisa cada gestión."""


@rt(f"{BASE}/admin/politica/nueva")
def get(auth):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    pol = servicio.politica_vigente()
    return _form_politica(pol["texto"] if pol else POLITICA_SUGERIDA)


def _form_politica(texto, errores=()):
    return modal("Nueva versión de la política",
                 Form(mensaje_error(*errores),
                      Div(FormLabel("Texto", fr="texto"),
                          TextArea(texto, id="texto", name="texto", rows=16, cls="uk-textarea text-sm"), cls="space-y-1"),
                      P("Se guarda como borrador; pasa a regir cuando usted la aprueba.", cls=TextPresets.muted_sm),
                      Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                          Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                      hx_post=f"{BASE}/admin/politica", hx_target=f"#{ID_MODAL}", cls="space-y-4"),
                 ancho="max-w-2xl")


@rt(f"{BASE}/admin/politica")
def post(auth, sess, texto: str = ""):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    _, err = servicio.crear_politica(texto, auth["id"])
    if err:
        return _form_politica(texto, [err])
    add_toast(sess, "Versión guardada como borrador.", "success")
    return Redirect(f"{BASE}/admin")


@rt(f"{BASE}/admin/politica/{{pid}}/aprobar")
def post(auth, sess, pid: int):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    err = servicio.aprobar_politica(pid, auth["id"])
    add_toast(sess, err or "Política aprobada: es la vigente.", "error" if err else "success")
    return Redirect(f"{BASE}/admin")


@rt(f"{BASE}/admin/{{clave}}/activar")
def post(auth, sess, clave: str, responsable_id: str = ""):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    err = servicio.activar(clave, int(responsable_id) if responsable_id.isdigit() else None, auth["id"])
    add_toast(sess, err or "Función activada.", "error" if err else "success")
    return Redirect(f"{BASE}/admin")


@rt(f"{BASE}/admin/{{clave}}/apagar")
def post(auth, sess, clave: str):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    if not funcion(clave):
        return Response("No encontrado", status_code=404)
    servicio.desactivar(clave, auth["id"])
    add_toast(sess, "Función apagada.", "success")
    return Redirect(f"{BASE}/admin")


# --- Resultados del piloto ----------------------------------------------------------------------------------------

def _num(v, sufijo=""):
    return "—" if v is None else f"{v}{sufijo}".replace(".", ",")


def _form_cierre(errores=(), d=None):
    d = d or {}
    return Form(mensaje_error(*errores),
                Div(Div(FormLabel("Función", fr="cierre-clave"),
                        Select(Option("Elija…", value=""),
                               *[Option(f.nombre, value=f.clave, selected=f.clave == d.get("clave"))
                                 for f in sorted(FUNCIONES.values(), key=lambda f: f.nombre)],
                               id="cierre-clave", name="clave", cls="uk-select"), cls="space-y-1"),
                    Div(FormLabel("Decisión", fr="cierre-decision"),
                        Select(Option("Elija…", value=""),
                               *[Option(t, value=k, selected=k == d.get("decision"))
                                 for k, t in medicion.DECISIONES_CIERRE.items()],
                               id="cierre-decision", name="decision", cls="uk-select"), cls="space-y-1"),
                    cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                Div(FormLabel("Fundamento", fr="cierre-fundamento"),
                    TextArea(d.get("fundamento", ""), id="cierre-fundamento", name="fundamento", rows=3,
                             cls="uk-textarea"), cls="space-y-1"),
                P("«Retirar» apaga la función.", cls=TextPresets.muted_sm),
                Div(Button("Registrar la decisión", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                    cls="flex justify-end"),
                hx_post=f"{BASE}/cierre", hx_target="this", hx_swap="outerHTML", cls="space-y-3")


@rt(f"{BASE}/usos")
def get(auth):
    if (error := _solo(auth, "ver_uso_ia")):
        return error
    filas = medicion.piloto()
    cierres = medicion.cierres()
    tabla = Div(Table(
        Thead(Tr(*[Th(t) for t in ("Función", "Año", "Usos", "Sin cambios", "Con cambios", "Descartadas", "Errores",
                                   "Aceptadas", "Horas hasta decidir", "Edición media", "Valoración")])),
        Tbody(*[Tr(Td(x["nombre"]), Td(x["anio"]), Td(x["n"]), Td(x["aprobada"]), Td(x["editada"]), Td(x["rechazada"]),
                   Td(x["error"]), Td(_num(x["pct_aceptadas"], " %")), Td(_num(x["horas"])),
                   Td(_num(x["distancia"])), Td(_num(x["valoracion"]))) for x in filas]),
        cls="uk-table uk-table-divider uk-table-small text-sm"), cls="overflow-x-auto") if filas else \
        P("Aún no hay usos registrados.", cls=TextPresets.muted_sm)
    recientes = medicion.recientes()
    return pagina(
        "Resultados del piloto de IA",
        Div(Div(H2("Resultados del piloto de IA"),
                P("Cada función es un piloto. «Edición media»: cuánto cambió la persona el borrador (0 = nada, 1 = todo). "
                  "No hay cifras por persona.", cls=TextPresets.muted_sm)),
            A("Reporte de sesgos", href=f"{BASE}/sesgos", cls="uk-btn uk-btn-default uk-btn-sm"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(H3("Por función y año", cls="text-base font-semibold mb-2"), tabla, cls="mb-6"),
        Div(Card(H3("Decisiones de cierre", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(Div(Span(funcion(c["funcion_clave"]).nombre if funcion(c["funcion_clave"]) else c["funcion_clave"],
                                  cls="font-medium"),
                             insignia(medicion.DECISIONES_CIERRE[c["decision"]],
                                      {"ampliar": "verde", "ajustar": "ambar", "retirar": "gris"}[c["decision"]]),
                             cls="flex flex-wrap items-center gap-2"),
                         P(c["fundamento"], cls="text-sm whitespace-pre-line mt-1"),
                         P(f"{c['por']}, {_fecha(c['fecha'])}", cls=TextPresets.muted_sm), cls="py-2")
                      for c in cierres], cls="divide-y divide-border") if cierres else
                 P("Aún no hay decisiones.", cls=TextPresets.muted_sm),
                 Div(H3("Registrar una decisión", cls="text-sm font-semibold mt-4 mb-2"), _form_cierre())
                 if permisos.puede(auth, "gestionar_ia") else ""),
            Card(H3("Usos recientes", cls="text-base font-semibold mb-2"),
                 Div(Table(Thead(Tr(Th("Fecha"), Th("Función"), Th("Estado"), Th("Proveedor"), Th("Instrucciones"))),
                           Tbody(*[Tr(Td(fecha_local(u["creado_en"])),
                                      Td(funcion(u["funcion_clave"]).nombre if funcion(u["funcion_clave"]) else u["funcion_clave"]),
                                      Td(insignia(*ESTADOS[u["estado"]])),
                                      Td(f"{u['proveedor'] or '—'}" + (" · seudonimizado" if u["seudonimizado"] else "")),
                                      Td(f"v{u['version_prompt']}")) for u in recientes]),
                           cls="uk-table uk-table-divider uk-table-small text-sm"), cls="overflow-x-auto")
                 if recientes else P("Sin usos.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        P("Para conocer la percepción de los académicos, la Dirección o la Coordinación pueden crear, una vez por "
          "gestión, la encuesta «Percepción del uso de la IA en TAU» desde Encuestas.", cls=(TextPresets.muted_sm, "mt-6")),
        usuario=auth)


@rt(f"{BASE}/cierre")
def post(auth, sess, clave: str = "", decision: str = "", fundamento: str = ""):
    if (error := _solo(auth, "gestionar_ia")):
        return error
    errores = medicion.cerrar(clave, decision, fundamento, auth["id"])
    if errores:
        return _form_cierre(errores, {"clave": clave, "decision": decision, "fundamento": fundamento})
    add_toast(sess, "Decisión registrada.", "success")
    return Redirect(f"{BASE}/usos")


@rt(f"{BASE}/sesgos")
def get(auth):
    if (error := _solo(auth, "ver_uso_ia")):
        return error
    s = medicion.sesgos()

    def tabla(titulo, filas):
        return Card(H3(titulo, cls="text-base font-semibold mb-2"),
                    Div(Table(Thead(Tr(Th("Nombre"), Th("Sugerencias"), Th("Descartadas"), Th("%"), Th(""))),
                              Tbody(*[Tr(Td(x["nombre"]), Td(x["n"]), Td(x["descartadas"]), Td(f"{x['pct']} %"),
                                         Td(insignia("Revisar", "ambar", icono="triangle-alert",
                                                     titulo="Se descarta claramente más que el promedio")
                                            if x["senal"] else "")) for x in filas]),
                              cls="uk-table uk-table-divider uk-table-small text-sm"), cls="overflow-x-auto")
                    if filas else P("Sin datos.", cls=TextPresets.muted_sm))
    return pagina(
        "Reporte de sesgos",
        Div(H2("Reporte de sesgos: líneas de los productos"),
            P(f"Sugerencias revisadas: {s['total']}; descartadas en promedio: "
              f"{s['pct'] if s['pct'] is not None else '—'} %. Se señala una línea o un tipo de producto cuya "
              f"sugerencia se descarta al menos {medicion.FACTOR_SESGO:g} veces más que el promedio (con "
              f"{medicion.MIN_SESGO} sugerencias o más): puede indicar que el modelo favorece o perjudica un área o "
              "un tipo de trabajo. Úselo al decidir si la función se ajusta.",
              cls=TextPresets.muted_sm), cls="mb-6"),
        Div(tabla("Por línea sugerida", s["por_linea"]), tabla("Por tipo de producto", s["por_tipo"]),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        P(A("Volver a los resultados del piloto", href=f"{BASE}/usos", cls="text-primary hover:underline"),
          cls="text-sm mt-6"),
        usuario=auth)

