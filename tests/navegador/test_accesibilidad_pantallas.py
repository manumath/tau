"""Accesibilidad de las pantallas reales (PLAN §62; auditoría del 8-nov-2026). Sin descargas (decisión del usuario):
una verificación propia, en el navegador, de lo que la auditoría encontró y que la CI no veía:

- contraste del texto visible (WCAG 1.4.3: 4,5:1, o 3:1 si es grande), en tema claro y oscuro;
- controles de formulario y botones o enlaces sin nombre accesible (WCAG 1.3.1 y 4.1.2);
- ids repetidos;
- un solo <h1> por página (WCAG 1.3.1 y 2.4.6) y fechas legibles: ni «2026-08-01» ni «08-11-2026» (PLAN §62, etapa 3).
"""
from datetime import date

import pytest

from tests.navegador.conftest import entrar

REVISAR = r"""
() => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
    && getComputedStyle(e).visibility !== 'hidden';
  const nombre = e => (e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') &&
      document.getElementById(e.getAttribute('aria-labelledby'))?.textContent) || e.textContent ||
      e.getAttribute('title') || '').trim();
  const problemas = [];
  document.querySelectorAll('input:not([type=hidden]):not([type=submit]),select,textarea').forEach(i => {
    if (!vis(i) || i.getAttribute('aria-label') || i.getAttribute('aria-labelledby') || i.title) return;
    if ((i.id && document.querySelector(`label[for="${CSS.escape(i.id)}"]`)) || i.closest('label')) return;
    problemas.push('control sin etiqueta: ' + i.outerHTML.slice(0, 120));
  });
  document.querySelectorAll('button,a[href]').forEach(b => {
    if (vis(b) && !nombre(b) && !b.querySelector('img[alt]:not([alt=""])'))
      problemas.push('sin nombre accesible: ' + b.outerHTML.slice(0, 120));
  });
  const ids = {};
  document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id] || 0) + 1; });
  Object.entries(ids).filter(([, n]) => n > 1).forEach(([id]) => problemas.push('id repetido: ' + id));
  const rgb = s => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const fondo = e => { for (; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor);
                         if (c.length && (c.length < 4 || c[3] > 0.5)) return c; }
                       return rgb(getComputedStyle(document.body).backgroundColor); };
  const opaco = e => { for (; e; e = e.parentElement) if (parseFloat(getComputedStyle(e).opacity) < 1) return false; return true; };
  document.querySelectorAll('body *').forEach(e => {
    if (!vis(e) || !opaco(e) || e.closest('[disabled],[aria-disabled=true],.sr-only')) return;
    if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const cs = getComputedStyle(e), c = rgb(cs.color);
    if (c.length > 3 && c[3] < 0.5) return;
    const a = lum(c), b = lum(fondo(e)), razon = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const grande = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && parseInt(cs.fontWeight) >= 700);
    if (razon < (grande ? 3 : 4.5) - 0.05)
      problemas.push(`contraste ${razon.toFixed(2)}: «${e.textContent.trim().slice(0, 30)}» (${cs.color})`);
  });
  document.querySelectorAll('table[data-tabla]').forEach(t => {
    if (vis(t) && !t.caption && !nombre(t)) problemas.push('tabla sin nombre: ' + t.dataset.tabla);
  });
  const foco = document.querySelector('main a[href], main button');
  if (foco) { foco.focus({focusVisible: true});
              if (parseFloat(getComputedStyle(foco).outlineWidth) < 2 && getComputedStyle(foco).boxShadow === 'none')
                problemas.push('foco sin indicador visible de 2 px'); foco.blur(); }
  const h1 = document.querySelectorAll('h1').length;
  if (h1 !== 1) problemas.push(`${h1} encabezados h1 (debe haber uno)`);
  const texto = document.querySelector('main')?.innerText || '';
  (texto.match(/\b\d{4}-\d{2}-\d{2}\b|\b\d{2}-\d{2}-\d{4}\b/g) || []).slice(0, 3)
    .forEach(f => problemas.push('fecha sin formato: ' + f));
  return [...new Set(problemas)];
}
"""

PANTALLAS = {
    "investigadora": ["/", "/productos", "/actividades", "/proyectos", "/perfil", "/informes",
                      "/docencia", "/pendientes", "/calendario", "/docencia/pendientes", "/docencia/calendario", "/docencia/preferencias", "/docencia/programas", "/docencia/listas", "/docencia/evaluacion", "/docencia/historial", "/docencia/certificados", "/investigacion/pendientes", "/investigacion/calendario",
                      "/investigacion/acceso-abierto", "/investigacion/coautores", "/calidad/mejora/actividades/1", "/avisos", "/buscar?q=noether",
                      # Con fechas a la vista (ensayo del piloto, PLAN §72, etapa 11).
                      "/tutoria"],
    "direccion": ["/", "/admin/usuarios", "/admin/propuestas", "/docencia/planes", "/docencia/planes?estado=elaboracion",
                  "/docencia/planes/reforma/nueva", "/docencia/planes/reforma/2", "/docencia/planes/5",
                  "/docencia/planes/5/malla", "/docencia/planes/5/equivalencias", "/docencia/oferta",
                  # Gestiones (PLAN §66): lista, planificación (en planificación, activa y concluida) y oferta con cambios.
                  "/docencia/preparacion", f"/docencia/preparacion?semestre=I-{date.today().year + 5}",
                  f"/docencia/preparacion?semestre=II-{date.today().year - 4}", "/docencia/oferta?gestion=5",
                  "/docencia/oferta?gestion=6", "/docencia/oferta/5/cambios",
                  "/docencia/carga", "/docencia/preferencias/todas", "/docencia/programas/cobertura", "/docencia/listas/cargar", "/docencia/evaluacion/gestion", "/docencia/certificados/verificar", "/docencia/gestiones", "/docencia/preparacion", "/docencia/cohortes", "/docencia/cohortes/vacantes", "/docencia/cohortes/rendimiento",
                  "/docencia/encuestas", "/docencia/tutoria", "/docencia/cohortes/actividades", "/docencia/egresados", "/estudiantes",
                  "/servicios/comunicados", "/servicios/auxiliaturas",
                  # Auxiliaturas según el reglamento de 2023 (PLAN §70): convocatoria, ítem, resultado y los cinco formularios.
                  "/servicios/auxiliaturas/nueva", "/servicios/auxiliaturas/1", "/servicios/auxiliaturas/1/designacion", "/servicios/auxiliaturas/item/1",
                  *[f"/servicios/auxiliaturas/item/1/formulario/{n}" for n in range(1, 6)],
                  "/servicios/grado", "/informes",
                  "/calidad/marco", "/calidad/indicadores", "/calidad/evidencias", "/calidad/autoevaluaciones",
                  "/calidad/ficha", "/calidad/mejora", "/calidad/mejora/cronograma",
                  "/calidad/mejora/acciones/1", "/calidad/mejora/actividades/1",
                  "/calidad/mejora/cortes", "/calidad/mejora/cortes/1", "/admin/revistas", "/admin/lineas", "/admin/catalogos",
                  "/personas/externos"],
    "admin": ["/admin/usuarios", "/admin/auditoria", "/admin/piloto", "/admin/modulos", "/admin/unidades", "/informes/calidad"],
}


@pytest.mark.parametrize("oscuro", [False, True], ids=["claro", "oscuro"])
@pytest.mark.parametrize("quien", list(PANTALLAS))
def test_pantallas_sin_problemas_de_accesibilidad(page, quien, oscuro):
    page.emulate_media(color_scheme="dark" if oscuro else "light")
    entrar(page, quien)
    hallados = {}
    for ruta in PANTALLAS[quien]:
        page.goto(ruta)
        page.wait_for_load_state("networkidle")
        if (p := page.evaluate(REVISAR)):
            hallados[ruta] = p
    assert hallados == {}, "\n".join(f"{r}:\n  " + "\n  ".join(p) for r, p in hallados.items())


def test_pantallas_del_estudiante_sin_problemas_de_accesibilidad(estudiante):
    """Portal del estudiante (PLAN §49 y §58), en claro y en oscuro con la misma sesión."""
    page = estudiante
    hallados = {}
    for oscuro in (False, True):
        page.emulate_media(color_scheme="dark" if oscuro else "light")
        for ruta in ["/estudiante", "/estudiante/comunicados", "/estudiante/auxiliaturas", "/estudiante/grado",
                     "/estudiante/grado/nuevo", "/avisos",
                     # Servicios del estudiante (PLAN §67).
                     "/estudiante/plan", "/estudiante/calendario", "/estudiante/tutoria", "/estudiante/apoyo",
                     "/estudiante/biblioteca", "/estudiante/orientacion", "/estudiante/buzon", "/estudiante/oportunidades",
                     "/estudiante/temas", "/estudiante/encuestas", "/estudiante/evaluacion"]:
            page.goto(ruta)
            page.wait_for_load_state("networkidle")
            if (p := page.evaluate(REVISAR)):
                hallados[f"{ruta} ({'oscuro' if oscuro else 'claro'})"] = p
    assert hallados == {}, "\n".join(f"{r}:\n  " + "\n  ".join(p) for r, p in hallados.items())


def test_paginas_publicas_sin_problemas_de_accesibilidad(page):
    hallados = {}
    for ruta in ["/login", "/acceso", "/recuperar", "/publico", "/publico/indicadores", "/publico/privacidad"]:
        page.goto(ruta)
        page.wait_for_load_state("networkidle")
        if (p := page.evaluate(REVISAR)):
            hallados[ruta] = p
    assert hallados == {}, "\n".join(f"{r}:\n  " + "\n  ".join(p) for r, p in hallados.items())


@pytest.mark.parametrize("ruta", ["/admin/usuarios"])
def test_tablas_como_tarjetas_en_el_telefono(page, ruta):
    """Bajo 640 px las tablas de trabajo son tarjetas con el título de cada columna y la página no se desplaza a lo
    ancho (PLAN §62, UX-01)."""
    page.set_viewport_size({"width": 375, "height": 800})
    entrar(page, "admin" if ruta == "/admin/usuarios" else "direccion")
    page.goto(ruta)
    tabla = page.locator("table[data-tabla-lista]").first
    if not tabla.count():
        pytest.skip(f"{ruta} no muestra una tabla con estos datos")
    celda = tabla.locator("tbody tr:not(:has(td[colspan])) td[data-label]").first
    assert celda.count(), "las celdas no llevan el título de su columna"
    assert celda.evaluate("c => getComputedStyle(c).display") == "flex"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_oferta_filtra_los_paralelos_sin_docente(page):
    """«Ver los N sin docente» escribe el filtro de la tabla; otro clic lo quita (PLAN §62, UX-02)."""
    entrar(page, "direccion")
    page.goto("/docencia/oferta")
    boton = page.locator('[data-accion="filtrar-tabla"]')
    if not boton.count():
        pytest.skip("la oferta de prueba no tiene paralelos sin docente")
    filas = page.locator("table[data-tabla] tbody tr:visible")
    total = filas.count()
    boton.click()
    assert page.locator('input[aria-label="Filtrar la tabla"]').input_value() == "Sin docente"
    assert 0 < filas.count() <= total and boton.get_attribute("aria-pressed") == "true"
    boton.click()
    assert filas.count() == total
