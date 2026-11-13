"""«Mi historial docente» y certificados de tribunal y tutoría (PLAN §68, etapa 6). Solo lo propio: la persona sale de la sesión.
Verificar un código es de quien ve la carga horaria (las direcciones y la Comisión de calidad)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, P, Response, Span, Ul
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import historial
from app.comun import config, formato, permisos
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/docencia/historial"
CERT = "/docencia/certificados"
ROLES = {"titular": "Titular", "auxiliar": "Auxiliar"}


def _lista(titulo, filas, vacio):
    return Card(H3(titulo, cls="text-base font-semibold"),
                Ul(*filas, cls="mt-2 divide-y divide-border") if filas else P(vacio, cls=(TextPresets.muted_sm, "mt-2")))


@rt(BASE)
def get(auth):
    h = historial.historial(auth["id"])
    from app.servicios import grado
    por_gestion: dict[str, list] = {}
    for m in h["materias"]:
        por_gestion.setdefault(m["gestion"], []).append(m)
    materias = [Li(Div(Span(g, cls="text-sm font-medium w-24 shrink-0"),
                       Div(*[Div(Span(m["sigla"], cls="font-mono text-sm"), Span(f" {m['nombre']} · paralelo {m['paralelo']} · "
                                                                                  f"{ROLES[m['rol']].lower()}", cls="text-sm"),
                                 Span(" · retirada", cls=TextPresets.muted_sm) if m["retirada"] else "") for m in ms]),
                       cls="flex gap-3 py-2")) for g, ms in por_gestion.items()]

    def tramite(t):
        return Li(Div(Span(f"{grado.TIPOS[t['tipo']]} · {t['nombres']} {t['apellidos']}", cls="text-sm"),
                      Div(t["titulo"], cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                  insignia(grado.ESTADOS[t["estado"]], "verde" if t["estado"] in ("aprobado", "defendido") else "gris"),
                  cls="flex items-center gap-3 py-2")
    t = h["tutorados"]
    return pagina(
        "Mi historial docente", H2("Mi historial docente"),
        P("Lo que ha hecho en la Carrera, reunido de lo que ya está en el sistema: materias, tutorías y tribunales de grado, "
          "auxiliaturas y proyectos. Solo usted lo ve.", cls=(TextPresets.muted_sm, "mb-2 max-w-3xl")),
        Div(A(UkIcon("award", height=14, width=14), "Mis certificados", href=CERT,
              cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"), cls="mb-4"),
        Div(_lista("Materias dictadas", materias, "Aún no dictó materias en la Carrera."),
            _lista("Tutorías de grado", [tramite(x) for x in h["tutor"]], "No tuteló proyectos de grado."),
            _lista("Tribunales de grado", [tramite(x) for x in h["tribunal"]], "No integró tribunales de grado."),
            _lista("Tribunales de auxiliaturas",
                   [Li(Span(f"{i['convocatoria']}", cls="text-sm"), Span(f" · {i['mi_tipo']}", cls=TextPresets.muted_sm), cls="py-2")
                    for i in h["auxiliaturas"]], "No integró tribunales de auxiliaturas."),
            _lista("Proyectos de investigación e interacción social",
                   [Li(A(p["nombre"], href=f"/proyectos/{p['id']}", cls="text-sm hover:underline"),
                       Span(f" · {p['rol'].replace('_', ' ')} · {formato.fecha(p['fecha_desde'])}"
                            + (f" a {formato.fecha(p['fecha_hasta'])}" if p["fecha_hasta"] else ""), cls=TextPresets.muted_sm), cls="py-2")
                    for p in h["proyectos"]], "No participó en proyectos."),
            Card(H3("Tutoría de estudiantes", cls="text-base font-semibold"),
                 P(f"{t['total']} estudiante(s) tutelados en total, {t['vigentes']} vigentes. Lo que se habló en las reuniones es "
                   "confidencial y no aparece aquí.", cls="text-sm mt-1")), cls="space-y-4"),
        usuario=auth, seccion="docencia")


def _certificado_lista(auth):
    certs = historial.elegibles(auth["id"])
    filas = [Li(Div(Div(f"{TIPOS[c['tipo']]}: {c['titulo']}", cls="text-sm font-medium"),
                    Div(c["detalle"] + (f" · {formato.fecha(c['fecha'])}" if c["fecha"] else ""), cls=TextPresets.muted_sm),
                    cls="min-w-0 flex-1"),
                A("Ver y imprimir", href=f"{CERT}/{c['tipo']}/{c['ref']}", cls="text-sm text-primary hover:underline"),
                cls="flex items-center gap-3 py-2") for c in certs]
    return pagina(
        "Mis certificados", A(UkIcon("arrow-left", height=14, width=14), "Mi historial", href=BASE,
                              cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Mis certificados"),
        P("Constancias de tutorías y tribunales de grado concluidos y de tribunales de auxiliaturas de convocatorias concluidas. Cada una "
          "lleva un código que la Dirección de Carrera puede verificar.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(Ul(*filas, cls="divide-y divide-border")) if filas else Card(P("Aún no tiene trámites concluidos para certificar.", cls="text-sm")),
        P(A("Verificar un código", href=f"{CERT}/verificar", cls="text-sm text-primary hover:underline"), cls="mt-4")
        if permisos.puede(auth, "ver_carga") else "", usuario=auth, seccion="docencia")


TIPOS = historial.TIPOS_CERT


@rt(CERT)
def get(auth):
    return _certificado_lista(auth)


@rt(f"{CERT}/verificar")
def get(auth, codigo: str = ""):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    c = historial.verificar(codigo) if codigo else None
    if codigo:
        auditar(auth["id"], "verificar_certificado_docente", "certificado", None, "válido" if c else "no encontrado")
    return pagina(
        "Verificar un certificado", A(UkIcon("arrow-left", height=14, width=14), "Mis certificados", href=CERT,
                                      cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Verificar un certificado"),
        fh.Form(Input(name="codigo", value=codigo, placeholder="TAU-XXXXXXXXXX", cls="uk-input w-64", aria_label="Código del certificado"),
                Button("Verificar", type="submit", cls=ButtonT.primary), method="get", action=f"{CERT}/verificar",
                cls="flex flex-wrap items-center gap-2 mb-4"),
        Card(P(f"Certificado válido: {c['persona']} · {TIPOS[c['tipo']]} · «{c['titulo']}» ({c['detalle']})"
               + (f", {formato.fecha(c['fecha'])}" if c["fecha"] else "") + ".", cls="text-sm")) if c
        else (Card(P("No existe un certificado con ese código.", cls="text-sm")) if codigo else ""),
        usuario=auth, seccion="docencia")


@rt(f"{CERT}/{{tipo}}/{{ref}}")
def get(auth, tipo: str, ref: int):
    c = historial.obtener_cert(auth["id"], tipo, ref)
    if not c:
        return Response("No encontrado", status_code=404)
    nombre = f"{auth['nombres']} {auth['apellidos']}"
    if tipo == "tutor_grado":
        texto = f"fue tutor(a) del {c['clase'].lower()} «{c['titulo']}» (estudiante: {c['estudiante']}), con estado: {c['estado'].lower()}"
    elif tipo == "tribunal_grado":
        texto = f"integró el tribunal del {c['clase'].lower()} «{c['titulo']}» (estudiante: {c['estudiante']}), con estado: {c['estado'].lower()}"
    else:
        texto = f"integró el tribunal de la convocatoria a auxiliaturas «{c['titulo']}» ({c['detalle'].lower()})"
    return pagina(
        "Certificado",
        Div(fh.Button(UkIcon("printer", height=14, width=14), "Imprimir", type="button", data_accion="imprimir",
                      cls="uk-btn uk-btn-default uk-btn-sm gap-1 no-imprimir"), cls="flex justify-end"),
        Div(P(config.UNIVERSIDAD, cls="font-semibold"), P(config.FACULTAD), P(config.NOMBRE_CARRERA), cls="text-center text-sm"),
        H2("Certificado", cls="text-center mt-6"),
        P("Se certifica que", cls="text-center mt-6"), P(nombre, cls="text-center text-2xl font-semibold my-2"),
        P(texto + (f", el {formato.fecha(c['fecha'])}" if c["fecha"] else "") + ".", cls="text-center max-w-2xl mx-auto"),
        P(f"Código de verificación: {c['codigo']}", cls=(TextPresets.muted_sm, "text-center mt-10")),
        P(f"Emitido por {config.NOMBRE_SISTEMA}; la Dirección de Carrera puede verificar el código.",
          cls=(TextPresets.muted_sm, "text-center")), usuario=auth, seccion="docencia")
