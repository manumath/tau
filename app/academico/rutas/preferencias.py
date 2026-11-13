"""Preferencias del docente para la oferta (PLAN §68, etapa 2): cada persona indica las suyas y quien arma la oferta
(`gestionar_oferta`) ve las de todos. La persona sale de la sesión, nunca de la dirección."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import gestiones, oferta, preferencias
from app.comun import permisos
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
MIAS = "/docencia/preferencias"
TODAS = "/docencia/preferencias/todas"
TONO = {"prefiere": "verde", "no_puede": "ambar"}


def _selector(g, abiertas, base):
    if len(abiertas) < 2:
        return ""
    return Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in abiertas],
                  aria_label="Gestión", cls="uk-select w-40", data_navegar=f"{base}?gestion=")


def _elegida(gestion: str, lista: list[dict]):
    return next((x for x in lista if str(x["id"]) == gestion), None) or (lista[0] if lista else None)


def _grilla(indisponible: set[str]):
    return fh.Table(
        fh.Thead(fh.Tr(fh.Th(""), *[fh.Th(t, cls="text-center") for t in preferencias.TURNOS.values()])),
        fh.Tbody(*[fh.Tr(fh.Td(nombre, cls="text-sm"),
                         *[fh.Td(Input(type="checkbox", name="turno", value=f"{d}-{t}", checked=f"{d}-{t}" in indisponible,
                                       cls="uk-checkbox", aria_label=f"No puedo dictar el {nombre.lower()}, turno {tn.lower()}"),
                                 cls="text-center") for t, tn in preferencias.TURNOS.items()])
                   for d, nombre in preferencias.DIAS.items()]),
        cls="uk-table uk-table-divider uk-table-small max-w-md")


@rt(MIAS)
def get(auth, gestion: str = "", errores: str = ""):
    abiertas = preferencias.gestiones_abiertas()
    g = _elegida(gestion, abiertas)
    cabecera = Div(Div(H2("Mis preferencias de oferta"),
                       P("Antes de armar la oferta, indique qué materias prefiere dictar, cuáles no puede y en qué turnos no tiene "
                         "disponibilidad. Es una ayuda para la Dirección de Carrera y la Coordinación académica: no asigna nada. "
                         "Solo usted y quienes arman la oferta ven esto.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
                   _selector(g, abiertas, MIAS) if g else "", cls="flex flex-wrap items-end justify-between gap-4 mb-6")
    if not g:
        return pagina("Mis preferencias de oferta", cabecera,
                      Card(P("No hay una gestión en planificación: las preferencias se indican antes de armar la oferta.",
                             cls="text-sm")), usuario=auth, seccion="docencia")
    motivo = preferencias.puede_indicar(auth["id"], g)
    mio = preferencias.de_persona(g["id"], auth["id"])
    en_oferta = {o["asignatura_id"] for o in oferta.listar(g["id"])}
    filas = []
    for a in oferta.asignaturas_ofertables():
        m = mio["materias"].get(a["id"], {"nivel": "", "nota": ""})
        filas.append(fh.Tr(
            fh.Td(a["sigla"], cls="font-mono text-sm whitespace-nowrap"),
            fh.Td(Div(a["nombre"], cls="text-sm"), insignia("En la oferta", "azul") if a["id"] in en_oferta else ""),
            fh.Td(Select(Option("—", value=""), *[Option(t, value=k, selected=m["nivel"] == k) for k, t in preferencias.NIVELES.items()],
                         name=f"m_{a['id']}", cls="uk-select h-8 text-sm w-44", aria_label=f"{a['sigla']}: preferencia")),
            fh.Td(Input(name=f"n_{a['id']}", value=m["nota"], maxlength=preferencias.MAX_NOTA, cls="uk-input h-8 text-sm",
                        placeholder="Nota (opcional)", aria_label=f"{a['sigla']}: nota"))))
    cuerpo = fh.Form(
        mensaje_error(*[e for e in errores.split("|") if e]),
        Card(H3("Materias", cls="text-base font-semibold"),
             P("Deje en «—» las que le da igual dictar.", cls=TextPresets.muted_sm),
             Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("Preferencia"), fh.Th("Nota"))),
                          fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto mt-2")),
        Card(H3("Turnos en que no tiene disponibilidad", cls="text-base font-semibold"),
             P("Marque los turnos en que no puede dictar clases.", cls=(TextPresets.muted_sm, "mb-2")),
             _grilla(mio["indisponible"]),
             campo("Comentario para la Coordinación", fh.Textarea(mio["comentario"], name="comentario", rows=3,
                                                                  maxlength=preferencias.MAX_COMENTARIO, cls="uk-textarea mt-3"))),
        Input(type="hidden", name="gestion", value=str(g["id"])),
        Button(UkIcon("save", height=14, width=14), "Guardar mis preferencias", type="submit", cls=ButtonT.primary),
        method="post", action=MIAS, cls="space-y-4")
    return pagina("Mis preferencias de oferta", cabecera,
                  Card(P(motivo, cls="text-sm")) if motivo else cuerpo, usuario=auth, seccion="docencia")


@rt(MIAS)
async def post(auth, sess, req):
    f = await req.form()
    g = gestiones.obtener(int(f["gestion"])) if str(f.get("gestion", "")).isdigit() else None
    if not g:
        return Response("No encontrado", status_code=404)
    materias = {int(k[2:]): (v, f.get(f"n_{k[2:]}", "")) for k, v in f.items() if k.startswith("m_") and k[2:].isdigit() and v}
    errores = preferencias.guardar(g, auth["id"], materias, f.getlist("turno"), f.get("comentario", ""))
    if errores:
        return Redirect(f"{MIAS}?gestion={g['id']}&errores={'|'.join(errores)}")
    add_toast(sess, "Preferencias guardadas.", "success")
    return Redirect(f"{MIAS}?gestion={g['id']}")


@rt(TODAS)
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "gestionar_oferta"):
        return Response("No autorizado", status_code=403)
    lista = [g for g in gestiones.listar() if g["estado"] != "concluida"][::-1] or gestiones.listar()
    g = _elegida(gestion, lista)
    cabecera = Div(Div(H2("Preferencias de los docentes"),
                       P("Lo que los docentes indicaron para la oferta. Es una ayuda: al asignar un docente a una materia, el "
                         "selector marca a quien la prefiere o no puede dictarla.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
                   _selector(g, lista, TODAS) if g else "", cls="flex flex-wrap items-end justify-between gap-4 mb-6")
    if not g:
        return pagina("Preferencias de los docentes", cabecera, Card(P("Aún no hay gestiones.", cls="text-sm")),
                      usuario=auth, seccion="docencia")
    personas = preferencias.de_gestion(g["id"])
    sin = preferencias.sin_indicar(g["id"])
    tarjetas = [Card(
        H3(f"{p['apellidos']}, {p['nombres']}", cls="text-base font-semibold"),
        Ul(*[Li(insignia(preferencias.NIVELES[m["nivel"]], TONO[m["nivel"]]),
                Span(f" {m['sigla']} · {m['nombre']}", cls="text-sm"),
                Span(f" — {m['nota']}", cls=TextPresets.muted_sm) if m["nota"] else "", cls="py-0.5") for m in p["materias"]],
           cls="mt-2") if p["materias"] else "",
        P(f"Sin disponibilidad: {preferencias.texto_turnos(p['indisponible'])}.", cls="text-sm mt-2") if p["indisponible"] else "",
        P(p["comentario"], cls=(TextPresets.muted_sm, "mt-2")) if p["comentario"] else "") for p in personas]
    return pagina("Preferencias de los docentes", cabecera,
                  P(f"{len(personas)} docente(s) indicaron preferencias para {gestiones.codigo(g)}.", cls="text-sm mb-3"),
                  Div(*tarjetas, cls="grid grid-cols-1 lg:grid-cols-2 gap-4") if tarjetas
                  else Card(P("Nadie ha indicado preferencias todavía.", cls="text-sm")),
                  Card(H3("Aún no indicaron", cls="text-base font-semibold"),
                       P(", ".join(f"{p['apellidos']}, {p['nombres']}" for p in sin), cls=(TextPresets.muted_sm, "mt-1")),
                       cls="mt-4") if sin else "",
                  P(A("Ir a la oferta", href=f"/docencia/oferta?gestion={g['id']}", cls="text-sm text-primary hover:underline"),
                    cls="mt-4"), usuario=auth, seccion="docencia")
