"""Flujos de los estudiantes en Chrome (PLAN §62, etapa 8): ingreso por enlace al correo, postulación a una
auxiliatura con un documento y perfil de proyecto de grado. La lógica la cubren tests/test_servicios.py y
tests/test_portal_estudiante.py; aquí se prueba lo que solo se ve en el navegador (formularios, subida de archivos,
redirecciones, CSP)."""
import re

from playwright.sync_api import expect

PDF = b"%PDF-1.4\n" + b"0" * 64


def test_la_estudiante_entra_por_el_enlace_y_solo_ve_lo_suyo(estudiante):
    page = estudiante
    expect(page.locator("main h1")).to_be_visible()
    assert "/estudiante" in page.url
    # Las pantallas del personal la devuelven a su inicio.
    page.goto("/admin/usuarios")
    page.wait_for_url("**/estudiante")
    page.goto("/docencia/oferta")
    page.wait_for_url("**/estudiante")


def test_postula_a_una_auxiliatura_y_sube_un_documento(estudiante, tmp_path):
    page = estudiante
    page.goto("/estudiante/auxiliaturas")
    expect(page.locator("main")).to_contain_text("Auxiliaturas de prueba")
    page.locator("main button:has-text('Postular')").first.click()
    page.wait_for_url(re.compile(r".*/estudiante/auxiliaturas/\d+$"))
    expect(page.locator("main")).to_contain_text("Requisitos")
    archivo = tmp_path / "matricula.pdf"
    archivo.write_bytes(PDF)
    campo = page.locator("main input[type=file]").first
    campo.set_input_files(str(archivo))
    campo.locator("xpath=ancestor::form").locator("button[type=submit]").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("main")).to_contain_text("matricula.pdf")
    # Volver a la lista: ya no ofrece postular, sino continuar.
    page.goto("/estudiante/auxiliaturas")
    expect(page.locator("main a:has-text('Continuar')").first).to_be_visible()


def test_crea_su_perfil_de_grado(estudiante):
    page = estudiante
    page.goto("/estudiante/grado")
    page.click("a:has-text('Empezar mi perfil')")
    page.wait_for_url("**/estudiante/grado/nuevo")
    page.fill("#titulo", "Coloraciones de grafos $G$ con $\\chi(G) \\le 4$")
    page.select_option("select[name=tutor_id]", label="Noether, Emmy")
    page.click("button:has-text('Crear mi perfil')")
    page.wait_for_url(re.compile(r".*/estudiante/grado/\d+$"))
    expect(page.locator("main")).to_contain_text("Tutor: Emmy Noether")
    expect(page.locator("main input[name=titulo]")).to_have_value(re.compile(r"^Coloraciones de grafos \$G\$"))
