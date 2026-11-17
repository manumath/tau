"""Evidencias del marco de calidad (PLAN §57, etapa 4): documentos, enlaces e informes con huella, criterios, vigencia,
verificación de archivos y permisos."""
import io
from datetime import date, timedelta

import pytest
from openpyxl import Workbook

from app.calidad import evidencias, marco
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login

CLAVE = "Clave-evidencias-1"
PDF = b"%PDF-1.4\n% acta de prueba\n%%EOF\n"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _criterio(codigo):
    return get_db().q("SELECT * FROM criterio_calidad WHERE codigo = ?", [codigo])[0]


def _xlsx():
    b = io.BytesIO()
    Workbook().save(b)
    return b.getvalue()


def _subir(cliente, titulo="Acta del Consejo", contenido=PDF, nombre="acta.pdf", criterios=("D1.1",), **extra):
    data = {"titulo": titulo, "criterios": [str(_criterio(c)["id"]) for c in criterios], **extra}
    return cliente.post("/calidad/evidencias?tipo=documento", headers=HX, data=data,
                        files={"archivo": (nombre, contenido, "application/octet-stream")})


def test_formatos_y_huella(app):
    assert evidencias.detectar_tipo(PDF)[1] == "pdf"
    assert evidencias.detectar_tipo(_xlsx())[1] == "xlsx"
    assert evidencias.detectar_tipo(b"PK\x03\x04no es un zip") is None
    assert evidencias.detectar_tipo(b"MZ ejecutable") is None
    assert evidencias.huella(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_documento_con_huella_y_criterios(carrera):
    r = _subir(carrera, fecha="2026-03-10", vigente_hasta="2027-12-31", criterios=("D1.1", "D1.2"))
    assert r.status_code in (200, 303)
    e = evidencias.listar(_marco()["id"])[0]
    assert e["sha256"] == evidencias.huella(PDF) and e["tipo"] == "documento" and e["nombre_archivo"] == "acta.pdf"
    assert [c["codigo"] for c in e["criterios"]] == ["D1.1", "D1.2"]
    assert evidencias.ruta(e).read_bytes() == PDF
    # Se descarga con su nombre; se ve en el marco y en el filtro por criterio.
    d = carrera.get(f"/calidad/evidencias/{e['id']}/archivo")
    assert d.content == PDF and "acta.pdf" in d.headers["content-disposition"]
    assert "1 evidencia vigente" in carrera.get("/calidad/marco").text
    assert "Acta del Consejo" in carrera.get(f"/calidad/evidencias?criterio={_criterio('D1.2')['id']}").text
    assert "Acta del Consejo" not in carrera.get(f"/calidad/evidencias?criterio={_criterio('D2.1')['id']}").text
    # Un criterio con evidencias no se elimina.
    assert not marco.eliminar_criterio(_criterio("D1.2")["id"])
    # Editar cambia datos y criterios, no el archivo.
    carrera.put(f"/calidad/evidencias/{e['id']}", headers=HX,
                data={"titulo": "Acta 3/2026", "criterios": [str(_criterio("D2.1")["id"])]})
    e2 = evidencias.obtener(e["id"])
    assert (e2["titulo"], e2["sha256"], [c["codigo"] for c in e2["criterios"]]) == ("Acta 3/2026", e["sha256"], ["D2.1"])
    # Eliminar borra también el archivo.
    carrera.delete(f"/calidad/evidencias/{e['id']}", headers=HX)
    assert evidencias.obtener(e["id"]) is None and not evidencias.ruta(e).exists()
    acciones = {a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
    assert {"crear_evidencia_calidad", "editar_evidencia_calidad", "eliminar_evidencia_calidad"} <= acciones


def test_validaciones(carrera):
    r = _subir(carrera, contenido=b"MZ ejecutable", nombre="virus.exe")
    assert "Solo se admiten archivos" in r.text
    r = _subir(carrera, criterios=())
    assert "Marque al menos un criterio" in r.text
    r = _subir(carrera, fecha="2026-05-01", vigente_hasta="2026-01-01")
    assert "La vigencia termina antes" in r.text
    r = carrera.post("/calidad/evidencias?tipo=enlace", headers=HX,
                     data={"titulo": "Web", "url": "javascript:alert(1)", "criterios": [str(_criterio("D1.1")["id"])]})
    assert "debe empezar con http" in r.text
    assert evidencias.listar(_marco()["id"]) == []


def test_enlace_vencido(carrera):
    ayer = (date.today() - timedelta(days=1)).isoformat()
    carrera.post("/calidad/evidencias?tipo=enlace", headers=HX,
                 data={"titulo": "Convenio", "url": "https://ejemplo.test/convenio", "vigente_hasta": ayer,
                       "criterios": [str(_criterio("D6.1")["id"])]})
    e = evidencias.listar(_marco()["id"])[0]
    assert e["vencida"] and e["archivo"] is None and e["sha256"] is None
    assert evidencias.listar(_marco()["id"], estado="vigentes") == []
    assert evidencias.conteo_por_criterio(_marco()["id"]) == {}   # una vencida no respalda


def test_informe_del_sistema_y_verificacion(carrera):
    anio = date.today().year
    carrera.post("/calidad/evidencias?tipo=informe", headers=HX,
                 data={"titulo": "Tablero al cierre", "informe": "indicadores", "desde": str(anio - 2),
                       "hasta": str(anio), "criterios": [str(_criterio("D9.1")["id"])]})
    e = evidencias.listar(_marco()["id"])[0]
    assert (e["tipo"], e["informe"], e["parametros"]) == ("informe", "indicadores", f"{anio - 2}–{anio}")
    contenido = evidencias.ruta(e).read_bytes()
    assert evidencias.detectar_tipo(contenido)[1] == "xlsx" and e["sha256"] == evidencias.huella(contenido)
    # Verificar: el mismo archivo coincide; uno cambiado, no.
    r = carrera.post("/calidad/evidencias/verificar", headers=HX,
                     files={"archivo": ("tablero.xlsx", contenido, "application/octet-stream")})
    assert "Coincide" in r.text and "Tablero al cierre" in r.text
    r = carrera.post("/calidad/evidencias/verificar", headers=HX,
                     files={"archivo": ("tablero.xlsx", contenido + b"x", "application/octet-stream")})
    assert "No coincide" in r.text
    # Un periodo imposible no genera nada.
    r = carrera.post("/calidad/evidencias?tipo=informe", headers=HX,
                     data={"titulo": "X", "informe": "indicadores", "desde": str(anio), "hasta": str(anio + 3),
                           "criterios": [str(_criterio("D9.1")["id"])]})
    assert "El periodo va de" in r.text and len(evidencias.listar(_marco()["id"])) == 1


@pytest.fixture
def cuenta(app):
    def crear(email, rol, sigla):
        u = usuarios.crear(email, "Prueba", "Evidencias", CLAVE, debe_cambiar_pass=False, es_investigador=False)
        permisos.asignar(u["id"], rol, unidades.id_de(sigla))
        return u
    return crear


def test_permisos(client, cuenta):
    cuenta("comision@test.cl", "comision_calidad", "UMSA")
    cuenta("coord@test.cl", "coordinacion_academica", "CMAT")
    cuenta("datos@test.cl", "gestion_datos", "CMAT")
    # La Comisión de calidad registra evidencias (decisión 2).
    login(client, "comision@test.cl", CLAVE)
    assert "Subir documento" in client.get("/calidad/evidencias").text
    _subir(client)
    eid = evidencias.listar(_marco()["id"])[0]["id"]
    client.get("/logout")
    # La Coordinación académica las ve y descarga, pero no las registra ni las cambia.
    login(client, "coord@test.cl", CLAVE)
    r = client.get("/calidad/evidencias")
    assert r.status_code == 200 and "Acta del Consejo" in r.text and "Subir documento" not in r.text
    assert client.get(f"/calidad/evidencias/{eid}/archivo").content == PDF
    assert _subir(client).status_code == 403
    assert client.delete(f"/calidad/evidencias/{eid}").status_code == 403
    assert client.get("/calidad/evidencias/nueva?tipo=enlace").status_code == 403
    client.get("/logout")
    # Gestión de datos ve el marco, pero no las evidencias.
    login(client, "datos@test.cl", CLAVE)
    assert client.get("/calidad/evidencias").status_code == 403
    assert client.get(f"/calidad/evidencias/{eid}/archivo").status_code == 403
    assert "evidencia vigente" not in client.get("/calidad/marco").text
