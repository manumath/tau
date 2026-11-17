"""Colores de la marca (PLAN.md §55 y §74): la genérica y la de cada instancia del repositorio se leen bien en claro y
en oscuro, y la aplicación sirve el tema de la instancia de la instalación."""
import pytest

from app.comun import config, marca
from app.comun.componentes import recursos

# Las paletas que se revisan aquí: la de la instalación (en las pruebas, la de Matemática) y las de las instancias del
# repositorio que traen marca. La genérica del código se revisa aparte, en otro proceso sin instancia.
PALETAS = {"de la instalación": marca.TEMA,
           **{f"instancia {c.name}": {**marca.leer(c)["tema"]} for c in sorted((config.RAIZ / "instancias").iterdir())
              if marca.leer(c)}}

# (texto, fondo): pares que la interfaz usa como texto; WCAG AA pide 4,5:1.
TEXTOS = [("foreground", "background"), ("muted-foreground", "background"), ("muted-foreground", "muted"),
          ("primary-foreground", "primary"), ("primary", "background"), ("primary", "muted"),
          ("secondary-foreground", "secondary"), ("destructive-foreground", "destructive"),
          ("destructive", "background")]


def test_colores_del_manual():
    assert marca.hex_de(marca.TEMA["claro"]["primary"]) == marca.AZUL
    assert marca.GRAFICOS[:4] == (marca.AZUL, marca.TURQUESA, marca.ROJO, marca.GRIS)


def test_la_paleta_generica_tambien_se_revisa():
    """Las pruebas corren con la instancia de Matemática: la paleta genérica se revisa leyendo el código sin instancia."""
    import subprocess
    import sys
    codigo = ("from app.comun import marca; import tests.test_marca as t;"
              "[t._contraste_aa(marca.TEMA, m) or t._contraste_del_panel(marca.TEMA, m) for m in ('claro', 'oscuro')];"
              "assert marca.PRINCIPAL == '#1d4059' and marca.hex_de(marca.TEMA['claro']['primary']) == marca.PRINCIPAL")
    sin_instancia = str(config.RAIZ / "instancias" / "no-existe")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=config.RAIZ, capture_output=True, text=True,
                       env={**__import__("os").environ, "TAU_INSTANCIA": sin_instancia})
    assert r.returncode == 0, r.stderr[-800:]


def _contraste_aa(tema, modo):
    t = {k: marca.hex_de(v) for k, v in tema[modo].items()}
    for texto, fondo in TEXTOS:
        assert marca.contraste(t[texto], t[fondo]) >= 4.5, (modo, texto, fondo)
    assert marca.contraste(t["ring"], t["background"]) >= 3, modo        # el foco se ve (no es texto: 3:1)


def _contraste_del_panel(tema, modo):
    t = {k: marca.hex_de(v) for k, v in tema[modo].items()}
    for fondo in (t["lateral"], t["lateral-fin"]):
        assert marca.contraste(t["lateral-foreground"], fondo) >= 7, (modo, fondo)
        for opacidad in marca.OPACIDAD_MENU:
            assert marca.contraste(marca.mezcla(t["lateral-foreground"], fondo, opacidad), fondo) >= 4.5, (modo, fondo)
    assert marca.contraste(t["lateral"], t["lateral-foreground"]) >= 4.5, modo
    assert marca.contraste(t["acento"], t["background"]) >= 3, modo          # la cinta de los títulos (no es texto)


@pytest.mark.parametrize("paleta", PALETAS)
@pytest.mark.parametrize("modo", ["claro", "oscuro"])
def test_contraste_de_cada_paleta(paleta, modo):
    """WCAG AA en el texto y en el menú lateral (PLAN §63), para la marca de la instalación y la de cada instancia."""
    tema = {m: {**marca.TEMA[m], **PALETAS[paleta][m]} for m in ("claro", "oscuro")}
    _contraste_aa(tema, modo)
    _contraste_del_panel(tema, modo)


@pytest.mark.parametrize("modo", ["claro", "oscuro"])
def test_contraste_aa(modo):
    t = {k: marca.hex_de(v) for k, v in marca.TEMA[modo].items()}
    for texto, fondo in TEXTOS:
        assert marca.contraste(t[texto], t[fondo]) >= 4.5, (modo, texto, fondo)
    assert marca.contraste(t["ring"], t["background"]) >= 3, modo        # el foco se ve (no es texto: 3:1)


@pytest.mark.parametrize("modo", ["claro", "oscuro"])
def test_contraste_del_panel(modo):
    """Menú lateral (PLAN §63): el texto se lee arriba y abajo del degradado, también con la opacidad de los enlaces
    y de los títulos de grupo; el enlace activo (fondo claro, texto del color del panel) y su marca roja, también."""
    t = {k: marca.hex_de(v) for k, v in marca.TEMA[modo].items()}
    for fondo in (t["lateral"], t["lateral-fin"]):
        assert marca.contraste(t["lateral-foreground"], fondo) >= 7, (modo, fondo)
        for opacidad in marca.OPACIDAD_MENU:
            assert marca.contraste(marca.mezcla(t["lateral-foreground"], fondo, opacidad), fondo) >= 4.5, (modo, fondo)
    assert marca.contraste(t["lateral"], t["lateral-foreground"]) >= 4.5, modo
    assert marca.contraste(t["acento"], t["background"]) >= 3, modo          # la cinta de los títulos (no es texto)


def test_el_tema_se_sirve_con_la_marca_de_la_instalacion(client):
    """El tema ya no se compila con Tailwind: la aplicación lo sirve en /tema.css (público, lo usa el ingreso)."""
    css = client.get(recursos.url_del_tema())
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    assert css.text == marca.css_del_tema() and f".{marca.CLASE_TEMA} {{" in css.text
    assert f"--primary: {marca.TEMA['claro']['primary']};" in css.text
    assert "#2563eb" not in css.text.replace("%23", "#")                        # sin el azul de Franken UI
    assert "uk-theme-" not in (config.RAIZ / "static/css/tailwind.css").read_text()
    assert marca.CLASE_TEMA in (config.RAIZ / "static/js/tema-inicial.js").read_text()
    assert recursos.url_del_tema() in client.get("/login").text


def test_fuentes_de_la_marca():
    """Equivalentes libres de Gotham y Garamond Pro (PLAN.md §55), propios (la CSP solo admite font-src 'self')."""
    fuentes = config.RAIZ / "static/vendor/fonts"
    for carpeta, archivos in {"montserrat": ("montserrat-400", "montserrat-500", "montserrat-700"),
                              "eb-garamond": ("eb-garamond-400", "eb-garamond-400-italic", "eb-garamond-600")}.items():
        assert "Open Font License" in (fuentes / carpeta / "OFL.txt").read_text()
        for nombre in archivos:
            assert (fuentes / carpeta / f"{nombre}.woff2").read_bytes()[:4] == b"wOF2"
            assert f"../vendor/fonts/{carpeta}/{nombre}.woff2" in (config.RAIZ / "static/css/tailwind.css").read_text()


def test_marca_en_la_interfaz(client):
    """Isotipo junto a «TAU» en el menú; marca horizontal en el ingreso; las dos versiones (color y blanco, que el
    tema oscuro muestra) y el favicon con el isotipo."""
    r = client.get("/login").text
    assert "img/marca/logotipo.png" in r and "img/marca/logotipo-blanco.png" in r
    assert f'alt="{config.NOMBRE_CARRERA}"' in r
    for archivo in ("isotipo.svg", "isotipo-blanco.svg", "logotipo.png", "logotipo-blanco.png", "icono-192.png"):
        assert (config.RAIZ / "static/img/marca" / archivo).stat().st_size > 300          # la marca genérica
        assert recursos.archivo(f"img/marca/{archivo}").parent == config.INSTANCIA / "marca"   # la de la instancia manda
        assert client.get(recursos.url(f"img/marca/{archivo}")).content == (config.INSTANCIA / "marca" / archivo).read_bytes()
    assert (config.RAIZ / "static/favicon.svg").read_text() == (config.RAIZ / "static/img/marca/isotipo.svg").read_text()
    for isotipo in (config.RAIZ / "static/img/marca/isotipo.svg", config.INSTANCIA / "marca/isotipo.svg"):
        assert "<image" not in isotipo.read_text()                                        # vectorial, sin mapas de bits
    assert client.get("/static/img/marca/../../../pyproject.toml").status_code == 404     # nada fuera de la carpeta


def test_panel_de_la_marca(admin, client):
    """PLAN §63: el menú lateral es el panel azul marino con el isotipo en blanco; las páginas sin sesión van en una
    tarjeta sobre el lienzo de la marca (también la de error); la fuente de los títulos se precarga."""
    import re
    r = admin.get("/").text
    lateral = re.search(r'<nav[^>]*id="menu-lateral".*?</nav>', r, re.S).group(0)
    assert "isotipo-blanco.svg" in lateral and "isotipo.svg" not in lateral
    assert "text-lateral-foreground" in lateral and "text-foreground/80" not in lateral
    assert 'aria-label="Cuenta de Ada"' in r
    assert 'rel="preload"' in r and 'as="font"' in r and "montserrat-700.woff2" in r
    css = (config.RAIZ / "static/css/tailwind.css").read_text()
    for regla in (".lienzo-marca", "--lateral-fin", "--acento", ".uk-btn"):
        assert regla in css, regla
    assert "uk-radii-md" in (config.RAIZ / "static/js/tema-inicial.js").read_text()
    from starlette.testclient import TestClient
    anonimo = TestClient(client.app)
    for ruta in ("/login", "/acceso", "/recuperar", "/no-existe"):
        html = anonimo.get(ruta).text
        assert "lienzo-marca" in html and "uk-card" in html, ruta


def test_membrete_y_exportaciones(app, monkeypatch):
    """Membrete oficial: la marca de la Carrera siempre, el IIMAT solo en los de investigación, y la dirección al
    pie si está configurada; encabezados XLSX en azul marino."""
    import io

    from fasthtml.common import H1, to_xml
    from openpyxl import load_workbook

    from app.informes.rutas import informes
    from app.comun import exportar
    monkeypatch.setattr(config, "DIRECCION", "Av. Ejemplo 123, La Paz")
    docencia, investigacion = to_xml(informes.hoja(H1("Carga"))), to_xml(informes.hoja(H1("Memoria"), instituto=True))
    assert "img/marca/logotipo.png" in docencia and "instituto.png" not in docencia and "Av. Ejemplo 123" in docencia
    assert "img/marca/instituto.png" in investigacion and config.NOMBRE_INSTITUTO in investigacion
    celda = load_workbook(io.BytesIO(exportar.a_xlsx({"Hoja": [{"a": 1}]})))["Hoja"]["A1"]
    assert celda.fill.fgColor.rgb.endswith(marca.AZUL[1:].upper()) and celda.font.bold
