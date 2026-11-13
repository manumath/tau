"""«Mi plan de estudios» del estudiante (PLAN §67, etapa 1): la malla de su plan, con lo que marcó como aprobado, solo como
ayuda personal. Solo ve y marca lo suyo: la ficha sale de su cuenta, nunca de la dirección."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Li, P, Response, Span, Ul
from monsterui.all import H2, H3, Button, ButtonT, Card, Progress, TextPresets, UkIcon

from app.academico import planes, programas
from app.comun.componentes.layout import pagina
from app.comun.db import get_db
from app.comun.componentes.registros import insignia
from app.estudiantil import mi_plan
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
BASE = "/estudiante/plan"
ID = "mi-plan"
ESTADOS = {"aprobada": ("verde", "Aprobada", "check"), "disponible": ("azul", "Puede cursarla", "arrow-right"),
           "bloqueada": ("gris", "Le falta un requisito", "lock")}


def _horas(f, sistema):
    if sistema == "creditos":
        return f"{f['creditos']} créditos" if f["creditos"] else ""
    h = [f["horas_teoricas"], f["horas_practicas"], f["horas_laboratorio"]]
    return " + ".join(str(x) for x in h if x) + " h/sem" if any(h) else ""


def _fila(f, plan, con_programa=frozenset()):
    if f["asignatura_id"] is None:
        return Li(Span(planes.TIPOS[f["tipo"]], cls="italic text-sm"), Span(" · se llena con una electiva",
                                                                              cls=TextPresets.muted_sm),
                  cls="py-2")
    tono, texto, icono = ESTADOS[f["estado"]]
    marca = Button(UkIcon("circle-check" if f["estado"] == "aprobada" else "circle", height=18, width=18),
                   type="button", cls=(ButtonT.ghost, ButtonT.icon), role="switch",
                   aria_checked="true" if f["estado"] == "aprobada" else "false",
                   aria_label=f"Aprobada: {f['sigla']} {f['nombre']}", hx_post=f"{BASE}/marca/{f['asignatura_id']}",
                   hx_target=f"#{ID}", hx_swap="outerHTML")
    req = f"Requisitos: {', '.join(f['requisitos'])}" if f["requisitos"] else ""
    return Li(marca, Div(Div(Span(f["sigla"], cls="font-mono text-sm"), Span(f["nombre"], cls="text-sm font-medium")
                             , cls="flex flex-wrap gap-x-2"),
                         Div(" · ".join(x for x in (_horas(f, plan["sistema"]), req) if x), cls=TextPresets.muted_sm),
                         fh.A("Ver el programa", href=f"/estudiante/programa/{f['asignatura_id']}",
                              cls="text-xs text-primary hover:underline") if f["asignatura_id"] in con_programa else "",
                         cls="min-w-0 flex-1"),
              insignia(texto, tono, icono=icono), cls="flex items-center gap-2 py-1.5")


def contenido(externo, plan):
    av = mi_plan.avance(externo, plan)
    compartido = mi_plan.comparte(externo)
    con_programa = programas.con_programa()
    semestres = [Card(H3(f"{planes.ORDINALES[s['semestre']]} semestre" + (f" · ciclo {s['ciclo']}" if s["ciclo"] else ""),
                         cls="text-base font-semibold mb-1"),
                      Ul(*[_fila(f, plan, con_programa) for f in s["filas"]], cls="divide-y divide-border")) for s in av["semestres"]]
    electivas = [Card(H3("Asignaturas electivas", cls="text-base font-semibold mb-1"),
                      P("Marque las que aprobó.", cls=(TextPresets.muted_sm, "mb-1")),
                      Ul(*[_fila(f, plan, con_programa) for f in av["electivas"]], cls="divide-y divide-border"))] if av["electivas"] else []
    return Div(
        Card(Div(Span(f"{av['hechas']} de {av['obligatorias']} obligatorias aprobadas", cls="font-medium"),
                 Span(f"{av['pct']} %", cls="text-2xl font-semibold tabular-nums"),
                 cls="flex items-baseline justify-between gap-2"),
             Progress(value=av["hechas"], max=max(av["obligatorias"], 1), aria_label="Avance en las obligatorias",
                      cls="my-2"),
             P(f"Electivas aprobadas: {av['electivas_aprobadas']}.", cls=TextPresets.muted_sm),
             Div(H3("Puede cursar ahora", cls="text-sm font-semibold mt-3"),
                 P(", ".join(f"{f['sigla']} {f['nombre']}" for f in av["disponibles"][:12])
                   + ("…" if len(av["disponibles"]) > 12 else ""), cls="text-sm")) if av["disponibles"] else ""),
        Card(fh.Form(
            fh.Label(fh.Input(type="checkbox", name="comparte", value="1", checked=compartido or None, cls="uk-checkbox"),
                     Span("Compartir mi avance con mi tutor(a)", cls="text-sm font-medium"), cls="flex items-center gap-2"),
            P("Si lo activa, su tutor(a) ve cuántas obligatorias aprobó y cuáles puede cursar, en las reuniones de tutoría. "
              "Nadie más lo ve, nunca.", cls=TextPresets.muted_sm),
            Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
            hx_post=f"{BASE}/compartir", hx_target=f"#{ID}", hx_swap="outerHTML", cls="space-y-2")),
        *semestres, *electivas, id=ID, cls="space-y-4")


@rt(BASE)
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    plan = mi_plan.plan_de(externo)
    return pagina(
        "Mi plan de estudios",
        H2("Mi plan de estudios"),
        P("Es una ayuda personal: TAU no tiene sus notas ni sus materias cursadas. Marque lo que aprobó para ver su avance y "
          "qué puede cursar. Solo usted lo ve (y su tutor(a), si usted lo decide). Lo oficial lo emite Kardex.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        P(f"{plan['programa']} · {plan['nombre']}" + (f" · {plan['resolucion']}" if plan["resolucion"] else ""),
          cls="font-medium mb-4") if plan else "",
        contenido(externo, plan) if plan else Card(P("Su plan de estudios todavía no está registrado en TAU. Avise a la "
                                                      "Dirección de Carrera para que lo registre.", cls="text-sm")),
        usuario=auth)


@rt(f"{BASE}/marca/{{aid}}")
def post(auth, aid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    plan = mi_plan.plan_de(externo)
    if not plan or mi_plan.marcar(externo, aid, plan["id"]) is None:
        return Response("No encontrado", status_code=404)
    return contenido(externo, plan)


@rt(f"{BASE}/compartir")
def post(auth, comparte: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    plan = mi_plan.plan_de(externo)
    mi_plan.fijar_comparte(externo, comparte == "1")
    return contenido(externo, plan) if plan else Response("No encontrado", status_code=404)


@rt("/estudiante/programa/{aid}")
def get(auth, aid: int):
    """El programa analítico vigente de una asignatura (información pública de la materia, no personal)."""
    from app.academico.rutas.programas import lectura
    externo, error = _requiere(auth)
    if error:
        return error
    p = programas.vigente(aid)
    a = get_db().q("SELECT sigla, nombre FROM asignatura WHERE id = ?", [aid])
    if not p or not a:
        return Response("Esta materia aún no tiene un programa publicado.", status_code=404)
    return pagina(f"Programa de {a[0]['sigla']}", Div(fh.A(UkIcon("arrow-left", height=14, width=14), "Mi plan de estudios", href=BASE,
                                                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4")),
                  H2(f"{a[0]['sigla']} · {a[0]['nombre']}"),
                  P(f"Programa de la gestión {p['tipo']}-{p['anio']}, versión {p['version']}, de {p['nombres']} {p['apellidos']}.",
                    cls=(TextPresets.muted_sm, "mb-4")), lectura(p), usuario=auth)
