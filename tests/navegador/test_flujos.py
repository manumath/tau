"""Flujos críticos en un navegador real (fase 1, paso 1.5). Ejecutar con: pytest --navegador

Cubren lo que las pruebas con TestClient no ven: htmx, modales, confirmaciones, JavaScript de
Franken UI y KaTeX, la política de seguridad de contenido y las descargas.
"""
import openpyxl
from playwright.sync_api import expect

from tests.navegador.conftest import entrar
from tests.navegador.preparar import CLAVE, INVESTIGADORA


def test_ingreso_y_salida(page):
    page.goto("/productos")  # sin sesión, lleva al ingreso
    page.wait_for_url("**/login**")
    page.fill("#email", INVESTIGADORA)
    page.fill("#password", CLAVE + "x")
    page.click("button:has-text('Ingresar')")
    expect(page.get_by_text("Correo o contraseña incorrectos.")).to_be_visible()
    page.fill("#password", CLAVE)
    page.click("button:has-text('Ingresar')")
    page.wait_for_url("**/")
    expect(page.locator("nav").get_by_role("button", name="Emmy")).to_be_visible()
    page.locator("nav").get_by_role("button", name="Emmy").click()
    page.get_by_role("button", name="Salir").click()
    page.wait_for_url("**/login**")
    page.goto("/productos")
    page.wait_for_url("**/login**")


def test_registrar_producto(page):
    entrar(page, "investigadora")
    page.goto("/productos")
    page.get_by_role("button", name="Nuevo producto").click()
    modal = page.locator("#modal")
    modal.locator("select[name=tipo_id]").select_option(label="Preprint")
    modal.locator("input[name=titulo]").fill("Anillos noetherianos y autómatas finitos")
    modal.get_by_role("button", name="Guardar").click()
    expect(modal.locator("form")).to_have_count(0)  # el modal se cierra al guardar
    lista = page.locator("#lista-productos")
    expect(lista).to_contain_text("Anillos noetherianos y autómatas finitos")
    lista.get_by_role("link", name="Anillos noetherianos y autómatas finitos").click()
    expect(page.locator("main")).to_contain_text("Preprint")


def proponer(page, nombre: str) -> str:
    """La investigadora crea y envía una propuesta institucional completa. → URL de la propuesta."""
    page.goto("/proyectos")
    page.get_by_role("button", name="Proponer proyecto institucional").click()
    page.locator("#modal input[name=nombre]").fill(nombre)
    page.locator("#modal").get_by_role("button", name="Crear borrador").click()
    page.wait_for_url("**/propuestas/*")
    editor = page.locator("#editor-propuesta")
    # Incompleta: no se envía y dice qué falta.
    page.get_by_role("button", name="Enviar propuesta").click()
    expect(editor).to_contain_text("Antes de enviar, complete")
    editor.get_by_label("Sistemas Dinámicos").check()
    editor.locator("textarea[name=descripcion]").fill("Dinámica simbólica de autómatas celulares.")
    editor.locator("textarea[name=objetivo_general]").fill("Clasificar autómatas por su dinámica.")
    editor.locator("input[name=objetivo]").fill("Estudiar la entropía topológica.")
    editor.get_by_role("button", name="Agregar objetivo").click()
    editor.locator("input[name=objetivo]").nth(1).fill("Formar a un tesista.")
    editor.locator("textarea[name=metodologia]").fill("Métodos de dinámica simbólica: $h_{top}(\\sigma)$.")
    editor.locator("textarea[name=resultados_esperados]").fill("Un artículo y una tesis.")
    editor.locator("select[name=act_mes]").select_option(index=1)
    editor.locator("input[name=act_desc]").fill("Seminario de lanzamiento.")
    editor.locator("textarea[name=bibliografia]").fill("Lind, D. y Marcus, B. (1995).")
    page.get_by_role("button", name="Enviar propuesta").click()  # confirma el diálogo (conftest)
    expect(page.locator("main")).to_contain_text("Enviada")
    return page.url


def test_proponer_proyecto_institucional(page):
    entrar(page, "investigadora")
    proponer(page, "Dinámica de autómatas celulares")
    main = page.locator("main")
    expect(main).to_contain_text("Sistemas Dinámicos")
    expect(main).to_contain_text("Formar a un tesista.")
    expect(main.locator(".katex").first).to_be_visible()  # la fórmula de la metodología se renderiza


def test_decidir_propuesta(page):
    entrar(page, "investigadora")
    url = proponer(page, "Sistemas dinámicos en redes")
    page.context.clear_cookies()
    entrar(page, "admin")
    page.goto("/admin/propuestas")
    page.get_by_role("link", name="Sistemas dinámicos en redes").click()
    panel = page.locator("#panel-decision")
    panel.get_by_label("Aceptar con condiciones").check()
    panel.get_by_role("button", name="Registrar decisión").click()
    expect(panel).to_contain_text("Indique las condiciones")  # sin condiciones no se registra
    panel.get_by_label("Aceptar", exact=True).check()
    panel.get_by_role("button", name="Registrar decisión").click()
    expect(page.locator("main")).to_contain_text("Aceptada")
    assert page.url.endswith(url.rsplit("/", 1)[1])


def test_anexo_de_acreditacion(page, tmp_path):
    entrar(page, "admin")
    page.goto("/informes/acreditacion")
    expect(page.locator("main h1, main h2").first).to_contain_text("Anexo")
    with page.expect_download() as descarga:
        page.locator("main").get_by_role("link", name="XLSX").click()
    archivo = tmp_path / descarga.value.suggested_filename
    descarga.value.save_as(archivo)
    assert archivo.name.startswith("anexo-idi-") and archivo.suffix == ".xlsx"
    hojas = openpyxl.load_workbook(archivo).sheetnames
    assert len(hojas) > 3, hojas
