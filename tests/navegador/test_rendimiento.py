"""Rendimiento percibido (PLAN §62, etapa 6): la página no salta mientras carga (CLS) y KaTeX se pide solo si hay
fórmulas."""
import pytest

from tests.navegador.conftest import entrar

MEDIR_CLS = """() => new Promise(fin => {
  let total = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) total += e.value; })
    .observe({type: 'layout-shift', buffered: true});
  setTimeout(() => fin(total), 1500);
})"""


@pytest.mark.parametrize("ruta", ["/", "/productos", "/proyectos", "/investigadores", "/admin/usuarios"])
def test_la_pagina_no_salta_al_cargar(page, ruta):
    entrar(page, "admin")
    page.goto(ruta)
    cls = page.evaluate(MEDIR_CLS)
    assert cls < 0.1, f"{ruta}: CLS {cls:.3f} (umbral «bueno» de Web Vitals: 0,1)"


def test_katex_solo_con_formulas(page):
    pedidos = []
    page.on("request", lambda r: pedidos.append(r.url))
    entrar(page, "admin")
    page.goto("/admin/usuarios")
    page.wait_for_load_state("networkidle")
    assert not [u for u in pedidos if "katex" in u and "katex.mjs" not in u]
