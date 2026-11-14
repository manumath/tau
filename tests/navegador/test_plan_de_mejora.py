"""Plan de mejora en un navegador real (PLAN §72, etapa 10): cargar el plan, registrar un avance desde «Mis pendientes»,
pedir y aprobar una reprogramación y cerrar un corte. Ejecutar con: pytest --navegador

Comparten el servidor de la sesión (tests/navegador/conftest.py): la base de preparar.py trae la acción A4 con la
actividad 4.1 a cargo de la investigadora y el corte 1 abierto. Las pruebas van en el orden en que se usa el plan."""
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect

from tests.navegador.conftest import confirmar, entrar

PLAN = Path(__file__).resolve().parents[2] / "datos" / "calidad" / "plan-de-mejora-2026-2030.csv"


def test_1_la_direccion_carga_el_plan(page):
    entrar(page, "direccion")
    page.goto("/calidad/mejora")
    page.get_by_role("button", name="Cargar CSV").click()
    page.set_input_files("#modal input[type=file]", str(PLAN))
    page.get_by_role("button", name="Revisar").click()
    modal = page.locator("#modal")
    expect(modal).to_contain_text("14 acción(es) nueva(s)")                 # A4 ya estaba en el plan: se omite
    expect(modal).to_contain_text("Ya está en el plan")
    modal.get_by_role("button", name="Cargar 14 acción(es)").click()
    expect(page.locator("main")).to_contain_text("Operar de forma permanente el sistema interno")   # la página se recargó
    page.wait_for_load_state()
    expect(page.locator("main")).to_contain_text("Fortalecer la retención estudiantil")
    page.goto("/calidad/mejora/cronograma")
    expect(page.locator("main")).to_contain_text("Cronograma")


def test_2_la_responsable_registra_su_avance_desde_sus_pendientes(page):
    entrar(page, "investigadora")
    page.goto("/investigacion/pendientes")
    tarjeta = page.locator("div.uk-card", has_text="Mi parte del plan de mejora")
    expect(tarjeta).to_contain_text("Taller de inducción para el primer semestre")
    tarjeta.get_by_role("button", name="Registrar avance").first.click()
    modal = page.locator("#modal")
    modal.locator("textarea[name=texto]").fill("Segundo taller dictado con 40 estudiantes.")
    modal.locator("input[name=porcentaje]").fill("60")
    modal.get_by_role("button", name="Registrar avance").click()
    # Vuelve a donde estaba, con la cifra nueva.
    expect(page.locator("div.uk-card", has_text="Mi parte del plan de mejora")).to_contain_text("avance 60 %")
    page.wait_for_load_state()
    assert page.url.endswith("/investigacion/pendientes")


def test_3_reprogramar_con_el_plan_aprobado(page):
    entrar(page, "direccion")
    page.goto("/calidad/mejora")
    page.get_by_role("button", name="Registrar la aprobación").click()
    page.fill("#modal input[name=resolucion]", "Res. HCC N.º 1/2026")
    page.fill("#modal input[name=fecha]", date.today().isoformat())
    page.locator("#modal").get_by_role("button", name="Guardar").click()
    expect(page.locator("main")).to_contain_text("Res. HCC N.º 1/2026")
    page.context.clear_cookies()

    entrar(page, "investigadora")
    page.goto("/calidad/mejora/actividades/1")
    page.get_by_role("button", name="Pedir reprogramación").click()
    nuevo = (date.today() + timedelta(days=700)).isoformat()
    page.fill("#modal input[name=plazo_nuevo]", nuevo)
    page.fill("#modal textarea[name=causa]", "El aula del taller está en refacción hasta el próximo año.")
    page.locator("#modal").get_by_role("button", name="Enviar el pedido").click()
    expect(page.locator("main")).to_contain_text("en refacción")
    page.context.clear_cookies()

    entrar(page, "direccion")
    page.goto("/calidad/mejora")
    expect(page.locator("main")).to_contain_text("Reprogramaciones por resolver")
    page.goto("/calidad/mejora/actividades/1")
    page.get_by_role("button", name="Aprobar").click()
    confirmar(page)
    expect(page.locator("main")).to_contain_text("Aprobada")


def test_4_cerrar_un_corte(page):
    entrar(page, "direccion")
    page.goto("/calidad/mejora/cortes/1")
    expect(page.locator("main")).to_contain_text("Piden atención")
    page.get_by_role("button", name="Cerrar el corte").click()
    page.fill("#modal textarea[name=conclusion]", "Avance general adecuado; seguir de cerca la retención.")
    page.locator("#modal").get_by_role("button", name="Cerrar el corte").click()
    expect(page.locator("main")).to_contain_text("cerrado por")
    page.goto("/calidad/evidencias")
    expect(page.locator("main")).to_contain_text("Plan de mejora: corte trimestral")
