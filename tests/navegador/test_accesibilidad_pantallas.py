"""Accesibilidad de las pantallas reales (PLAN §62; auditoría del 8-nov-2026). Sin descargas (decisión del usuario):
una verificación propia, en el navegador, de lo que la auditoría encontró y que la CI no veía:

- contraste del texto visible (WCAG 1.4.3: 4,5:1, o 3:1 si es grande), en tema claro y oscuro;
- controles de formulario y botones o enlaces sin nombre accesible (WCAG 1.3.1 y 4.1.2);
- ids repetidos;
- un solo <h1> por página (WCAG 1.3.1 y 2.4.6) y fechas legibles: ni «2026-08-01» ni «08-11-2026» (PLAN §62, etapa 3).
"""
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
                      "/docencia", "/avisos", "/buscar?q=noether"],
    "direccion": ["/", "/admin/usuarios", "/admin/propuestas", "/docencia/planes", "/docencia/oferta",
                  "/docencia/carga", "/docencia/gestiones", "/docencia/preparacion", "/docencia/cohortes",
                  "/docencia/encuestas", "/docencia/tutoria", "/docencia/egresados", "/estudiantes",
                  "/servicios/comunicados", "/servicios/auxiliaturas", "/servicios/grado", "/informes",
                  "/calidad/marco", "/calidad/indicadores", "/calidad/evidencias", "/calidad/autoevaluaciones",
                  "/calidad/ficha", "/calidad/mejora", "/admin/revistas", "/admin/lineas", "/admin/catalogos",
                  "/personas/externos"],
    "admin": ["/admin/usuarios", "/admin/auditoria", "/informes/calidad"],
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


def test_paginas_publicas_sin_problemas_de_accesibilidad(page):
    hallados = {}
    for ruta in ["/login", "/acceso", "/recuperar", "/publico", "/publico/indicadores"]:
        page.goto(ruta)
        page.wait_for_load_state("networkidle")
        if (p := page.evaluate(REVISAR)):
            hallados[ruta] = p
    assert hallados == {}, "\n".join(f"{r}:\n  " + "\n  ".join(p) for r, p in hallados.items())
