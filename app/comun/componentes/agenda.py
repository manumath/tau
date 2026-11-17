"""Cómo se muestran los pendientes y las fechas de una persona (PLAN §68, §69 y §73): la lista de pendientes y el
calendario por meses que comparten «Mis pendientes» y «Mi calendario», sean los de toda la persona (`/pendientes`,
`/calendario`) o los de la docencia y la investigación por separado."""
from datetime import date

from fasthtml.common import A, Div, Li, P, Span, Ul
from monsterui.all import H3, Card, TextPresets, UkIcon

from app.comun import calendario, formato
from app.comun.componentes.registros import insignia

# tipo de un pendiente o de una fecha → (etiqueta, tono de la insignia). Un tipo nuevo de un aporte se agrega aquí.
TIPOS = {"grado": ("Grado", "verde"), "auxiliatura": ("Auxiliaturas", "ambar"), "tutoria": ("Tutoría", "gris"),
         "tema": ("Temas de grado", "azul"), "vinculo": ("Vínculo", "ambar"), "preferencias": ("Oferta", "azul"),
         "programa": ("Programa", "azul"), "gestion": ("Semestre", "gris"), "evento": ("Evento", "azul"),
         "mejora": ("Plan de mejora", "azul"), "propuesta": ("Convocatoria", "azul"), "proyecto": ("Proyectos", "verde"),
         "plan": ("Plan del proyecto", "ambar"), "producto": ("Productos", "gris"), "perfil": ("Perfil", "gris"),
         "carga": ("Carga horaria", "ambar"), "actividad": ("Actividades", "azul"), "acceso": ("Acceso abierto", "verde")}
SITUACIONES = {"vencido": ("Vencido", "rojo"), "proximo": ("Próximo", "ambar")}
PLAZOS = {"30": 30, "90": 90, "180": 180}
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
         "Diciembre")


def _tipo(clave: str):
    return insignia(*TIPOS.get(clave, (clave.capitalize(), "gris")))


def _fila(p: dict, hoy: date):
    s = calendario.situacion(p, hoy)
    titulo = A(p["titulo"], href=p["href"], cls="hover:underline") if p["href"] else p["titulo"]
    return Li(Div(Div(Div(titulo, cls="text-sm font-medium"),
                      Div(" · ".join(x for x in (p["detalle"], f"vence el {formato.fecha(p['cuando'])}" if p["cuando"] else "")
                                     if x), cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                  insignia(*SITUACIONES[s]) if s in SITUACIONES else "", _tipo(p["tipo"]), cls="flex items-start gap-3 py-2"))


def lista_pendientes(lista: list[dict], hoy: date):
    """La tarjeta con los pendientes, o «No tiene nada pendiente»."""
    if not lista:
        return Card(P(UkIcon("circle-check", height=16, width=16, cls="inline mr-1"), "No tiene nada pendiente.", cls="text-sm"))
    return Card(Ul(*[_fila(p, hoy) for p in lista], cls="divide-y divide-border"))


def dias_de(dias: str) -> int:
    return PLAZOS.get(dias, 90)


def calendario_por_meses(eventos: list[dict], hoy: date, n: int, base: str) -> list:
    """Los filtros de plazo con la descarga .ics y una tarjeta por mes (o «No hay fechas en este periodo»)."""
    meses: dict = {}
    for e in eventos:
        meses.setdefault(e["fecha"][:7], []).append(e)
    bloques = []
    for mes, es in meses.items():
        f = date.fromisoformat(mes + "-01")
        bloques.append(Card(H3(f"{MESES[f.month - 1]} de {f.year}", cls="text-base font-semibold mb-2"),
                            Ul(*[Li(Div(Span(formato.fecha(e["fecha"], anio=False) if e["fecha"] != hoy.isoformat() else "Hoy",
                                             cls="text-sm font-medium w-24 shrink-0"),
                                        Div(Div(A(e["titulo"], href=e["href"], cls="hover:underline") if e["href"]
                                                else e["titulo"], cls="text-sm"),
                                            Div(" · ".join(x for x in (e["hora"], e["detalle"]) if x), cls=TextPresets.muted_sm),
                                            cls="min-w-0 flex-1"),
                                        _tipo(e["tipo"]), cls="flex items-start gap-3 py-2")) for e in es],
                               cls="divide-y divide-border")))
    filtros = Div(*[A(f"{k} días", href=f"{base}?dias={k}", aria_current="true" if k == str(n) else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == str(n) else "hover:bg-muted")) for k in PLAZOS],
                   A(UkIcon("download", height=14, width=14), "Llevar a mi calendario (.ics)", href=f"{base}.ics",
                     cls="inline-flex items-center gap-1 text-sm text-primary hover:underline ml-auto"),
                   cls="flex flex-wrap items-center gap-2 mb-4")
    return [filtros, *(bloques or [Card(P("No hay fechas en este periodo.", cls="text-sm"))])]
