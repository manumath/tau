"""Preparación del semestre (Dirección de Carrera y Coordinación académica): las etapas para que un
semestre arranque, con su avance, lo que falta y un enlace a donde se resuelve cada cosa."""
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Response, Select, Span, Ul
from monsterui.all import H2, H3, Card, Progress, TextPresets, UkIcon

from app.academico import gestiones, preparacion
from app.academico.componentes import prepara_semestres
from app.comun import permisos, vinculos
from app.comun.componentes.etapas import etapas
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
BASE = "/docencia/preparacion"
MAX_PENDIENTES = 8
# Qué se hace en cada etapa y con qué permiso (sin él, se indica quién lo hace).
ACCION = {"gestion": ("Crear las gestiones", "gestionar_oferta"), "oferta": ("Ir a la oferta", "gestionar_oferta"),
          "contratos": ("Renovar contratos", "gestionar_vinculos"), "docentes": ("Asignar en grilla", "gestionar_oferta"),
          "carga": ("Ver la carga horaria", "ver_carga")}


def puede_ver(auth) -> bool:
    return prepara_semestres(auth)


def _puede(auth, accion):
    return permisos.puede(auth, accion, vinculos.carrera() if accion == "gestionar_vinculos" else None)


def _semestre(texto: str) -> tuple[int, str]:
    tipo, _, anio = (texto or "").upper().rpartition("-")
    elegibles = preparacion.semestres_elegibles()
    if anio.isdigit() and (int(anio), tipo) in elegibles:
        return int(anio), tipo
    return preparacion.semestre_siguiente()


def _tarjeta(e, auth):
    texto, accion = ACCION[e["clave"]]
    tono, etiqueta = {"hecho": ("verde", "Lista"), "actual": ("ambar", "En curso"),
                      "pendiente": ("gris", "Pendiente")}[e["estado"]]
    if e["bloqueada"]:
        etiqueta = "Espera la etapa anterior"
    resto = len(e["pendientes"]) - MAX_PENDIENTES
    return Card(
        Div(H3(e["titulo"], cls="text-base font-semibold"), insignia(etiqueta, tono), cls="flex items-center justify-between gap-2"),
        P(e["detalle"], cls="text-sm"),
        Progress(value=e["hechos"], max=e["total"], aria_label=e["titulo"], cls="mt-1") if e["total"] else "",
        Ul(*[Li(x, cls="text-sm") for x in e["pendientes"][:MAX_PENDIENTES]],
           Li(f"… y {resto} más.", cls=TextPresets.muted_sm) if resto > 0 else "",
           cls="list-disc pl-5 space-y-0.5") if e["pendientes"] else "",
        (A(texto, UkIcon("arrow-right", height=14, width=14), href=e["href"],
           cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")
         if _puede(auth, accion) else P("Lo hace la Dirección de Carrera.", cls=TextPresets.muted_sm))
        if e["href"] and not e["listo"] else "",
        cls="space-y-2")


@rt(BASE)
def get(auth, semestre: str = ""):
    if not puede_ver(auth):
        return Response("No autorizado", status_code=403)
    anio, tipo = _semestre(semestre)
    est = preparacion.estado(anio, tipo)
    g = est["gestion"]
    selector = Select(*[Option(f"{t}-{a}", value=f"{t}-{a}", selected=(a, t) == (anio, tipo))
                        for a, t in preparacion.semestres_elegibles()],
                      aria_label="Semestre", cls="uk-select w-36", data_navegar=f"{BASE}?semestre=")
    cuando = (f"{gestiones.nombre(g)} · {'empezó' if est['empezado'] else 'empieza'} el {g['fecha_inicio']}" if g
              else f"{gestiones.TIPOS[tipo]} {anio} · aún sin gestión creada")
    return pagina(
        "Preparación del semestre",
        Div(Div(H2(f"Preparación de {est['codigo']}"),
                P(cuando, cls=TextPresets.muted_sm),
                P("Lo necesario para que el semestre arranque: gestión, oferta, contratos, docentes y carga. Cada "
                  "etapa enlaza a donde se resuelve; esta página no cambia nada.", cls=TextPresets.muted_sm)),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(Div(Span(f"{est['hechas']} de {est['total']} etapas listas", cls="text-sm font-medium"),
                 Span("El semestre está listo." if est["hechas"] == est["total"] else "", cls="text-sm text-green-700"),
                 cls="flex flex-wrap justify-between gap-2 mb-4"),
             etapas([{"titulo": e["titulo"], "estado": e["estado"], "detalle": e["detalle"],
                      "href": e["href"] if _puede(auth, ACCION[e["clave"]][1]) else None} for e in est["etapas"]],
                    etiqueta=f"Etapas de la preparación de {est['codigo']}"),
             cls="mb-6"),
        Div(*[_tarjeta(e, auth) for e in est["etapas"]], cls="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"),
        usuario=auth, seccion="docencia")
