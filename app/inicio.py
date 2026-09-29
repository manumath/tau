"""Inicio: «Para hoy» según el rol (lo que requiere atención, con enlace directo) y los accesos a
los módulos con el estado del perfil."""
from datetime import date, timedelta

from fasthtml.common import A, APIRouter, Div, Li, P, Span, Ul
from monsterui.all import H2, H3, H4, Card, Grid, Label, LabelT, Progress, TextPresets, UkIcon

from app.academico import carga, gestiones
from app.academico.componentes import tiene_docencia
from app.acreditacion import anexo, calidad
from app.comun import permisos, vinculos
from app.comun.db import get_db
from app.investigacion import actividades, filiacion, institucionales, perfiles, productos, proyectos
from app.comun.componentes.layout import pagina

rt = APIRouter()

# (icono, título, descripción, fase en que se habilita, enlace si ya está disponible)
MODULO_DIRECTORIO = ("book-user", "Investigadores",
                     "Directorio interno: busque colegas por nombre o área MSC.", 2, "/investigadores")
MODULO_USUARIOS = ("users", "Usuarios", "Crear cuentas, restablecer contraseñas y desactivar accesos.",
                   1, "/admin/usuarios")


def _tarjeta(icono, titulo, descripcion, fase, href, extra=None):
    disponible = href is not None
    contenido = Div(
        Div(UkIcon(icono, height=22, width=22, cls="text-primary"),
            "" if disponible else Label(f"Fase {fase}", cls=LabelT.secondary),
            cls="flex items-center justify-between"),
        H4(titulo, cls="mt-3"),
        P(descripcion, cls=TextPresets.muted_sm),
        extra or "",
    )
    tarjeta = Card(contenido, cls="h-full" + ("" if disponible else " opacity-70"))
    return A(tarjeta, href=href, cls="block hover:shadow-md transition") if disponible else tarjeta


def _cifra(valor, texto):
    return Div(Span(str(valor), cls="text-2xl font-semibold"), Span(texto, cls=TextPresets.muted_sm),
               cls="flex flex-col")


def _tarjetas_produccion(uid):
    anio = date.today().year
    prods = productos.de_investigador(uid)
    del_anio = [p for p in prods if p["anio"] == anio]
    acts = [a for a in actividades.de_investigador(uid) if a["fecha_inicio"].startswith(str(anio))]
    pendientes = filiacion.pendientes(uid)
    extra_p = Div(Div(_cifra(len(del_anio), f"en {anio}"),
                      _cifra(sum(productos.cuenta_para_informe(p) for p in del_anio), "para el informe"),
                      _cifra(len(prods), "en total"), cls="grid grid-cols-3 gap-2 mt-3"),
                  P(f"{pendientes} sin filiación declarada: indique si los firmó con IIMAT/UMSA.",
                    cls="text-sm text-amber-600 mt-2") if pendientes else "")
    extra_a = Div(_cifra(len(acts), f"en {anio}"),
                  _cifra(sum(a["ambito"] == "internacional" for a in acts), "internacionales"),
                  cls="grid grid-cols-3 gap-2 mt-3")
    return [
        _tarjeta("book-open", "Mis productos", "Artículos indexados o arbitrados, reportes de "
                 "investigación, libros y presentaciones.", 3,
                 "/productos?sin_filiacion=1" if pendientes else "/productos", extra_p),
        _tarjeta("calendar-days", "Mis actividades", "Seminarios, congresos, visitas y escuelas.",
                 3, "/actividades", extra_a),
    ]


def _tarjeta_proyectos(auth):
    mios = [p for p in proyectos.de_investigador(auth["id"]) if p["vigente"] and p["estado"] != "finalizado"]
    por_revisar = proyectos.n_pendientes_para(auth)
    propias = proyectos.mis_propuestas(auth["id"])
    rechazadas = sum(v["estado"] == "rechazado" for v in propias)
    extra = Div(
        Div(_cifra(len(mios), "vigentes"), _cifra(por_revisar, "por revisar"),
            _cifra(len(propias), "propuestas mías"), cls="grid grid-cols-3 gap-2 mt-3"),
        P(f"{rechazadas} propuesta{'s' if rechazadas != 1 else ''} rechazada{'s' if rechazadas != 1 else ''}: "
          "revise el motivo en «Proyectos».", cls="text-sm text-red-600 mt-2") if rechazadas else "",
        P(f"Tiene {por_revisar} propuesta{'s' if por_revisar != 1 else ''} por revisar.",
          cls="text-sm text-amber-600 mt-2") if por_revisar else "")
    return _tarjeta("folder-kanban", "Mis proyectos", "Proyectos en que participa y el flujo de "
                    "propuestas y aprobaciones.", 4, "/proyectos", extra)


def _tarjeta_perfil(uid):
    p = perfiles.obtener(uid)
    porcentaje, faltan = perfiles.completitud(p, len(perfiles.areas(uid)))
    extra = Div(Progress(value=str(porcentaje), cls="mt-3 mb-1"),
                P(f"{porcentaje} % completo" + (f" · falta: {', '.join(faltan[:3])}"
                                                 + ("…" if len(faltan) > 3 else "") if faltan else ""),
                  cls=TextPresets.muted_sm))
    return _tarjeta("user-round", "Mi perfil", "Datos básicos, ORCID, MathSciNet, zbMATH, áreas MSC "
                    "y foto.", 2, "/perfil", extra)


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
    items = [x for x in items if x]
    return Card(Div(UkIcon(icono, height=18, width=18, cls="text-primary"), H3(titulo, cls="text-base font-semibold"),
                    cls="flex items-center gap-2 mb-2"),
                Ul(*items, cls="-mx-2") if items else
                P(UkIcon("check", height=14, width=14, cls="inline mr-1 text-green-600"), "Nada pendiente.",
                  cls=TextPresets.muted_sm))


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
    if dirige:
        vencen = carga.contratos_por_vencer(30)
        if vencen:
            items.append(_item(f"{_plural(len(vencen), 'vínculo')} termina{'n' if len(vencen) != 1 else ''} en los "
                               "próximos 30 días sin un periodo nuevo registrado", "/admin/usuarios",
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


def _para_acreditacion(auth):
    """Quien ve los informes institucionales: el cuerpo académico del año, en cifras."""
    if not permisos.puede(auth, "ver_informes_institucionales"):
        return None
    anio = date.today().year
    cuerpo = anexo.cuerpo_academico(anio, date.today().isoformat())
    vigentes = get_db().q("SELECT COUNT(*) n FROM proyecto WHERE estado = 'vigente'")[0]["n"]
    cifras = Div(_cifra(cuerpo["total"], "académicos vinculados"), _cifra(cuerpo["jce"], "jornadas completas eq."),
                 _cifra(vigentes, "proyectos vigentes"), cls="grid grid-cols-3 gap-2")
    return Card(Div(UkIcon("chart-column", height=18, width=18, cls="text-primary"),
                    H3(f"Acreditación · {anio}", cls="text-base font-semibold"), cls="flex items-center gap-2 mb-3"),
                cifras,
                Div(A("Memoria", href="/informes/memoria", cls="text-sm text-primary hover:underline"),
                    A("Anexo de I+D+i", href="/informes/acreditacion", cls="text-sm text-primary hover:underline"),
                    cls="flex gap-4 mt-3"))


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


def _para_calidad(auth):
    """Quien ve la calidad de datos: cuántos registros quedan por completar (enlace al tablero)."""
    if not permisos.puede(auth, "ver_calidad_datos"):
        return None
    r = calidad.resumen()
    item = _item(f"{_plural(r['registros'], 'registro')} por completar en {r['con_observaciones']} de "
                 f"{r['chequeos']} revisiones", "/informes/calidad",
                 detalle="Antes de generar la memoria o el anexo.") if r["registros"] else None
    return _grupo("list-checks", "Calidad de datos", [item])


@rt("/")
def get(auth):
    grupos = [x for x in (_para_mi(auth), _para_carrera(auth), _para_instituto(auth), _para_acreditacion(auth),
                          _para_calidad(auth)) if x]
    tarjetas = []
    if auth["es_investigador"]:
        tarjetas += [_tarjeta_proyectos(auth), *_tarjetas_produccion(auth["id"]),
                     _tarjeta_perfil(auth["id"])]
    tarjetas.append(_tarjeta(*MODULO_DIRECTORIO))
    if permisos.puede(auth, "ver_usuarios"):
        tarjetas.append(_tarjeta(*MODULO_USUARIOS))
    return pagina(
        "Inicio",
        Div(H2(f"Hola, {auth['nombres']}"),
            P("Lo que requiere su atención y sus accesos.", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Div(H4("Para hoy", cls="mb-3"),
            Div(*grupos, cls="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start"),
            cls="mb-8") if grupos else "",
        H4("Accesos", cls="mb-3"),
        Grid(*tarjetas, cols_sm=1, cols_md=2, cols_lg=3, gap=4),
        usuario=auth, seccion="inicio")
