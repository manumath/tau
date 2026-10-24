"""Inicio (PLAN.md §54): una sola bandeja de pendientes, con un subtítulo por rol (lo que requiere atención, con
enlace directo), y una fila de cifras con enlace. Los accesos a los módulos los da el menú lateral: el inicio no
los repite."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, Div, Li, P, Span, Ul
from monsterui.all import H2, H3, Card, TextPresets, UkIcon

from app.academico import carga, gestiones, preparacion
from app.academico.componentes import tiene_docencia
from app.acreditacion import anexo, calidad
from app.comun import estudiantes, permisos, vinculos
from app.estudiantil import actividad as actividad_estudiantil, tutoria
from app.comun.db import get_db
from app.investigacion import filiacion, institucionales, perfiles, productos, proyectos
from app.comun.componentes.layout import pagina

rt = APIRouter()

def _cifra(valor, texto, href=None):
    contenido = (Span(str(valor), cls="text-2xl font-semibold tabular-nums"), Span(texto, cls=TextPresets.muted_sm))
    cls = "flex flex-col rounded-lg border border-border px-4 py-3"
    return A(*contenido, href=href, cls=cls + " hover:bg-muted") if href else Div(*contenido, cls=cls)


def _cifras_mias(auth):
    """Para quien investiga: su producción del año, sus proyectos y su perfil."""
    if not auth["es_investigador"]:
        return None
    uid, anio = auth["id"], date.today().year
    del_anio = [p for p in productos.buscar(uid) if p["anio"] == anio]  # para contar basta año, revisión y estado
    mios = [p for p in proyectos.de_investigador(uid) if p["vigente"] and p["estado"] != "finalizado"]
    pct, _ = perfiles.completitud(perfiles.obtener(uid), len(perfiles.areas(uid)))
    return ("Mi producción", [
        _cifra(len(del_anio), f"productos en {anio}", "/productos"),
        _cifra(sum(productos.cuenta_para_informe(p) for p in del_anio), "cuentan para el informe", "/productos?informe=1"),
        _cifra(len(mios), "proyectos vigentes", "/proyectos"),
        _cifra(f"{pct} %", "perfil completo", "/perfil")])


def _cifras_acreditacion(auth):
    """Quien ve los informes institucionales: el cuerpo académico del año."""
    if not permisos.puede(auth, "ver_informes_institucionales"):
        return None
    anio = date.today().year
    cuerpo = anexo.cuerpo_academico(anio, date.today().isoformat())
    vigentes = get_db().q("SELECT COUNT(*) n FROM proyecto WHERE estado = 'vigente'")[0]["n"]
    return (f"Acreditación · {anio}", [
        _cifra(cuerpo["total"], "académicos vinculados", "/informes/cuerpo-academico"),
        _cifra(cuerpo["jce"], "jornadas completas eq.", "/informes/cuerpo-academico"),
        _cifra(vigentes, "proyectos vigentes", "/informes/memoria"),
        _cifra("Anexo", "de I+D+i", "/informes/acreditacion")])


# --- Para hoy ---------------------------------------------------------------------------------------

def _plural(n, singular, plural=None):
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _item(texto, href, tono="ambar", detalle=None):
    color = {"ambar": "text-amber-600", "rojo": "text-red-600", "info": "text-primary"}[tono]
    return Li(A(Div(UkIcon("circle-alert" if tono != "info" else "info", height=16, width=16, cls=f"shrink-0 mt-0.5 {color}"),
                    Div(Span(texto, cls="text-sm"),
                        P(detalle, cls=TextPresets.muted_sm) if detalle else "", cls="min-w-0"),
                    UkIcon("chevron-right", height=14, width=14, cls="ml-auto shrink-0 mt-0.5 text-muted-foreground"),
                    cls="flex items-start gap-2"),
                href=href, cls="block rounded px-2 py-2 hover:bg-muted"))


def _grupo(icono, titulo, items):
    """Una sección de la bandeja: (icono, título, ítems no vacíos)."""
    return (icono, titulo, [x for x in items if x])


def _nombres(filas, n=3):
    nombres = [f"{f['nombres']} {f['apellidos']}" for f in filas[:n]]
    return ", ".join(nombres) + (f" y {len(filas) - n} más" if len(filas) > n else "")


def _para_carrera(auth):
    """Dirección de Carrera y Coordinación académica: el semestre y los vínculos."""
    dirige = permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())
    if not (dirige or permisos.puede(auth, "gestionar_oferta")):
        return None
    g = carga.semestre_de_referencia()
    items = []
    if g:
        sin_docente = get_db().q(
            """SELECT COUNT(*) n FROM oferta o WHERE o.gestion_id = ? AND NOT EXISTS (
                   SELECT 1 FROM oferta_docente d WHERE d.oferta_id = o.id AND d.rol = 'titular')""", [g["id"]])[0]["n"]
        if sin_docente:
            items.append(_item(f"{_plural(sin_docente, 'materia')} sin docente titular en {gestiones.codigo(g)}",
                               f"/docencia/oferta?gestion={g['id']}"))
        if dirige:
            revisar = [x for x in carga.personas(g) if x["avisos"]]
            if revisar:
                items.append(_item(f"{_plural(len(revisar), 'docente')} con la carga de {gestiones.codigo(g)} por revisar",
                                   f"/docencia/carga?gestion={g['id']}", detalle=_nombres(revisar)))
    prox = preparacion.estado(*preparacion.semestre_siguiente())
    if prox["hechas"] < prox["total"]:
        falta = next(e for e in prox["etapas"] if not e["listo"])
        items.append(_item(f"Preparación de {prox['codigo']}: {prox['hechas']} de {prox['total']} etapas listas",
                           f"/docencia/preparacion?semestre={prox['codigo']}", tono="info",
                           detalle=f"Siguiente: {falta['falta']}."))
    if dirige:
        vencen = carga.contratos_por_vencer(30)
        if vencen:
            items.append(_item(f"{_plural(len(vencen), 'vínculo')} termina{'n' if len(vencen) != 1 else ''} en los "
                               "próximos 30 días sin un periodo nuevo registrado", "/docencia/renovaciones",
                               detalle="; ".join(f"{f['nombres']} {f['apellidos']} ({f['fecha_fin']})" for f in vencen[:4])))
        sin_carga = carga.vigentes_sin_carga()
        if sin_carga:
            items.append(_item(f"{_plural(len(sin_carga), 'docente')} con vínculo vigente sin carga contratada",
                               "/admin/usuarios", detalle=_nombres(sin_carga)))
    return _grupo("graduation-cap", "Dirección de Carrera" if dirige else "Docencia", items)


def _para_instituto(auth):
    """Dirección del Instituto: el ciclo de vida de los proyectos institucionales."""
    if not permisos.puede(auth, "decidir_propuestas"):
        return None
    items = []
    n = institucionales.n_por_decidir()
    if n:
        items.append(_item(f"{_plural(n, 'propuesta')} institucional{'es' if n != 1 else ''} por decidir",
                           "/admin/propuestas"))
    hoy = date.today()
    terminan = get_db().q(
        """SELECT id, nombre, fecha_fin FROM proyecto WHERE tipo = 'institucional' AND estado = 'vigente'
           AND fecha_fin BETWEEN ? AND ? ORDER BY fecha_fin""", [hoy.isoformat(), (hoy + timedelta(days=60)).isoformat()])
    if terminan:
        items.append(_item(f"{_plural(len(terminan), 'proyecto')} institucional{'es' if len(terminan) != 1 else ''} "
                           "termina en los próximos 60 días", "/proyectos", tono="info",
                           detalle="; ".join(f"{p['nombre']} ({p['fecha_fin']})" for p in terminan[:3])))
    sin_vinculo = get_db().q("""SELECT COUNT(*) n FROM aviso_carga WHERE tipo = 'desvinculado'
                                AND atendido_en IS NULL""")[0]["n"]
    if sin_vinculo:
        items.append(_item(f"{_plural(sin_vinculo, 'participante')} con carga en proyectos quedó sin vínculo "
                           "(lo atiende cada responsable)", "/proyectos", tono="info"))
    sin_filiacion = get_db().q(
        """SELECT COUNT(DISTINCT p.id) n FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
           WHERE pa.investigador_id IS NOT NULL AND pa.filiacion_instituto IS NULL
             AND p.revision IN ('indexado', 'arbitrado')""")[0]["n"]
    if sin_filiacion:
        items.append(_item(f"{_plural(sin_filiacion, 'publicación', 'publicaciones')} sin filiación declarada: "
                           "no cuentan en la memoria hasta que sus autores la declaren", "/informes/memoria"))
    return _grupo("landmark", "Dirección del Instituto", items)


def _para_mi(auth):
    """Lo que le toca a la persona: revisar, corregir, declarar y su docencia."""
    uid, items = auth["id"], []
    if auth["es_investigador"]:
        n = proyectos.n_pendientes_para(auth)
        if n:
            items.append(_item(f"{_plural(n, 'pendiente')} por revisar en sus proyectos", "/proyectos"))
        condicionales = [x for x in proyectos.mis_propuestas(uid) if x["estado"] == "condicional"]
        if condicionales:
            items.append(_item("Propuesta aceptada con condiciones: corríjala y reenvíela",
                               f"/propuestas/{condicionales[0]['id']}", detalle=condicionales[0]["nombre"]))
        sin_fil = filiacion.pendientes(uid)
        if sin_fil:
            items.append(_item(f"{_plural(sin_fil, 'publicación', 'publicaciones')} sin filiación declarada",
                               "/productos?sin_filiacion=1"))
        periodo = institucionales.periodo_abierto()
        if periodo is not None and institucionales.puede_proponer(auth):
            items.append(_item(f"Convocatoria de proyectos institucionales {institucionales.periodo_texto(periodo)} "
                               f"abierta hasta el {institucionales.fecha_texto(institucionales.plazo(periodo)['cierra'])}",
                               "/proyectos", tono="info"))
    if tiene_docencia(auth):
        g = carga.semestre_de_referencia()
        if g:
            r = carga.resumen(uid, g)
            n = len(carga.materias_con_detalle(uid, g["id"]))
            items.append(_item(f"{gestiones.codigo(g)}: {_plural(n, 'materia')}"
                               + (f" · {r['contratada']} h/mes contratadas" if r["contratada"] else ""),
                               "/docencia/mia", tono="ambar" if r["avisos"] else "info",
                               detalle=r["avisos"][0] if r["avisos"] else None))
    return _grupo("list-checks", "Lo mío", items) if items or auth["es_investigador"] else None


def _para_estudiantes(auth):
    """El tutor: tutorados sin reuniones. La Dirección de Carrera y la Coordinación: actividad estudiantil por
    verificar."""
    items = []
    if estudiantes.es_tutor(auth["id"]):
        sin = [t for t in tutoria.tutorados(auth["id"]) if not t["reuniones"]]
        if sin:
            items.append(_item(f"{_plural(len(sin), 'tutorado')} sin reuniones registradas", "/tutoria",
                               detalle=_nombres(sin)))
    if permisos.puede(auth, "verificar_actividad", vinculos.carrera()):
        n = actividad_estudiantil.n_pendientes()
        if n:
            items.append(_item(f"{_plural(n, 'actividad estudiantil', 'actividades estudiantiles')} por verificar",
                               "/docencia/cohortes/actividades"))
    return _grupo("users-round", "Estudiantes", items) if items else None


def _para_fichas(auth):
    """Gestión de datos (y quien gestiona fichas sin otra bandeja que lo muestre): académicos sin grado."""
    if not permisos.puede(auth, "gestionar_fichas") or permisos.puede(auth, "ver_calidad_datos"):
        return None   # las direcciones lo ven en «Calidad de datos»
    c = calidad.sin_grado()
    return _grupo("id-card", "Fichas académicas", [
        _item(f"{_plural(c['n'], 'académico vinculado', 'académicos vinculados')} sin grado registrado", "/admin/usuarios",
              detalle=_nombres([{"nombres": i["texto"].split(", ")[-1], "apellidos": i["texto"].split(", ")[0]}
                                for i in c["items"]]))] if c["n"] else [])


def _para_calidad(auth):
    """Quien ve la calidad de datos: cuántos registros quedan por completar (enlace al tablero)."""
    if not permisos.puede(auth, "ver_calidad_datos"):
        return None
    r = calidad.resumen()
    item = _item(f"{_plural(r['registros'], 'registro')} por completar en {r['con_observaciones']} de "
                 f"{r['chequeos']} revisiones", "/informes/calidad",
                 detalle="Antes de generar la memoria o el anexo.") if r["registros"] else None
    return _grupo("list-checks", "Calidad de datos", [item])


def _bandeja(secciones):
    """Todos los pendientes en una tarjeta: un subtítulo por rol, o «Todo al día»."""
    con_algo = [(i, t, items) for i, t, items in secciones if items]
    if not con_algo:
        return Card(P(UkIcon("circle-check", height=18, width=18, cls="inline mr-2 text-green-600"),
                      "Todo al día: no tiene pendientes.", cls="text-sm"))
    bloques = [Div(Div(UkIcon(icono, height=16, width=16, cls="text-primary"),
                       H3(titulo, cls="text-xs font-semibold uppercase tracking-wide text-muted-foreground"),
                       cls="flex items-center gap-2 px-2"),
                   Ul(*items, cls="mt-1"), cls="py-3 first:pt-0 last:pb-0")
               for icono, titulo, items in con_algo]
    return Card(Div(*bloques, cls="divide-y divide-border -mx-2"))


@rt("/")
def get(auth):
    secciones = [x for x in (_para_mi(auth), _para_carrera(auth), _para_instituto(auth), _para_estudiantes(auth),
                             _para_fichas(auth), _para_calidad(auth)) if x]
    cifras = [x for x in (_cifras_mias(auth), _cifras_acreditacion(auth)) if x]
    return pagina(
        "Inicio",
        Div(H2(f"Hola, {auth['nombres']}"), P("Lo que requiere su atención.", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Div(H3("Pendientes", cls="text-base font-semibold mb-3"), _bandeja(secciones), cls="mb-8 max-w-3xl"),
        *[Div(H3(titulo, cls="text-base font-semibold mb-3"), Div(*tiles, cls="grid grid-cols-2 md:grid-cols-4 gap-3"),
              cls="mb-8 max-w-3xl") for titulo, tiles in cifras],
        usuario=auth, seccion="inicio")
