"""Colores de la Carrera (PLAN.md §55): el tema generado está al día y se lee bien en claro y en oscuro."""
import importlib.util

import pytest

from app.comun import config, marca

# (texto, fondo): pares que la interfaz usa como texto; WCAG AA pide 4,5:1.
TEXTOS = [("foreground", "background"), ("muted-foreground", "background"), ("muted-foreground", "muted"),
          ("primary-foreground", "primary"), ("primary", "background"), ("primary", "muted"),
          ("secondary-foreground", "secondary"), ("destructive-foreground", "destructive"),
          ("destructive", "background")]


def test_colores_del_manual():
    assert marca.hex_de(marca.TEMA["claro"]["primary"]) == marca.AZUL
    assert marca.GRAFICOS[:4] == (marca.AZUL, marca.TURQUESA, marca.ROJO, marca.GRIS)


@pytest.mark.parametrize("modo", ["claro", "oscuro"])
def test_contraste_aa(modo):
    t = {k: marca.hex_de(v) for k, v in marca.TEMA[modo].items()}
    for texto, fondo in TEXTOS:
        assert marca.contraste(t[texto], t[fondo]) >= 4.5, (modo, texto, fondo)
    assert marca.contraste(t["ring"], t["background"]) >= 3, modo        # el foco se ve (no es texto: 3:1)


def test_tema_generado_al_dia():
    """Si cambia marca.py: uv run python scripts/tema_marca.py && scripts/estilos.sh."""
    spec = importlib.util.spec_from_file_location("tema_marca", config.RAIZ / "scripts/tema_marca.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    assert (config.RAIZ / "estilos/tema-cmat.css").read_text() == modulo.generar()
    assert "#2563eb" not in modulo.generar().replace("%23", "#")                # sin el azul de Franken UI
    assert "uk-theme-cmat" in (config.RAIZ / "static/css/tailwind.css").read_text()


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
    for archivo in ("isotipo.svg", "isotipo-blanco.svg", "logotipo.png", "logotipo-blanco.png"):
        assert (config.RAIZ / "static/img/marca" / archivo).stat().st_size > 1000
    assert (config.RAIZ / "static/favicon.svg").read_text() == (config.RAIZ / "static/img/marca/isotipo.svg").read_text()
    assert "<image" not in (config.RAIZ / "static/img/marca/isotipo.svg").read_text()      # vectorial, sin mapas de bits
