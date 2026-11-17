"""Preparación del semestre (Dirección de Carrera y Coordinación académica): las etapas para que un
semestre arranque, con su avance, lo que falta y un enlace a donde se resuelve cada cosa."""
from datetime import date

import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Progress, TextPresets, UkIcon

from app.academico import gestiones, preparacion, semestre as ciclo
from app.academico.componentes import prepara_semestres
from app.academico.rutas.oferta import estado_insignia
from app.comun import formato, permisos, vinculos
from app.comun.componentes.etapas import etapas
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, mensaje_error, modal, pagina
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


def _estado_y_acciones(g, auth):
    """El estado de la gestión y lo que se puede hacer con él (activar, borrar); explica qué falta para activar."""
    if not g:
        return ""
    partes = [Div(estado_insignia(g), cls="mb-2")]
    if g["estado"] == "planificacion":
        falta, avisos = ciclo.bloqueos(g), ciclo.avisos(g)
        botones = []
        if permisos.puede(auth, "decidir_gestion"):
            botones.append(Button(UkIcon("play", height=14, width=14), "Activar el semestre",
                                  hx_post=f"{BASE}/{g['id']}/activar", hx_swap="none", disabled=bool(falta),
                                  hx_confirm=f"¿Activar {gestiones.codigo(g)}? A partir de ahora, los cambios en la oferta y "
                                             "en los docentes piden motivo y fecha de efecto, y quedan registrados.",
                                  cls=ButtonT.primary))
        if permisos.puede(auth, "gestionar_oferta"):
            botones.append(Button(UkIcon("trash-2", height=14, width=14), "Borrar la gestión",
                                  hx_post=f"{BASE}/{g['id']}/borrar", hx_swap="none",
                                  hx_confirm=f"¿Borrar la gestión {gestiones.codigo(g)} con toda su oferta y docentes? No se "
                                             "puede deshacer.", cls=(ButtonT.ghost, "text-destructive")))
        partes.append(Div(*botones, cls="flex flex-wrap gap-2 mb-2"))
        if falta:
            partes.append(Div(P("Para activarla falta:", cls="text-sm font-medium"),
                              Ul(*[Li(x, cls="text-sm") for x in falta], cls="list-disc pl-5"), cls="mb-2"))
        if avisos:
            partes.append(Div(P("Conviene revisar (no impide activarla):", cls="text-sm font-medium"),
                              Ul(*[Li(x, cls="text-sm") for x in avisos], cls="list-disc pl-5"), cls="mb-2"))
        if not permisos.puede(auth, "decidir_gestion"):
            partes.append(P("La activa la Dirección de Carrera.", cls=TextPresets.muted_sm))
    elif g["estado"] == "activa":
        partes.append(P(f"Activa desde el {formato.fecha((g['activada_en'] or g['fecha_inicio'])[:10])}: los cambios en la "
                        "oferta y en los docentes piden motivo y fecha de efecto.", cls=TextPresets.muted_sm))
        if permisos.puede(auth, "decidir_gestion"):
            terminado = g["fecha_fin"] < date.today().isoformat()
            partes.append(Div(Button(UkIcon("archive", height=14, width=14), "Concluir el semestre",
                                     hx_get=f"{BASE}/{g['id']}/concluir", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
                                     cls=ButtonT.primary if terminado else ButtonT.default),
                              P(f"Terminó el {formato.fecha(g['fecha_fin'])}: al concluirlo pasa al historial."
                                if terminado else f"Termina el {formato.fecha(g['fecha_fin'])}. Antes de esa fecha solo "
                                                  "se concluye con motivo.", cls=(TextPresets.muted_sm, "mt-1")),
                              cls="mt-2"))
    else:
        partes.append(P(f"Concluida el {formato.fecha((g['concluida_en'] or g['fecha_fin'])[:10])}: es parte del historial."
                        + (f" Motivo: {g['motivo_conclusion']}." if g["motivo_conclusion"] else ""),
                        cls=TextPresets.muted_sm))
        if permisos.puede(auth, "decidir_gestion"):
            partes.append(Button(UkIcon("rotate-ccw", height=14, width=14), "Reabrir para corregir",
                                 hx_get=f"{BASE}/{g['id']}/reabrir", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
                                 cls=(ButtonT.default, ButtonT.sm)))
    return Div(*partes, cls="mb-6")


def _form_motivo(g, url, titulo, texto, boton, obligatorio, errores=(), motivo=""):
    return modal(titulo, fh.Form(
        mensaje_error(*errores), P(texto, cls=(TextPresets.muted_sm, "mb-3")),
        campo("Motivo" + ("" if obligatorio else " (obligatorio si se concluye antes de su término)"),
              fh.Textarea(motivo, name="motivo", rows=3, cls="uk-textarea", required=obligatorio)),
        Div(Button(boton, type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=url, hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", hx_disabled_elt="find button[type='submit']",
        cls="space-y-3"), ancho="max-w-lg")


def _modal_concluir(g, errores=(), motivo=""):
    return _form_motivo(g, f"{BASE}/{g['id']}/concluir", f"Concluir {gestiones.codigo(g)}",
                        "Una gestión concluida pasa al historial y queda de solo lectura; la Dirección de Carrera puede "
                        "reabrirla si hay algo que corregir.", "Concluir el semestre", False, errores, motivo)


@rt(f"{BASE}/{{gid}}/concluir")
def get(auth, gid: int):
    if not permisos.puede(auth, "decidir_gestion"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "activa":
        return Response("No encontrado", status_code=404)
    return _modal_concluir(g)


@rt(f"{BASE}/{{gid}}/concluir")
def post(auth, sess, gid: int, motivo: str = ""):
    if not permisos.puede(auth, "decidir_gestion"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "activa":
        return Response("No encontrado", status_code=404)
    errores = ciclo.concluir(gid, motivo, auth["id"])
    if errores:
        return _modal_concluir(g, errores, motivo)
    add_toast(sess, f"{gestiones.codigo(g)} pasó al historial.", "success")
    return Redirect(f"{BASE}?semestre={gestiones.codigo(g)}")


def _modal_reabrir(g, errores=(), motivo=""):
    return _form_motivo(g, f"{BASE}/{g['id']}/reabrir", f"Reabrir {gestiones.codigo(g)}",
                        "La gestión vuelve a estar activa: los cambios piden motivo y fecha de efecto y quedan registrados. "
                        "Concluya de nuevo cuando termine la corrección.", "Reabrir", True, errores, motivo)


@rt(f"{BASE}/{{gid}}/reabrir")
def get(auth, gid: int):
    if not permisos.puede(auth, "decidir_gestion"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "concluida":
        return Response("No encontrado", status_code=404)
    return _modal_reabrir(g)


@rt(f"{BASE}/{{gid}}/reabrir")
def post(auth, sess, gid: int, motivo: str = ""):
    if not permisos.puede(auth, "decidir_gestion"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g or g["estado"] != "concluida":
        return Response("No encontrado", status_code=404)
    errores = ciclo.reabrir(gid, motivo, auth["id"])
    if errores:
        return _modal_reabrir(g, errores, motivo)
    add_toast(sess, f"{gestiones.codigo(g)} está activa otra vez.", "success")
    return Redirect(f"{BASE}?semestre={gestiones.codigo(g)}")


@rt(f"{BASE}/{{gid}}/activar")
def post(auth, sess, gid: int):
    if not permisos.puede(auth, "decidir_gestion"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g:
        return Response("No encontrado", status_code=404)
    errores = ciclo.activar(gid, auth["id"])
    if errores:
        add_toast(sess, errores[0], "error")
    else:
        add_toast(sess, f"{gestiones.codigo(g)} está activa.", "success")
    return Redirect(f"{BASE}?semestre={gestiones.codigo(g)}")


@rt(f"{BASE}/{{gid}}/borrar")
def post(auth, sess, gid: int):
    if not permisos.puede(auth, "gestionar_oferta"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g:
        return Response("No encontrado", status_code=404)
    error = gestiones.eliminar(gid, auth["id"])
    if error:
        add_toast(sess, error, "error")
        return Redirect(f"{BASE}?semestre={gestiones.codigo(g)}")
    add_toast(sess, f"Gestión {gestiones.codigo(g)} borrada.", "success")
    return Redirect("/docencia/gestiones")


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
    cuando = (f"{gestiones.nombre(g)} · {'empezó' if est['empezado'] else 'empieza'} el {formato.fecha(g['fecha_inicio'])}" if g
              else f"{gestiones.TIPOS[tipo]} {anio} · aún sin gestión creada")
    return pagina(
        "Preparación del semestre",
        Div(Div(H2(f"Preparación de {est['codigo']}"),
                P(cuando, cls=TextPresets.muted_sm),
                P({"planificacion": "Lo necesario para que el semestre arranque: gestión, oferta, contratos, docentes y "
                                    "carga. Cada etapa enlaza a donde se resuelve. Cuando está lista, la Dirección de "
                                    "Carrera activa el semestre.",
                   "activa": "El semestre está en marcha. Esto es el estado de su planificación; los cambios con motivo se "
                             "registran en «Oferta y docentes».",
                   "concluida": "Historial: así quedó la planificación del semestre."}[g["estado"] if g else "planificacion"],
                  cls=TextPresets.muted_sm)),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        _estado_y_acciones(g, auth),
        Card(Div(Span(f"{est['hechas']} de {est['total']} etapas listas", cls="text-sm font-medium"),
                 Span("El semestre está listo." if est["hechas"] == est["total"] else "", cls="text-sm text-green-700 dark:text-green-400"),
                 cls="flex flex-wrap justify-between gap-2 mb-4"),
             etapas([{"titulo": e["titulo"], "estado": e["estado"], "detalle": e["detalle"],
                      "href": e["href"] if _puede(auth, ACCION[e["clave"]][1]) else None} for e in est["etapas"]],
                    etiqueta=f"Etapas de la preparación de {est['codigo']}"),
             cls="mb-6"),
        Div(*[_tarjeta(e, auth) for e in est["etapas"]], cls="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"),
        usuario=auth, seccion="docencia")
