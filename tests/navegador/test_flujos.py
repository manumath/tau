"""Flujos críticos en un navegador real (fase 1, paso 1.5). Ejecutar con: pytest --navegador

Cubren lo que las pruebas con TestClient no ven: htmx, modales, confirmaciones, JavaScript de
Franken UI y KaTeX, la política de seguridad de contenido y las descargas.
"""
import re

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
    page.locator("#modal").get_by_label("Investigación").check()
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


def test_cambiar_tema(page):
    """Claro, oscuro o el del sistema, desde el menú del usuario; la elección se mantiene al recargar."""
    entrar(page, "investigadora")
    html = page.locator("html")
    menu = page.locator("nav").get_by_role("button", name="Emmy")
    menu.click()
    page.get_by_role("button", name="Oscuro").click()
    expect(html).to_have_class(re.compile(r"\bdark\b"))
    page.reload()
    expect(html).to_have_class(re.compile(r"\bdark\b"))
    menu.click()
    expect(page.get_by_role("button", name="Oscuro")).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Claro").click()
    expect(html).not_to_have_class(re.compile(r"\bdark\b"))
    page.get_by_role("button", name="Sistema").click()
    assert page.evaluate("JSON.parse(localStorage.getItem('__FRANKEN__') || '{}').mode") is None


def test_tabla_ordena_filtra_y_descarga(page):
    """Componente de tablas (static/js/tablas.js): orden y CSV en Usuarios; filtro en la memoria."""
    entrar(page, "admin")
    page.goto("/admin/usuarios")
    tabla = page.locator("table[data-tabla='usuarios']")
    filas = tabla.locator("tbody tr")
    assert filas.count() >= 2
    encabezado = tabla.locator("th", has_text="Nombre")
    encabezado.click()
    encabezado.click()
    expect(encabezado).to_have_attribute("aria-sort", "descending")
    nombres = [t.split("\n")[0].strip() for t in filas.locator("td:first-child").all_inner_texts()]
    assert nombres == sorted(nombres, reverse=True, key=str.lower)
    with page.expect_download() as descarga:
        page.get_by_role("button", name="Descargar CSV").click()
    lineas = open(descarga.value.path(), encoding="utf-8-sig").read().splitlines()
    assert lineas[0].startswith("Nombre,Correo") and len(lineas) == filas.count() + 1
    page.goto("/informes/memoria")
    filtro = page.locator("input[aria-label='Filtrar la tabla']").first
    filtro.fill("zzz-nadie")
    expect(page.get_by_text(re.compile(r"^0 de \d+ filas?$")).first).to_be_visible()


def test_campana_de_avisos(page):
    """La campana se carga aparte y abre su menú con el enlace a todos los avisos."""
    entrar(page, "investigadora")
    campana = page.locator("#campana-avisos button").first
    expect(campana).to_be_visible()
    campana.click()
    expect(page.get_by_role("link", name="Ver todos los avisos y elegir cómo recibirlos")).to_be_visible()
    page.get_by_role("link", name="Ver todos los avisos y elegir cómo recibirlos").click()
    page.wait_for_url("**/avisos")
    expect(page.get_by_text("Cómo recibir los avisos")).to_be_visible()


def test_acciones_sin_codigo_en_linea(page):
    """Lo que antes era JavaScript en el HTML (CSP estricta): modal, filas, avisos y selectores."""
    entrar(page, "investigadora")
    page.goto("/actividades")
    modal = page.locator("#modal")
    abrir = lambda: page.get_by_role("button", name="Nueva actividad").click()  # noqa: E731
    abrir()
    expect(modal.locator("form")).to_have_count(1)
    page.keyboard.press("Escape")                                   # Escape lo cierra
    expect(modal.locator("form")).to_have_count(0)
    abrir()
    modal.get_by_role("dialog").get_by_text("Nueva actividad").click()   # un clic dentro no lo cierra
    expect(modal.locator("form")).to_have_count(1)
    modal.locator("[data-fondo-modal]").click(position={"x": 5, "y": 5})  # un clic fuera, sí
    expect(modal.locator("form")).to_have_count(0)
    abrir()
    modal.get_by_role("button", name="Cancelar").click()
    expect(modal.locator("form")).to_have_count(0)

    # Filas repetibles de una propuesta: «Quitar» la elimina; el aviso de la creación aparece y se va.
    page.goto("/proyectos")
    page.get_by_role("button", name="Proponer proyecto institucional").click()
    page.locator("#modal").get_by_label("Investigación").check()
    page.locator("#modal input[name=nombre]").fill("Prueba de filas")
    page.locator("#modal").get_by_role("button", name="Crear borrador").click()
    page.wait_for_url("**/propuestas/*")
    aviso = page.locator("#fh-toast-container .fh-toast")
    expect(aviso).to_contain_text("Borrador creado")
    expect(aviso).to_have_count(0, timeout=8000)                    # se retira solo
    editor = page.locator("#editor-propuesta")
    editor.get_by_role("button", name="Agregar objetivo").click()
    expect(editor.locator("input[name=objetivo]")).to_have_count(2)
    editor.get_by_role("button", name="Quitar objetivo").first.click()
    expect(editor.locator("input[name=objetivo]")).to_have_count(1)


def test_selector_de_periodo_de_la_memoria(page):
    entrar(page, "admin")
    # Un selector que navega (data-navegar): el periodo de la bandeja de propuestas.
    page.goto("/admin/propuestas")
    opciones = page.locator("select[aria-label=Periodo] option")
    otro = opciones.nth(opciones.count() - 1).get_attribute("value")
    page.locator("select[aria-label=Periodo]").select_option(otro)
    page.wait_for_url(f"**/admin/propuestas?periodo={otro}")
    page.goto("/informes/memoria")
    page.locator("select[name=modo]").select_option("periodo")
    expect(page.locator("[data-modo=periodo]")).to_be_visible()
    expect(page.locator("[data-modo=anio]")).to_be_hidden()


def test_clasificacion_msc_del_producto(page):
    """Selector MSC2020 (PLAN.md §45): buscar, agregar, reordenar (el primero es el principal) y filtrar."""
    entrar(page, "investigadora")
    page.goto("/productos")
    page.get_by_role("button", name="Nuevo producto").click()
    modal = page.locator("#modal")
    modal.locator("select[name=tipo_id]").select_option(label="Preprint")
    modal.locator("input[name=titulo]").fill("Funciones zeta de anillos")
    lista = modal.locator("#lista-msc")
    buscar = modal.locator("#buscar-msc")
    for texto, codigo in (("13E05", "13E05"), ("11M06", "11M06")):
        buscar.click()
        buscar.fill(texto)
        modal.locator("#resultados-msc button", has_text=codigo).first.click()
        expect(lista.locator(f"input[value='{codigo}']")).to_have_count(1)
        expect(buscar).to_have_value("")                       # el buscador se limpia tras agregar
    buscar.fill("13E")                                         # no ofrece los ya elegidos
    expect(modal.locator("#resultados-msc button", has_text="13E10")).to_have_count(1)
    expect(modal.locator("#resultados-msc button", has_text="13E05")).to_have_count(0)
    buscar.fill("")
    filas = lista.locator("li")
    principal = lista.get_by_text("Principal")
    expect(filas.first).to_contain_text("13E05")
    expect(principal.first).to_be_visible()
    expect(filas.nth(1).get_by_text("Principal")).to_be_hidden()
    filas.nth(1).get_by_role("button", name="Subir 11M06").click()     # 11M06 pasa a ser el principal
    expect(filas.first).to_contain_text("11M06")
    expect(filas.first.get_by_text("Principal")).to_be_visible()
    modal.get_by_role("button", name="Guardar").click()
    expect(modal.locator("form")).to_have_count(0)
    page.reload()                                                  # el filtro ofrece las áreas al cargar
    page.locator("select[name=area]").select_option("11")
    expect(page.locator("#lista-productos")).to_contain_text("Funciones zeta de anillos")
    page.get_by_role("link", name="Funciones zeta de anillos").click()
    expect(page.locator("main")).to_contain_text("Clasificación MSC2020")


def test_enlazar_preprint_con_su_version_publicada(page):
    """PLAN.md §46: desde la ficha del preprint se elige la versión publicada; la ficha se actualiza."""
    entrar(page, "investigadora")
    page.goto("/productos")
    modal = page.locator("#modal")
    for tipo, titulo in (("Preprint", "Cuerpos de clases y reciprocidad"),
                         ("Artículo en revista", "Cuerpos de clases y reciprocidad.")):
        page.get_by_role("button", name="Nuevo producto").click()
        modal.locator("select[name=tipo_id]").select_option(label=tipo)
        modal.locator("input[name=titulo]").fill(titulo)
        modal.get_by_role("button", name="Guardar").click()
        expect(modal.locator("form")).to_have_count(0)
    page.locator("#lista-productos").get_by_role("link", name="Cuerpos de clases y reciprocidad", exact=True).click()
    page.get_by_role("button", name="Enlazar con su versión publicada").click()
    expect(modal.get_by_text("Versión publicada del preprint")).to_be_visible()
    modal.get_by_role("button", name="Enlazar").click()
    expect(modal.locator("form")).to_have_count(0)
    ficha = page.locator("#ficha-producto")
    expect(ficha.get_by_role("link", name="Cuerpos de clases y reciprocidad.")).to_be_visible()
    ficha.get_by_role("button", name="Desenlazar").click()
    expect(ficha.get_by_role("button", name="Enlazar con su versión publicada")).to_be_visible()


def test_cargar_mas_y_fila_de_autor_en_el_telefono(page):
    """Listas largas de 50 en 50 (htmx reemplaza el botón por los siguientes) y la fila de un autor en
    pantalla de teléfono: el selector de filiación baja a su línea sin tapar el nombre."""
    entrar(page, "prolifico")
    page.goto("/productos")
    filas = page.locator("#lista-productos [id^=producto-]")
    expect(filas).to_have_count(50)
    page.get_by_role("button", name="Cargar 5 más").click()
    expect(filas).to_have_count(55)
    expect(page.get_by_role("button", name=re.compile("Cargar"))).to_have_count(0)
    page.set_viewport_size({"width": 375, "height": 812})
    page.get_by_role("button", name="Nuevo producto").click()
    fila = page.locator("#lista-autor li").first
    nombre, selector = fila.get_by_text("Alan Turing"), fila.locator("select[name=filiacion]")
    expect(selector).to_be_visible()
    assert selector.bounding_box()["y"] >= nombre.bounding_box()["y"] + nombre.bounding_box()["height"]
